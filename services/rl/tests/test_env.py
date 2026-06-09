from __future__ import annotations

import numpy as np
from rl.env import EnvConfig, ZoneSamplingEnv


def test_env_reset_returns_correct_obs_shape() -> None:
    env = ZoneSamplingEnv(EnvConfig(seed=0))
    obs, info = env.reset()
    assert obs.shape == (2 * env.cfg.num_zones + 1,)
    assert obs.dtype == np.float32
    assert info == {}


def test_env_step_advances_and_returns_finite_reward() -> None:
    env = ZoneSamplingEnv(EnvConfig(seed=0))
    env.reset()
    action = np.full(env.cfg.num_zones, 1.0, dtype=np.float32)
    obs, reward, terminated, truncated, info = env.step(action)
    assert np.isfinite(reward)
    assert obs.shape == (2 * env.cfg.num_zones + 1,)
    assert info["true_incidents"] >= 0
    assert info["detected"] + info["missed"] == info["true_incidents"]
    assert not terminated and not truncated


def test_env_terminates_at_end_of_episode() -> None:
    cfg = EnvConfig(hours_per_episode=3, seed=0)
    env = ZoneSamplingEnv(cfg)
    env.reset()
    rewards = []
    for _ in range(cfg.hours_per_episode):
        _, r, terminated, _, _ = env.step(np.ones(cfg.num_zones, dtype=np.float32))
        rewards.append(r)
    assert terminated is True
    assert len(rewards) == cfg.hours_per_episode


def test_env_clips_action_outside_bounds() -> None:
    env = ZoneSamplingEnv(EnvConfig(seed=0))
    env.reset()
    # Push way past the upper bound; step must not crash.
    out_of_range = np.full(env.cfg.num_zones, 100.0, dtype=np.float32)
    _, reward, _, _, info = env.step(out_of_range)
    assert np.isfinite(reward)
    # heavy false-alarm + compute cost expected
    assert info["false_alarms"] >= 0


def test_zone_rate_is_periodic() -> None:
    env = ZoneSamplingEnv(EnvConfig(seed=0))
    r0 = env._zone_rate(0)
    r24 = env._zone_rate(24)
    # Same hour-of-day → same rate (period = 24h)
    assert np.allclose(r0, r24, atol=1e-5)
