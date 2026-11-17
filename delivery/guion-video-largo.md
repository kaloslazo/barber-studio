# Guion del video largo

Duración máxima: **20 minutos**. El plan suma **19:30**; apunten a 18 para tener margen. Archivo final: `delivery/videos/video-largo.mp4`.

Cada integrante graba **sus bloques por separado** y después se unen en orden. Para que se entienda como un solo video, el orden sigue a la app: primero la base que usa todo (la malla de la cara), después las herramientas con foto, en vivo, 3D, juegos y Fiesta. La rúbrica premia que cada uno **domine y defienda** su parte (11 de los 20 puntos), así que cada bloque dice qué tiene que quedar claro; no lo lean, díganlo con sus palabras.

| # | Tiempo | Quién | Bloque | Lámina de inicio |
|---|---|---|---|---|
| 1 | 0:00 – 1:45 | Kalos | Problema, equipo y arquitectura | «El problema» |
| 2 | 1:45 – 3:30 | Gianpier | Puntos de la cara, Delaunay de Fortune y warp afín | «De puntos a malla» |
| 3 | 3:30 – 5:00 | Gianpier | Barba con plantillas reales | «Barba: el proceso» |
| 4 | 5:00 – 8:00 | Kalos | Tinte (CIELAB y YOLO), corte (pull-push) y forma de cara | «Tinte: el proceso» |
| 5 | 8:00 – 9:45 | Gianpier | En vivo: barba sobre la malla 3D y física | «En vivo: el proceso» |
| 6 | 9:45 – 11:45 | Gianpier | Gaussianas 2D y Espejo 3D | «Gaussianas 2D: el proceso» |
| 7 | 11:45 – 13:45 | Sofía | Peluca 3D y Laboratorio | «Peluca 3D: el proceso» |
| 8 | 13:45 – 15:15 | Gianpier | Peluca en una vuelta y Contrarreloj | «Peluca en una vuelta» |
| 9 | 15:15 – 18:30 | Kalos | Galería, El practicante y Fiesta | «Galería: barbas famosas» |
| 10 | 18:30 – 19:30 | Sofía | Resultados, límites y cierre | «Calidad y rendimiento» |

Por persona: **Kalos 8:00**, **Gianpier 8:30**, **Sofía 3:00**. Si un bloque se pasa por más de 30 s, se recorta ese mismo bloque.

## Para que se sienta como un solo video

- **Misma app y misma foto:** todos graban con la app del último `main` (`http://localhost:8001` o `docker compose up -d --build app` en `:8000`) y la foto de ejemplo del astronauta, para que se vea igual en todo el video.
- **Cada clip empieza con su lámina** (columna de arriba, en `slides/main.pdf` a pantalla completa) y después pasa a la app.
- **Primera frase: enlace con lo anterior. Última frase: pasa la posta.** Cada bloque trae las dos frases sugeridas.
- **Un archivo por bloque**, con el número delante: `01-kalos.mov`, `02-gianpier.mov`, `03-gianpier.mov`, `04-kalos.mov`, `05-gianpier.mov`, `06-gianpier.mov`, `07-sofia.mov`, `08-gianpier.mov`, `09-kalos.mov`, `10-sofia.mov`. Se dejan en `delivery/videos/clips/` y se unen en ese orden.
- **Mostrar 5 segundos de código** en cada bloque (el archivo que se indica): es la prueba de que el aporte es propio.

---

## 1. Problema, equipo y arquitectura (Kalos, 1:45)

**Pantalla:** portada, «El problema», «Qué hace Fresh», «Arquitectura» y «Qué es nuestro y qué no»; después el inicio de la app.

**Tiene que quedar claro:**
- elegir un corte o una barba es una decisión a ciegas: el resultado se ve cuando ya está hecho;
- las apps que existen pegan una imagen encima o generan una cara nueva; Fresh modela la geometría de **tu** cara y dibuja sobre tu foto original;
- quién hizo qué: Gianpier la malla, la barba, el modo en vivo, las gaussianas, el espejo 3D, la vuelta 360 y el Contrarreloj; Sofía la peluca 3D y el laboratorio; Kalos la arquitectura, el tinte, el corte, la forma de la cara, la galería, el practicante y Fiesta;
- arquitectura: un solo proceso de FastAPI sirve la interfaz y la API; los endpoints son delgados y la gráfica vive en `backend/app/core`, una carpeta por técnica; interfaz en HTML y JavaScript sin compilación; visor 3D propio en WebGL2;
- lo único que viene de modelos ya entrenados: los puntos de la cara y la segmentación de MediaPipe, y YOLO ajustado por nosotros. Todo lo que se dibuja es código propio;
- 123 pruebas automáticas, integración continua en GitHub y Docker para levantarlo con un comando.

