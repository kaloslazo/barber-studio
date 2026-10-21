# 3D Mirror — Qué es hoy y cómo seguir

> BarberStudio · CS4016 Computación Gráfica · UTEC
>
> El *3D Mirror* convierte **una foto** en una **cabeza 3D hecha de gaussianas**
> que se puede girar, con la barba en volumen. Hoy es una **prueba de concepto
> (PoC) centrada en la cara**. Este documento explica el flujo actual (qué entra,
> qué sale y de dónde sale cada cosa), qué limita la calidad y la hoja de ruta para
> llegar a una cabeza completa y, después, a un avatar en vivo.
>
> Detalle técnico de la implementación actual: [`features_technical.md`](features_technical.md) §5.

---

## 1. La idea en una frase

Cada punto de la cabeza es una **mancha 3D (gaussiana)**: un pequeño elipsoide
borroso con posición, forma, orientación, color y transparencia. Con decenas de
miles de manchas se forma la cabeza, y para verla desde cualquier ángulo se
**proyectan** a la pantalla y se mezclan de la más lejana a la más cercana. Esa es
la técnica *3D Gaussian Splatting*.

---

## 2. Flujo actual (PoC)

```
 Tu foto
   │
   ├─► 1. Puntos 3D de la cara (MediaPipe) ─► 2. Malla de triángulos 3D (Delaunay)
   │                                               │
   ├─► 3. (opcional) barba realista pintada en la foto
   │                                               │
   │      4. Cara: ~40 000 discos 3D pegados a la malla, color de la foto
   │      5. Barba: hasta 6 000 pelos 3D (3 gaussianas c/u), color de la barba real
   │      6. Resto de la foto (pelo, orejas, fondo): "relieve" detrás de la cara
   │                                               │
   └──────────────────────────────► 7. Archivo de ~100 000 gaussianas (~5 MB)
                                                   │
                                     8. Visor WebGL propio: proyectar, ordenar, mezclar
                                                   │
                                     9. Imagen 3D que gira  (+ descarga .ply estándar)
```

| Paso | Entra | Sale | ¿De dónde sale? |
|---|---|---|---|
| 1. Puntos 3D | La foto (hasta 1024 px de ancho) | 478 puntos con **profundidad** | Modelo **MediaPipe Face Landmarker** (Google, preentrenado): estima x, y y qué tan adelante está cada punto |
| 2. Malla | Los 478 puntos | Triángulos 3D de la cara | **Nuestro** Delaunay (algoritmo de Fortune) sobre (x, y), elevado a 3D con la profundidad |
| 3. Barba realista | Foto + estilo | La foto con barba | El **mismo pipeline de barba del modo foto** |
| 4. Cara | Malla + foto | ~37–40 mil discos tangentes a la piel | **Nuestro** código: muestreo estratificado por área 3D de cada triángulo; color leído de la foto con interpolación bilineal |
| 5. Barba 3D | Zona de barba + malla + foto con barba | Pelos 3D finos y semitransparentes | **Nuestro** código: raíces sobre la piel (coordenadas baricéntricas), crecen hacia afuera y hacia abajo; color de la barba realista |
| 6. Relieve | El resto de la foto | ~50 mil discos: finos cerca de la cara, gruesos lejos | **Nuestro** código: profundidad que "sale" hacia el contorno de la cara |
| 7. Empaquetar | Todas las gaussianas | 13 números por gaussiana (posición, covarianza, color, opacidad) | Servidor (`/api/head3d`) |
| 8. Visor | El archivo + el ángulo de cámara | La imagen en pantalla | **Nuestro** visor WebGL2: proyección EWA `Σ' = J W Σ Wᵀ Jᵀ`, counting sort por profundidad, mezcla alfa |
| 9. Export | Las gaussianas | `.ply` estándar de 3DGS | **Nuestro** exportador (escalas + cuaternión + armónicos esféricos de grado 0) |

---

## 3. Por qué hoy se ve como se ve (límites honestos)

