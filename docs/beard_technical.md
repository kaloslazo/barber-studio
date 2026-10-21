# Pipeline de barba — Documento técnico

> BarberStudio · CS4016 Computación Gráfica · UTEC
>
> Qué hace cada pieza, **dónde está en el código**, **cómo** funciona y **por qué**
> se eligió así. Versión simple: [`beard_overview.md`](beard_overview.md).
> Implementaciones propias vs. librería: [`implementaciones_desde_cero.md`](implementaciones_desde_cero.md).
> Opciones nuevas (física, gaussianas, juego, 3D): [`features_technical.md`](features_technical.md).
>
> Refleja el estado del código en el *working tree* actual (incluye los cambios
> del modo en vivo aún no commiteados).

---

## 0. Mapa de archivos

| Pieza | Archivo | Función principal |
|---|---|---|
| Orquestación | `backend/app/core/pipeline.py` | `StylePipeline.apply_beard` |
| Endpoints | `backend/app/api/routes.py` | `POST /api/beard` (foto), `POST /api/live` (cámara) |
| Detección de cara | `backend/app/core/detection/face_detector.py` | `FaceDetector.largest_face` (Haar) |
| Landmarks | `backend/app/core/detection/landmarks.py` | `LandmarkDetector.landmarks` |
| Filtro temporal | `backend/app/core/detection/one_euro.py` | `OneEuroFilter` |
| Color de pelo | `backend/app/core/segmentation/hair_region.py` | `provisional_hair_mask` |
| Render de barba | `backend/app/core/compositing/beard.py` | `apply_real_beard`, `beard_mask`, `LiveAnchor` |
| Feather | `backend/app/core/compositing/alpha.py` | `organic_feather` |
| Delaunay | `backend/app/core/geometry/delaunay_fortune.py` | `delaunay_triangles` (Fortune, propio) |
| Warp | `backend/app/core/geometry/warp.py` | `warp_template` (afín por triángulo, propio) |
| Plantillas | `backend/app/assets/beards/*.npz` | 10 barbas reales |
| Cosecha de plantillas | `backend/training/harvest_beards.py` | Script offline sobre CelebAMask-HQ |

Flujo de llamadas (foto):

```
routes.beard ─► StylePipeline.apply_beard
                 ├─ FaceDetector.largest_face          (1)
                 ├─ LandmarkDetector.landmarks         (2)
                 ├─ hair_mask → color mediano YCrCb    (3)
                 └─ apply_real_beard
                     ├─ elegir plantilla               (4)
                     ├─ _extended_points + Delaunay    (5)
                     ├─ warp_template                  (5)
                     ├─ _recolor_beard                 (3→5)
                     ├─ beard_mask + recorte al hull   (6)
                     ├─ organic_feather                (6)
                     └─ capas: cuerpo, hebras, detalle (7)
```

---

## 1. Detección de cara — Haar cascade

**Qué:** `cv2.CascadeClassifier` con `haarcascade_frontalface_default.xml`
(`scaleFactor=1.1`, `minNeighbors=5`, `minSize=80×80`). Nos quedamos con la cara de
mayor área.

**Cómo funciona:** un clasificador en cascada (Viola-Jones) evalúa *features* de
Haar (diferencias de suma de intensidad entre rectángulos, calculadas en O(1) con
la imagen integral) en una ventana deslizante a varias escalas. Cada etapa descarta
rápido las ventanas que claramente no son cara.

**Por qué:** viene con OpenCV, no requiere pesos extra y es rápido. El recuadro
solo se usa para ubicar la zona del pelo (paso 3).

**Limitación medida:** solo detecta caras **frontales**. En una sesión de cámara
falló en **822 de 2695 frames (30 %)** al girar la cabeza. Por eso **el modo en
vivo ya no lo usa** (ver §9).

> El plan original mencionaba YOLO para detectar la cara (6.4.5). En el código
> actual la cara la detecta Haar (foto) o directamente MediaPipe (vivo).

---

## 2. Landmarks — MediaPipe Face Landmarker → 68 puntos

**Qué:** el modelo preentrenado `models/face_landmarker.task` (Google MediaPipe,
API *Tasks*) devuelve **478 puntos** normalizados `(x, y) ∈ [0,1]` (468 de malla
facial + 10 de iris). **No lo entrenamos**: es una entrada de datos.

