# Capturas de resultados

Todas las imágenes de prueba son retratos oficiales de la NASA en **dominio
público** (Wikimedia Commons). Créditos en `data/test_faces/CREDITS.txt`.

| Carpeta | Qué muestra | Cómo se generó |
|---|---|---|
| `beard_photo/` | Barba en modo foto, los 4 estilos sobre 2 retratos (control de regresión) | `apply_beard` en modo foto |
| `p2_physics/` | Barba con física: `*_sway.gif` (vaivén + tirón brusco; rubio y kim), `*_strip.jpg` (8 instantes, las 4 caras), `*_rest_vs_swing.jpg` (reposo vs. balanceo), `*_lag.csv` (velocidad de la cabeza vs. retraso de las puntas) | Secuencia sintética de 48 cuadros a 10 fps sobre el pipeline real (`apply_beard_physics`) |
| `p3_gaussians/` | `*_stages.jpg`: 20 → 2000 gaussianas (fila 1 suave, fila 2 elipses); `psnr_charts.png`; `psnr_table.csv` | `fit_gaussians` sobre 6 retratos (+2 con barba) |
| `p4_speedrun/` | Barber Speedrun: tira por cara y objetivo (6 casos) y GIF de 4 de ellos, con puntaje en vivo | "Bot barbero" que mueve la máquina en zigzag sobre el pipeline real (`game_frame`) |
| `p5_mirror/` | Espejo 3D: `*_turntable.gif` (24 ángulos), vistas `front/left/right/below`, `*_splats.png` (gaussianas individuales) | Visor WebGL2 real en Chrome headless (SwiftShader) |
| `ui/` | Interfaz real funcionando: P3 (progreso, suave, elipses), P2 en vivo, P4 (listo, a mitad de ronda, final con ranking) | Chrome headless con cámara simulada (`.y4m`), subida de archivos y mouse vía DevTools Protocol |

> Los GIF están comprimidos (paleta de 64 colores) para mantener el repo liviano.
