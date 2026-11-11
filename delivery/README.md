# Entrega del curso (P2)

Arma el `.zip` con la estructura que piden los lineamientos del proyecto final de CS4016:

```
documentación-en-pdf/informe.pdf
documentacion-en-latex/
titulo.txt
descripcion-breve.txt
codigo-fuente/                     (git archive de HEAD, sin report/, slides/ ni delivery/)
imagenes-y-videos/                 (figuras, GIFs y los dos videos)
pagina-web/index.html              (funciona sin internet)
diapositivas-exposicion-final/diapositivas.pdf
diapositivas-exposicion-final/original-latex/
```

## Pasos

1. Compilar el informe (`report/`) y las diapositivas (`slides/`); ver el README de cada carpeta.
2. Poner los videos en `delivery/videos/` (esa carpeta no se sube a git):
   - `video-corto.mp4`: pitch, de 1:30 como máximo;
   - `video-largo.mp4`: explicación, de 20 minutos como máximo.
3. Desde la raíz del repositorio:

```bash
python3 delivery/build_zip.py
```

El resultado queda en `dist/entrega-cs4016-fresh.zip`. El script avisa si falta algún video, si un video dura más de lo permitido (cuando `ffprobe` está instalado) o si la página tiene enlaces a internet.

El código se toma del último commit (`HEAD`). Hay que hacer commit de los cambios antes de armar el `.zip`.

## Archivos

- `titulo.txt` y `descripcion-breve.txt`: van tal cual al `.zip`.
- `pagina-web/index.html`: plantilla de la página. El script completa la descripción, la galería y las animaciones.
- `build_zip.py`: arma la carpeta `dist/entrega-cs4016-fresh/` y el `.zip`.
