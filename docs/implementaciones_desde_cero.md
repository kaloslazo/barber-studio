# Implementaciones desde cero — Librería vs. Nuestra versión

> CS4016 Computación Gráfica · UTEC · BarberStudio
>
> Este documento registra, para cada pieza gráfica del pipeline de barba, **qué
> hacía la librería** y **qué implementamos nosotros a mano**. La frontera
> acordada: los *landmarks* faciales (visión/ML, no gráfica) siguen viniendo de
> una librería como simple entrada de datos; **toda la geometría y el rendering
> son propios**.

---

## Tabla resumen

| Pieza | Antes (librería) | Ahora (desde cero) | Tema del sílabo | Estado |
|---|---|---|---|---|
| Triangulación de Delaunay | `cv2.Subdiv2D` | **Fortune (sweepline)** ⭐ en uso; Bowyer-Watson como alternativa | 6.2.5 ⭐ | ✅ verificado |
| Warp por triángulo | `cv2.getAffineTransform` + `cv2.warpAffine` | Matriz afín resuelta a mano | 6.1.4 | ✅ verificado |
| Muestreo de textura | `cv2.INTER_LINEAR` (interno) | Interpolación bilineal propia | 6.1.3 – 6.1.4 | ✅ verificado |
| Test de interior de triángulo | `cv2.fillConvexPoly` | Coordenadas baricéntricas | 6.2 | ✅ verificado |
| Landmarks (68 puntos) | MediaPipe | *(se mantiene: es entrada, no gráfica)* | 6.4.3 | — |

Archivos: `backend/app/core/geometry/delaunay_fortune.py` (**en uso**),
`backend/app/core/geometry/delaunay.py` (Bowyer-Watson, alternativa),
`backend/app/core/geometry/warp.py`.

> **En uso ahora:** `beard.py` importa `delaunay_triangles` desde
> `delaunay_fortune`. Para volver a Bowyer-Watson, se cambia esa línea de import.

---

## 1. Triangulación de Delaunay

### Antes — `cv2.Subdiv2D`
```python
subdiv = cv2.Subdiv2D(rect)
for px, py in points:
    subdiv.insert((float(px), float(py)))
for t in subdiv.getTriangleList():
    ...  # recuperar índices por cercanía
```
OpenCV construye la triangulación con un algoritmo incremental interno (*edge
flips*) y devuelve coordenadas; había que re-mapear cada vértice a su índice
buscando el punto más cercano.

### Ahora — Fortune (sweepline), el que corre en el pipeline
`delaunay_fortune.delaunay_triangles(points, rect=None)` — misma firma, devuelve
tripletas de índices. **Algoritmo de barrido:**

1. Una **línea de barrido** horizontal baja por el plano (de arriba a abajo).
2. Se mantiene la **beach line**: la envolvente inferior de las parábolas de los
   sitios ya pasados (cada sitio + la directriz define una parábola).
3. **Site event**: al cruzar un sitio nuevo, aparece un arco nuevo en la beach line.
4. **Circle event**: cuando un arco se estrangula a ancho cero, desaparece — y ese
   punto es un **vértice de Voronoi**.
5. **Truco para Delaunay:** cada circle event tiene 3 sitios cocirculares con
   círculo circunscrito vacío → **ese trío es un triángulo de Delaunay**. Los
   recolectamos directamente, sin construir todo el diagrama de Voronoi.

Piezas clave: la **cola de prioridad** de eventos (`heapq`), el cálculo del
**breakpoint** entre dos parábolas (`_breakpoint`, una cuadrática), el
**circumcentro** (`_circumcenter`) y el test de orientación (`_cross`) que decide
cuándo un arco converge.

> **Nota conceptual:** *Delaunay* es el resultado (la propiedad: ningún punto
> dentro de ningún círculo circunscrito). *Fortune*, *Bowyer-Watson* y el interno
> de `cv2.Subdiv2D` son **algoritmos distintos** que producen **el mismo**
> Delaunay. Complejidad: Fortune es O(n log n); Bowyer-Watson (nuestra otra
> versión) es O(n²) — para ~83 landmarks ambos son instantáneos.

