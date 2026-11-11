# Fresh (BarberStudio)

Try on beards, hair dyes and haircuts on your own photo or webcam before going to the barber. Course project for CS4016 (Computer Graphics, UTEC). The repository keeps its original name, `barber-studio`; the app is called **Fresh**.

The app does not generate a new face: it models the geometry of your face and hair and composites every style over the original photo, on the CPU. The only learned models are MediaPipe (face points, hands, segmentation) and our own fine-tuned YOLOv8n-seg for hair; everything else (Delaunay, warping, dye, haircut engine, physics, Gaussian splatting) is written by the team.

## Team

- Kalos Lazo
- Sofia Herrera
- Gianpier Segovia

## Features

- **Beard** on a photo and live: 478 MediaPipe points mapped to the 68-point layout, Delaunay triangulation with our own Fortune sweep, piecewise-affine warp of 10 real beard templates (CelebAMask-HQ), layered compositing (multiply, Bézier strands, high-frequency detail).
- **Hair dye** in CIELAB, keeping the strands' detail. Hair mask from our YOLOv8n-seg (mask mAP50 0.968, Figaro1k + CelebAMask-HQ) or MediaPipe, with the IoU between both reported per photo. It can also dye the beard.
- **Haircuts** (low, mid and high fade, taper, undercut, hard part, crew cut, buzz): pull-push fill of the background, head frame measured in head widths, superellipse skull fitted to the crown, hairline from the visible forehead, short hair with its own color and Lambert shading.
- **Combine** beard, dye and cut on one result, plus a sheet for the barber with the clipper numbers.
- **Face shape**: measured on the 3D mesh and classified against means calibrated on 419 CelebAMask-HQ faces, with suggested cuts and beards.
- **Beard physics** live: Verlet chains with distance constraints anchored to the face mesh.
- **Gaussians 2D**: a photo rebuilt from N 2D Gaussians with analytic gradients and a hand-written Adam, with a guessing game.
- **3D Mirror**: your head as more than 100k 3D Gaussians from one photo and the MediaPipe 3D mesh, drawn by our own WebGL2 splatting viewer (EWA projection, counting sort), exportable as `.ply`.
- **3D Wig**: a 12 s webcam scan turned into a hair volume (visual hull per slice), textured from the best views; recolor, shorten and trim it with scissors. The lab keeps Gaussians in each triangle's local frame so they follow the face live.
- **Speedrun** (game): shave a physics beard down to a target style in 30 s with your index finger (MediaPipe Hands) or the mouse.

## Course topics covered

| Topic | Where it applies |
|---|---|
| Color theory (6.1.1) | Hair dye in CIELAB, beard recoloring in YCrCb |
| Sampling and interpolation (6.1.3-6.1.4) | Own bilinear sampling in the warp, pull-push pyramid fill |
| Convex hull (6.2.2) | Face and beard region masks |
| Delaunay triangulation (6.2.5) | Fortune sweep line, facial mesh for warping |
| OpenCV (6.4.4) | Image I/O, filters, guided filter |
| YOLO + fine-tuning (6.4.5-6.4.6) | Hair segmentation (`backend/training/`) |
| Physics simulation | Verlet integration and position-based constraints for beard strands |
| Rendering | Lambert shading of short hair, 2D and 3D Gaussian splatting in WebGL2 |

## Architecture

