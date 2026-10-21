# Opciones nuevas — Explicación simple (flujo)

> BarberStudio · CS4016 Computación Gráfica · UTEC
>
> Cómo funcionan, paso a paso y sin palabras técnicas, las opciones nuevas:
> **barba con física (P2)**, **"¿Cuántas gaussianas sos?" (P3)**, el juego
> **Barber Speedrun (P4)** y el **Espejo 3D (P5)**. En cada paso se indica **qué entra**, **qué sale** y
> **de dónde sale**. El detalle técnico está en
> [`features_technical.md`](features_technical.md); la barba base, en
> [`beard_overview.md`](beard_overview.md).

---

## Lo que viene "de afuera" vs. lo que hicimos nosotros

| Pieza | ¿De dónde sale? |
|---|---|
| Puntos de la cara (478 → 68) | Modelo **MediaPipe Face Landmarker** de Google, ya entrenado (`backend/models/face_landmarker.task`) |
| Puntos de la mano (21) | Modelo **MediaPipe Hand Landmarker** de Google, ya entrenado (`backend/models/hand_landmarker.task`, descargado de Google) |
| Fotos de prueba | Retratos oficiales de la NASA, **dominio público**, de Wikimedia Commons (`data/test_faces/CREDITS.txt`) |
| Malla de triángulos, física, gaussianas, juego, dibujo de pelos | **Programado por nosotros** en el proyecto |

> No entrenamos ningún modelo de IA para estas opciones. Usamos los modelos de
> Google solo para **ubicar** la cara y la mano; todo lo gráfico es nuestro.

---

## P2 — Barba con física ("Beard physics" en *Live*)

**La idea:** una barba larga cuyos pelos **se balancean** cuando mueves la
cabeza, como una barba de verdad. Si giras rápido, las puntas se quedan un poco
atrás y después vuelven.

```
 Cámara ─► 1. Puntos de la cara ─► 2. Malla de triángulos ─► 3. Plantar los pelos
                                                                   │
 Resultado ◄── 6. Pintar ◄── 5. Mover cada pelo (física) ◄── 4. Pegar raíces a la piel
```

| Paso | Entra | Sale | ¿De dónde sale? |
|---|---|---|---|
| 1. Puntos de la cara | Un cuadro de la cámara | 68 puntos | Modelo MediaPipe (Google). Si en un cuadro se pierde la cara, se reutilizan los últimos puntos, corridos según cuánto se movió la imagen |
| 2. Malla | Los 68 puntos (+15 bajo la mandíbula) | Una red de triángulos | Nuestro código (triangulación de Delaunay) |
| 3. Plantar los pelos | La zona de la barba completa | Cientos de pelos (uno cada ~30 píxeles de la zona, hasta 2600), cada uno con su largo, curva y tono | Nuestro código: se eligen al azar puntos dentro del molde de barba. Son más largos cerca del mentón y más cortos cerca de la boca |
| 4. Pegar raíces | Cada raíz + su triángulo | La posición de la raíz en el cuadro actual | Nuestro código: la raíz recuerda "en qué parte de su triángulo" está, y viaja con él |
| 5. Física | Raíces nuevas + posición anterior de cada pelo | Nueva forma de cada pelo | Nuestro código: cada pelo es una **cadena de 4 puntitos**. Tienen **inercia** (siguen moviéndose), **gravedad** (cuelgan), un **resorte** que los devuelve a su forma, y el largo de cada tramo no cambia |
| 6. Pintar | Forma de los pelos + color del pelo | La imagen final | Nuestro código: debajo va la barba normal (sombra) y encima los pelos. Cada pelo se dibuja como una **cadena de manchitas alargadas** (gaussianas), más transparentes en la punta, que lo hace verse fino y suave |

**Controles:** *Intensity* = cuántos pelos; *Beard length* = qué tan larga es.

**Qué medimos:** con la cabeza quieta, las puntas casi no se mueven (~3 px).
Con un giro brusco se atrasan hasta ~8–12 px y vuelven solas en menos de un
segundo. El atraso sube y baja con la velocidad de la cabeza (correlación
≈ 0.8). En el navegador corre a ~10 cuadros por segundo (lo optimizamos de 139 a ~75 ms por cuadro).

