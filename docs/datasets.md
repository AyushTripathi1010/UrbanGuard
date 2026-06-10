# Datasets — what we use, where they came from, how to pull them

UrbanGuard relies on three real-world video datasets plus an image dataset for
negatives. This doc is the developer-perspective tour: how a real engineer
*found* each one, what's inside, what it costs to download, and the exact
commands to pull it. Everything below is reproducible from a clean clone.

The single entry point is the `scripts/download_datasets.py` script:

```bash
uv run python scripts/download_datasets.py nexar              # 5 clips/split, ~250 MB
uv run python scripts/download_datasets.py nexar --sample 50  # bigger sample
uv run python scripts/download_datasets.py nexar --full       # all 31 GB
uv run python scripts/download_datasets.py hwid12             # Kaggle, needs auth
uv run python scripts/download_datasets.py dota               # clones the repo
```

All data lands under `data/raw/<dataset>/`. The `data/` directory is gitignored
on purpose — datasets do not live in git.

---

## 1. Nexar Collision Prediction (primary dashcam source)

**Repo:** [`nexar-ai/nexar_collision_prediction`](https://huggingface.co/datasets/nexar-ai/nexar_collision_prediction)
**License:** Nexar Open Data License
**Size:** ~31 GB
**Public, no gating, no email approval.**

### How a developer finds this

Open Hugging Face, search "collision prediction." This dataset is the first
result. Nexar is a known dashcam company (you may have heard of their
crowd-sourced AI safety camera work), so the data provenance is credible right
away. Click into the dataset page and confirm:
- "Use this dataset" button shows a one-liner: `load_dataset("nexar-ai/nexar_collision_prediction")`
- Files tab lists `train/positive/*.mp4`, `train/negative/*.mp4`, etc.
- Linked Kaggle competition has community-validated baselines.

Once those three boxes are checked, this becomes the default starting point —
anything else added is to compensate for what this lacks.

### What's inside

| Split | Positive (incident) | Negative (normal) |
|---|---|---|
| `train` | 751 mp4s | 751 mp4s |
| `test-public` | 335 mp4s | 334 mp4s |
| `test-private` | 339 mp4s | 340 mp4s |
| **Total** | **1,425** | **1,425** |

Properties:
- Dashcam perspective (forward-looking, single fixed-angle from a moving vehicle)
- 1280×720 @ 30 fps
- Clips are ~40 seconds long
- 50/50 positive/negative split — no class-imbalance pain on day one
- Metadata sidecars: `weather`, `lighting`, `time_of_event`, pre-event offsets

Auxiliary files at the repo root:
- `solution.csv` — ground-truth labels
- `sample_submission.csv` — Kaggle competition submission format
- `evaluate_submission.py` — official metric
- `time_to_accident_test_map.csv` — when each positive incident occurs in the clip

### Commands

```bash
# A 30-clip sample across the 6 (split, label) combinations. ~250 MB. Default.
uv run python scripts/download_datasets.py nexar

# Custom sample size:
uv run python scripts/download_datasets.py nexar --sample 50

# Full ~31 GB pull — do this on home wifi, not a phone hotspot.
uv run python scripts/download_datasets.py nexar --full
```

Under the hood the script uses `huggingface_hub.hf_hub_download` per file, which
resumes interrupted downloads automatically and respects the existing local
cache. Files land at `data/raw/nexar/<split>/<label>/<id>.mp4`.

### Why we use it as the *primary* source

It's the only dataset that hits all four boxes simultaneously:
- Publicly downloadable (no auth, no email approval, no YouTube link rot)
- Real footage (not synthetic)
- Balanced positive/negative labels
- Metadata fields that align with our RL state space (weather, time)

---

## 2. HWID12 — Highway Incidents Detection (primary CCTV source)

**Page:** [Kaggle — `landrykezebou/hwid12-highway-incidents-detection-dataset`](https://www.kaggle.com/datasets/landrykezebou/hwid12-highway-incidents-detection-dataset)
**License:** Listed on the Kaggle page (visit before redistributing)
**Size:** ~3 GB
**Requires Kaggle account + API token.**

### How a developer finds this

Nexar is dashcam-perspective. Our system pretends to ingest **CCTV** — which
means *overhead*, *fixed-mount* cameras. Dashcam ≠ CCTV; the visual prior is
different (vehicles enter and exit the frame, no ego-motion, weather affects
the whole frame uniformly).

So you search: "highway incident CCTV", "traffic accident overhead camera",
"fixed camera accident dataset." Kaggle's search ranks HWID12 highly. Open it
and confirm:
- Sample images on the page show clearly overhead/elevated angles
- 12 incident classes (more than the original plan's "accident yes/no")
- Updated within the last year
- No gating beyond a free Kaggle account

This is the *only* legitimately public CCTV-perspective accident dataset that
shows up after a serious search. CADP (the obvious alternative) is
YouTube-sourced from 2018 with severe link rot — rejected after one look at
its README.

### What's inside

- 2,780+ overhead/CCTV clips of highway incidents
- 12 incident classes (collisions, hit-and-run, lane violations, debris,
  pedestrian, etc.)
- 500K+ frames total
- 3-8 seconds per clip
- Real fixed-camera angle — exactly what UrbanGuard's "CCTV ingest" pretends to be

### Commands

You need a Kaggle API token first. **One-time setup:**

```bash
# 1. Go to https://www.kaggle.com/settings/account
# 2. Click "Create New Token" — downloads kaggle.json
mkdir -p ~/.kaggle
mv ~/Downloads/kaggle.json ~/.kaggle/kaggle.json
chmod 600 ~/.kaggle/kaggle.json
```

Then:

```bash
uv run python scripts/download_datasets.py hwid12
```

The script invokes the official Kaggle CLI (`kaggle datasets download -d
landrykezebou/hwid12-highway-incidents-detection-dataset --unzip`). It checks
for the token file first and exits with a clear error if missing.

### Why we use it as the *CCTV* source

It's the *only* genuinely public CCTV-perspective accident dataset that exists
today. Anything else is either:
- YouTube-sourced (link rot)
- Email/registration-gated for academic use only (IITH, IDD-PeD)
- Synthetic / simulator-generated (doesn't help us calibrate against real visuals)

---

## 3. DoTA — Detection of Traffic Anomaly (anomaly-class diversity)

**Repo:** [`github.com/MoonBlvd/Detection-of-Traffic-Anomaly`](https://github.com/MoonBlvd/Detection-of-Traffic-Anomaly)
**Paper:** [arXiv:2004.03044](https://arxiv.org/abs/2004.03044) — "When, Where, and What? A New Dataset for Anomaly Detection in Driving Videos"
**License:** Code GPL-3.0; video license inherits from YouTube source clips
**Size on disk after pull:** ~6 GB; metadata-only is ~50 MB
**Half the YouTube clips will fail to download** due to link rot — that's expected.

### How a developer finds this

After Nexar and HWID12 are set up, you ask yourself: "what does CLIP's
zero-shot prompt set need to discriminate?" Our prompts mention five concepts:
accident, near-miss, fire/overturn, normal traffic, empty road. Nexar gives a
binary label; HWID12 has 12 classes but they're highway-specific.

You want a dataset with **rich anomaly vocabulary in driving scenes**. You go
to Google Scholar or arXiv, search "traffic anomaly detection dataset
multi-class." The Yao et al. 2020 paper comes up. The paper introduces DoTA
with 9 anomaly classes (ST, AH, LA, OC, TC, VP, VO, OO, UK — defined in the
paper). The GitHub repo is linked.

DoTA is YouTube-sourced like CADP, but:
- Newer (2020 vs 2018)
- Active repo
- Better-defined class taxonomy
- ~4,677 clips before link rot, ~3,000 after

Worth the engineering pain to add — it directly improves the CLIP prompt
calibration story.

### What's inside

- 4,677 clips listed in the metadata
- 9 anomaly classes:
  - **ST**: collision with another vehicle (start-up traffic)
  - **AH**: ahead — collision with the vehicle ahead
  - **LA**: lateral — collision with the vehicle in the adjacent lane
  - **OC**: oncoming — collision with the oncoming vehicle
  - **TC**: turning collision
  - **VP**: vehicle hits pedestrian
  - **VO**: vehicle hits obstacle / out-of-control
  - **OO**: out-of-control with no collision
  - **UK**: unknown / other
- Each clip has temporal annotations: when the anomaly starts, where in the
  frame (bbox), and which class it belongs to.
- Diverse weather/lighting/country (clips harvested from YouTube driving
  channels globally).

### Commands

```bash
# Step 1: clone the upstream repo (script does this; ~50 MB of metadata).
uv run python scripts/download_datasets.py dota

# Step 2: download the actual YouTube clips. The repo has its own script;
#         run it manually so you can supervise the ~40 min process.
cd data/raw/dota
uv pip install yt-dlp
python dataset/download_DoTA.py

# Expect 30%+ failure rate — that's the YouTube link rot tax.
```

The `download_datasets.py dota` subcommand stops at step 1 on purpose:
1. We don't want a 40-minute YouTube scrape silently running in the background
2. The yt-dlp pulls are interactive enough (rate limits, dead URLs, video
   format changes) that they deserve a human at the keyboard

### Why we use it

The CLIP zero-shot prompt set in `services/detect/src/detect/clip_classifier.py`
mentions "a pedestrian almost being hit by a vehicle" and "vehicles overturned
or on fire" — those phrasings come straight from DoTA's class taxonomy. The
dataset is calibration data for the prompts, not training data for ResNet.

---

## 4. Open Images V7 (negative samples — *not* core data)

**Page:** [Open Images V7 download](https://storage.googleapis.com/openimages/web/download_v7.html)
**License:** Images CC BY 2.0; annotations CC BY 4.0
**Size:** 561 GB full; we only pull the `Vehicle`, `Car`, `Person`, `Road` subset
**Public, requires no auth.**

### How a developer finds this

Every computer-vision project mentions Open Images. We don't even need to
search — we know it exists. What we *do* search for is: "FiftyOne Open Images
subset by class." The
[FiftyOne docs](https://docs.voxel51.com/integrations/open_images.html) show
the exact incantation:

```python
import fiftyone.zoo as foz
dataset = foz.load_zoo_dataset(
    "open-images-v7",
    split="train",
    label_types=["detections"],
    classes=["Car", "Person", "Vehicle", "Road"],
    max_samples=5000,
)
```

We don't add a sub-command to `download_datasets.py` for this because (a)
FiftyOne is already the standard interface for Open Images subsetting and
should not be wrapped, (b) negative samples are needed only when we fine-tune
ResNet — that work lives in a Colab notebook (`notebooks/04_finetune_resnet_colab.ipynb`)
and the Colab notebook pulls Open Images at its time.

### What's inside (what we'd pull)

- ~5,000 still images (not video) showing normal traffic / pedestrians /
  vehicles / roads
- Bounding-box annotations (we don't use them)
- Used strictly to balance the ResNet training set so it doesn't learn to call
  every road frame an incident

---

## Why we don't use these (rejected after evaluation)

### CADP (Car Accident Detection and Prediction)
- [Original repo](https://github.com/ankitshah009/CarCrash_forecasting_and_detection),
  [paper](https://arxiv.org/abs/1809.05782)
- 1,416 YouTube clips claimed; only 205 fully annotated
- Repo last meaningful commit was ~2019
- YouTube link rot from 2018 will kill 30-50% of clips
- The original `urbanguard-datasets` notes called this out and skipped it.

### IITH Accident / IDD-PeD (Indian context)
- Real Indian CCTV footage, would be a strong fit for the project's India
  motivation
- IITH needs email request; IDD-PeD needs registration at
  [idd.insaan.iiit.ac.in](https://idd.insaan.iiit.ac.in/)
- Deferred until the model is strong enough on the public datasets to warrant
  the friction. Add later as Phase 7+.

---

## Summary card

| Dataset | Source | Auth needed | Size | What it gives us |
|---|---|---|---|---|
| **Nexar** | HF | None | 31 GB | Balanced dashcam, primary training |
| **HWID12** | Kaggle | Token | ~3 GB | Real CCTV-perspective, primary CCTV |
| **DoTA** | GitHub + YouTube | None | ~6 GB | Anomaly-class taxonomy, CLIP calibration |
| **Open Images** | Google | None | ~5 GB subset | Negative samples for ResNet |

If you only have time for one: **Nexar**. The whole pipeline works on Nexar
alone. HWID12 makes the "CCTV" framing honest. DoTA improves the CLIP prompts.
Open Images is needed only when ResNet fine-tuning starts.
