# Guion de demo — BarberStudio (≈ 8 minutos)

> Para la exposición del curso CS4016. Pensado para que el profe **participe**.
> Cada bloque dice **qué mostrar**, **qué decir** (el gancho técnico) y un **plan B**.

---

## Antes de empezar (checklist)

- [ ] `./run.sh` en la raíz y abrir **http://localhost:8000** en Chrome.
- [ ] Luz de frente, fondo liso, cámara a la altura de la cara.
- [ ] Fotos de respaldo en `data/test_faces/` (retratos NASA de dominio público).
- [ ] Probar una vez cada pestaña (la primera carga de los modelos tarda unos segundos).
- [ ] Plan B general: si la cámara falla, todo lo de foto (P3, Beard, 3D Mirror)
      funciona con las imágenes de respaldo, y hay GIFs en `docs/captures/`.

---

## 1. Apertura — "¿Cuántas gaussianas sos?" (1:30)

**Mostrar:** pestaña *Gaussian Splatting* → subir una foto (idealmente del profe o
de un compañero) → activar **Guess mode** → *Start*.

**Decir:**
> "Antes de mostrar la barbería, una pregunta: ¿con cuántas manchitas borrosas
> pueden reconocer una cara? Cada etapa es una imagen hecha **solo** de gaussianas
> 2D, ajustadas con descenso de gradiente y un Adam que escribimos a mano en
> NumPy, sin PyTorch. Aprieten el botón cuando la reconozcan: menos gaussianas,
> más puntos."

**Gancho técnico:** el PSNR sube casi lineal en log N (~8 dB por cada ×10). Cambiar
a *Ellipses* para que vean cada gaussiana como una elipse.

**Plan B:** `docs/captures/p3_gaussians/*_stages.jpg`.

---

## 2. Barba en foto + malla (1:00)

**Mostrar:** pestaña *Beard* → foto → estilo *Full* → activar *Show Delaunay mesh*.

**Decir:**
> "Un modelo preentrenado (MediaPipe) nos da los puntos de la cara. Todo lo demás
> es nuestro: la triangulación de Delaunay con el algoritmo de **Fortune**, el
> warp afín por triángulo con muestreo bilineal propio y la composición en capas
> (multiply para conservar la luz de la piel, hebras con curvas de Bézier y
> transferencia de gradientes de una barba real)."

---

## 3. En vivo + barba con física (1:30)

**Mostrar:** *Live* → *Beard* (estilos) → *Beard physics* → mover la cabeza rápido.

**Decir:**
> "En vivo, la cara se **rastrea** en vez de re-detectarse, con un filtro
> One-Euro contra el temblor. Si el modelo pierde la cara un instante, estimamos
> el movimiento con correlación de fase (FFT). Y esta barba larga tiene física:
> cada pelo es una cadena de partículas con integración de **Verlet**, un resorte
> a su pose y restricciones de distancia. La raíz está pegada a la malla con
> coordenadas baricéntricas, por eso viaja con la piel. Y cada pelo se dibuja
> como una cadena de gaussianas alargadas, no como una línea."

**Plan B:** `docs/captures/p2_physics/*_sway.gif`.

---

## 4. Barber Speedrun — el profe juega (2:00)

**Mostrar:** *Barber Speedrun* → objetivo *Goatee* → nombre "Profe" → *Start
camera* → *Start round*.

**Decir:**
> "Profe, le toca. Tiene barba completa y 30 segundos para dejar un candado.
> Apunte con el índice para cortar; con la mano abierta solo mueve la máquina."

**Gancho técnico (mientras juega):** la mano la detecta MediaPipe Hands. El corte
usa una **cápsula barrida** entre cuadros (para que no se "escape" pelo a 10 fps)
y solo corta al ras de la piel (raíz y primer tramo). El puntaje es
**afeitado × conservado × 1000**, y empieza en 0.

**Plan B:** sin mano, mantener apretado el mouse sobre la imagen.
Videos: `docs/captures/p4_speedrun/*.gif`.

---

## 5. 3D Mirror — el cierre (1:30)

**Mostrar:** *3D Mirror* → foto → *Full* → *Build 3D head* → arrastrar para girar
→ activar **Show individual splats** → *Download .ply*.

**Decir:**
> "Con **una sola foto** y la malla 3D de MediaPipe armamos ~55 000 gaussianas
> 3D: discos tangentes a la piel, el entorno como relieve y la barba como hebras
> 3D. El visor es nuestro, en WebGL2: proyecta cada gaussiana con la jacobiana
> (**EWA splatting**, Σ' = J W Σ Wᵀ Jᵀ), las ordena con counting sort y las
> compone de atrás hacia adelante, igual que el render de 3D Gaussian Splatting.
> Y el *.ply* es el formato estándar: se abre en SuperSplat."

**Honestidad (si preguntan):** es el **render** de 3DGS con gaussianas
construidas, no un 3DGS entrenado con muchas vistas y GPU. Por eso no hay nuca.

**Plan B:** `docs/captures/p5_mirror/*_turntable.gif`.

---

## 6. Cierre (0:30)

> "Usamos IA solo para **ubicar** la cara y la mano. Todo lo gráfico es nuestro:
> Delaunay de Fortune, warps afines, muestreo bilineal, composición alpha, física
> de Verlet, gaussianas 2D con gradientes analíticos y un renderer de Gaussian
> Splatting en WebGL. 33 tests automáticos y pruebas de punta a punta en el
> navegador."

---

## Temas del sílabo que aparecen

| Tema | Dónde se ve en la demo |
|---|---|
| 6.1.1 Color | Color de barba desde el pelo en YCrCb |
| 6.1.2 Representaciones de imagen | Píxeles vs. gaussianas (P3), capas alpha |
| 6.1.3 Sampling | Bilineal, muestreo estratificado de splats, gaussianas |
| 6.1.4 Interpolación | Warp afín, Bézier/Chaikin, Verlet, One-Euro, baricéntricas |
| 6.2.2 Convex hull | Recorte de regiones, contorno facial en 3D |
| 6.2.5 Delaunay | Malla de la cara (Fortune) en 2D y 3D |
| 6.4.3–6.4.5 Features / detección | MediaPipe Face y Hands |
| Proyección / cámaras | Visor 3D: matriz de vista, perspectiva, jacobiana EWA |
