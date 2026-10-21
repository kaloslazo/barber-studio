# ¿Cómo le ponemos barba a una cara? — Explicación simple

> BarberStudio · CS4016 Computación Gráfica · UTEC
>
> Este documento explica **qué pasa desde que subes una foto (o prendes la cámara)
> hasta que ves tu cara con barba**, sin entrar en fórmulas. Para el detalle de
> cada pieza y su código, ver [`beard_technical.md`](beard_technical.md).
> Las dos opciones nuevas (barba con física y "¿Cuántas gaussianas sos?") están en
> [`features_overview.md`](features_overview.md).

---

## La idea en una frase

Encontramos **dónde está cada parte de tu cara** (mandíbula, boca, nariz),
**dibujamos sobre la piel la zona donde crecería la barba**, y ahí **pintamos la
barba en capas**: primero una sombra, luego pelos individuales y al final textura
de barba real tomada de fotos de personas con barba.

---

## El flujo, paso a paso

```
 Foto / cámara
      │
      ▼
 1. ¿Dónde está la cara?              → un recuadro alrededor del rostro
      │
      ▼
 2. ¿Dónde está cada parte?           → 68 puntos sobre la cara (el "mapa")
      │
      ▼
 3. ¿De qué color es tu pelo?         → el color que tendrá la barba
      │
      ▼
 4. Elegimos una barba real de ejemplo → una foto de barba que se parezca a tu tono
      │
      ▼
 5. La "estiramos" sobre tu cara      → usando una malla de triángulos
      │
      ▼
 6. Recortamos la zona de la barba    → la "máscara" (un molde) según el estilo
      │
      ▼
 7. Pintamos en capas                 → sombra + pelos + textura real
      │
      ▼
 Resultado
```

### Entradas y salidas de cada paso (resumen)

| Paso | Entra | Sale | ¿De dónde sale? |
|---|---|---|---|
| 1. Encontrar la cara | Tu foto (o un frame de la cámara) | Un recuadro alrededor de la cara | Detector "Haar" que viene incluido en OpenCV (no lo entrenamos) |
| 2. Poner los puntos | Tu foto | 68 puntos sobre la cara | Modelo de IA de Google **MediaPipe Face Landmarker**, archivo `models/face_landmarker.task` (ya entrenado, lo descargamos) |
| 3. Color del pelo | Tu foto + el recuadro | Un color (el de tu pelo) | Lo calculamos nosotros mirando los píxeles oscuros sobre la cabeza |
| 4. Barba de ejemplo | El estilo elegido + tu tono de piel | Una barba real recortada con sus 68 puntos | Archivos `assets/beards/*.npz`, sacados **antes** del dataset **CelebAMask-HQ** con nuestro script `training/harvest_beards.py` |
| 5. Estirar con la malla | La barba de ejemplo + tus 68 puntos | La barba deformada a la forma de tu cara | Malla de triángulos y deformación **programadas por nosotros** (`geometry/`) |
| 6. El molde | Tus 68 puntos + el estilo | Una máscara: dónde sí y dónde no va barba | Lo dibujamos nosotros con figuras (polígonos, elipses, curvas) |
| 7. Pintar en capas | Tu foto + molde + barba deformada + color | **La foto final con barba** | Lo programamos nosotros (`compositing/beard.py`) |

> **Lo único que viene "de afuera" ya hecho:** el detector de caras de OpenCV y el
> modelo de puntos de MediaPipe. El dataset solo se usó una vez para sacar las 10
> barbas de ejemplo. Todo lo demás (malla, deformación, máscaras, capas, física,
> gaussianas) está programado en el proyecto.

### 1. Encontrar la cara
> **Entra:** tu foto · **Sale:** un recuadro `(x, y, ancho, alto)` · **De dónde:** OpenCV (`haarcascade_frontalface_default.xml`)

Primero hay que saber **dónde** está la cara en la imagen. Para una foto usamos
un detector clásico de OpenCV que reconoce el patrón típico de un rostro de frente
(zona de ojos más oscura que la frente, etc.) y devuelve un **recuadro**.

