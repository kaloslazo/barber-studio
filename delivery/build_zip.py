"""Assembles the course delivery zip with the exact folder layout the
CS4016 guidelines ask for. Run from anywhere: python3 delivery/build_zip.py"""

import html
import io
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELIVERY = ROOT / "delivery"
OUT = ROOT / "dist" / "entrega-cs4016-fresh"
ZIP = ROOT / "dist" / "entrega-cs4016-fresh.zip"

GALLERY = [
    ("ui_inicio.jpg", "Inicio de Fresh, con la demostración de estilos de barba.", False),
    ("ui_corte.jpg", "Panel de corte con las sugerencias según la forma de la cara.", False),
    ("cortes.jpg", "Los ocho cortes sobre tres retratos: degradado bajo, medio y alto, taper, undercut, raya marcada, crew cut y rapado.", True),
    ("combinado.jpg", "Look combinado: barba completa, tinte que incluye la barba y degradado medio.", True),
    ("barba_estilos.jpg", "Los cuatro estilos de barba: completa, candado, bigote y tres días.", True),
    ("malla.jpg", "Malla de Delaunay calculada con nuestro algoritmo de Fortune.", False),
    ("forma_cara.jpg", "Medidas sobre la malla 3D para clasificar la forma de la cara.", False),
    ("pull_push.jpg", "Relleno del fondo donde se quita pelo: Telea arrastra el pelo; pull-push con solo fondo queda limpio.", True),
    ("tinte_modelos.jpg", "Máscara del YOLO propio y de MediaPipe, y el tinte con cada una.", False),
    ("barba_tinte.jpg", "Tinte que incluye la barba: una barba de la app y un bigote real.", False),
    ("ui_tinte.jpg", "Panel de tinte con barba y selector de modelo.", False),
    ("ui_ficha.jpg", "Ficha para el barbero con indicaciones de máquina.", False),
    ("fisica.jpg", "Barba con física: en reposo y durante un movimiento rápido.", True),
    ("gaussianas2d.jpg", "Retrato con 20, 60, 200, 600 y 2000 gaussianas 2D, y cada gaussiana como elipse.", True),
    ("psnr.png", "Calidad de la reconstrucción según el número de gaussianas.", True),
    ("espejo3d_frente.jpg", "Espejo 3D: cabeza de gaussianas construida desde una foto.", False),
    ("espejo3d_splats.jpg", "Espejo 3D mostrando cada gaussiana.", False),
    ("peluca3d.jpg", "Peluca de gaussianas sobre el maniquí.", False),
    ("espejo3d_giro.jpg", "Espejo 3D girado: con una sola vista, el relieve detrás de la cara se estira.", False),
    ("contrarreloj.jpg", "Una ronda de Contrarreloj, de la barba completa al candado.", True),
]

ANIMATIONS = [
    ("docs/captures/p5_mirror/rubio_full_turntable.gif", "Espejo 3D girando."),
    ("docs/captures/p5_mirror/kim_goatee_turntable.gif", "Espejo 3D con candado."),
    ("docs/captures/p2_physics/rubio_sway.gif", "Física de la barba."),
    ("docs/captures/p2_physics/kim_sway.gif", "Física con otro retrato."),
    ("docs/captures/p4_speedrun/rubio_goatee.gif", "Contrarreloj hasta el candado."),
    ("docs/captures/p4_speedrun/horowitz_chinstrap.gif", "Contrarreloj hasta el collar."),
]

DIAGRAMS = [
    ("general", "Pipeline general. En gris, los modelos preentrenados, que solo ubican la cara, el pelo y la mano; el resto lo implementó el equipo."),
    ("arquitectura", "Arquitectura: el navegador y un solo proceso de FastAPI dentro de Docker."),
    ("barba", "Barba: puntos, malla de Delaunay, plantilla deformada por triángulo y composición."),
    ("tinte", "Tinte: máscara de YOLO o MediaPipe y recoloreo en CIELAB que conserva los mechones."),
    ("corte", "Corte: marco de la cabeza, plan del corte, relleno pull-push y pelo corto con Lambert."),
    ("vivo", "En vivo: seguimiento, anclaje baricéntrico y física con Verlet y PBD."),
    ("gaussianas", "Gaussianas 2D: optimización con gradientes analíticos y Adam escrito a mano."),
    ("espejo", "Espejo 3D: gaussianas construidas en el servidor y dibujadas con shaders propios en WebGL2."),
    ("peluca", "Peluca 3D: envolvente visual por cortes y textura de varias vistas."),
    ("juego", "Contrarreloj: corte por cápsula entre dos cuadros y puntaje."),
]

VIDEOS = ["video-corto.mp4", "video-largo.mp4"]
VIDEO_LIMITS = {"video-corto.mp4": 90, "video-largo.mp4": 1200}
CODE_EXCLUDE = ("report/", "slides/", "delivery/")


