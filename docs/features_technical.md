# Opciones nuevas — Documento técnico

> BarberStudio · CS4016 Computación Gráfica · UTEC
>
> Implementación de **P2 (barba con física)**, **P3 ("¿Cuántas gaussianas sos?")**,
> **P4 (Barber Speedrun)** y **P5 (3D Mirror)**: qué hace cada pieza, dónde está,
> cómo funciona, por qué se eligió así y qué medimos. Versión sin tecnicismos:
> [`features_overview.md`](features_overview.md). Pipeline de barba base:
> [`beard_technical.md`](beard_technical.md).

---

## 0. Mapa de archivos

| Pieza | Archivo | Entrada principal |
|---|---|---|
| Física de hebras (P2, P4) | `backend/app/core/compositing/beard_physics.py` | `BeardPhysics` |
| Anclaje baricéntrico (compartido) | `backend/app/core/compositing/beard.py` | `barycentric_locate`, `barycentric_map`, `LiveAnchor` |
| Imagen con gaussianas 2D (P3) | `backend/app/core/splatting/gaussian_image.py` | `fit_gaussians`, `render_gaussians`, `draw_ellipses` |
| Juego (P4) | `backend/app/core/game/speedrun.py` | `SpeedrunGame`, `target_mask` |
| Dedo índice (P4) | `backend/app/core/detection/hands.py` | `FingerTracker` |
| Cabeza 3D en gaussianas (P5) | `backend/app/core/splatting/head3d.py` | `build_head_splats` |
| Malla 3D de MediaPipe (P5) | `backend/app/core/detection/landmarks.py` | `LandmarkDetector.mesh3d` |
| Orquestación | `backend/app/core/pipeline.py` | `apply_beard_physics`, `gaussian_portrait`, `game_frame`, `head3d` |
| Endpoints | `backend/app/api/routes.py` | `/api/live` (`mode=physics`), `/api/gaussians`, `/api/game/start`, `/api/game/frame`, `/api/head3d` |
| Visor WebGL2 (P5) | `frontend/js/splat3d.js` | `SplatViewer` |
| Interfaz | `frontend/index.html`, `frontend/js/app.js` | paneles *Live*, *Gaussian Splatting*, *Barber Speedrun*, *3D Mirror* |
| Tests | `backend/tests/test_splatting_physics.py`, `backend/tests/test_api.py` | 33 tests en total |

Modelos externos (solo inferencia, no entrenados por nosotros):
`backend/models/face_landmarker.task` y `backend/models/hand_landmarker.task`
(MediaPipe, Google).

---

## 1. Mejoras transversales del modo en vivo

### 1.1 Gating temporal con correlación de fase (Fase 5.3 del plan)
`StylePipeline._live_points`: si MediaPipe no devuelve la cara en un cuadro, se
reutilizan los últimos landmarks **hasta 3 cuadros**, desplazados por la
traslación global estimada con **correlación de fase**:

```
R(u,v) = F₁·F₂* / |F₁·F₂*|      →      (dx, dy) = argmax  IFFT(R)
```

(`cv2.phaseCorrelate` sobre la zona de la cara con ventana de Hann; se descarta si
la respuesta es < 0.05). En una prueba con un tirón brusco, sin esto la barba
desaparecía o quedaba "fantasma" en la posición vieja; con esto se mantiene sobre
la cara.

### 1.2 Color de pelo plausible
El color mediano del pelo (máscara heurística) se pasa a YCrCb y se limita a
`Cr ≥ 128`, `Cb ≤ 128`, es decir, a tonos cálidos o neutros. Un pelo natural no es
azul ni verde. En fondos azules oscuros, la máscara capturaba el fondo y la barba
salía azul.

---

## 2. P2 — Barba con física

### 2.1 Modelo
Cada hebra es una cadena de **4 partículas** `x₀…x₃`. Hay una hebra por cada ~30 píxeles de la región (3.5 %, máximo 2600): con una cara de webcam a 640 px salen unas 300.

- **Raíz `x₀`:** pegada a la piel. Se guarda una vez en **coordenadas
  baricéntricas** `(λ₁, λ₂, λ₃)` dentro de un triángulo de la malla de Delaunay de
  referencia (83 vértices). En cada cuadro, `x₀ = λ₁A' + λ₂B' + λ₃C'` con los
  vértices actuales. Fuera de la malla se usa la similitud global (`LiveAnchor.M`).
