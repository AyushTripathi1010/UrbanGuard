"""ZoneSamplingEnv — a gymnasium environment for the PPO policy.

The agent allocates a sampling-rate multiplier per zone, given the recent
incident heatmap + time-of-day. The simulator generates incidents from a
time-varying Poisson rate per zone; higher sampling raises detection probability
but adds compute cost and false-alarm risk.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import gymnasium as gym
import numpy as np
from gymnasium import spaces


@dataclass(frozen=True)
class EnvConfig:
    num_zones: int = 10
    hours_per_episode: int = 24
    base_incident_rate: float = 0.4  # per zone per hour at rate-multiplier=1.0
    detection_alpha: float = 1.2  # logit slope for detection_prob vs sampling_rate
    false_alarm_alpha: float = 0.08  # false alarms per hour per zone per rate unit
    early_detect_reward: float = 10.0
    false_alarm_penalty: float = -2.0
    miss_penalty: float = -5.0
    compute_cost_per_frame: float = -0.01
    frames_per_rate_unit: float = 120  # 2fps * 60s, scaled
    seed: int | None = None


class ZoneSamplingEnv(gym.Env):
    """Each step is one simulated hour.

    Observation: (recent_incident_count[Z], hour_of_day_norm, last_clip_score[Z])
        shape = (2 * num_zones + 1,)

    Action: rate multiplier per zone, Box([0.5]*Z, [4.0]*Z)
    """

    metadata: ClassVar[dict] = {"render_modes": []}

    def __init__(self, config: EnvConfig | None = None) -> None:
        super().__init__()
        self.cfg = config or EnvConfig()
        Z = self.cfg.num_zones
        # rate profile by hour-of-day per zone — peaks shift by zone for variety
        self._zone_phase = np.linspace(0, 2 * np.pi, Z, endpoint=False)
        self.action_space = spaces.Box(low=0.5, high=4.0, shape=(Z,), dtype=np.float32)
        obs_dim = 2 * Z + 1
        self.observation_space = spaces.Box(
            low=np.concatenate(
                [
                    np.zeros(Z, dtype=np.float32),
                    np.zeros(1, dtype=np.float32),
                    np.zeros(Z, dtype=np.float32),
                ]
            ),
            high=np.concatenate(
                [
                    np.full(Z, 50, dtype=np.float32),
                    np.ones(1, dtype=np.float32),
                    np.ones(Z, dtype=np.float32),
                ]
            ),
            shape=(obs_dim,),
            dtype=np.float32,
        )
        self._rng = np.random.default_rng(self.cfg.seed)
        self._hour = 0
        self._recent = np.zeros(Z, dtype=np.float32)
        self._last_clip = np.zeros(Z, dtype=np.float32)

    def _zone_rate(self, hour: int) -> np.ndarray:
        # Periodic with two rush hours: 8am + 5pm, modulated per zone
        h = 2 * np.pi * (hour / 24.0)
        base = 0.5 + 0.5 * np.sin(h + self._zone_phase)
        boost = np.exp(-((hour - 8) ** 2) / 4) + np.exp(-((hour - 17) ** 2) / 4)
        return self.cfg.base_incident_rate * (base + 0.6 * boost)

    def _obs(self) -> np.ndarray:
        hour_norm = np.array(
            [self._hour / max(1, self.cfg.hours_per_episode - 1)], dtype=np.float32
        )
        return np.concatenate(
            [self._recent.astype(np.float32), hour_norm, self._last_clip], dtype=np.float32
        )

    def reset(self, *, seed: int | None = None, options=None):
        super().reset(seed=seed)
        if seed is not None:
            self._rng = np.random.default_rng(seed)
        self._hour = 0
        self._recent = np.zeros(self.cfg.num_zones, dtype=np.float32)
        self._last_clip = np.zeros(self.cfg.num_zones, dtype=np.float32)
        return self._obs(), {}

    def step(self, action: np.ndarray):
        action = np.clip(action, 0.5, 4.0).astype(np.float32)

        true_rate = self._zone_rate(self._hour)
        # Effective rate scales mildly with sampling — sampling doesn't *cause* incidents,
        # it only changes detection probability and compute cost.
        true_incidents = self._rng.poisson(true_rate)

        # Detection probability as a soft function of rate multiplier.
        det_prob = 1.0 / (1.0 + np.exp(-self.cfg.detection_alpha * (action - 1.0)))
        detected = self._rng.binomial(true_incidents, det_prob)
        missed = true_incidents - detected
        false_alarms = self._rng.poisson(self.cfg.false_alarm_alpha * action)

        # Compute cost per rate unit per zone
        frames = action * self.cfg.frames_per_rate_unit
        compute_penalty = frames.sum() * self.cfg.compute_cost_per_frame

        reward = (
            float(detected.sum()) * self.cfg.early_detect_reward
            + float(false_alarms.sum()) * self.cfg.false_alarm_penalty
            + float(missed.sum()) * self.cfg.miss_penalty
            + float(compute_penalty)
        )

        self._recent = detected.astype(np.float32)
        # mock "last clip confidence" — proportional to detection prob this hour
        self._last_clip = det_prob.astype(np.float32)

        self._hour += 1
        terminated = self._hour >= self.cfg.hours_per_episode
        truncated = False
        info = {
            "true_incidents": int(true_incidents.sum()),
            "detected": int(detected.sum()),
            "missed": int(missed.sum()),
            "false_alarms": int(false_alarms.sum()),
            "compute_penalty": float(compute_penalty),
        }
        return self._obs(), reward, terminated, truncated, info
