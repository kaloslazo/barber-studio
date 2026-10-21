# Gaussian Splatting en BarberStudio — Propuestas

> BarberStudio · CS4016 Computación Gráfica · UTEC
>
> Ideas para llevar el proyecto un nivel más arriba con **Gaussian Splatting**,
> ordenadas de la más factible a la más ambiciosa, con lo que cuesta cada una y por
> qué le puede gustar a un profe que ama la computación gráfica.

> **Estado (21-oct-2026):** ✅ **P2** (barba con física), ✅ **P3** (¿Cuántas gaussianas
> sos?, implementado desde cero en NumPy, sin PyTorch), ✅ **P4** (Barber Speedrun) y
> ✅ **P5** en su versión de *render* (cabeza 3D en gaussianas desde una foto + malla
> 3D de MediaPipe, visor WebGL2 propio; sin entrenamiento multivista) y ✅ **P1**: los pelos
> de la física y del juego se dibujan como cadenas de gaussianas 2D anisotrópicas
> (`splat_strands`). Detalle en
> [`features_overview.md`](features_overview.md) y
> [`features_technical.md`](features_technical.md).

---

## 1. ¿Qué es Gaussian Splatting? (en 1 minuto)

En vez de representar una imagen o una escena con **píxeles** o **triángulos**, se
representa con **miles de manchitas gaussianas** ("splats"). Cada una es una
elipse borrosa con:

| Parámetro | Qué es |
|---|---|
| `μ` | Centro (posición) |
| `Σ` | Covarianza: forma, tamaño y orientación de la elipse |
| `o` | Opacidad |
| `c` | Color (en 3D, armónicos esféricos para que cambie según el ángulo) |

**En 2D**, el aporte de un splat en el píxel `x` es

```
G(x) = exp( −½ (x − μ)ᵀ Σ⁻¹ (x − μ) ),      Σ = R · diag(sₓ², s_y²) · Rᵀ
```

y la imagen final se arma **componiendo los splats ordenados de adelante hacia
atrás** (alpha compositing, el mismo de nuestra barba):

```
C(x) = Σᵢ cᵢ · αᵢ · Tᵢ ,    αᵢ = oᵢ · Gᵢ(x) ,    Tᵢ = Πⱼ<ᵢ (1 − αⱼ)
```

**En 3D** (Kerbl et al., *3D Gaussian Splatting for Real-Time Radiance Field
Rendering*, SIGGRAPH 2023), cada splat es una gaussiana 3D con
`Σ = R S Sᵀ Rᵀ`. Para dibujarla se **proyecta** a una elipse 2D en pantalla con la
jacobiana de la cámara (`Σ' = J W Σ Wᵀ Jᵀ`, la idea del *EWA splatting*) y se
compone igual que arriba. Sus parámetros se **optimizan con descenso de
gradiente** comparando el render con fotos reales.

### ¿Por qué encaja con una barbería?
**El pelo es justamente lo que peor se representa con triángulos:** son millones
de hebras finas, semitransparentes, que se superponen. Una gaussiana alargada es,
literalmente, **un pelo borroso**. Hoy dibujamos cada hebra como una línea de
1–2 px (`cv2.polylines`). Con splats, cada hebra pasa a ser una cadena de
elipses suaves que se mezclan bien entre sí y con la piel. Trabajos recientes ya
modelan cabello como hebras de gaussianas.

---

## 2. Las propuestas

### P1 — "Pelos de gaussianas": la barba como splats 2D ⭐ recomendada
**Qué:** reemplazar las hebras dibujadas (capa 2) por **cadenas de 3–4 gaussianas
alargadas** orientadas según el campo de dirección del pelo que ya tenemos.

**Por qué es la mejor primera apuesta:**
- Se implementa **desde cero en NumPy** (encaja con la línea de
  `implementaciones_desde_cero.md`), sin GPU.
- **Reutiliza todo lo que ya existe:** la máscara, el campo de dirección, el color
  de pelo y el anclaje por **coordenadas baricéntricas** del modo en vivo. Cada
  splat vive en un triángulo de la malla y viaja con la piel.
- Resultado visible: pelos suaves con antialiasing "natural", sin el aspecto de
  línea dura, y una densidad que se controla con la **opacidad** y el **tamaño**
  de los splats, no solo con la cantidad.

**Cómo (esbozo):**
```python
def strand_covariance(direction, length, thickness):
    ux, uy = direction
    R = np.array([[ux, -uy], [uy, ux]])
    S = np.diag([(length / 2) ** 2, (thickness / 2) ** 2])
    return R @ S @ R.T

def splat(canvas_rgb, canvas_t, mu, cov, color, opacity):
    inv = np.linalg.inv(cov)
    r = int(3 * np.sqrt(np.linalg.eigvalsh(cov).max()))
    x0, y0 = int(mu[0]) - r, int(mu[1]) - r
    ys, xs = np.mgrid[y0:y0 + 2 * r + 1, x0:x0 + 2 * r + 1]
    d = np.stack([xs - mu[0], ys - mu[1]], -1)
    g = np.exp(-0.5 * np.einsum("...i,ij,...j", d, inv, d))
    a = opacity * g
    canvas_rgb[ys, xs] += (color * a[..., None]) * canvas_t[ys, xs, None]
    canvas_t[ys, xs] *= 1 - a
```

