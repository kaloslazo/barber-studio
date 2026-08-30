# BarberStudio — Project Conventions

## Language
- Code, scaffold, folder/file names, commits and UI text: **English**.
- Course deliverables (LaTeX document, slides, video scripts): **Spanish** (the course is taught in Spanish).

## Architecture
- Web app: FastAPI backend (Python + OpenCV + YOLO) and vanilla HTML/CSS/JS frontend (no build step, must stay easy to reproduce for the course).
- Pipeline logic lives in `backend/app/core/*`: detection, segmentation, coloring, geometry, compositing.
- API endpoints stay thin; real logic goes into core modules.
- Fine-tuning scripts/notebooks live in `backend/training/` and run on Google Colab (no local GPU assumed).
- `data/` and `models/` are gitignored (datasets and weights are too heavy for git).

## Style
- No comments in code unless requested.
- Follow existing patterns in the codebase.
- UI follows the project design-system skill when it is created (barber theme).