📸 `docs/captures/p2_physics/` (GIFs `*_sway.gif`, tiras `*_strip.jpg`) y
`docs/captures/ui/p2_live_physics_*.png`.

---

## P3 — "¿Cuántas gaussianas sos?" (*Gaussian Splatting*)

**La idea:** reconstruir tu foto usando **solo manchitas borrosas** (gaussianas).
Con 20 manchitas se ve una silueta; con 2000 ya te reconocés. Es la misma idea
detrás de *Gaussian Splatting*, la técnica de moda en gráficos.

```
 Foto ─► 1. (opcional) barba ─► 2. Recortar la cara ─► 3. Repartir N manchitas
                                                              │
 Resultado ◄── 5. Dibujar (suave / elipses) ◄── 4. Ajustarlas para que se parezcan a la foto
```

| Paso | Entra | Sale | ¿De dónde sale? |
|---|---|---|---|
| 1. Barba (opcional) | Tu foto + estilo | Tu foto con barba | El pipeline de barba del proyecto |
| 2. Recortar | Tu foto | Un cuadrado con tu cara | Detector de caras de OpenCV |
| 3. Repartir | La foto recortada + N | N manchitas iniciales (más donde hay bordes y detalles) | Nuestro código |
| 4. Ajustar | Las manchitas + la foto | Manchitas en su mejor posición, forma y color | Nuestro código: se compara el dibujo con la foto y cada manchita se corrige un poquito, ~150 veces ("descenso de gradiente") |
| 5. Dibujar | Las manchitas | Imagen suave o "mosaico de elipses" | Nuestro código. Como son manchitas y no píxeles, se pueden dibujar **a cualquier tamaño** |

**El juego:** con *Guess mode*, el original queda escondido y aparecen etapas de
20, 60, 200, 600 y 2000 gaussianas. Apretás *"I recognize it!"* apenas reconocés
la cara. **Menos gaussianas = más puntos.**

**Qué medimos:** la calidad (PSNR) sube de ~18 dB con 20 gaussianas a ~35 dB con
2000. Cada etapa tarda 1–5 segundos.

📸 `docs/captures/p3_gaussians/` y `docs/captures/ui/p3_*.png`.

---

## P4 — Barber Speedrun (el juego)

**La idea:** empezás con **barba completa** y tenés **30 segundos** para
afeitarla hasta dejar el estilo objetivo (candado, bigote o mentonera). La
máquina de afeitar es **tu dedo índice** (o el mouse).

```
 Cámara ─► 1. Puntos de la cara ─► 2. Barba completa con física (P2)
   │                                          │
   └─► 3. Punta del dedo (mano) ─► 4. Cortar los pelos que toca la máquina
                                              │
 Pantalla + puntaje ◄── 6. Puntaje ◄── 5. Pelos cortados caen y desaparecen
```

| Paso | Entra | Sale | ¿De dónde sale? |
|---|---|---|---|
| 1. Puntos de la cara | Cuadro de la cámara | 68 puntos | MediaPipe Face (Google) |
| 2. Barba completa | Puntos + molde de barba | Barba de pelos con física | La misma simulación de P2 |
| 3. Dedo | Cuadro de la cámara | Posición de la punta del índice + "¿está apuntando?" | Modelo **MediaPipe Hand** (Google). Apuntar con el índice = máquina prendida; mano abierta = solo mover |
| 4. Cortar | Recorrido del dedo entre dos cuadros | Lista de pelos cortados | Nuestro código: se corta todo pelo cuya **raíz** queda cerca del recorrido (como una máquina al ras de la piel) |
| 5. Caída | Pelos cortados | Pelitos que caen con gravedad y se desvanecen | Nuestro código |
| 6. Puntaje | Pelos vivos vs. molde objetivo | Puntaje 0–1000 | Nuestro código: **afeitado × conservado × 1000**. "Afeitado" = cuánto quitaste de lo que sobraba; "conservado" = cuánto del objetivo quedó intacto. Empieza en 0 |

**Detalles de juego:** cuenta regresiva 3-2-1-¡YA! y, con la cámara, se dibuja el
esqueleto de tu mano (verde = cortando, blanco = solo moviendo).