**Conversión a 68 (formato iBUG):**
- **Mandíbula (0–16):** tomamos los 23 puntos del contorno inferior de MediaPipe
  (`MP_JAW_ARC`) y los **re-muestreamos por longitud de arco** a 17 puntos
  equiespaciados (`_resample_polyline`: longitud acumulada + `np.interp`). Así la
  mandíbula queda distribuida uniforme aunque MediaPipe no tenga 17 puntos ahí.
- **Resto (17–67):** cejas, nariz, ojos y boca salen por una tabla de índices
  (`MP_TO_68`), 51 puntos.

**Por qué 68 y no 478:** todo el resto (máscaras, plantillas cosechadas, tabla de
estilos) se diseñó sobre el estándar iBUG de 68 puntos. Los 478 se reducen a una
convención estable y conocida.

**Fallback:** si MediaPipe no está, se usa LBF (`lbfmodel.yaml`) anclado a
detecciones YuNet. Hoy `models/yunet.onnx` **no existe** en la máquina, así que
este respaldo devuelve "sin cara" en vez de fallar.

**Modo de ejecución:**
- Foto: `RunningMode.IMAGE` (cada imagen independiente).
- Vivo: `RunningMode.VIDEO` con `detect_for_video(img, timestamp_ms)` →
  **tracking** usando el frame anterior (ver §9).

---

## 3. Color del pelo

**Qué:** `pipeline.hair_mask` intenta usar un segmentador YOLO (`hair_best.pt`).
Esos pesos **no están** en `models/`, así que en la práctica se usa la máscara
heurística `provisional_hair_mask`:

1. **Cúpula:** elipse centrada sobre el recuadro de la cara
   (`ejes = 1.15·ancho × 1.75·alto`).
2. **Píxeles oscuros:** umbral de **Otsu** (invertido) sobre el gris de la zona de
   la cabeza. Otsu elige el umbral que maximiza la varianza entre las dos clases
   (pelo oscuro vs. piel/fondo).
3. `cúpula ∧ oscuros` + apertura y cierre morfológicos.

Del resultado tomamos la **mediana BGR** (robusta a outliers) y la pasamos a
**YCrCb** (Y = luminancia, Cr/Cb = croma). El croma se limita a tonos naturales
(`Cr ≥ 136`, `Cb ≤ 121`, castaño oscuro): sin esto, con un fondo azul oscuro la barba salía azul. Un primer intento forzaba gris neutro (`128/128`) y la barba se veía gris y falsa. En vivo se suaviza en el tiempo:
`color_t = 0.9·color_{t−1} + 0.1·medido_t`, porque la cúpula depende de un
recuadro que salta entre frames.

**Por qué YCrCb:** separa brillo de color, así se puede desplazar el tono de la
barba de forma independiente en luminancia y croma (§5.4).

---

## 4. Plantillas de barba real (dataset)

**Origen:** `training/harvest_beards.py` corre **una vez, offline**, sobre
**CelebAMask-HQ**:

1. Filtra fotos por atributos: `Male`, sin sombrero, no borrosas, y clasifica en
   `goatee` / `mustache` / `stubble` (`5_o_Clock_Shadow`) / `full` (`No_Beard = -1`).
2. Detecta los 68 landmarks de cada foto.
3. Calcula un **alpha de pelo** por píxel: pelo = "más oscuro que su entorno
   local": `clip((Y_local − 10 − Y) / 14, 0, 1)`, con `Y_local` un desenfoque
   gaussiano grande de la luminancia; limitado a cara y cuello usando las máscaras
   de partes del dataset.
4. Descarta plantillas **asimétricas** (> 25 % de diferencia izquierda/derecha),
   con poca cobertura o poco contraste.
5. Guarda un `.npz` con: recorte **BGRA**, sus **68 puntos** y el **tono de piel**
   (YCrCb).

**En uso:** 10 plantillas → `full` 2, `goatee` 3, `mustache` 1, `stubble` 4.

**Selección en runtime:** dentro del estilo pedido, se elige la plantilla cuyo
tono de piel tenga el croma más cercano al del usuario:

```
mejor = argmin  (Cr_t − Cr_u)² + (Cb_t − Cb_u)²
```

donde el tono del usuario se muestrea en 3 parches del dorso de la nariz
(`_target_skin_ycrcb`).

---

## 5. Malla y warp (la plantilla se adapta a tu cara)

### 5.1 Puntos extendidos (83)
`_extended_points` agrega **15 puntos virtuales** bajo la mandíbula (los puntos
1–15 desplazados hacia abajo un 18 % de la altura de la cara). Sin ellos, la malla
terminaría en la línea de la mandíbula y la barba bajo el mentón quedaría fuera.
Total: **68 + 15 = 83 vértices**.