**Mostrar:** subir la foto de ejemplo una vez y ver que queda cargada en todas las herramientas.

**Código:** `backend/app/api/routes.py` (un endpoint delgado que llama a `core`).

**Última frase:** «Todo parte de los puntos de la cara. Gianpier explica cómo los volvemos una malla».

## 2. Puntos de la cara, Delaunay de Fortune y warp afín (Gianpier, 1:45)

**Primera frase:** «Todo Fresh se apoya en una malla de triángulos sobre la cara».

**Pantalla:** «De puntos a malla», luego Barba con «Mostrar la malla de triángulos».

**Tiene que quedar claro:**
- MediaPipe da 478 puntos; se convierten a los 68 estándar y se agregan 15 bajo la mandíbula;
- Delaunay: ningún punto cae dentro del círculo circunscrito de un triángulo, lo que evita triángulos finos;
- Fortune: línea de barrido, *beach line* de parábolas, evento de sitio y evento de círculo; cada evento de círculo da un triángulo. Nuestra versión guarda la *beach line* en una lista: $O(n^2)$ en el peor caso, 3 ms con 83 puntos;
- se validó contra Bowyer–Watson; los casos degenerados se resuelven con una perturbación mínima;
- warp afín por triángulo con **mapeo inverso**: para cada píxel del destino se busca de dónde viene en la fuente y se lee con interpolación bilineal propia. Esto lo usan la barba, el corte, Fiesta y la galería.

**Código:** `backend/app/core/geometry/delaunay_fortune.py`.

**Última frase:** «Sobre esta malla deformamos barbas reales».

## 3. Barba con plantillas reales (Gianpier, 1:30)

**Pantalla:** «Barba: el proceso», «Barba con plantillas reales» y la app aplicando los cuatro estilos.

**Tiene que quedar claro:**
- las 10 plantillas salen de CelebAMask-HQ, con su alfa de pelo y su tono de piel;
- cada triángulo de la plantilla se lleva a tu cara con la afín del bloque anterior;
- recoloreo en YCrCb con un desplazamiento (no un reemplazo), para conservar los pelos;
- las tres capas: multiply (no tapa la luz de la piel), hebras con Bézier y detalle de alta frecuencia.

**Código:** `backend/app/core/compositing/beard.py`.

**Última frase:** «Además de la barba, el pelo: Kalos explica el tinte y el corte».

## 4. Tinte, corte y forma de cara (Kalos, 3:00)

**Primera frase:** «Con la misma malla, ahora el pelo».

**Pantalla:** «Tinte: el proceso» y «Tinte en CIELAB»; Tinte en rubio y en azul, cambiando entre «YOLO propio» y «MediaPipe». Después «Corte: el proceso», «Cortar el pelo», Corte con dos estilos, combinar barba + tinte + corte y la ficha para el barbero.

**Tiene que quedar claro (tinte, 1:30):**
- por qué CIELAB y no HSV: separa la luminosidad del color, así un pelo negro puede quedar rubio sin perder los mechones;
- la máscara de YOLO pasa por dos filtros guiados con la foto como guía: queda suave y sin agujeros;
- la luminosidad se recorta al rango del propio pelo y se separa en tres bandas (detalle, mechones y sombreado); el croma baja en las sombras, como un pigmento real;
- YOLOv8n-seg ajustado con Figaro1k y CelebAMask-HQ en Colab: mAP50 de máscara de 0,968; la app mide la IoU entre YOLO y MediaPipe en cada foto.

**Tiene que quedar claro (corte y forma de cara, 1:30):**
- el problema: hay que quitar pelo y reconstruir lo que había detrás;
- Telea falla porque toma color del mismo pelo; **pull-push** rellena con una pirámide usando solo el fondo seguro;
- el cráneo es una superelipse ajustada a la coronilla y el pelo corto se sombrea con Lambert usando la luz estimada de la cara;
- la forma de la cara se mide sobre la malla 3D con umbrales calibrados en 419 caras, y sugiere estilos.

**Código:** `backend/app/core/coloring/dye.py` y `backend/app/core/compositing/haircut.py`.

**Última frase:** «Todo esto también funciona con la cámara. Gianpier explica el modo en vivo».

## 5. En vivo: barba sobre la malla 3D y física (Gianpier, 1:45)

**Primera frase:** «Lo mismo, pero a 10 cuadros por segundo».

**Pantalla:** «En vivo: el proceso», En vivo → Barba girando la cabeza, «Depurar: ver malla y zona» un momento, y «Física de barba».

