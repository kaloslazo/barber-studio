# Informe final (LaTeX)

Documento del proyecto final de CS4016, en español. `main.pdf` es la versión compilada.

## Compilar

Requiere una distribución de LaTeX (MacTeX, TeX Live o MiKTeX) con `pdflatex` y `bibtex`.

```bash
cd report
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

## Estructura

- `main.tex`: preámbulo, portada y orden de las secciones.
- `sections/`: una sección por archivo.
- `references.bib`: referencias (estilo IEEE, `ieeetr`).
- `figures/`: figuras. Los retratos son oficiales de la NASA, de dominio público. Las capturas de la interfaz se tomaron de la aplicación corriendo en `http://localhost:8000`.
- `diagramas/`: los diagramas de pipeline en TikZ, con un estilo común (`estilo.tex`) y miniaturas reales de cada etapa (`img/`). Para regenerarlos:

```bash
cd backend && venv/bin/python ../report/diagramas/miniaturas.py
cd .. && python3 report/diagramas/build.py
```

`build.py` necesita `pdflatex` y `pymupdf`. Deja `figures/diagrama_<nombre>.pdf` para el informe, una copia en `slides/figures/` y un PNG en `docs/diagramas/`.