- **Backend** (`backend/`): one FastAPI app that serves the UI and the API. Endpoints in `backend/app/api/routes.py` stay thin; the graphics code lives in `backend/app/core/`, one package per technique: `detection`, `segmentation`, `geometry`, `coloring`, `compositing`, `splatting`, `game`, `lab`. `backend/app/core/pipeline.py` ties them together.
- **Frontend** (`frontend/`): vanilla HTML, CSS and JavaScript, no build step. `frontend/js/splat3d.js` is the WebGL2 Gaussian viewer. The animated details in `frontend/js/bits.js` (rotating headline, blur-in titles, threads divider, pill nav fill, spotlight, count up) are vanilla ports of components from [React Bits](https://reactbits.dev) (MIT + Commons Clause).
- **One server process on purpose.** Live mode, the 3D wig try-on and the game keep per-session state in memory (face anchor, hair color, current round). Uvicorn runs a single process, and every call into the pipeline runs in a worker thread behind one lock, so the server keeps answering while a photo is processed.
- **Fine-tuning** scripts and the Colab notebook live in `backend/training/`.

## Run

With Docker (recommended; it installs CPU PyTorch for YOLO, so the first build takes a few minutes):

```bash
docker compose up -d --build app
```

Then open http://localhost:8000.

Without Docker, from the repo root (creates the venv and installs dependencies on first run; it also frees port 8000 if a previous instance is stuck):

```bash
./run.sh
```

Tests (49):

```bash
cd backend && venv/bin/python -m pytest tests/ -q
```

The GitHub Actions workflow (`.github/workflows/ci.yml`) runs the same tests on every push and pull request to `main`.

## Models

All the models the app needs are in `backend/models/`:

- `face_landmarker.task`: MediaPipe face mesh.
- `selfie_multiclass_256x256.tflite`: MediaPipe multiclass segmenter (hair, skin, background).
- `hand_landmarker.task`: MediaPipe hand points for the game. Without it the game falls back to the mouse.
- `hair_best.pt`: our fine-tuned YOLOv8n-seg hair model. Retrain it with `backend/training/barberstudio_colab.ipynb` (about 3.5 h on a free Colab T4).
- `lbfmodel.yaml`: OpenCV LBF landmarks, a fallback when MediaPipe is not available.

YOLO needs `requirements-yolo.txt`. Without it, or without `hair_best.pt`, the app uses MediaPipe and the model switch in the dye panel is hidden. Install order matters, because ultralytics pulls `opencv-python`, which hides the `cv2.face` and `cv2.ximgproc` modules:

```bash
pip install -r requirements.txt -r requirements-dev.txt
pip install -r requirements-yolo.txt
pip uninstall -y opencv-python
pip install --force-reinstall --no-deps "opencv-contrib-python>=4.9,<5"
```

The UI loads two things from the internet: the Google fonts (with local fallbacks) and the JavaScript build of MediaPipe, used only by the live 3D wig try-on.

## API

| Endpoint | Description |
|---|---|
| `GET /api/health` | Status and whether YOLO is available |
| `POST /api/face-shape` | Face shape and suggestions. Field: `image` |
| `POST /api/dye` | Hair dye. Fields: `image`, `color` (hex), `strength`, `beard`, `beard_style`, `model` (`auto`/`yolo`/`mediapipe`). Headers `X-Hair-Model`, `X-Mask-Agreement`, `X-Beard-Dyed` |
| `POST /api/beard` | Beard on a photo. Fields: `image`, `style` (`full`/`goatee`/`mustache`/`stubble`), `strength` |
| `POST /api/haircut` | Haircut. Fields: `image`, `style` (`low-fade`/`mid-fade`/`high-fade`/`taper`/`undercut`/`hard-part`/`crew`/`buzz`), `strength` |
| `POST /api/mesh` | Image with the Delaunay mesh drawn. Field: `image` |
| `POST /api/live` | One webcam frame. Fields: `image`, `mode` (`dye`/`beard`/`mesh`/`physics`), `color`, `style`, `strength`, `length`. Returns JPEG |
| `POST /api/gaussians` | Fits N 2D Gaussians. Fields: `image`, `count` (10-5000), `face_crop`, `beard`. Returns JSON with data URLs and PSNR |
| `POST /api/head3d` | 3D Gaussian head. Fields: `image`, `beard`, `format` (`raw`/`ply`) |
| `POST /api/transfer/scan`, `/transfer/face`, `/transfer/reconstruct`, `/transfer/splat`, `/transfer/photos` | 3D wig: scan frames, face scan, hair volume, Gaussians (`raw`/`ply`) and a zip with the captures |
| `POST /api/transfer/asset`, `/transfer/tryon` | 2D wig asset and live try-on anchor |
| `POST /api/lab/build`, `/lab/mesh` | Lab: Gaussians bound to the face mesh and the live mesh |
| `POST /api/game/start` | Starts a Speedrun round. Field: `target` (`goatee`/`mustache`/`chinstrap`) |
| `POST /api/game/frame` | One game frame. Fields: `image`, `pointer_x`, `pointer_y`, `pointer_down`, `use_hand`. Returns JSON (image + score) |

## Course deliverables

- `report/`: LaTeX report (Spanish), see its README to build `main.pdf`.
- `slides/`: Beamer slides for the final presentation.
- `delivery/`: title, short description, offline web page, video scripts and `build_zip.py`, which builds the `.zip` the course asks for.