**Tiene que quedar claro:**
- seguimiento en video y filtro One-Euro contra el temblor;
- la barba en vivo es una textura sobre la malla 3D: se descartan los triángulos que dan la espalda y el resto se pinta de atrás hacia adelante, así la región no se aplasta al girar;
- física: cuatro partículas por pelo, Verlet amortiguado, resorte a la pose y restricción de distancia (PBD);
- el Contrarreloj y la física usan esta misma barba en vivo.

**Código:** `backend/app/core/compositing/beard_mesh.py` y `beard_physics.py`.

**Última frase:** «Para pasar a 3D necesitamos otra forma de representar la cara: gaussianas».

## 6. Gaussianas 2D y Espejo 3D (Gianpier, 2:00)

**Primera frase:** «Una gaussiana es una manchita con posición, forma y color».

**Pantalla:** «Gaussianas 2D: el proceso», Juegos → Gaussianas cambiando a «Elipses»; después «Espejo 3D: el proceso», 3D → Espejo 3D girando, «Ver cada gaussiana» y descargar el `.ply`.

**Tiene que quedar claro:**
- 2D: cada gaussiana tiene centro, color y el factor de Cholesky de la inversa de la covarianza (así siempre es válida); gradientes analíticos y Adam escrito a mano, sin PyTorch; el PSNR sube unos 8 dB cada vez que se multiplican por 10;
- 3D: gaussianas construidas desde una foto y la malla 3D (no es un 3DGS entrenado);
- proyección EWA $\Sigma_{2D}=JW\Sigma W^\top J^\top$ en el *vertex shader*, ordenamiento de atrás hacia adelante con *counting sort* y mezcla alfa, todo en un visor propio de WebGL2.

**Código:** `backend/app/core/splatting/gaussian_image.py` y `frontend/js/splat3d.js`.

**Última frase:** «Con estas gaussianas 3D, Sofía arma pelucas».

## 7. Peluca 3D y Laboratorio (Sofía, 2:00)

**Primera frase:** «Si una cara se puede hacer con gaussianas, un peinado también».

**Pantalla:** «Peluca 3D: el proceso» y «Peluca 3D»; 3D → Peluca 3D: escaneo de 12 s, la peluca girando sobre tu cara con los hombros, «Mi cara / Maniquí / Solo pelo», color, largo y tijeras (se ven caer los pelos). Después «Laboratorio» y el avatar en vivo.

**Tiene que quedar claro:**
- la máscara de pelo de cada captura y el ángulo de giro;
- envolvente visual por cortes: en cada altura y dirección, cada vista limita dónde hay pelo; la intersección da la forma;
- la textura sale de las vistas que mejor ven cada punto; el pelo se orienta con el tensor de estructura;
- la cara escaneada: discos tangentes orientados con la normal de los vértices interpolada (sombreado de Phong), para que no se vean triángulos;
- el busto: una superelipse con el color de tu ropa; cara, maniquí o solo pelo cambian al instante porque el servidor arma todo una vez;
- el laboratorio: gaussianas guardadas en el marco local de cada triángulo $R=[e_1\;e_2\;n]$, que siguen a la cara en vivo; el color se ajusta con Adam dentro de $\pm0{,}04$ del color fusionado para que no salgan vetas.

**Código:** `backend/app/core/splatting/hair3d.py` y `backend/app/core/lab/avatar.py`.

**Última frase:** «Para ver también la nuca, Gianpier agregó la vuelta completa en una silla».

## 8. Peluca en una vuelta y Contrarreloj (Gianpier, 1:30)

**Primera frase:** «El escaneo de 180° no ve la nuca».

**Pantalla:** «Peluca en una vuelta», 3D → Peluca 3D → «Empezar escaneo 360°» con alguien girando en una silla (se escucha la guía por voz). Después «Contrarreloj: el proceso» y una ronda con el dedo.

**Tiene que quedar claro:**
- de espaldas no hay cara, así que el giro se mide con flujo óptico: la cabeza es una esfera que gira sobre un eje vertical y cada punto vota por $\Delta\theta=\arcsin u_1-\arcsin u_0$; se toma la mediana;
- los cuadros con la cara a la vista fijan el ángulo real y un ajuste por mínimos cuadrados reparte el error del resto de la vuelta; de cada tramo de 12° se elige el cuadro más nítido;
- la vuelta se guía con voz y sonidos, y si falla dice por qué;
- Contrarreloj: la máquina corta con el índice extendido; a 10 fps el dedo salta, así que se corta todo lo que toca la **cápsula** entre dos cuadros; puntaje = limpieza × conservación × 1000.

**Código:** `backend/app/core/splatting/turntable.py` y `backend/app/core/game/speedrun.py`.

