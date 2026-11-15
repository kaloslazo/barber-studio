"""Compila los diagramas TikZ y los deja listos para el informe, las
diapositivas y docs/.

    python3 report/diagramas/build.py [nombre ...]

Necesita pdflatex y pymupdf (pip install pymupdf). Cada diagrama se compila
como una página, se recorta a su contenido y se guarda como:

- report/figures/diagrama_<nombre>.pdf (informe)
- slides/figures/diagrama_<nombre>.pdf (diapositivas)
- docs/diagramas/<nombre>.png (documentación y página web de la entrega)
- frontend/assets/diagramas/<nombre>.png (página «Cómo funciona» de la app)
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pymupdf

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PAD = 4


def build(name):
    with tempfile.TemporaryDirectory() as tmp:
        for item in ("estilo.tex", f"{name}.tex"):
            shutil.copy2(HERE / item, tmp)
        shutil.copytree(HERE / "img", Path(tmp) / "img")
        run = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", f"{name}.tex"],
            cwd=tmp, capture_output=True, text=True,
        )
        if run.returncode != 0:
            print(run.stdout[-3000:])
            raise SystemExit(f"{name}: no compila")
        source = pymupdf.open(Path(tmp) / f"{name}.pdf")
        page = source[0]
        box = pymupdf.Rect()
        for rect in page.get_bboxlog():
            box |= pymupdf.Rect(rect[1])
        box = pymupdf.Rect(box.x0 - PAD, box.y0 - PAD, box.x1 + PAD, box.y1 + PAD) & page.rect
        page.set_cropbox(box)
        for folder in (ROOT / "report" / "figures", ROOT / "slides" / "figures", ROOT / "paper" / "figures"):
            target = folder / f"diagrama_{name}.pdf"
            if folder.parent.name == "paper" and not target.exists():
                continue
            source.save(target, garbage=3, deflate=True)
        for folder in (ROOT / "docs" / "diagramas", ROOT / "frontend" / "assets" / "diagramas"):
            folder.mkdir(parents=True, exist_ok=True)
            page.get_pixmap(dpi=220).save(folder / f"{name}.png")
        print(f"{name}: {box.width / 72 * 2.54:.1f} x {box.height / 72 * 2.54:.1f} cm")


if __name__ == "__main__":
    names = sys.argv[1:] or sorted(p.stem for p in HERE.glob("*.tex") if p.stem != "estilo")
    for name in names:
        build(name)