### 5.2 Triangulación de Delaunay (propia, Fortune)
`delaunay_fortune.delaunay_triangles` (O(n log n), algoritmo de barrido). Produce
la triangulación donde **ningún punto cae dentro del círculo circunscrito de
ningún triángulo**, lo que maximiza el ángulo mínimo y evita triángulos "aguja"
que deformarían mal la textura. Detalle del algoritmo en
`implementaciones_desde_cero.md`.

### 5.3 Warp afín por triángulo (propio)
`warp.warp_template(plantilla, puntos_src, puntos_dst, triángulos, …)`. Por cada
triángulo:

1. **Afín inversa** destino → origen, resolviendo un sistema 3×3
   (`u = a·x + b·y + c`, igual para `v`). Es inversa para recorrer los píxeles de
   **salida** y preguntar "¿de dónde leo?" (sin huecos).
2. **Rasterización** con test de **coordenadas baricéntricas**: un píxel `(x, y)`
   está dentro si sus pesos `(λ₁, λ₂, λ₃)` son todos ≥ 0.
3. **Muestreo bilineal** propio:
   `v = (1−wx)(1−wy)·P₀₀ + wx(1−wy)·P₁₀ + (1−wx)wy·P₀₁ + wx·wy·P₁₁`.

Solo se procesan los triángulos cerca de la región de barba (`focus_bbox`).

### 5.4 Recoloreo al tono del pelo
`_recolor_beard`: en YCrCb, se desplaza **toda la nube de color** de la barba
warpeada hacia el color del pelo:

```
objetivo = color_pelo  con  Y ← 0.88 · Y      (la barba lee un poco más oscura)
desplazamiento = objetivo − media(barba visible)
barba ← barba + desplazamiento
```

Un **desplazamiento constante** (no un reemplazo) conserva la variación interna,
es decir, los pelos. Sin esto, un rubio recibía barba negra (las plantillas son de
barbas oscuras).

---

## 6. Máscara de la región (`beard_mask`) y bordes

### 6.1 Forma por estilo
Todas se construyen con polígonos y elipses sobre los 68 puntos:

| Estilo | Construcción |
|---|---|
| `full` | Puntos de mandíbula 0–16 **expandidos 4 %** hacia afuera del centroide + "línea superior" (comisuras, punto subnasal 33, puntos intermedios). Menos la elipse de la boca. |
| `goatee` | Comisuras 48/54 ensanchadas 18 % + mentón (mandíbula 5–11, expandida 3 %). Menos elipse de boca, más la banda del bigote. |
| `mustache` | **Banda en arco**: curva de Bézier cuadrática comisura → subnasal → comisura, rellenada con círculos cuyo radio sigue `0.35 + 0.45·sin(π·t)` (más grueso al centro). |
| `stubble` | Misma región que `full`. |

En todos los estilos:
- se **restan los labios** (polígono 48–59 dilatado 5×5),
- se aplica **cierre morfológico** 5×5 para tapar huecos,
- la región se **intersecta con el convex hull** de los 68 puntos, erosionado un
  1 % del ancho de cara. Esto evita que la barba se salga de la cara (antes
  aparecían manchas sobre la pared).

### 6.2 Feather orgánico
`alpha.organic_feather`: un borde suave con algo de irregularidad.

```
d(p) = distancia al borde, medida hacia adentro (distance transform)
α(p) = clip( (d − ruido·feather·0.6) / feather , 0, 1 ) · clip(d/2, 0, 1)
feather = clamp(ancho_cara / 14, 6, 30) px
```

El ruido hace que el borde no sea una línea perfecta. El último factor fuerza
**α = 0 fuera de la máscara**. Antes no estaba, y el feather "goteaba" alpha
de hasta 0.30 sobre el **59 %** del fondo (manchas negras en la pared).

---

## 7. Composición en capas

Notación: `ρ` = **densidad** (slider *Intensity*, 0–1), `α_r` = alpha de la región
(§6.2), `c_b` = color de la barba (media de la plantilla recoloreada).

### Capa 1 — Cuerpo (multiply)
```
α_cuerpo = α_r · (0.78 + 0.22·veta) · fuerza_estilo · ρ
color    = c_b · (0.90 + 0.20·grano)
salida   = base·(1−α) + base·mult·α ,   mult = 0.35 + 0.65·(color/255)
```
- **Multiply** (no "pegar encima"): la luz y las sombras de la piel siguen
  visibles a través de la barba → volumen, no calcomanía. El *floor* 0.35 evita
  que la zona se vuelva negra.
