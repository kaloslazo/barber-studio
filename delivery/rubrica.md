# Rúbrica P2 frente a lo que tenemos

Para revisar antes de entregar (lunes 16-nov, 23:59) y antes de exponer. No va en el `.zip`.

`python3 delivery/verificar.py http://localhost:8000` revisa el zip contra los lineamientos y prueba cada herramienta de la app con la foto de ejemplo.

## Lineamientos (si falta uno, el proyecto no es satisfactorio)

| Pide | Dónde está | Estado |
|---|---|---|
| a. Documento en LaTeX y PDF, reproducible | `report/` → `documentacion-en-latex/` y `documentación-en-pdf/informe.pdf` | Listo; actualizar y recompilar con lo de hoy |
| b. Título | `delivery/titulo.txt` | Listo |
| c. Descripción de 1 o 2 párrafos | `delivery/descripcion-breve.txt` | Listo |
| d. Código fuente y cómo reproducir | `codigo-fuente/` (git archive de HEAD) + `README.md` | Listo; el zip toma el último commit |
| e. Video corto ≤ 1:30 | `delivery/videos/video-corto.mp4` | **Falta grabarlo** (guion en `guion-video-corto.md`) |
| f. Video largo ≤ 20 min | `delivery/videos/video-largo.mp4` | **Falta grabarlo** (guion en `guion-video-largo.md`) |
| g. Imágenes y videos extra | `imagenes-y-videos/` (galería, GIFs, diagramas) | Listo |
| h. Diapositivas (PDF y original) | `slides/` → `diapositivas-exposicion-final/` | Listo; recompilar |
| i. Página HTML con todo | `pagina-web/index.html`, sin internet | Listo |
| j. Todo en un solo .zip, sin links | `python3 delivery/build_zip.py` | Armar al final |
| k. El zip puede ir por Drive | Subir `dist/entrega-cs4016-fresh.zip` | Al final |
| l. Estructura de carpetas exacta | La arma `build_zip.py`, la revisa `verificar.py` | Listo |

## Criterios de la rúbrica

| Criterio (puntos) | Qué miran | Nuestra evidencia | Qué hacer antes de exponer |
|---|---|---|---|
| Dominio y aporte técnico en CG (11) | Aporte propio, no trivial; explicar fundamentos, código, decisiones, límites; responder casos límite y extensiones | ~87 % del núcleo es código propio: Fortune, warp afín por triángulo con muestreo bilineal propio, tinte en CIELAB con filtro guiado, cortes con pull-push y Lambert, Verlet + PBD, gaussianas 2D con gradientes analíticos y Adam, splatting 3D en WebGL2, y Fiesta (cambio de cara con mezcla multibanda, caricatura de Brennan, morphing). Tabla «Temas del sílabo» en el informe | Cada uno repasa `preguntas-defensa.md` de su parte; saber dibujar en la pizarra: mapeo inverso, afín por triángulo, pirámide laplaciana, fórmula de Brennan |
| Comunicación escrita (1,5) | Estructura, redacción técnica clara, ortografía, citado ACM/IEEE | Informe con estilo `ieeetr`, citas en el texto, paper de 4 páginas | Revisar que todas las citas compilen (sin «?») |
| Comunicación oral (2) | Claridad, tiempo, recursos visuales, contacto visual | Diapositivas Beamer + demo en vivo (`demo-en-vivo.md`) | Ensayar una vez con cronómetro; cada uno habla de lo suyo |
| Liderazgo / iniciativa (1,5) | Participación constante, propone mejoras | Historial de git por integrante, PRs | Que cada uno muestre y explique su módulo |
| Colaboración (2) | Integra ideas de otros, clima positivo | Ramas y PRs integrados (la de Gianpier entra en este PR) | Presentar como un solo producto, no tres partes sueltas |
| Desarrollo de software (2) | Metodología, calidad, verificación de requisitos | 107 pruebas automáticas (`pytest`), CI en GitHub Actions, Docker, API documentada, `verificar.py` | Correr las pruebas antes de exponer y mostrarlas 10 s |

## Pendiente de cada uno

- Todos: grabar los dos videos con los guiones y ponerlos en `delivery/videos/`.
- Gianpier: revisar que la descripción de su barba en vivo y la peluca 360 en el informe sea exacta.
- Kalos: armar el zip (`build_zip.py`), correr `verificar.py` y subirlo.