| Lo que se nota | Causa | Se arregla en |
|---|---|---|
| Solo la **cara** tiene volumen real; el pelo y las orejas parecen un "póster" curvado | MediaPipe solo da la malla de la cara (de la frente al mentón) | Fase C (cabeza completa) |
| **No hay nuca** ni parte de atrás, y girar más de ~40° muestra huecos | Una sola foto: lo que la cámara no vio no existe | Fase B (varias vistas) |
| El fondo se ve borroso | Se dibuja con gaussianas grandes a propósito, para ahorrar | Opcional: más gaussianas en el fondo |
| Algunas líneas o estiramientos en el borde de la nariz y las orejas | Triángulos que cruzan un salto de profundidad | Fase B (optimización con varias vistas) |
| Los colores son los de la foto, con la luz "pegada" | No modelamos la iluminación | Fase B (armónicos esféricos de mayor grado) |

**Mejoras aplicadas hoy (21-oct):**
- se procesa a 1024 px (antes 640);
- la cantidad de gaussianas de la cara es proporcional a su tamaño (~40 mil);
- el fondo es fino cerca de la cara y grueso lejos;
- la cámara arranca más cerca;
- los pelos 3D son finos, semitransparentes y del color de la barba real (antes
  parecían pinceladas).

El modo *Show individual splats* encoge cada gaussiana a propósito para mostrarlas
sueltas: es una vista didáctica, no la calidad final.

---

## 4. Hoja de ruta

### Fase A — PoC de una foto ✅ (hecha)
Lo descrito arriba. Sirve para explicar la técnica y mostrar la barba en volumen.

### Fase B — Varias vistas: "escaneo 3D" de la cabeza
**Idea:** reutilizar el escaneo de la pestaña *Transfering hair*, que ya guía al
usuario a girar la cabeza 180° y captura ~7 ángulos.

| Paso | Entra | Sale | Cómo |
|---|---|---|---|
| B1. Captura | Video o 7 fotos girando la cabeza | Fotos + ángulo estimado de cada una | Ya existe (`transfer_scan` / `transfer_pose`) |
| B2. Poses de cámara | Landmarks 3D de MediaPipe en cada foto | Rotación y traslación de la cabeza por vista | Alineación de Procrustes entre las mallas 3D de cada vista (no hace falta COLMAP: la cara misma es el "patrón") |
| B3. Inicialización | Malla de la vista frontal | Gaussianas iniciales (como en la Fase A) | Código actual |
| B4. **Optimización tipo 3DGS** | Gaussianas + todas las vistas | Gaussianas ajustadas: posición, forma, color y opacidad | Render **diferenciable**: se dibuja cada vista, se compara con la foto (L1 + SSIM) y se corrige cada gaussiana por descenso de gradiente. Es lo mismo que ya hicimos en 2D en P3, pero proyectando en 3D |
| B5. Densificar y podar | Gaussianas con mucho error o muy grandes | Se dividen o clonan; las transparentes se eliminan | Como en el paper original de 3DGS |

**Opciones para B4:**
1. **NumPy en CPU** (coherente con "desde cero"): factible con ~20–50 mil gaussianas
   e imágenes de 256 px, en minutos. El gradiente de la composición alfa ordenada
   es más complejo que en 2D, pero acotado.
2. **PyTorch + `gsplat` en Colab con GPU** (el notebook de Colab ya existe): calidad
   de paper en ~10–20 min por cabeza. Se usaría solo para entrenar; el visor sigue
   siendo el nuestro.

**Cómo medimos el éxito:** PSNR o SSIM en una vista que **no** se usó para entrenar
(held-out), y comparación visual girando a ±60°.

### Fase C — Cabeza completa
- **Cráneo y nuca:** la malla de la cara se completa con una cabeza genérica
  ajustada a los puntos (por ejemplo, un elipsoide deformable o un modelo
  paramétrico de cabeza). Las vistas laterales de la Fase B le dan color.