**Rangos:** ≥900 *Master barber!* · ≥750 *Pro barber* · ≥500 *Apprentice*.
El ranking guarda los 5 mejores en el navegador.

**Qué medimos:** un "bot barbero" que recorre las mejillas logra entre ~650 y
~830 puntos según el estilo; si corta sin cuidado (pasando por encima del
objetivo), el puntaje cae a 0. En el navegador, con cámara simulada y mouse,
el juego completo funciona sin errores.

📸 `docs/captures/p4_speedrun/` (GIFs y tiras por cara y estilo) y
`docs/captures/ui/p4_*.png`.

---

## P5 — Espejo 3D (*3D Mirror*)

**La idea:** subís **una sola foto** y obtenés **tu cabeza en 3D**, hecha con
unas 100 000 manchitas 3D (gaussianas). La podés **girar con el mouse** y ver la
barba de costado y desde abajo, con volumen de verdad.

```
 Foto ─► 1. Puntos 3D de la cara ─► 2. Malla de triángulos 3D ─► 3. Cubrir la cara de manchitas
   │                                                                     │
   └─► 4. El resto de la foto como "relieve" ─► 5. Barba como pelitos 3D ─┘
                                                                         │
                                Pantalla ◄── 7. Dibujar (visor 3D) ◄── 6. Enviar al navegador
```

| Paso | Entra | Sale | ¿De dónde sale? |
|---|---|---|---|
| 1. Puntos 3D | Tu foto | 478 puntos con **profundidad** (qué tan cerca está cada punto) | Modelo MediaPipe Face (Google): además de dónde está cada punto, estima qué tan adelante está |
| 2. Malla 3D | Los 478 puntos | Una red de triángulos en 3D | Nuestro código (Delaunay) |
| 3. Cara | Malla + foto | ~40 000 discos 3D pegados a la piel, con el color de la foto | Nuestro código: se reparte una cantidad pareja de discos en cada triángulo |
| 4. Relieve | El resto de la foto | ~50 000 discos para el pelo, las orejas, el cuello y el fondo (finos cerca de la cara, gruesos lejos) | Nuestro código: lo que está cerca de la cara "sale" hacia adelante y el fondo queda atrás |
| 5. Barba 3D | Molde de barba + malla | Miles de pelitos 3D (cada uno, 3 manchitas alargadas) | Nuestro código: crecen hacia afuera de la piel y hacia abajo. El bigote va hacia los lados, sin tapar los dientes |
| 6. Enviar | Todas las manchitas | Un archivo de ~3 MB | Nuestro servidor |
| 7. Dibujar | Las manchitas + el ángulo de la cámara | La imagen 3D que gira | **Nuestro visor 3D** en el navegador (WebGL): proyecta cada manchita a la pantalla, las ordena de la más lejana a la más cercana y las mezcla |

Hoja de ruta (de esta PoC a una cabeza completa y un avatar en vivo): [`mirror3d_proposal.md`](mirror3d_proposal.md).

**Importante (para explicarlo bien):** esto es el **dibujado** de *3D Gaussian
Splatting* (la parte que convierte manchitas 3D en imagen), hecho por nosotros.
No es la versión "entrenada" que necesita filmar la cabeza desde muchos ángulos y
una GPU potente. Por eso no existe la parte de atrás de la cabeza, y se ve mejor
girando hasta ~40° hacia cada lado.

**Bonus:** el botón *Download .ply* descarga tu cabeza en el **formato estándar**
de Gaussian Splatting. Se puede abrir en visores profesionales como SuperSplat,
así que no es un formato inventado por nosotros.

**Tip para la demo:** activá *Show individual splats* y la cabeza se ve como lo
que realmente es: miles de manchitas sueltas.

**Qué medimos:** unas 90–105 mil gaussianas por cabeza (antes ~55 mil a menor resolución), armadas en ~3 segundos
(incluida la descarga). Se probó con 3 caras y 3 estilos de barba, con capturas
desde 4 ángulos y un GIF giratorio de cada una.

📸 `docs/captures/p5_mirror/` (`*_turntable.gif`, `p5_mirror_*_{front,left,right,below}.png`).