- **Pose de reposo:** la hebra "crece" en la dirección del pelo `d` (campo de
  dirección de la barba, sesgado hacia abajo) con una leve curva lateral,
  **rotada con la cabeza** usando la parte lineal de la similitud.
- **Largo:** `L = ancho_cara · U(0.10, 0.20) · (0.35 + 0.65·profundidad) · largo_usuario`,
  donde "profundidad" = cuán por debajo de la boca está la raíz (0 en la boca,
  1 en el mentón).
- **Labio superior:** las raíces por encima de la boca (bigote) crecen hacia los
  lados y miden la mitad. Así no cuelgan sobre los dientes. No se eliminan,
  porque el objetivo "bigote" del juego las necesita.

### 2.2 Integración (por cuadro, 4 subpasos `h = Δt/4`)
```
raíz(s)  = lerp(raíz_anterior, raíz_actual, s/4)            # sin saltos entre cuadros
v        = (x − x_prev) · 0.86                               # Verlet con amortiguamiento
x_prev   = x
x       += v + g·h²                                          # g = 2.2 · ancho_cara px/s²
x       += kᵢ · (x_reposo − x)                               # resorte, kᵢ = [0, .34, .22, .13]
x₀       = raíz(s)
repetir 2 veces:  xₖ = xₖ₋₁ + (xₖ − xₖ₋₁)/‖·‖ · ℓ            # restricción de distancia (PBD)
```
La rigidez baja hacia la punta, para que la base siga la cara y la punta tenga
inercia. Las restricciones de distancia mantienen el largo de cada tramo, que es lo
que hace que la hebra se balancee como un péndulo y no se estire.

### 2.3 Render: pelos como cadenas de gaussianas (P1)
- Suavizado **Chaikin** (un corte de esquinas, equivale a una B-spline cuadrática):
  4 nodos → 8 puntos → 7 tramos.
- **Cada tramo es una gaussiana 2D anisotrópica** (`splat_strands`): centro en el
  medio del tramo, `σ_largo = largo/2` a lo largo del tramo y `σ_ancho` =
  0.5–0.75 px a lo ancho, con opacidad que baja hacia la punta
  (`0.8·(1 − 0.6·j/(n−1))`).
- **Acumulación sin ordenar:** se suman la densidad `A = Σ oᵢGᵢ` y el color
  `Σ oᵢGᵢcᵢ` con `np.bincount`; la cobertura es `α = 1 − e^{−A}` (Beer-Lambert) y
  el color es el promedio ponderado. Muchos pelos superpuestos saturan suavemente
  sin necesidad de ordenar por profundidad.
- Comparado con las polilíneas antialias + desenfoque 3×3 anteriores, los pelos
  quedan **finos y nítidos**. Cuesta ~10 ms para ~2 000 tramos, con todo
  vectorizado sobre parches de 13×13.
- Los pelos cortados del juego (escombros) usan el mismo render, con opacidad que
  se desvanece con la edad.
- Se compone sobre la barba base del modo en vivo (`apply_beard(..., "full")`).

### 2.4 Mediciones (`docs/captures/p2_physics/`)
Secuencia sintética de 48 cuadros a 10 fps (vaivén + tirón brusco) sobre 4
retratos:

| Cara | Retraso máx. de puntas | Retraso medio | corr(velocidad cabeza, retraso) |
|---|---|---|---|
| rubio | 12.2 px | 2.5 px | 0.82 |
| kim | 11.8 px | 2.4 px | 0.82 |
| cockrell | 8.1 px | 1.8 px | 0.78 |
| horowitz | 8.5 px | 2.2 px | 0.81 |

El retraso aparece cuando la cabeza se mueve y se recupera solo, que es el
comportamiento físico buscado. En el navegador (Chrome con cámara simulada) el
modo corre a **~10 fps** (rango medido 7.6–11.4): ~72–78 ms por cuadro en el servidor.

### 2.5 Optimización del modo en vivo
El perfil mostraba 139 ms por cuadro. El 60 % se iba en:
- **warpear la plantilla de barba:** en vivo su detalle está apagado y solo se
  usaba para un color, que ahora sale directo del color de pelo en YCrCb;