**Temas del sílabo:** 6.1.2 (representación), 6.1.3 (sampling de la gaussiana),
6.1.4 (interpolación), alpha compositing.
**Esfuerzo:** bajo–medio (1–2 semanas). **GPU:** no.

---

### P2 — "Barba con física": que se mueva al girar ⭐ recomendada
**Qué:** cada hebra de P1 pasa a ser una **mini cadena de partículas** (raíz +
2–3 nodos) unida por resortes. La raíz va pegada a la piel con las coordenadas
baricéntricas. El resto sigue con **inercia** y gravedad mediante **integración de
Verlet**.

**Por qué:** ataca directamente la sensación de "barba estática" del modo en vivo.
Si giras la cabeza rápido, las puntas **se atrasan un poco y vuelven**. Es el
detalle que hace que algo se vea vivo. Además es simulación física sencilla y muy
vistosa en una demo.

**Cómo (esbozo):**
```python
def verlet_step(pos, prev, root, rest_len, dt, gravity=(0, 9.8), damping=0.92):
    vel = (pos - prev) * damping
    prev = pos.copy()
    pos = pos + vel + np.array(gravity) * dt * dt
    pos[:, 0] = root
    for _ in range(3):
        for k in range(1, pos.shape[1]):
            seg = pos[:, k] - pos[:, k - 1]
            dist = np.linalg.norm(seg, axis=1, keepdims=True) + 1e-6
            pos[:, k] = pos[:, k - 1] + seg / dist * rest_len
    return pos, prev
```
Cada nodo se dibuja como un splat de P1, orientado según el segmento.

**Temas:** 6.1.4 (interpolación temporal), animación.
**Esfuerzo:** medio (1 semana sobre P1). **GPU:** no.
**Ojo:** el estado de las partículas es por sesión, igual que el `LiveAnchor`.

---

### P3 — "¿Cuántas gaussianas sos?" (apertura de la presentación)
**Qué:** tomar la foto del usuario y **ajustar N gaussianas 2D** que la
reconstruyan (estilo *GaussianImage*), minimizando el error con descenso de
gradiente. Se muestra en vivo cómo la cara **emerge** a medida que se agregan
splats: 50 → 200 → 1000 → 5000.

**Versión juego:** el público tiene que adivinar **quién es** con la menor cantidad
de gaussianas posible, o qué estilo de barba tiene. Funciona muy bien como
arranque de la exposición.

**Cómo:** PyTorch en Colab (ya tenemos un notebook en `backend/training/`). Se
optimizan `μ, Σ (vía R y escalas), color, opacidad` con Adam y pérdida
L1 + SSIM. El resultado (lista de splats) se puede dibujar después en el
navegador con un `<canvas>` sin GPU.

**Temas:** 6.1.2 (una representación de imagen alternativa al píxel), 6.1.3
(muestreo), optimización.
**Esfuerzo:** medio. **GPU:** Colab (se puede hacer offline; la demo muestra el
resultado).

---

### P4 — "Barbero Speedrun" 🎮 el juego
**Qué:** un juego en la pestaña *Live*. Aparece un **estilo objetivo**
(por ejemplo, candado prolijo) y el jugador tiene **30 segundos** para "afeitar"
su barba de splats hasta dejarla igual. La **máquina de afeitar** es el dedo
índice, detectado con **MediaPipe Hands** (misma familia de modelos que ya usamos),
o el mouse como respaldo.

**Por qué funciona con splats:** cada pelo es un objeto independiente. "Cortar" es
borrar los splats que toca la máquina, con partículas que caen usando la física de
P2. Con píxeles esto sería un borrador. Con splats se siente como cortar pelo.

**Puntaje:** IoU (*intersection over union*) entre la máscara que queda y la
máscara del estilo objetivo (`beard_mask(style)`, que ya existe), menos una
penalización por cortar de más, más un bonus por tiempo.

```
puntaje = 1000 · IoU(barba_restante, objetivo) − 5 · splats_fuera + bonus_tiempo
```

**Sabor local:** modos con nombre, por ejemplo *"Corte de Barrio"*, *"Modo Tango"*
(bigote finito con las puntas para arriba) o *"Modo Mundial"* (barba completa).
También un ranking en pantalla para que la clase compita en vivo. Al profe le
damos el primer turno.