- `veta`: ruido **anisotrópico**, ruido blanco desenfocado con núcleos de línea
  orientados según la dirección local del pelo (12 orientaciones mezcladas).
- `grano`: ruido gaussiano σ = 1.5.
- `fuerza_estilo`: full 0.55, goatee 0.55, mustache 0.50, stubble 0.20.

### Capa 2 — Hebras dibujadas
- **Campo de dirección** (`_direction_maps`): hacia abajo y afuera desde el centro
  de la cara; en la banda del bigote, horizontal hacia cada lado.
- **Cantidad:** `N = 6 %` de los píxeles de la región (stubble 2 %) · `ρ`, máximo
  9000. **Así se sube o se baja la densidad de pelos.**
- Cada hebra es una **Bézier cuadrática**
  `B(t) = (1−t)²p₀ + 2(1−t)t·p₁ + t²p₂`, con:
  - largo = 4.5–10 % del ancho de cara (stubble 1.2–2.5 %),
  - curvatura aleatoria (`curl ∈ [−0.7, 0.7]`),
  - color = `c_b · jitter` (jitter 0.72–1.08), alpha 150–235, grosor 1–2 px.
- Se dibujan con antialiasing, se suavizan con un gaussiano 3×3 y se componen con
  `α_hebras · α_r · 0.55`.

### Capa 3 — Detalle real (transferencia de gradientes)
```
detalle = plantilla − Gauss(plantilla, σ = ancho_cara/70)      (alta frecuencia)
salida += detalle · α_r · α_plantilla · ρ · 1.3
```
Solo se transfiere la **alta frecuencia** (los pelos), no el brillo ni el color
de la plantilla. Un Poisson blend completo igualaría el brillo con la piel del
borde y aclararía la barba.

### Stubble — reemplaza las capas 2 y 3
```
fino   = ruido gaussiano σ = 0.45, estandarizado (z-score)
umbral = 0.95 − 1.2·ρ − 0.25·(densidad_local − 0.5)
puntos = clip((fino − umbral)·1.1, 0, 1)
α      = α_r · puntos · 0.5 ,   color = 0.85·c_b
```
Es un grano de ~1 px, denso y de bajo contraste ("five o'clock shadow"). Subir
`ρ` **baja el umbral** → aparecen más puntos.

---

## 8. Densidad: resumen de todas las perillas

| Perilla | Dónde | Efecto |
|---|---|---|
| `ρ` (slider Intensity) | todas las capas | Escala el alpha del cuerpo, el **número** de hebras, el peso del detalle y el umbral del stubble |
| `fuerza_estilo` | Capa 1 | Base de oscurecimiento por estilo |
| Fracción de hebras (6 % / 2 %; vivo 10 % / 4 %) | Capa 2 | Hebras por píxel de región |
| `strand_gain` (0.55 foto, 0.8 vivo) | Capa 2 | Opacidad de las hebras |
| `detail_gain` (1.3 / 1.0) | Capa 3 | Cuánta textura real se inyecta |
| *floor* del multiply (0.35) | Capa 1 | Oscurecimiento máximo |
| Umbral del stubble | Stubble | Cantidad de puntos |

---

## 9. Modo en vivo (`/api/live`, Fase 5 del plan)

El frontend captura la webcam, la espeja, la escala a 640 px y la envía como JPEG,
sin pausa entre frames. El servidor responde JPEG. Mide **~8 fps** (~119 ms por
frame en el servidor). Hubo una versión de ~12 fps sin la textura de barba
real, pero se veía como una sombra lisa y gris, así que se priorizó el realismo.

| Problema | Causa medida | Solución | Archivo |
|---|---|---|---|
| Jitter de landmarks | `IMAGE` re-detecta desde cero cada frame | `RunningMode.VIDEO` (tracking) | `landmarks.py` |
| Temblor residual / lag | — | **Filtro One-Euro** (`min_cutoff=3.0`, `beta=0.3`) | `one_euro.py` |
| La barba desaparece al girar | Haar falla en el 30 % de los frames | Solo MediaPipe; recuadro derivado de los landmarks | `pipeline.py` |
| El color parpadea | Recuadro de Haar ±8 px → Otsu cambia | Media exponencial del color (0.9 / 0.1) | `pipeline.py` |
| Textura "nada" sobre la cara | Ruido generado en coordenadas de **pantalla** | **`LiveAnchor`**: textura anclada a la malla | `beard.py` |
| Deslizamiento | Detalle de plantilla re-warpeado cada frame | Se probó apagar la capa 3 en vivo (−58 % de deslizamiento), pero se perdía el realismo; **se mantiene encendida** (`live_detail=True`) | `beard.py` |