### Alternativa — Bowyer-Watson (`delaunay.py`)
Incremental: super-triángulo → por cada punto, borrar los triángulos cuyo círculo
circunscrito lo contiene → re-triangular la cavidad → quitar los que tocan el
super-triángulo. Sigue disponible como módulo alterno.

### Verificación
`scratchpad/test_fortune.py` compara Fortune contra Bowyer-Watson y contra la
teoría:
- **0 violaciones** de la propiedad de Delaunay en 25 nubes aleatorias y en el
  layout tipo cara.
- Fortune **acierta el conteo exacto de Euler** (`2n − 2 − h`, con `h` = puntos
  del convex hull).
- Layout tipo cara (68 landmarks, el caso real): **94 triángulos, idénticos** a
  Bowyer-Watson.

> **Hallazgo (bonus):** implementar Fortune destapó un fallo sutil de robustez en
> nuestro Bowyer-Watson: su **super-triángulo era demasiado pequeño (×20)**, así
> que al descartar los triángulos que lo tocan perdía **1–2 triángulos del borde
> (hull)**. Fortune da el conteo correcto; subir el super-triángulo de BW a ×1000
> lo iguala. Por eso el pipeline se quedó con **Fortune**, que es el más robusto.

---

## 2. Warp por triángulo (piecewise-affine)

### Antes — OpenCV
```python
transform = cv2.getAffineTransform(src[[a, b, c]], tri_dst)
warped = cv2.warpAffine(template, transform, (w, h), flags=cv2.INTER_LINEAR)
tri_mask = cv2.fillConvexPoly(...)  # recortar al triángulo
```
Para cada triángulo, OpenCV calculaba la matriz afín, deformaba **toda** la
imagen y luego la recortaba con una máscara.

### Ahora — desde cero
`warp_template(...)` — misma firma. Por cada triángulo:

1. **Matriz afín a mano** (`_affine_from_triangles`): se resuelve el sistema
   3×3 que mapea el triángulo *destino → origen* (mapeo inverso, para saber de
   dónde leer cada píxel de salida). Cada coordenada es `u = a·x + b·y + c`,
   obtenida con `np.linalg.solve`.
2. **Rasterización del triángulo** (`_points_in_triangle`): en vez de dibujar
   una máscara, se usa el test de **coordenadas baricéntricas** — un píxel está
   dentro si sus tres pesos son ≥ 0.
3. **Muestreo bilineal propio** (`_bilinear_sample`): para cada píxel interior
   se mapea al origen y se lee la textura mezclando los **4 píxeles vecinos**
   con pesos según la parte fraccionaria. Los puntos fuera de la imagen se
   marcan inválidos para no arrastrar basura del borde.

Solo se recorre el *bounding box* de cada triángulo (no la imagen completa), así
que además es más eficiente que deformar todo y recortar.

### La interpolación bilineal, en una línea
En un punto `(x, y)` con parte entera `(x0, y0)` y fracciones `(wx, wy)`:

```
valor = (1-wx)(1-wy)·P(x0,y0) + wx(1-wy)·P(x1,y0)
      + (1-wx)wy·P(x0,y1)     + wx·wy·P(x1,y1)
```

### Verificación
`scratchpad/test_warp.py`, con NumPy puro (sin cv2):
- **Warp identidad** (destino = origen) reproduce la textura → error medio
  **0.0000**.
- **Warp afín conocido** (escala ×2 + traslación) vs. el mapeo inverso analítico
  → error medio **0.0000**.
- **Bilinear** en `(1.5, 1.5)` sobre una rampa → **7.5** exacto.

---

## 3. Mejoras de realismo (Paso 4)