- **Pelo como hebras 3D:** el mismo enfoque que la barba (cadenas de gaussianas
  alargadas), creciendo desde el cuero cabelludo y con la dirección estimada de la
  silueta del pelo en cada vista. Conecta con *Transfering hair*.
- **Orejas y cuello:** gaussianas libres, inicializadas por el relieve actual y
  luego optimizadas.

### Fase D — Avatar 3D en vivo (el gran salto)
**Idea:** que las gaussianas **sigan tu cara en tiempo real** con la webcam.
1. Cada gaussiana de la cara se "pega" a un triángulo de la malla de MediaPipe
   con coordenadas baricéntricas y un desplazamiento en la normal. Es lo mismo que
   ya hacemos en 2D con el `LiveAnchor` y las raíces de la física.
2. En cada cuadro de la webcam, MediaPipe da la malla 3D nueva, y las gaussianas
   se mueven y rotan con su triángulo. No hay que re-entrenar nada.
3. La barba 3D usa la **física de Verlet de P2, ahora en 3D**: los pelos se
   balancean con volumen real.
4. El visor dibuja desde la cámara virtual que el usuario elija: puede verse de
   costado mientras mira de frente a la cámara.

Esto es lo que hacen trabajos de investigación como *GaussianAvatars* (CVPR 2024),
con una versión simplificada sobre la malla de MediaPipe.

### Fase E — Probador 3D de estilos
- **Biblioteca de barbas como assets de gaussianas** (`.ply`), intercambiables
  sobre cualquier cabeza, porque están ancladas a la malla estándar.
- Comparar estilos lado a lado, girando.
- Exportar el resultado para verlo en cualquier visor de 3DGS (ya existe la
  exportación `.ply`).

---

## 4b. Estado: B + D implementados como prueba (pestaña *3D Lab (beta)*)

Están separados del resto de la app: pestaña propia, `backend/app/core/lab/`
(`avatar.py`, `session.py`), endpoints `/api/lab/build` y `/api/lab/mesh`, y
`frontend/js/lab.js`. El *3D Mirror* y las demás funciones no se modificaron.

**Cómo usarlo:** *Start camera* → *Scan (7 s)* (mirar de frente, girar a la
izquierda y a la derecha según el aviso; también se pueden subir fotos) → elegir
barba → *Build head* (~15–20 s) → *Live avatar*. Los botones *Front / 3/4 / Side*
o el arrastre del mouse permiten verte de costado mientras miras a la cámara.

**Qué hace (flujo):**

| Paso | Entra | Sale | Cómo |
|---|---|---|---|
| 1. Escaneo | 8 cuadros de la webcam girando la cabeza | 8 fotos (1024 px) | Captura guiada en el navegador |
| 2. Malla por vista | Cada foto | 478 puntos 3D por vista | MediaPipe (modo imagen) |
| 3. Referencia | Las mallas | La vista más frontal | Menor desvío nariz–centro de la cara |
| 4. Gaussianas ancladas | Malla de referencia | ~40 mil gaussianas de cara (+ hebras de barba), cada una guardada como **triángulo + baricéntricas + desplazamiento y covarianza en el marco local del triángulo** | `AnchoredHead` |
| 5. **Fusión multivista (B)** | Gaussianas + todas las vistas | Un color por gaussiana | Cada gaussiana se ubica en cada foto **a través de la malla de esa foto**; promedio ponderado por cuánto mira esa superficie a la cámara (`n_z²`) |
| 6. **Optimización (B)** | Colores fusionados + vistas | Colores ajustados | Render 2D normalizado de las gaussianas en cada vista vs. la foto (solo píxeles de cara); **Adam, 30 iteraciones** sobre todas las vistas de entrenamiento |
| 7. Barba | Foto de referencia con barba realista | Textura de barba en la piel + hebras 3D | Pipeline del modo foto + hebras ancladas |
| 8. **Avatar en vivo (D)** | Webcam (480 px) | Malla 3D filtrada (One-Euro) | `/api/lab/mesh` (~5 KB por cuadro) |
| 9. Deformación en el navegador | Malla nueva + modelo anclado | Posición y covarianza de cada gaussiana | `lab.js`: `p = Σ wᵢ·vᵢ + R·o·s`, `Σ = R·C·Rᵀ·s²` por gaussiana, con el marco `R` de su triángulo |
| 10. Render | Gaussianas | Imagen 3D | El mismo visor WebGL de 3D Mirror (subclase, sin modificarlo) |