### 9.1 Filtro One-Euro
Es un pasa-bajos cuyo corte se adapta a la velocidad:

```
α(fc, Δt) = 1 / (1 + τ/Δt),   τ = 1 / (2π·fc)
ẋ̂  = α(1, Δt)·ẋ + (1−α)·ẋ̂_{t−1}          (velocidad suavizada)
fc  = min_cutoff + β·|ẋ̂|                  (corte adaptativo)
x̂  = α(fc, Δt)·x + (1−α)·x̂_{t−1}
```
Cuando la cara está quieta (velocidad baja), el corte es bajo y suaviza fuerte, sin
temblor. Cuando se mueve rápido, el corte sube y la barba no queda atrás. Es
interpolación temporal adaptativa (6.1.4).

### 9.2 `LiveAnchor`: textura pegada a la cara
1. Con el **primer frame** se generan una vez los ruidos (veta, grano, borde,
   stubble fino) y se triangula la malla de 83 puntos con Delaunay. Esa topología
   queda **fija**.
2. En cada frame, los ruidos se **warpean** con `warp_template` desde la malla de
   referencia a la malla actual. El ruido viaja con la piel, incluso cuando la
   cara se acorta al girar.
3. Las **hebras** guardan su posición en **coordenadas baricéntricas** dentro de
   su triángulo de referencia: `p = λ₁A + λ₂B + λ₃C`. En cada frame se recalcula
   `p` con los vértices actuales, así cada pelo queda en el mismo punto de la piel.
4. Fuera de la malla se usa una **similitud** (rotación + escala + traslación,
   `estimateAffinePartial2D` con LMEDS sobre ojos, nariz y extremos de la
   mandíbula). Si la escala sale de `[0.6, 1.7]`, el ancla se recrea.

### 9.3 Medición (208 frames reales de webcam)
Para medir el deslizamiento usamos **flujo óptico** (Farneback) entre frames
crudos, que da el movimiento real de la piel. Con ese flujo deshicimos el
movimiento del frame renderizado siguiente y medimos cuánto difiere de la barba
del frame anterior, por encima de lo que difiere la piel sola:

| Configuración | Quieto | En movimiento | Rápido | Total |
|---|---|---|---|---|
| Similitud (rígido) | 1.30 | 2.83 | 4.42 | 2.88 |
| Malla (triángulos) | 1.22 | 2.49 | 4.14 | 2.63 |
| Malla + filtro suave | 1.00 | 2.13 | 3.53 | 2.24 |
| **Malla + filtro suave + sin capa 3** (actual) | **0.11** | **0.91** | **2.28** | **1.11** |

### 9.3b Corrección del 21-oct (realismo de `full` sin perder estabilidad)
Anclar el ruido a la malla (`LiveAnchor`) elimina el temblor, pero el warp
bilineal **desenfocaba el grano fino**, porque interpolar ruido blanco baja su
varianza. Con eso, las hebras densas y oscuras en vivo y el recorte duro de
bordes, la barba *full* se veía como una mancha gris. Arreglo:
- **Contraste restaurado:** después de warpear las texturas ancladas, cada canal
  se re-escala para recuperar la desviación estándar original
  (`media + (x − media)·σ_original/σ_warpeado`, medida en la zona de la barba).
  El grano vuelve a ser nítido y sigue pegado a la piel.
- **Hebras de `full`/`mustache` con los parámetros de foto:** 6 % de densidad,
  tono 0.72–1.08, opacidad 0.55. Las variantes densas y oscuras (10 %, 0.8)
  quedan solo para `goatee` y `stubble`.
- `full` ya no resta los labios ni se recorta al contorno de la cara.
- El borde difuso puede salirse de la región solo en una franja de
  1.2 × feather. Vuelve la transición natural sin manchas en la pared.

**Medición** (retrato con ruido de sensor y microtemblor, luego vaivén;
diferencia de la barba entre cuadros descontando el movimiento conocido):