- **dibujar las hebras de la barba base de a una**, con un bucle de Python. Ahora
  se agrupan por (tono, opacidad, grosor), con una llamada a `cv2.polylines` por
  grupo.

Resultado: física **139 → 72 ms**, barba en vivo **~100 → 61 ms** (de ~10 a
~12 fps en el navegador).

---

## 3. P3 — "¿Cuántas gaussianas sos?" (GaussianImage desde cero)

### 3.1 Representación
`N` gaussianas 2D con centro `μᵢ`, factor de Cholesky de la **inversa** de la
covarianza `L = [[l₁, 0], [l₂, l₃]]` (así `Σ⁻¹ = LLᵀ` siempre es definida positiva)
y peso RGB `cᵢ`:

```
u = l₁·dx + l₂·dy ,   v = l₃·dy ,   Gᵢ(x) = exp(−½ (u² + v²))
C(x) = Σᵢ cᵢ · Gᵢ(x)                      (acumulación, sin orden: estilo GaussianImage)
```

### 3.2 Optimización
- **Pérdida:** MSE contra la imagen (recortada a la cara, lado máximo 160 px).
- **Gradientes analíticos:** con `t = ∂L/∂Gᵢ · (−Gᵢ/2)`:
  `∂q/∂l₁ = 2u·dx`, `∂q/∂l₂ = 2u·dy`, `∂q/∂l₃ = 2v·dy`,
  `∂q/∂μₓ = −2u·l₁`, `∂q/∂μᵧ = −2u·l₂ − 2v·l₃`, `∂L/∂cᵢ = Σ ∂L/∂C · Gᵢ`.
- **Adam escrito a mano** (β₁ = 0.9, β₂ = 0.999), entre 110 y 160 iteraciones según `N`.
- **Inicialización guiada por bordes:** las posiciones se muestrean con
  probabilidad ∝ 0.35 + |∇I| (Sobel). El tamaño inicial es `σ₀ = 0.6·√(área/N)` y
  el color se divide por el solapamiento esperado.
- **Parches truncados por cubetas de radio:** cada gaussiana solo se evalúa en un
  parche de radio `⌈2.5σ_max⌉`, agrupado por niveles de radio. Así todo queda
  vectorizado (sin bucles por gaussiana), y la acumulación usa `np.bincount`.
- Optimizaciones medidas: `float32`, niveles de radio finos en vez de potencias
  de 2, corte en 2.5σ. Una etapa bajó de **10–21 s a 1–4 s**.

### 3.3 Independencia de resolución
`render_gaussians` reescala `μ` y `L` (`L/escala`), así que la misma lista de
gaussianas se dibuja a cualquier tamaño. `draw_ellipses` dibuja cada gaussiana como
su elipse de 1σ (eigen-descomposición de `Σ`), rellena con el color del render en
su centro.

### 3.4 Resultados (6 retratos, `docs/captures/p3_gaussians/psnr_table.csv`)

| N gaussianas | PSNR medio | rango | tiempo medio |
|---|---|---|---|
| 20 | 18.4 dB | 16.7–20.2 | 0.9 s |
| 60 | 22.2 dB | 20.3–24.9 | 2.4 s |
| 200 | 26.0 dB | 24.1–28.4 | 4.1 s |
| 600 | 29.8 dB | 27.5–31.8 | 3.8 s |
| 2000 | 34.5 dB | 32.9–35.9 | 3.6 s |

El PSNR crece casi **lineal en log N**, ~8 dB por cada ×10 gaussianas
(`psnr_charts.png`). La convergencia se estabiliza hacia las 100 iteraciones.

### 3.5 Juego
Etapas `[20, 60, 200, 600, 2000]`. Puntos al reconocer en la etapa `n`:
`max(50, 1000·(1 − ln n / ln 3000))`.

---

## 4. P4 — Barber Speedrun

### 4.1 Estado del juego (`SpeedrunGame`)
- **Barba inicial:** `BeardPhysics` sobre la región completa más la banda del
  bigote (`full_region`), con largo 0.8.
