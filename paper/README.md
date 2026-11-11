# Resumen tipo paper

Versión corta del informe, en formato de artículo a dos columnas (4 páginas): problema, pipeline, métodos con sus fórmulas clave, resultados, limitaciones y referencias. El informe completo está en `report/`.

## Compilar

Desde esta carpeta, con `pdflatex` y `bibtex`:

```bash
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

## Figuras

`figures/` tiene copias de `report/figures/`. `report/diagramas/build.py` actualiza los diagramas que ya están aquí cuando se regeneran.
