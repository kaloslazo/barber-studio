"""Revisa la entrega contra los lineamientos del proyecto final de CS4016 y,
si se le pasa la URL de la app, prueba cada herramienta con la foto de ejemplo.

    python3 delivery/verificar.py                          # solo el zip
    python3 delivery/verificar.py http://localhost:8000    # zip y app
"""

import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZIP = ROOT / "dist" / "entrega-cs4016-fresh.zip"
SAMPLE = ROOT / "frontend" / "assets" / "samples" / "ejemplo.jpg"
LIMITS = {"imagenes-y-videos/video-corto.mp4": 90, "imagenes-y-videos/video-largo.mp4": 1200}

results = []


def check(ok, text):
    results.append(ok)
    print(("  ok    " if ok else "  FALTA ") + text)


def duration(data):
    probe = shutil.which("ffprobe")
    if not probe:
        return None
    path = ROOT / "dist" / f".video-{uuid.uuid4().hex}.mp4"
    path.write_bytes(data)
    try:
        out = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                             capture_output=True, text=True).stdout.strip()
        return float(out) if out else None
    finally:
        path.unlink()


def revisar_zip():
    print(f"\nZip: {ZIP.relative_to(ROOT)}")
    if not ZIP.exists():
        check(False, "no existe: corre python3 delivery/build_zip.py")
        return
    with zipfile.ZipFile(ZIP) as archive:
        names = set(archive.namelist())
        tops = {name.split("/")[0] for name in names}
        for folder in ["documentación-en-pdf", "documentacion-en-latex", "codigo-fuente", "imagenes-y-videos",
                       "pagina-web", "diapositivas-exposicion-final"]:
            check(folder in tops, f"carpeta {folder}/")
        for file in ["titulo.txt", "descripcion-breve.txt", "pagina-web/index.html",
                     "diapositivas-exposicion-final/diapositivas.pdf", "documentacion-en-latex/main.tex"]:
            check(file in names, file)
        check(any(n.startswith("documentación-en-pdf/") and n.endswith(".pdf") for n in names), "informe en PDF")
        check(any(n.startswith("diapositivas-exposicion-final/original-latex/") and n.endswith(".tex") for n in names),
              "original de las diapositivas")
        check(any(n.startswith("codigo-fuente/") and n.endswith("README.md") for n in names),
              "código fuente con instrucciones (README)")
        images = [n for n in names if n.startswith("imagenes-y-videos/") and n.lower().endswith((".jpg", ".png", ".gif"))]
        check(len(images) >= 5, f"imágenes del trabajo ({len(images)})")
        for video, limit in LIMITS.items():
            if video not in names:
                check(False, f"{video} (máximo {limit} s)")
                continue
            seconds = duration(archive.read(video))
            if seconds is None:
                check(True, f"{video} (instala ffprobe para medir la duración)")
            else:
                check(seconds <= limit, f"{video} dura {seconds:.0f} s (máximo {limit} s)")
        if "titulo.txt" in names:
            check(bool(archive.read("titulo.txt").decode("utf-8").strip()), "título no vacío")
        if "descripcion-breve.txt" in names:
            text = archive.read("descripcion-breve.txt").decode("utf-8")
            paragraphs = [p for p in text.split("\n\n") if p.strip()]
            check(1 <= len(paragraphs) <= 2, f"descripción breve de 1 o 2 párrafos ({len(paragraphs)})")
        if "pagina-web/index.html" in names:
            page = archive.read("pagina-web/index.html").decode("utf-8")
            check(not re.search(r"(src|href)=[\"']https?://", page), "página web sin enlaces a internet")
            missing = [ref for ref in re.findall(r"(?:src|href)=\"\.\./([^\"]+)\"", page) if ref not in names]
            check(not missing, f"la página encuentra todos sus archivos ({len(missing)} faltan)")
        size = ZIP.stat().st_size / (1024 * 1024)
        print(f"  tamaño: {size:.0f} MB")


def post(base, path, fields=None, image=True):
    boundary = uuid.uuid4().hex
    body = b""
    for key, value in (fields or {}).items():
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode()
    if image:
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{image if isinstance(image, str) else 'image'}\"; "
                 f"filename=\"foto.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n").encode() + SAMPLE.read_bytes() + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    request = urllib.request.Request(base + path, data=body, method="POST",
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    start = time.time()
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status, time.time() - start
    except urllib.error.HTTPError as error:
        return error.code, time.time() - start


def revisar_app(base):
    print(f"\nApp: {base}")
    try:
        with urllib.request.urlopen(base + "/api/health", timeout=10) as response:
            health = json.loads(response.read())
        check(health.get("status") == "ok", f"servidor responde (YOLO {'sí' if health.get('yolo') else 'no'})")
    except OSError as error:
        check(False, f"servidor no responde: {error}")
        return
    pruebas = [
        ("Forma de la cara", "/api/face-shape", {}),
        ("Barba completa", "/api/beard", {"style": "full"}),
        ("Barba candado", "/api/beard", {"style": "goatee"}),
        ("Tinte rojo", "/api/dye", {"color": "#b3312c"}),
        ("Tinte rubio con barba", "/api/dye", {"color": "#d9b04a", "beard": "true"}),
        ("Corte degradado medio", "/api/haircut", {"style": "mid-fade"}),
        ("Corte rapado", "/api/haircut", {"style": "buzz"}),
        ("Malla de Delaunay", "/api/mesh", {}),
        ("En vivo: tinte", "/api/live", {"mode": "dye"}),
        ("En vivo: barba", "/api/live", {"mode": "beard"}),
        ("En vivo: física", "/api/live", {"mode": "physics"}),
        ("Gaussianas 2D", "/api/gaussians", {"count": "200"}),
        ("Espejo 3D", "/api/head3d", {}),
        ("Contrarreloj", "/api/game/frame", {"pointer_x": "0.5", "pointer_y": "0.6"}),
        ("Laboratorio", "/api/lab/mesh", {}),
        ("Peluca: prueba en vivo", "/api/transfer/tryon", {}),
        ("Fiesta: guardar cara", "/api/faces/source", {}),
        ("Fiesta: una cara para todos", "/api/faces/photo", {"mode": "wear"}),
        ("Fiesta: caricatura", "/api/faces/photo", {"mode": "caricature", "preset": "alien"}),
        ("Fiesta: en vivo", "/api/faces/live", {"mode": "caricature"}),
    ]
    post(base, "/api/game/start", {"target": "goatee"}, image=False)
    for name, path, fields in pruebas:
        status, seconds = post(base, path, fields)
        check(status == 200, f"{name:30s} {status}  {seconds:5.2f} s")


if __name__ == "__main__":
    revisar_zip()
    if len(sys.argv) > 1:
        revisar_app(sys.argv[1].rstrip("/"))
    print(f"\n{sum(results)} de {len(results)} puntos en orden.")
    sys.exit(0 if all(results) else 1)
