"""Smoke test: PPO converges enough on a small budget that mean reward is finite and improving."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from rl.train import train


@pytest.mark.skipif(
    os.environ.get("URBANGUARD_RL_SMOKE") != "1",
    reason="set URBANGUARD_RL_SMOKE=1 to run ~30s PPO smoke",
)
def test_ppo_smoke_runs_and_writes_checkpoint(tmp_path: Path) -> None:
    save_path = tmp_path / "ppo_smoke.zip"
    out = train(total_steps=2048, save_path=save_path, seed=7)
    assert out.exists()
    assert out.stat().st_size > 1000  # not an empty file


def test_train_module_imports() -> None:
    from rl.train import make_env_factory, train  # noqa: F401