**Última frase:** «Y para el final, lo más divertido: Kalos con la galería y Fiesta».

## 9. Galería, El practicante y Fiesta (Kalos, 3:15)

**Primera frase:** «La misma malla del inicio sirve para jugar con las caras».

**Pantalla:** «Galería: barbas famosas» y la Galería con la foto de ejemplo; El practicante tirando los dados; después «Fiesta: el proceso», «Cambio de cara» y «Caricatura y fusión», y Fiesta en vivo con Gianpier y Kalos frente a la cámara (Sofía maneja la laptop).

| Tiempo del bloque | Mostrar | Decir |
|---|---|---|
| 0:00 – 0:30 | Galería: tu cara en Marx, Lincoln y Van Gogh | Tu cara entra al retrato con el mismo cambio de cara; la barba del retrato queda encima, las fotos antiguas pasan a blanco y negro y Van Gogh se repinta con el filtro de Kuwahara usando imágenes integrales. |
| 0:30 – 0:45 | El practicante | Elige barba, tinte y corte al azar y los encadena sobre la misma foto. |
| 0:45 – 1:25 | Cambio de cara, «Entre ustedes» | Malla de 468 puntos con la triangulación calculada una vez, con nuestro Fortune, sobre una cara promedio: el triángulo i es la misma parte de la cara en los dos. Afín por triángulo con mapeo inverso y bilineal. Los triángulos que dan la espalda se descartan y esa mejilla se rellena en espejo. |
| 1:25 – 1:50 | «Una cara para todos» con el astronauta | El color se iguala con Reinhard en Lab y la cara se pega con una mezcla multibanda (pirámides laplacianas): por eso no se ve la costura. |
| 1:50 – 2:25 | Caricatura: «Caricatura», «Narizón» y «Alien» | Fórmula de Brennan: $P' = A + (1+k)(P-A)$, con $A$ la cara promedio ajustada por Umeyama. Crece lo que te hace distinto. |
| 2:25 – 3:15 | Fusión: «Kalos» y «Gianpier», «Foto a los dos en 3 s», mover el deslizador y «Animar» | Las dos caras se deforman a la forma intermedia $(1-t)A+tB$ y **solo se mezcla la cara**, que entra con la pirámide laplaciana sobre la foto de uno. Al principio se mezclaban las fotos enteras y salían fantasmas: el pelo y los hombros de los dos a la vez. A la mitad nace Kalpier. |

**Tiene que quedar claro:** todo corre en CPU a unos 15 cuadros por segundo; lo único que viene de un modelo son los puntos; el límite es la cabeza muy girada.

**Código:** `backend/app/core/faces/swap.py` y `backend/app/core/faces/morph.py`.

**Fiesta:** luz de frente, los dos a la misma distancia y Kalos a la izquierda de la pantalla (si no, el hijo se llama Gianlos).

**Última frase:** «Sofía cierra con cómo lo probamos y qué falta».

## 10. Resultados, límites y cierre (Sofía, 1:00)

**Pantalla:** «Calidad y rendimiento» y «Límites que conocemos».

**Decir:**
- se probó en 26 caras distintas (piel clara, morena y negra; pelo liso, rizado, largo y corto); 123 pruebas automáticas en cada cambio;
- tiempos de 0,1 a 2,5 s por foto; Fiesta a unos 15 cuadros por segundo;
- límites honestos: oclusiones, pelo que tapa ojos u orejas, el espejo 3D desde una sola vista, unos 10 fps en vivo y las poses muy giradas;
- lo siguiente: el tinte en vivo con un *shader* de WebGL;
- cierre: «Fresh: pruébate el look antes del corte».

---

## Producción

- **Grabar:** QuickTime (Cmd+Shift+5 → «Grabar toda la pantalla», micrófono de la Mac) u OBS, a 1080p. Un bloque por toma; si alguien se equivoca, repite solo ese bloque.
- **Antes de grabar:** levantar la app y entrar una vez a cada herramienta para que carguen los modelos. Tener las diapositivas abiertas a pantalla completa.
- **Entregar los clips:** en `delivery/videos/clips/`, con el número delante. Se unen en orden, con una cortinilla de un segundo entre bloques (sección y quién habla), y se exporta a `delivery/videos/video-largo.mp4` en MP4 (H.264, AAC).
- **Si pesa mucho:** `ffmpeg -i entrada.mov -vf "scale=-2:1080" -c:v libx264 -crf 24 -c:a aac -b:a 128k -movflags +faststart video-largo.mp4`.
- **Revisar la duración:** debe durar menos de 20:00; `python3 delivery/verificar.py` lo comprueba.