- **Objetivos** (`target_mask`): `goatee` y `mustache` (máscaras de `beard_mask`) y
  `chinstrap`, que es la región completa ∩ {distancia a la mandíbula < 0.09 ·
  ancho_cara}, calculada con distance transform sobre la polilínea de la mandíbula.
- Para cada hebra se guarda si su raíz cae en el objetivo (`in_target`), evaluado
  en el cuadro de referencia.

### 4.2 Corte (cápsula barrida)
La máquina se mueve de `p₀` (cuadro anterior) a `p₁` (actual). Se cortan las
hebras **vivas** con distancia < r (r = 0.05 · ancho_cara) desde la **raíz o el
primer nodo** al segmento `p₀p₁`:

```
t = clamp(((x − p₀)·(p₁ − p₀)) / ‖p₁ − p₀‖², 0, 1) ,   d = ‖x − (p₀ + t(p₁ − p₀))‖
```

- **Por qué un segmento:** a ~10 fps el dedo salta decenas de píxeles entre
  cuadros. Un punto aislado dejaría pelos sin cortar (tunneling).
- **Por qué solo raíz y primer nodo:** una máquina afeita al ras de la piel. En
  una prueba con todos los nodos, las puntas colgantes del candado se cortaban al
  pasar por debajo y se perdía el 55 % del objetivo.

Las hebras cortadas pasan a ser **escombros**: heredan la velocidad de su punta
más ruido e impulso hacia arriba, caen con 3.5 · ancho_cara px/s² y se
desvanecen en 1.4 s.

### 4.3 Máquina: mano o mouse
- **Mano** (`FingerTracker`, MediaPipe Hand Landmarker en modo VIDEO):
  - la herramienta es la punta del índice (landmark 8);
  - está **encendida** si el índice está extendido y el medio doblado (comparando
    distancias punta–muñeca contra articulación–muñeca, ×1.15);
  - con la mano abierta solo se mueve la máquina. Validado en una foto real CC0:
    detecta la punta y clasifica la mano abierta como "no corta".
- **Mouse:** corta solo mientras el botón está presionado (`pointer_down`).
- **Feedback visual:** se dibuja el esqueleto de la mano (21 landmarks, 21
  conexiones), verde con la máquina encendida y blanco si no. Validado en una foto
  real CC0 con cara de semiperfil y mano abierta: cara y mano se detectan a la vez,
  y la máquina queda apagada. La foto no se versiona por ser de una persona real.
- **Ritmo de juego:** cuenta regresiva 3-2-1-GO superpuesta antes de la ronda y
  "TIME!" al terminar. Ranking top 5 en `localStorage` del navegador.

### 4.4 Puntaje
```
limpieza    = |cortadas ∩ fuera_objetivo| / |fuera_objetivo|
conservación = |vivas ∩ objetivo| / |objetivo|
puntaje     = round(1000 · limpieza · conservación)
```
Empieza en 0 y lo perfecto es 1000. Se descartó el IoU puro como puntaje: con la
barba completa sin tocar, el IoU del candado ya valía 0.72, es decir, daba puntos
por no hacer nada. El IoU igual se reporta.

### 4.5 Sombra que se afeita
La sombra de la barba se construye con las **raíces vivas**: impulsos sumados con
`np.add.at`, desenfoque gaussiano (σ = ancho_cara/38) y normalización por la
densidad esperada (0.035 raíces/px). Al cortar desaparece también la sombra.
(Bug encontrado en la prueba de navegador: la normalización tenía un factor
`2πσ²` de más y la barba arrancaba casi invisible.)

### 4.6 Resultados
"Bot barbero" (zigzag sobre lo que hay que afeitar, con la máquina levantada en
los saltos largos), `docs/captures/p4_speedrun/`:

| Cara · objetivo | Puntaje | Limpieza | Conservación |
|---|---|---|---|
| rubio · goatee | 827 | 0.83 | 0.99 |
| rubio · mustache | 814 | 1.00 | 0.81 |
| rubio · chinstrap | 690 | 0.69 | 1.00 |
| kim · goatee | 817 | 0.83 | 0.99 |
| horowitz · chinstrap | 656 | 0.66 | 1.00 |
| cockrell · mustache | 646 | 0.98 | 0.66 |

