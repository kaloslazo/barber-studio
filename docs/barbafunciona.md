# ¿Cómo se pinta la barba?

Es una mezcla de las dos cosas, pero no funciona como "pegar una barba real dentro de la máscara". La barba se arma con **4 capas** encima de la cara, y la foto real es la que menos peso tiene. Todo está en `apply_real_beard` (`backend/app/core/compositing/beard.py:571`).

## Las capas, en orden

**0. La región: dónde va la barba.** Con los 68 landmarks de la cara se construye una máscara anatómica según el estilo: full, goatee, mustache o stubble (`beard_mask`, `beard.py:81`). En modo live se le quita la nariz y el borde se difumina con ruido para que no parezca recortado (`organic_feather`). Esta máscara decide **dónde** hay barba. La foto real no lo decide.

**1. El "cuerpo": la masa oscura de fondo** (`beard.py:684`). Es un oscurecimiento por multiplicación sobre la piel, teñido con el color de la barba. Para que no quede plano, se modula con una textura de "vetas": ruido aleatorio difuminado en la dirección del pelo (`_streak_texture`, `beard.py:153`). Esa textura da una sensación de fibra sin dibujar ningún pelo.

**2. Los pelos individuales, dibujados uno por uno.** Esta es la capa de los "miles de pelos curvos".

**3. Detalle de una barba real.** Se elige la plantilla (foto de barba real) cuyo tono de piel se parece más al del usuario. Se deforma sobre la cara con triangulación de Delaunay: sus landmarks pasan a coincidir con los de la cara. De esa foto solo se usan dos cosas: **su color** y **su detalle de alta frecuencia** (`_inject_detail`, `beard.py:368`). No define la cobertura. El comentario en `beard.py:633` explica por qué: las plantillas tienen huecos y asimetrías, y si definieran la forma, esos defectos pasarían a la cara.

## Cómo se dibujan los pelos curvos

En `_strand_layer` (`beard.py:194`) y en la versión live `_anchored_strand_layer` (`beard.py:520`):

1. **Raíces:** se toma al azar alrededor del 6 % de los píxeles de la región (4 % en stubble), con un tope de 9000 pelos. Cada uno es el punto donde nace un pelo.
2. **Dirección:** un "campo de direcciones" (`_direction_maps`, `beard.py:127`) le da a cada píxel hacia dónde crece el pelo: hacia abajo en la mandíbula, hacia afuera en las mejillas y horizontal hacia los lados en el bigote.
3. **Cada pelo es una curva de Bézier cuadrática** con 3 puntos:
   - `p0` = la raíz
   - `p1` = a media longitud, desplazado según un `curl` aleatorio (entre −0.7 y 0.7) para que se curve
   - `p2` = la punta, a una distancia de 4.5–10 % del ancho de la cara
4. La curva se muestrea en 6 puntos y se traza con `cv2.polylines` con antialiasing, grosor de 1 o 2 px y un tono y una opacidad que varían un poco entre pelos.
5. Al final, un blur de 3×3 suaviza los bordes.

En vivo sería lento hacer 9000 llamadas por frame. Por eso los pelos se agrupan por (tono, opacidad, grosor) y cada grupo se dibuja en **una sola llamada**, lo que da unas 36 llamadas en vez de 9000. Además, cada raíz queda "anclada" a la malla de la cara con coordenadas baricéntricas. Así, cuando se mueve la cabeza, cada pelo sigue en el mismo punto de la piel en vez de reaparecer en otro lugar y parpadear.

**Stubble (barba de 3 días)** no dibuja curvas. Usa puntitos: ruido fino al que se le aplica un umbral, y solo los valores que lo superan se pintan (`beard.py:697`).

## Cómo se controla si hay más o menos pelo

Viene del slider `beard-strength` (20–100) en `frontend/index.html:286`. Llega al backend como `strength`, que se convierte en `density` (0–1). Esa `density` afecta a varias capas al mismo tiempo:

| Qué controla | Dónde | Efecto |
|---|---|---|
| **Número de pelos** | `count = len(origins) * density` (`beard.py:528`) | Se dibujan los primeros N de una lista fija precalculada. Al subir el slider se **agregan** pelos sin cambiar de lugar los que ya estaban |
| **Oscuridad del cuerpo** | `body_alpha * density` (`beard.py:685`) | Más densidad hace la masa de fondo más tupida |
| **Detalle de la foto real** | `detail_w * density` (`beard.py:735`) | Más textura real cuando la densidad es alta |
| **Puntos del stubble** | `threshold = 0.95 - 1.2 * density` (`beard.py:704`) | Un umbral más bajo deja pasar más puntitos |

Además, cada estilo tiene su propia base: `fraction` (4/6/10 % de raíces) y `body_strength` (0.20 para stubble frente a 0.55 para full). En modo live, para full y stubble hay también un `density_field` (`beard.py:654`) que hace la barba **más tupida cerca de la mandíbula y más rala hacia las mejillas**, como en una barba real.

Hay además un modo aparte, `apply_beard_physics` (`beard_physics.py`), donde los pelos se simulan como hebras con física. Ese no es el renderer principal.
