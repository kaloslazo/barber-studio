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
- **Beard try-on** (photo and live webcam): MediaPipe landmarks, own Delaunay (Fortune) and piecewise-affine warp, layered compositing. Docs: `docs/beard_overview.md`, `docs/beard_technical.md`.
- **Beard physics** (Live → *Beard physics*): long beard strands simulated with Verlet chains anchored to the face mesh.
- **How many Gaussians are you?** (*Gaussian Splatting* tab): photo rebuilt from 2D Gaussians fitted from scratch (NumPy + hand-written Adam), with a guessing game.
- **Barber Speedrun** (game): shave a physics beard down to a target style in 30 s with your index finger (MediaPipe Hands) or the mouse.
- **3D Mirror**: your head as ~50k 3D Gaussians from one photo + the MediaPipe 3D mesh, rendered by our own WebGL2 Gaussian Splatting viewer.
- Docs for the new features: `docs/features_overview.md` (non-technical flow) and `docs/features_technical.md`; result captures in `docs/captures/`.

## Model setup

Most models are NOT in git (size). Set them up as follows:

- `backend/models/face_landmarker.task` — MediaPipe FaceLandmarker (3.6 MB, **included in the repo**).
- `backend/models/hand_landmarker.task` — MediaPipe HandLandmarker for Barber Speedrun (7.8 MB, **included in the repo**; source: `https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task`). Without it the game falls back to the mouse.
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
| `POST /api/beard` | Beard on a photo. Fields: `image`, `style` (`full`/`goatee`/`mustache`/`stubble`), `strength` |
| `POST /api/live` | One webcam frame. Fields: `image`, `mode` (`dye`/`beard`/`mesh`/`physics`), `style`, `strength`, `length`. Returns JPEG |
| `POST /api/gaussians` | Fits N 2D Gaussians to a photo. Fields: `image`, `count` (10–5000), `face_crop`, `beard`. Returns JSON with data URLs and PSNR |
| `POST /api/game/start` | Starts a Barber Speedrun round. Field: `target` (`goatee`/`mustache`/`chinstrap`) |
| `POST /api/game/frame` | One game frame. Fields: `image`, `pointer_x`, `pointer_y`, `pointer_down`, `use_hand`. Returns JSON (image + score) |
| `POST /api/head3d` | 3D Gaussian head. Fields: `image`, `beard`. Returns float32 rows `[x,y,z,cov6,r,g,b,a]` |

## Roadmap

- [ ] Weeks 3-5: photo pipeline (face detection + HSV dye)
- [ ] Week 7 (P1): photo demo (dye + first beard overlay)
- [ ] Weeks 8-11: dataset and YOLO fine-tuning on Colab
- [ ] Weeks 11-13: Delaunay warping, haircuts, before/after view
- [ ] Weeks 13-15: real-time video mode (stretch goal) + deliverables (LaTeX, videos, web page)