En la cámara en vivo este paso se salta: el paso 2 ya encuentra la cara por sí
solo, y además funciona cuando giras la cabeza (el detector clásico no).

### 2. Poner los puntos en la cara (el "mapa")
> **Entra:** tu foto · **Sale:** 68 puntos `(x, y)` · **De dónde:** modelo MediaPipe `models/face_landmarker.task`

Usamos un **modelo de inteligencia artificial ya entrenado por Google** (MediaPipe
Face Landmarker). Nosotros **no lo entrenamos**: lo usamos tal cual, como una
herramienta. El modelo mira la foto y coloca **478 puntos** sobre la cara.

De esos 478 nos quedamos con **68 puntos**, que es un formato estándar:
- 17 en la **mandíbula** (de oreja a oreja),
- 10 en las **cejas**,
- 9 en la **nariz**,
- 12 en los **ojos**,
- 20 en la **boca**.

Esos 68 puntos son el **mapa** de tu cara. Todo lo demás se construye encima.

> **¿Y el dataset?** Sí usamos un dataset (CelebAMask-HQ, fotos de famosos con
> etiquetas como "tiene barba", "tiene bigote"), pero **no para detectar puntos**,
> sino para **sacar ejemplos de barbas reales** (paso 4). Eso se hizo una sola vez,
> antes, y quedó guardado en el proyecto.

### 3. Averiguar el color de tu pelo
> **Entra:** tu foto + el recuadro · **Sale:** un color · **De dónde:** cálculo propio (`segmentation/hair_region.py`)

Una barba rubia en una persona morena (o al revés) se ve falsa. Por eso miramos
**la zona de arriba de la cabeza**, nos quedamos con los píxeles más oscuros (el
pelo suele ser más oscuro que la piel y el fondo) y sacamos su **color típico**.
La barba se teñirá de ese color, un poco más oscuro.

### 4. Elegir una barba real de ejemplo
> **Entra:** estilo + tono de piel · **Sale:** una barba real con sus puntos · **De dónde:** `backend/app/assets/beards/` (sacadas del dataset CelebAMask-HQ)

Guardamos **10 barbas recortadas de fotos reales** (2 completas, 3 de candado,
1 de bigote, 4 de barba de pocos días). Cada una viene con **sus propios 68
puntos**. Según el estilo que elijas, tomamos la barba de ejemplo cuyo **tono de
piel** se parezca más al tuyo.

### 5. Estirar la barba de ejemplo sobre tu cara (la malla)
> **Entra:** barba de ejemplo + tus 68 puntos · **Sale:** barba deformada a tu cara · **De dónde:** código propio (`geometry/delaunay_fortune.py`, `geometry/warp.py`)

La barba de ejemplo es de **otra persona**, con otra forma de cara. Para que
encaje en la tuya:

1. Unimos los puntos de tu cara formando una **malla de triángulos** (como una red).
2. La barba de ejemplo tiene la **misma malla** (mismos puntos, misma red).
3. Cada triángulo de la barba de ejemplo se **estira y rota** para calzar en el
   triángulo correspondiente de tu cara.

Es como tener una calcomanía de goma dividida en triángulos: cada pedacito se
estira hasta encajar en su lugar. Así la barba sigue la forma de **tu**
mandíbula. Esta red es lo que en la app se ve como **"Face mesh"**.

### 6. Recortar la zona de la barba (la máscara)
> **Entra:** tus 68 puntos + estilo · **Sale:** el molde (máscara) · **De dónde:** código propio (`beard_mask` en `compositing/beard.py`)

Una **máscara** es un molde: blanco donde **sí** va barba, negro donde **no**. La
dibujamos con los 68 puntos, y cambia según el estilo:

| Estilo | Forma del molde |
|---|---|
| **Full** (completa) | Toda la mandíbula hasta la línea de la boca y las mejillas bajas |
| **Goatee** (candado) | Alrededor de la boca y el mentón, más el bigote |
| **Mustache** (bigote) | Un arco entre la nariz y el labio de arriba |
| **Stubble** (de pocos días) | Igual que la full, pero se pinta muy suave |