Un bot que corta sin levantar la máquina (cruzando el objetivo) obtiene **0**. En
Chrome con cámara simulada y mouse, una ronda completa de 30 s funciona sin errores
de consola (`docs/captures/ui/p4_*.png`).

---

## 5. P5 — 3D Mirror (Gaussian Splatting 3D)

### 5.1 Qué es y qué no es
Es el **paso de render (forward)** de 3D Gaussian Splatting, implementado desde
cero en WebGL2, sobre gaussianas 3D **construidas** (no entrenadas) a partir de una
sola foto y de la malla 3D de MediaPipe.

No es un 3DGS entrenado por descenso de gradiente desde múltiples vistas: eso
requiere GPU, poses de cámara (COLMAP) y decenas de minutos. Por eso la parte de
atrás de la cabeza no existe, y el rango de giro útil es de ±40°.

### 5.2 Construcción (`build_head_splats`)
1. **Malla 3D:** `mesh3d` devuelve los 478 puntos `(x·w, y·h, z·w)`. MediaPipe
   da `z` en la misma escala que `x`, con valores menores más cerca de la cámara.
2. **Triangulación:** Delaunay propio (Fortune) sobre `(x, y)`, elevado a 3D.
3. **Cara (~37–40 mil gaussianas, proporcional al área del contorno facial; la foto se procesa hasta 1024 px):** muestreo **estratificado** por triángulo
   (cantidad ∝ área **3D**, subgrilla con jitter dentro de cada triángulo). Cada
   gaussiana es un **disco tangente** con
   `Σ = R·diag(s², s², (0.4s)²)·Rᵀ`, `R = [t₁ t₂ n]` (marco ortonormal desde la
   normal del triángulo) y `s = √(área/muestras)`. El color se lee de la foto
   con interpolación bilineal.
4. **Entorno (~50 000; grilla fina hasta 0.9 anchos de cara, 3× más gruesa lejos):** el resto de la foto como **relieve**. Su profundidad va
   de `z_fondo` a la profundidad del **vértice del contorno facial más cercano**:
   `z = z_fondo + (z_borde − z_fondo)·exp(−d / 0.4·ancho_cara)`. Así el pelo, las
   orejas y el cuello "salen" hacia la cara en vez de quedar en un plano. También
   se coloca detrás de la cara como respaldo ante cualquier hueco.
5. **Barba 3D:**
   - las raíces se toman de `beard_mask(estilo)`, sin labios (contorno exterior
     de labios de MediaPipe dilatado 5 %);
   - se elevan a 3D con coordenadas baricéntricas sobre la malla;
   - cada hebra son 3 gaussianas alargadas a lo largo de
     `d = normalizar(0.55·n + ŷ + ruido)`, con escalas `(L/3·0.6, w, w)`;
   - sobre el labio superior las hebras son más cortas y van hacia los lados
     (bigote), en vez de colgar sobre los dientes.
6. **Normalización:** `A = diag(1, −1, −1)/ancho_cara` (centrado, y hacia
   arriba, mirando a la cámara). `Σ' = A Σ Aᵀ`. Se envían 13 `float32` por
   gaussiana: posición, covarianza (6, triángulo superior), RGB y alpha.
   Ejemplo: 54 741 gaussianas son 2.8 MB y se construyen en ~1 s en el servidor.

### 5.3 Render (`frontend/js/splat3d.js`)
- **Proyección EWA**, por gaussiana en el vertex shader:
  ```
  J = [[f/−z, 0, f·x/z²], [0, f/−z, f·y/z²], [0, 0, 0]]   (jacobiana de la proyección)
  Σ₂D = (J W) Σ (J W)ᵀ + 0.3·I                           (W = rotación de la vista; 0.3 = low-pass)
  ```
- **Cuádrica de pantalla:** autovalores y autovectores de `Σ₂D` en forma cerrada;
  se dibuja un quad de ±3σ orientado según los autovectores.
- **Fragment shader:** `α = a·exp(−½ r²)`, con `r` en unidades de σ (exacto para la
  gaussiana 2D). Descarte si r > 3 o α < 0.004.
