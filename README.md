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

## Setup

Backend:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt        # app runtime
pip install -r requirements-dev.txt    # tests
pip install -r requirements-training.txt  # YOLO fine-tuning (Colab)
uvicorn app.main:app --reload --port 8000
```

Tests:

```bash
cd backend && venv/bin/python -m pytest tests/ -q
```

Frontend:

```bash
cd frontend
python3 -m http.server 5173
```

Then open http://localhost:5173.

## Current status

- Working **hair dye demo**: upload a photo, pick a color and the app recolors the hair region in HSV space (color theory). Hair region is still provisional (ellipse above the face box) until YOLO segmentation replaces it.

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