Siempre se le **quitan los labios** (para no pintarlos) y se recorta para que
**no se salga de la cara** (si no, aparecían manchas en la pared). Los bordes se
**difuminan** con un poco de irregularidad para que no parezca recortado con
tijera.

### 7. Pintar en capas
> **Entra:** foto + molde + barba deformada + color · **Sale:** la imagen final · **De dónde:** código propio (`apply_real_beard`)

Igual que un dibujante, pintamos la barba en **3 capas**:

1. **Sombra (cuerpo):** oscurecemos toda la zona del molde con el color de la
   barba. Se hace "multiplicando" el color, así las sombras y la luz de tu cara
   **se siguen viendo** a través de la barba (da volumen).
2. **Pelos individuales:** dibujamos miles de **pelitos curvos**, cada uno con su
   largo, curvatura, grosor y tono. Apuntan hacia abajo en la mandíbula, hacia
   afuera en las mejillas y hacia los lados en el bigote, como crece el pelo real.
3. **Textura real:** de la barba de ejemplo (paso 5) tomamos solo el **detalle
   fino** (los pelos, no su color) y lo sumamos encima. Esto da realismo.

**Stubble es distinto:** en vez de pelitos dibujados usa un **grano fino de
puntitos**, como la sombra de barba de pocos días ("five o'clock shadow").

---

## ¿Cómo se sube o se baja la densidad?

El slider **Intensity** de la app controla la densidad (de 0 a 100 %). Al moverlo
cambian tres cosas a la vez:

| Al subir la intensidad… | Al bajarla… |
|---|---|
| La **sombra** se oscurece más | La sombra se aclara |
| Se dibujan **más pelos** (la cantidad es proporcional) | Se dibujan menos pelos |
| Se suma **más textura real** | Se suma menos textura |
| En stubble aparecen **más puntitos** | Aparecen menos puntitos |

Además, cada estilo tiene su "fuerza base" fija: por ejemplo, el stubble arranca
mucho más suave que la barba completa, aunque el slider esté igual.

---

## ¿Qué cambia en la cámara en vivo?

En vivo se repite todo lo anterior **unas 9–10 veces por segundo**. Eso trae
problemas que una foto no tiene, y los resolvimos así:

| Problema | Solución (en simple) |
|---|---|
| La barba **temblaba** aunque estuvieras quieto | El modelo de puntos **sigue** tu cara frame a frame en vez de buscarla desde cero, y un **filtro** suaviza los movimientos chiquitos sin frenar los grandes |
| Al girar la cabeza la barba **desaparecía** | Dejamos de usar el detector clásico (que solo ve caras de frente) y usamos solo el de puntos |
| La textura **"nadaba"** sobre la cara | Los pelos y el grano se **pegan a la malla de triángulos** de tu cara, así viajan con tu piel |
| El color de la barba **parpadeaba** | El color del pelo se **promedia** con los frames anteriores |
| La textura real se deslizaba | En vivo **se apaga** esa capa (medimos que era la que más se deslizaba) |
| Si en un frame el modelo **pierde la cara** un instante, la barba desaparecía | Se **reutilizan los últimos puntos** (hasta 3 frames), corridos según cuánto se movió la imagen |
| En fondos azules la barba salía **azul** | El color del pelo se limita a tonos naturales (nunca azul ni verde) |

---

## Resumen para explicarlo en 30 segundos

> "Un modelo de IA ya entrenado pone 68 puntos en la cara. Con esos puntos armamos
> una malla de triángulos y un molde de dónde va la barba según el estilo. Una
> barba real, sacada de un dataset de fotos, se estira triángulo por triángulo
> para calzar en esa malla. Después pintamos en capas: una sombra que respeta la
> luz de la cara, miles de pelitos dibujados en la dirección en que crece el pelo,
> y el detalle de la barba real. El slider de intensidad controla cuánta sombra,
> cuántos pelos y cuánta textura se ponen. En vivo, además, seguimos la cara
> frame a frame y pegamos la textura a la malla para que no tiemble ni se
> deslice."
