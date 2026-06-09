"""PPO training entrypoint. Use a short run for local smoke; offload to Colab for serious training."""

from __future__ import annotations

import argparse
from pathlib import Path

import structlog
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv

from rl.env import EnvConfig, ZoneSamplingEnv

log = structlog.get_logger("rl.train")


def make_env_factory(seed: int):
    def _factory():
        return ZoneSamplingEnv(EnvConfig(seed=seed))

    return _factory


def train(total_steps: int, save_path: Path, seed: int = 42) -> Path:
    env = DummyVecEnv([make_env_factory(seed)])
    model = PPO(
        "MlpPolicy",
        env,
        learning_rate=3e-4,
        n_steps=512,
        batch_size=64,
        n_epochs=4,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        seed=seed,
        verbose=0,
    )
    model.learn(total_timesteps=total_steps, progress_bar=False)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(save_path))
    log.info("rl.trained", steps=total_steps, save_path=str(save_path))
    return save_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=5000)
    parser.add_argument("--save", type=Path, default=Path("data/checkpoints/ppo_zone_policy.zip"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    train(args.steps, args.save, args.seed)


if __name__ == "__main__":
    main()