| | Quieto | En movimiento |
|---|---|---|
| Textura por cuadro, sin anclar | 2.6–3.5 | 3.8–4.3 |
| **Anclada + contraste restaurado** | **0.12–0.15** | **0.64–0.68** |

Visualmente es equivalente al render del último commit, lado a lado sobre 2
retratos.

### 9.3c Barba en vivo en alta resolución (recorte de la cara)
En foto, la barba se pinta a la resolución completa de la imagen y el pelo se ve
nítido. En vivo, cada cuadro se reducía a 640 px: la cara quedaba en ~160 px y la
misma textura se veía como ruido borroso. Ahora el modo *Beard* en vivo
(`apply_beard_live_hd`) funciona así:
- el navegador envía el cuadro a la resolución de la cámara (hasta 1280 px);
- los **landmarks** corren sobre una copia de 640 px (rápido) y se reescalan;
- la barba se pinta **solo en un rectángulo fijo alrededor de la zona de la
  barba** (1.45 × 1.35 anchos de cara) a resolución completa, y se pega de vuelta;
- el rectángulo mantiene su tamaño mientras la cara no cambie de escala más de
  25 %, así el anclaje a la malla (sin temblor) no se reinicia.

| | Nitidez | Tiempo por cuadro |
|---|---|---|
| Antes (cuadro completo a 640 px) | borrosa | ~187 ms |
| **Recorte HD (cámara 1280 px)** | igual que el modo foto | **~89–163 ms** según el tamaño de la cara |

El temblor medido sigue en ~0 quieto (igual que la versión anclada). El modo
foto no se modificó. *Beard physics* usa la barba base sin la capa de textura
real (los pelos largos la tapan): ~84 ms por cuadro.

### 9.4 Ajustes solo en vivo para `stubble` y `goatee`
- Se **excluye la nariz** (convex hull de los puntos 27–35, dilatado): al girar,
  el contorno de la mandíbula del lado lejano cae sobre la nariz.
- **Degradé de densidad** desde la mandíbula (stubble):
  `ρ_local = clip(1.15 − 0.85·d_mandíbula / (0.30·ancho_cara), 0.30, 1)`.
- **Luz local:** el color de los puntos y las hebras se multiplica por
  `clip(L_local / L_medio, 0.75, 1.25)`, con L la luminancia desenfocada, para
  que la barba no tenga un tono plano distinto al de la piel.

---

## 10. Temas del sílabo cubiertos

| Tema | Dónde |
|---|---|
| 6.1.1 Teoría del color | Recoloreo en YCrCb, matching de piel por croma |
| 6.1.2 Representaciones de imágenes | Capas alpha, multiply, BGRA |
| 6.1.3 Sampling | Muestreo bilineal, ruido gaussiano, re-muestreo por arco |
| 6.1.4 Interpolación | Warp afín, Bézier, filtro One-Euro, baricéntricas |
| 6.2.2 Convex hull | Recorte de la región, exclusión de nariz |
| 6.2.5 Delaunay | Malla del warp (Fortune propio) |
| 6.4.2 Bordes | Feather por distance transform |
| 6.4.3 Features | Landmarks MediaPipe |
| 6.4.4 OpenCV | Haar, morfología, Otsu, flujo óptico |

---

## 11. Diferencias con el plan original (`plan_barberia_CS4016.md`)

| Plan | Código actual |
|---|---|
| Quadtree (6.2.4) para la máscara | **No implementado**: la máscara se hace con polígonos, elipses, morfología y convex hull |
| YOLO para detectar la cara | Haar (foto) / MediaPipe (vivo) |
| Sprite PNG escalado con `cv2.resize` | Plantillas reales + warp afín por triángulo propio |
| Canny para el borde | Feather por distance transform + ruido |
| 5.3 Gating por confianza | **Implementado** como *hold*: si MediaPipe pierde la cara, se reutilizan los últimos landmarks hasta 3 cuadros, desplazados por correlación de fase (ver `features_technical.md` §1.1) |

---

## 12. Limitaciones conocidas
- **Sin oclusión:** si pasas la mano delante, la barba se pinta encima de la mano.
- Con la cabeza muy inclinada (pitch), la región full queda como una banda delgada.
- Las plantillas son pocas (10) y de barbas oscuras; el recoloreo compensa, pero
  hay poca variedad de forma.
- El estado del modo en vivo es **global** al servidor: dos cámaras a la vez
  compartirían ancla y filtro.
- Giros rápidos: aún queda deslizamiento (2.28 en la tabla), porque a ~10 fps
  la barba no alcanza a seguirlos.