**Medición** (Chrome headless, cámara simulada; una vista se excluye del entrenamiento):

| PSNR (dB) | Vistas de entrenamiento | Vista excluida |
|---|---|---|
| Color de una sola vista | 29.1–30.5 | 28.3–30.4 |
| Fusión multivista | 30.2–30.3 | 29.7–30.3 |
| **Fusión + optimización** | **35.0–35.1** | **34.7–35.0** |

La optimización mejora unos **5 dB también en la vista que no vio**: generaliza, no
memoriza. Con la cámara simulada las "vistas" son el mismo retrato desplazado (no
hay giros 3D reales), así que la ganancia de la fusión multivista es pequeña. Con
una webcam y giros reales, la fusión debería aportar más en las mejillas y los
laterales, pero **todavía no está medido con un escaneo real**.

**Pruebas:** tests de que las gaussianas ancladas siguen una rotación y
traslación rígida de la malla (posición y covarianza exactas) y de los endpoints.
De punta a punta en Chrome: escaneo → build → avatar en vivo de frente y de
costado, sin errores de consola (`docs/captures/lab/`).

**Limitaciones de la versión beta:**
- Solo la **cara** (malla de MediaPipe): sin pelo, orejas ni nuca. Es la fase C.
- La geometría viene de MediaPipe. Se optimiza el **color**, no la posición ni la
  forma de las gaussianas (el 3DGS completo optimiza todo).
- La oclusión entre vistas se aproxima con la orientación de la superficie, sin
  z-buffer.
- La barba 3D del avatar es rígida respecto de la cara (aún sin la física de P2 en
  3D).
- Fps del avatar: en Chrome headless (render por software) da 1–3 fps; en un
  navegador con GPU depende de la máquina y **no está medido**.

## 5. Resumen de esfuerzo y riesgo

| Fase | Qué agrega | Esfuerzo | GPU | Riesgo |
|---|---|---|---|---|
| A ✅ | Cara 3D desde una foto | — | No | — |
| B | Vistas laterales reales, sin huecos hasta ±90° | Medio–alto | Opcional (Colab) | Medio: poses y gradientes de la composición |
| C | Cabeza completa con pelo 3D | Alto | Recomendable | Alto: pelo y nuca |
| D | Avatar que te sigue en vivo + barba 3D con física | Alto | No para el render | Medio: rendimiento del visor |
| E | Biblioteca de estilos 3D intercambiables | Medio (después de D) | No | Bajo |

**Recomendación:** para el curso, **B (con la opción NumPy o Colab) + D en su
versión básica** dan el mayor salto visible. Se puede decir "escaneamos tu cabeza
con la webcam y la animamos en vivo con Gaussian Splatting", reutilizando casi todo
lo que ya existe (escaneo, malla, anclaje baricéntrico, física, visor).

---

## 6. Temas del curso que toca

| Tema | Dónde |
|---|---|
| 6.1.2 Representación | Gaussianas 3D como primitiva gráfica alternativa a la malla |
| 6.1.3 Muestreo | Muestreo estratificado de la superficie, bilineal para el color |
| 6.1.4 Interpolación | Baricéntricas (anclaje a la malla), Verlet (fase D) |
| 6.2.2 Convex hull | Contorno de la cara para el relieve |
| 6.2.5 Delaunay | Malla 3D de la cara (Fortune) |
| Proyección y cámaras | Matriz de vista, perspectiva, jacobiana EWA, orden por profundidad |
| Optimización | Descenso de gradiente sobre el render (fase B), como en P3 |