| # | Mejora | Estado | Tema |
|---|---|---|---|
| — | Arreglar los 2 bugs de `beard.py` / `pipeline.py` (baseline vivo) | ✅ hecho | — |
| 1 | Recalibrar densidad/opacidad (cadena de alphas + multiply floor) | ✅ hecho | 6.1.2 |
| 2 | Transferencia de gradientes: reinyectar la alta frecuencia (pelos) de la textura real (`_gradient_detail` / `_inject_detail`) | ✅ hecho | 6.1.3 |
| 3 | **Recoloreo adaptativo al pelo** (luminancia + croma) en YCrCb (`_recolor_beard` + tinte de hebras) | ✅ hecho | 6.1.1 |
| 3b | Ajuste por estilo: mustache +opacidad, stubble +densidad, goatee más parejo | ✅ hecho | 6.1.2 |
| 3c | **Rediseño de cobertura**: la densidad la define la máscara anatómica por estilo (pareja), la plantilla solo aporta textura | ✅ hecho | 6.2.2 / 6.1.2 |
| 4 | Borde inferior con Sobel/Canny (sigue la sombra del cuello) | ⏭️ pendiente | 6.4.2 |

> **Nota:** se probó un intento de color cálido + clamp de piel/Sobel + reajuste de
> geometría (bigote/goatee), pero empeoró el resultado en pruebas reales y se
> **revirtió**. El estado bueno es el del rediseño de cobertura (#3c) + recoloreo (#3).

**Nota sobre el #2:** un Poisson blend *puro* igualaría el brillo de la barba con la
piel del borde y la *aclararía*. Por eso separamos la textura en baja frecuencia
(sombra/masa, vía el *multiply*) y alta frecuencia (los pelos), y solo
reinyectamos la alta frecuencia — se obtiene pelo nítido sin perder el color oscuro.

**Nota sobre el #3 (el gran arreglo del rubio):** las plantillas son fotos de
barba oscura, y el `_match_chroma` original solo ajustaba el *croma* (Cr/Cb), no
el brillo → a un rubio le ponía barba casi negra. `_recolor_beard` toma el color
mediano del **pelo real de la persona** (que ya calcula `pipeline.apply_beard`) y
desplaza toda la barba en YCrCb hacia ese tono (con `Y * 0.88` para que la barba
lea un poco más oscura que el pelo). Las hebras del `_strand_layer` también se
tiñen con ese color en vez del `PALETTE` fijo.

> **Bug encontrado y corregido:** `cv2.polylines` rechaza colores `np.float32`
> ("color is not numeric"). Al pasar el tinte como array de numpy, `apply_real_beard`
> lanzaba excepción y **caía al fallback oscuro** — que era la causa real de la
> "barba negra". Se solucionó casteando el color a `float` de Python.

**Nota sobre el #3c (densidad pareja):** antes la cobertura salía del `warped_alpha`
(el alpha de la plantilla), que es irregular → huecos, asimetría izquierda/derecha
y, en `stubble`, grumos oscuros aislados. Un campo de ruido `clump` de baja
frecuencia empeoraba esto apagando regiones enteras. Ahora:
> 1. La **cobertura** viene de `beard_mask(style)` — la máscara anatómica del estilo,
>    pareja y simétrica (convex-hull/polígono de landmarks, tema 6.2.2).
> 2. Un **cuerpo** uniforme oscurece toda esa región por igual (solo leve variación
>    de textura), tiñendo con el color del pelo.
> 3. Las **hebras** (`_strand_layer`) se dibujan por toda la región → pelo nítido y
>    distribuido parejo.
> 4. La plantilla real solo añade **detalle** donde tiene contenido.
> Se eliminó el `clump` y la dependencia del alpha irregular de la plantilla.

---

## Cómo reproducir las pruebas

```bash
# Solo requieren NumPy (no cv2 ni mediapipe)
python scratchpad/test_delaunay.py   # Bowyer-Watson: propiedad de Delaunay
python scratchpad/test_warp.py       # warp afín + bilinear vs. analítico
python scratchpad/test_fortune.py    # Fortune vs. Bowyer-Watson + conteo de Euler
```

> Los scripts de prueba viven hoy en el `scratchpad` (temporal). Conviene moverlos
> a `backend/tests/` para que queden versionados en el repo.