- **Composición:** las gaussianas se ordenan **de atrás hacia adelante** con un
  **counting sort** de 16 bits sobre la profundidad de vista (O(N); se recalcula
  solo si cambia la cámara). Se mezclan con `SRC_ALPHA, ONE_MINUS_SRC_ALPHA`, que
  es el compositing `C = Σ cᵢαᵢ Πⱼ<ᵢ(1 − αⱼ)` de 3DGS.
- **Cámara orbital:** arrastrar para rotar, rueda para zoom, auto-rotación
  sinusoidal.
- **"Show individual splats":** un uniform `u_splatScale = 0.32` encoge la huella
  de cada gaussiana en pantalla, y se ven las ~55 000 manchas una por una (discos
  sobre la piel, hebras alargadas en la barba). Es útil para explicar la técnica
  en la demo.

### 5.4 Exportación `.ply` estándar
`to_ply` escribe el formato de 3DGS de referencia, compatible con visores como
SuperSplat:
- por gaussiana, `x y z nx ny nz f_dc_0..2 opacity scale_0..2 rot_0..3` en
  binario little-endian;
- **covarianza → escala + rotación:** `Σ = V Λ Vᵀ` (eigh), se corrige el signo
  para que `det V = +1`, `scale = log √λ` y `rot` es el cuaternión `(w, x, y, z)`
  de `V`;
- **color → armónicos esféricos de grado 0:** `f_dc = (rgb − 0.5)/C₀`, con
  `C₀ = 0.2821`;
- **opacidad → logit:** `log(α/(1 − α))`.

Un test reconstruye `Σ = R·diag(e^{2s})·Rᵀ` desde el archivo y verifica que
coincide con la covarianza original. Botón **Download .ply** en la interfaz.

### 5.5 Resultados
- 3 retratos × 3 estilos (`full`, `goatee`, `stubble`), con capturas desde 4 vistas
  y GIF giratorio de 24 cuadros (`docs/captures/p5_mirror/`).
- Iteraciones de calidad, cada una vista en capturas:

| Iteración | Problema visto | Arreglo |
|---|---|---|
| 1 | Puntos blancos en la cara | Muestreo estratificado + discos más grandes + fondo detrás de la cara |
| 2 | Franja blanca sobre la frente, pelo plano | Profundidad del entorno desde el vértice de contorno más cercano, caída 0.4·ancho |
| 3 | Hebras del bigote colgando sobre los dientes | Labios excluidos, bigote corto y hacia los lados |
| 4 | Puntitos en la mejilla lejana, nariz y frente al girar | Cantidad y tamaño de gaussianas por **área 3D** del triángulo (antes 2D proyectada): las zonas inclinadas tenían gaussianas demasiado chicas para su superficie real |

- **Limitaciones:**
  - sin parte trasera de la cabeza;
  - en giros fuertes aparecen estiramientos donde un triángulo cruza una
    discontinuidad de profundidad (borde de nariz u oreja);
  - el pelo de la cabeza es parte del relieve de la foto, no hebras 3D.

---

## 6. Tests

`backend/tests/test_splatting_physics.py` cubre:
- más gaussianas dan mayor PSNR;
- la física se asienta quieta y se atrasa al mover la raíz;
- la densidad controla el render;
- el corte barre la cápsula y genera escombros que caen y desaparecen;
- el puntaje premia afeitar fuera del objetivo y empieza en 0;
- con la máquina apagada no se corta nada;
- `build_head_splats` da covarianzas PSD, valores finitos y colores en [0, 1];
- el `.ply` exportado reconstruye exactamente la covarianza original;
- el juego no se rompe si la cara queda fuera del cuadro;
- el render de pelos con gaussianas cubre el pelo y nada más.

`backend/tests/test_api.py` cubre los endpoints nuevos: `/gaussians` (render,
validación de `count`), `/live` en modo `physics`, `/game/start`, `/game/frame` y
`/head3d` (422 sin cara, 400 con estilo inválido).

**Resultado: 33 tests en verde.**

Además hay una prueba de punta a punta en Chrome headless controlado por el
protocolo DevTools:
- cámara simulada con un video `.y4m` del retrato en movimiento;
- subida de archivos con `DOM.setFileInputFiles`;
- mouse simulado para afeitar;
- WebGL por SwiftShader.

Las cuatro secciones funcionan **sin errores de consola**.