def copy_tree(src, dst, names):
    dst.mkdir(parents=True, exist_ok=True)
    for name in names:
        source = src / name
        if source.is_dir():
            shutil.copytree(source, dst / name)
        else:
            shutil.copy2(source, dst / name)


def export_code(dst):
    archive = subprocess.run(["git", "-C", str(ROOT), "archive", "--format=tar", "HEAD"], check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        members = [m for m in tar.getmembers() if not m.name.startswith(CODE_EXCLUDE)]
        tar.extractall(dst, members=members, filter="data")


def render_page(dst):
    template = (DELIVERY / "pagina-web" / "index.html").read_text(encoding="utf-8")
    paragraphs = [p.strip() for p in (DELIVERY / "descripcion-breve.txt").read_text(encoding="utf-8").split("\n\n") if p.strip()]
    description = "\n      ".join(f"<p>{html.escape(p)}</p>" for p in paragraphs)
    figures = []
    for name, caption, wide in GALLERY:
        opening = '<figure class="wide">' if wide else "<figure>"
        figures.append(f'{opening}<img src="../imagenes-y-videos/{name}" alt="">'
                       f"<figcaption>{html.escape(caption)}</figcaption></figure>")
    gallery = "\n        ".join(figures)
    animations = "\n        ".join(
        f'<figure><img src="../imagenes-y-videos/{Path(path).name}" alt=""><figcaption>{html.escape(caption)}</figcaption></figure>'
        for path, caption in ANIMATIONS
    )
    diagrams = "\n        ".join(
        f'<figure class="wide"><img src="../imagenes-y-videos/diagrama_{name}.png" alt=""><figcaption>{html.escape(caption)}</figcaption></figure>'
        for name, caption in DIAGRAMS
    )
    page = (template.replace("{{DESCRIPCION}}", description).replace("{{DIAGRAMAS}}", diagrams)
            .replace("{{GALERIA}}", gallery).replace("{{ANIMACIONES}}", animations))
    (dst / "index.html").write_text(page, encoding="utf-8")
    return page


def video_seconds(path):
    probe = shutil.which("ffprobe")
    if not probe:
        return None
    result = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                            capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def main():
    problems = []
    for needed in [ROOT / "report" / "main.pdf", ROOT / "slides" / "main.pdf"]:
        if not needed.exists():
            sys.exit(f"Falta {needed.relative_to(ROOT)}: compílalo primero (ver su README).")

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    pdf_dir = OUT / "documentación-en-pdf"
    pdf_dir.mkdir()
    shutil.copy2(ROOT / "report" / "main.pdf", pdf_dir / "informe.pdf")
    copy_tree(ROOT / "report", OUT / "documentacion-en-latex", ["main.tex", "references.bib", "sections", "figures", "diagramas", "README.md"])

    shutil.copy2(DELIVERY / "titulo.txt", OUT / "titulo.txt")
    shutil.copy2(DELIVERY / "descripcion-breve.txt", OUT / "descripcion-breve.txt")

    export_code(OUT / "codigo-fuente")

    media = OUT / "imagenes-y-videos"
    media.mkdir()
    for name, _, _ in GALLERY:
        shutil.copy2(ROOT / "report" / "figures" / name, media / name)
    for path, _ in ANIMATIONS:
        shutil.copy2(ROOT / path, media / Path(path).name)
    for name, _ in DIAGRAMS:
        shutil.copy2(ROOT / "docs" / "diagramas" / f"{name}.png", media / f"diagrama_{name}.png")
    for name in VIDEOS:
        source = DELIVERY / "videos" / name
        if not source.exists():
            problems.append(f"falta imagenes-y-videos/{name} (ponlo en delivery/videos/{name})")
            continue
        shutil.copy2(source, media / name)
        seconds = video_seconds(source)
        if seconds is not None and seconds > VIDEO_LIMITS[name]:
            problems.append(f"{name} dura {seconds:.0f} s y el máximo es {VIDEO_LIMITS[name]} s")

    (OUT / "pagina-web").mkdir()
    page = render_page(OUT / "pagina-web")
    if re.search(r"(src|href)=\"https?://", page):
        problems.append("la página web tiene enlaces a internet")

    slides = OUT / "diapositivas-exposicion-final"
    slides.mkdir()
    shutil.copy2(ROOT / "slides" / "main.pdf", slides / "diapositivas.pdf")
    copy_tree(ROOT / "slides", slides / "original-latex", ["main.tex", "figures", "README.md"])

    if ZIP.exists():
        ZIP.unlink()
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(OUT.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(OUT).as_posix())

    size = ZIP.stat().st_size / (1024 * 1024)
    print(f"Listo: {ZIP.relative_to(ROOT)} ({size:.1f} MB)")
    for entry in sorted(p.name for p in OUT.iterdir()):
        print("  ", entry)
    if problems:
        print("\nPendiente antes de entregar:")
        for problem in problems:
            print("  -", problem)


if __name__ == "__main__":
    main()