**Temas:** 6.2 (geometría de máscaras, IoU), 6.4.3 (landmarks de mano), todo lo de
P1 y P2.
**Esfuerzo:** medio sobre P1 + P2. **GPU:** no.

---

### P5 — "Espejo 3D": tu cabeza en splats 3D (la ambiciosa)
**Qué:** el usuario graba un video corto girando la cabeza (la pestaña
*Transfering hair* ya pide varias vistas), y se entrena un **3D Gaussian Splatting
real** de su cabeza. Después se le agrega la barba como **splats 3D** y se puede
rotar 360° en el navegador.

**Cómo:**
1. Video de 10–20 s orbitando la cabeza → ~100 frames.
2. Poses de cámara con **COLMAP** (structure-from-motion).
3. Entrenamiento con una librería abierta de 3DGS (por ejemplo `gsplat` o
   *nerfstudio*) en **Colab con GPU**: ~10–30 min.
4. Visor web en WebGL que cargue el archivo de splats (existen visores abiertos en
   JavaScript que se pueden servir desde nuestro frontend sin build step).
5. Barba: generar splats 3D sobre la superficie de la mandíbula, usando los
   landmarks 3D de MediaPipe (que también dan profundidad `z`).

**Riesgos (honestos):** requiere GPU, COLMAP puede fallar con caras (poca
textura y mucho movimiento), el entrenamiento no es en tiempo real y la demo
depende de un archivo pre-entrenado. Es la propuesta más vistosa, pero también la
de más riesgo.

**Temas:** 6.1 completo, proyección y cámaras, optimización.
**Esfuerzo:** alto (3–4 semanas). **GPU:** sí (Colab).

---

### P6 — Para soñar: avatar en vivo con splats anclados a la malla
**Qué:** splats **pegados a los triángulos de la malla de MediaPipe**, como en los
avatares de gaussianas recientes (por ejemplo *GaussianAvatars*, CVPR 2024, que
anclan splats a una malla paramétrica de cabeza). Se entrena una vez con el video
del usuario y después se **anima en vivo** con la cámara, con la barba incluida
como splats propios.

Es nivel investigación. Lo incluimos como **"trabajo futuro"** en la presentación:
muestra que entendemos hacia dónde va el área.

---

## 3. Comparación

| | Esfuerzo | GPU | Wow en demo | Temas del curso | Riesgo |
|---|---|---|---|---|---|
| **P1** Pelos de gaussianas | Bajo–medio | No | ★★★ | 6.1.2–6.1.4 | Bajo |
| **P2** Barba con física | Medio | No | ★★★★ | 6.1.4, animación | Bajo |
| **P3** ¿Cuántas gaussianas sos? | Medio | Colab | ★★★★ | 6.1.2, 6.1.3 | Bajo |
| **P4** Barbero Speedrun | Medio | No | ★★★★★ | 6.2, 6.4.3 | Medio |
| **P5** Espejo 3D | Alto | Sí | ★★★★★ | 6.1, proyección | Alto |
| **P6** Avatar en vivo | Muy alto | Sí | ★★★★★ | Investigación | Muy alto |

---

## 4. Recomendación

**Núcleo: P1 + P2. Demo: P4. Apertura: P3.**

1. **P1** mejora directamente la calidad de la barba y se apoya en lo que ya
   tenemos (máscara, dirección, anclaje baricéntrico).
2. **P2** resuelve la queja de "barba estática" y se ve espectacular en vivo.
3. **P4** convierte el proyecto en un **juego**, que es lo que más engancha en una
   exposición: la clase participa y el profe juega.
4. **P3** es un arranque de 2 minutos que explica qué es un splat mejor que
   cualquier diapositiva.
5. **P5** y **P6** van como "trabajo futuro" en la última diapositiva.

### Hoja de ruta sugerida
| Semana | Entregable |
|---|---|
| 1 | P1: renderer de splats 2D en NumPy + comparación lado a lado con las polilíneas |
| 2 | P2: física de Verlet sobre las hebras, anclada con baricéntricas en vivo |
| 3 | P4: modo juego (detección de mano, cortar splats, IoU, ranking) |
| 3 (paralelo) | P3: notebook de Colab + video o GIF del ajuste progresivo |

---

## 5. El pitch (para la primera diapositiva)

> "El pelo es la pesadilla de la computación gráfica: millones de hebras finas y
> semitransparentes que los triángulos no saben representar. Nosotros dejamos de
> dibujar pelos como líneas y los dibujamos como lo que son, **pequeñas gaussianas
> alargadas**: la misma idea detrás de *3D Gaussian Splatting*, la técnica que
> cambió el render neuronal en 2023. Cada pelo está anclado a una malla de
> Delaunay construida por nosotros, tiene física propia, y se puede cortar.
> Profe, ¿se anima a ser el primero en el ranking del Barbero Speedrun?"
