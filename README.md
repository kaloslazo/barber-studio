# BarberStudio

Interactive barbershop style simulator built with computer graphics — course project for CS4016 (Computer Graphics, UTEC).

## Description

Web app where the user uploads a photo (or uses the webcam) and can try on hair dyes, beards and haircuts, with a before/after comparison. The system detects the face and facial landmarks with OpenCV, segments hair and beard regions with a fine-tuned YOLO model, and fits each style to the face using Delaunay triangulation.

## Team

- Kalos Lazo
- Sofia Herrera
- Gianpier Segovia

## Course topics covered

| Topic | Where it applies |
|---|---|
| Color theory (6.1.1) | Hair dye recoloring in HSV space |
| Sampling and interpolation (6.1.3-6.1.4) | Edge feathering, blending, warping |
| Convex hull (6.2.2) | Facial region delimitation |
| Delaunay triangulation (6.2.5) | Facial mesh used to warp style overlays |
| OpenCV (6.4.4) | Face and landmark detection |
| YOLO + fine-tuning (6.4.5-6.4.6) | Hair and beard segmentation |

## Architecture

- **Backend** (`backend/`): FastAPI service in Python. Pipeline modules live in `backend/app/core/` (detection, segmentation, coloring, geometry, compositing). Fine-tuning scripts for Google Colab live in `backend/training/`.
- **Frontend** (`frontend/`): vanilla HTML/CSS/JS, no build step.
- `data/` and `models/` hold datasets and trained weights (gitignored).

## Run

One command from the repo root (creates the venv and installs dependencies on first run):

```bash
./run.sh
```

Then open http://localhost:8000 — the same server serves the UI and the API. The script also frees port 8000 automatically if a previous instance is stuck.

Tests:

```bash
cd backend && venv/bin/python -m pytest tests/ -q
```

## Current status

- **Hair segmentation with fine-tuned YOLOv8n-seg** (Mask mAP50 = 0.968, trained on Figaro1k + CelebAMask-HQ, see `backend/training/`). The dye pipeline now uses the real hair shape; the geometric dome remains as fallback.
- Working **hair dye demo**: upload a photo, pick a color and intensity, get a before/after view.

## Model setup

Most models are NOT in git (size). Set them up as follows:

- `backend/models/face_landmarker.task` — MediaPipe FaceLandmarker (3.6 MB, **included in the repo**).
- `backend/models/hair_best.pt` — train it with `backend/training/barberstudio_colab.ipynb` (Colab, ~3.5h on a free T4).
- `backend/models/lbfmodel.yaml` + `backend/models/yunet.onnx` — legacy fallback landmarks; download links in `backend/training/` scripts.

Without them, the app falls back to provisional masks.

Install order matters to avoid an OpenCV conflict pulled by ultralytics:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -r requirements-training.txt
pip install --force-reinstall "opencv-contrib-python>=4.9,<5"
```

## API

| Endpoint | Description |
|---|---|
| `GET /api/health` | Service status |
| `POST /api/preview` | Returns uploaded photo in grayscale (smoke test) |
| `POST /api/dye` | Applies hair dye. Form fields: `image` (file), `color` (hex). 422 if no face detected |

## Roadmap

- [ ] Weeks 3-5: photo pipeline (face detection + HSV dye)
- [ ] Week 7 (P1): photo demo (dye + first beard overlay)
- [ ] Weeks 8-11: dataset and YOLO fine-tuning on Colab
- [ ] Weeks 11-13: Delaunay warping, haircuts, before/after view
- [ ] Weeks 13-15: real-time video mode (stretch goal) + deliverables (LaTeX, videos, web page)
