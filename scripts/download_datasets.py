"""Pull the three datasets UrbanGuard uses.

Examples
--------
    # tiny sample (10 clips per split, ~50 MB) — fast, default
    uv run python scripts/download_datasets.py nexar

    # full pull — Nexar is ~31 GB; do this on the laptop's wifi, not a hotspot
    uv run python scripts/download_datasets.py nexar --full

    # HWID12 from Kaggle (requires ~/.kaggle/kaggle.json)
    uv run python scripts/download_datasets.py hwid12

    # DoTA — clones the upstream repo + prints the next steps
    uv run python scripts/download_datasets.py dota

Targets land under ``data/raw/<dataset>/``. ``data/`` is gitignored.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data" / "raw"


# --------------------------------------------------------------------------- #
# Nexar
# --------------------------------------------------------------------------- #


def _nexar(sample_per_split: int | None) -> None:
    """Download Nexar via the Hugging Face Hub.

    sample_per_split=None  → full repo (~31 GB)
    sample_per_split=N     → first N mp4s per (split, label) pair (~N * 6 * 5 MB)
    """
    from huggingface_hub import HfApi, hf_hub_download

    repo = "nexar-ai/nexar_collision_prediction"
    dst = DATA_ROOT / "nexar"
    dst.mkdir(parents=True, exist_ok=True)

    api = HfApi()
    files = api.list_repo_files(repo, repo_type="dataset")
    mp4s = [f for f in files if f.endswith(".mp4")]
    meta = [f for f in files if f.endswith((".csv", ".py", "README.md", "LICENSE"))]

    if sample_per_split is not None:
        from collections import defaultdict

        grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
        for f in mp4s:
            parts = f.split("/")  # train/positive/00001.mp4
            if len(parts) >= 3:
                grouped[(parts[0], parts[1])].append(f)
        picked: list[str] = []
        for _key, items in sorted(grouped.items()):
            picked.extend(sorted(items)[:sample_per_split])
        targets = picked + meta
        print(
            f"[nexar] sampling {sample_per_split} clips per (split,label) — {len(picked)} clips total"
        )
    else:
        targets = mp4s + meta
        print(f"[nexar] FULL pull — {len(mp4s)} clips, ~31 GB")

    for i, rel in enumerate(targets, 1):
        hf_hub_download(
            repo_id=repo,
            filename=rel,
            repo_type="dataset",
            local_dir=str(dst),
        )
        if i % 25 == 0 or i == len(targets):
            print(f"  [nexar] {i}/{len(targets)} done")
    print(f"[nexar] complete → {dst}")


# --------------------------------------------------------------------------- #
# HWID12
# --------------------------------------------------------------------------- #


def _hwid12() -> None:
    """Download HWID12 via the Kaggle API.

    Needs ``~/.kaggle/kaggle.json`` (Account → Create New API Token on kaggle.com).
    """
    if shutil.which("kaggle") is None:
        sys.exit("[hwid12] `kaggle` CLI not on PATH. install with: uv pip install kaggle")
    if not (Path.home() / ".kaggle" / "kaggle.json").exists():
        sys.exit(
            "[hwid12] missing ~/.kaggle/kaggle.json — generate it from "
            "https://www.kaggle.com/settings/account (Create New Token)."
        )

    dst = DATA_ROOT / "hwid12"
    dst.mkdir(parents=True, exist_ok=True)
    cmd = [
        "kaggle",
        "datasets",
        "download",
        "-d",
        "landrykezebou/hwid12-highway-incidents-detection-dataset",
        "-p",
        str(dst),
        "--unzip",
    ]
    print(f"[hwid12] running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    print(f"[hwid12] complete → {dst}")


# --------------------------------------------------------------------------- #
# DoTA
# --------------------------------------------------------------------------- #


def _dota() -> None:
    """Clone the DoTA repo and print next-step instructions.

    The repo ships metadata + a YouTube downloader script. We don't pull the
    YouTube videos here because each video can take ~30s and there are ~4,700;
    interactive supervision is better than a 40-minute background job.
    """
    dst = DATA_ROOT / "dota"
    if dst.exists():
        print(f"[dota] {dst} already exists — skipping clone")
    else:
        repo = "https://github.com/MoonBlvd/Detection-of-Traffic-Anomaly.git"
        subprocess.run(["git", "clone", "--depth=1", repo, str(dst)], check=True)
        print(f"[dota] cloned → {dst}")
    print(
        "[dota] next steps (run manually):\n"
        f"  cd {dst}\n"
        "  uv pip install yt-dlp\n"
        "  python dataset/download_DoTA.py\n"
        "  # ~30% of clips will fail on link rot — that's expected."
    )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_n = sub.add_parser("nexar", help="dashcam collision dataset (Hugging Face)")
    g = p_n.add_mutually_exclusive_group()
    g.add_argument("--full", action="store_true", help="pull all ~31 GB")
    g.add_argument(
        "--sample",
        type=int,
        default=10,
        help="clips per (split,label); defaults to 10 (~250 MB total)",
    )

    sub.add_parser("hwid12", help="CCTV highway-incident dataset (Kaggle)")
    sub.add_parser("dota", help="anomaly dataset (GitHub clone)")

    args = parser.parse_args()

    DATA_ROOT.mkdir(parents=True, exist_ok=True)

    if args.cmd == "nexar":
        _nexar(None if args.full else args.sample)
    elif args.cmd == "hwid12":
        _hwid12()
    elif args.cmd == "dota":
        _dota()


if __name__ == "__main__":
    main()
