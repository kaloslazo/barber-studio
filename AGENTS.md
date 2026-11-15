# BarberStudio — Project Conventions

## Language
- Code, scaffold, folder/file names and commits: **English**.
- UI text: **Spanish** (changed on 2026-11-09; the product is called Fresh). Backend error messages stay in English and the frontend translates them in `frontend/js/ui.js`.
- Course deliverables (LaTeX document, slides, video scripts): **Spanish** (the course is taught in Spanish).

## Architecture
- Web app: FastAPI backend (Python + OpenCV + YOLO) and vanilla HTML/CSS/JS frontend (no build step, must stay easy to reproduce for the course).
- Pipeline logic lives in `backend/app/core/*`: detection, segmentation, coloring, geometry, compositing, splatting, game, lab.
- API endpoints stay thin; real logic goes into core modules. Every call into the pipeline goes through `work()` in `routes.py` (worker thread + one lock).
- The server runs a single uvicorn process: live mode, the wig try-on and the game keep per-session state in memory, so more workers would split it.
- Fine-tuning scripts/notebooks live in `backend/training/` and run on Google Colab (no local GPU assumed).
- `data/` is gitignored (datasets are too heavy and have their own licenses). The models the app needs, including `backend/models/hair_best.pt`, are in git.

## Style
- No comments in code unless requested.
- Follow existing patterns in the codebase.
- UI follows the project design-system skill when it is created (barber theme).
