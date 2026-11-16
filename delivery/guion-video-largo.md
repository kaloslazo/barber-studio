# Guion del video largo

Duración máxima: **20 minutos**. El plan suma 19:30. Archivo final: `delivery/videos/video-largo.mp4`.

Cada integrante explica los módulos que hizo, según la tabla de aportes del informe y el historial de git; ajusten los turnos si cambian esa tabla. La rúbrica premia que cada uno **domine y defienda** su parte, así que cada bloque dice qué conceptos tienen que quedar claros. Conviene alternar las diapositivas (`slides/main.pdf`) con la app corriendo.

| # | Tiempo | Quién | Bloque |
|---|---|---|---|
| 1 | 0:00 – 0:45 | Kalos | Problema y equipo |
| 2 | 0:45 – 2:00 | Kalos | Arquitectura y producto |
| 3 | 2:00 – 3:45 | Gianpier | Puntos de la cara y Delaunay de Fortune |
| 4 | 3:45 – 5:30 | Gianpier | Barba con plantillas reales |
| 5 | 5:30 – 7:15 | Gianpier | Modo en vivo, barba sobre la malla 3D y física |
| 6 | 7:15 – 8:45 | Kalos | Tinte en CIELAB y YOLO propio |
| 7 | 8:45 – 10:30 | Kalos | Motor de cortes, combinación y forma de cara |
| 8 | 10:30 – 11:30 | Gianpier | Gaussianas 2D |
| 9 | 11:30 – 12:45 | Gianpier | Espejo 3D |
| 10 | 12:45 – 14:30 | Sofía | Peluca 3D y laboratorio |
| 11 | 14:30 – 15:15 | Gianpier | Peluca en una vuelta |
| 12 | 15:15 – 16:00 | Gianpier | Contrarreloj |
| 13 | 16:00 – 18:30 | Kalos | Fiesta: cambio de cara, caricatura y fusión |
| 14 | 18:30 – 19:30 | Sofía | Resultados, límites y cierre |

Por persona: Kalos 7:45, Gianpier 9:00, Sofía 2:45.

---

## 1. Problema y equipo (Kalos, 0:45)

**Pantalla:** portada de las diapositivas, después la lámina «El problema».

**Decir:** elegir un corte o una barba es una decisión a ciegas. Las apps que existen pegan una imagen encima o generan una cara nueva y pierden la identidad. Fresh modela la geometría de la cara y del pelo de la persona y compone sobre la foto original, todo en CPU. Presentar a los tres y qué hizo cada uno.

## 2. Arquitectura y producto (Kalos, 1:15)

**Pantalla:** láminas «Arquitectura» y «El pipeline completo», luego la terminal con `docker compose up -d --build app` y el navegador en `localhost:8000`.

**Decir:**
- un solo proceso de FastAPI sirve la interfaz y la API;
- los endpoints son delgados; la lógica gráfica está en `backend/app/core`, un paquete por técnica;
- la interfaz es HTML y JavaScript sin compilación; el 3D es un visor propio en WebGL2;
- 121 pruebas automáticas, integración continua en GitHub y Docker para reproducirlo con un comando.

**Mostrar:** subir una foto una vez y ver que queda cargada en todas las herramientas.

## 3. Puntos de la cara y Delaunay de Fortune (Gianpier, 1:45)

**Pantalla:** lámina de Delaunay, después Barba con «Mostrar la malla de triángulos».

**Tiene que quedar claro:**
- MediaPipe da 478 puntos y es lo único que viene de un modelo; se convierten a los 68 puntos estándar y se agregan 15 bajo la mandíbula;
- qué es Delaunay: ningún punto cae dentro del círculo circunscrito de un triángulo, lo que evita triángulos finos;
- cómo funciona Fortune: línea de barrido, *beach line* de parábolas, evento de sitio y evento de círculo; cada evento de círculo da un triángulo;
- complejidad: el algoritmo es $O(n\log n)$ con un árbol balanceado; nuestra versión guarda la *beach line* en una lista, así que es $O(n^2)$ en el peor caso (3 ms con 83 puntos);
- se validó contra Bowyer–Watson: Fortune encuentra un triángulo fino del borde de la mandíbula que Bowyer–Watson pierde por su supertriángulo;
- los casos degenerados (grilla) se resuelven con una perturbación mínima de los puntos.

## 4. Barba con plantillas reales (Gianpier, 1:45)

**Pantalla:** lámina «Barba: el proceso», la lámina de la barba y la app aplicando los cuatro estilos.

**Tiene que quedar claro:**
- las 10 plantillas salen de CelebAMask-HQ, con su alfa de pelo y su tono de piel;
- warp afín por triángulo: se resuelve la afín inversa, se recorre cada píxel del triángulo destino, se prueba con baricéntricas y se lee con interpolación bilineal propia;
- recoloreo en YCrCb con un desplazamiento (no un reemplazo), para conservar los pelos;
- las tres capas: multiply (por qué no tapa la luz de la piel), hebras con Bézier y detalle de alta frecuencia (por qué no Poisson).

## 5. Modo en vivo, barba sobre la malla 3D y física (Gianpier, 1:45)

**Pantalla:** lámina «En vivo: el proceso», luego En vivo → Barba girando la cabeza, con «Depurar: ver malla y zona» un momento, y después «Física de barba».

**Tiene que quedar claro:**
- seguimiento en video y filtro One-Euro contra el temblor;
- la barba en vivo es una textura sobre la malla 3D: cada vértice guarda su UV en un cuadro de frente; en cada cuadro se descartan los triángulos que dan la espalda y el resto se pinta de atrás hacia adelante, así lo que queda detrás de la nariz se tapa y la región no se aplasta al girar, como pasaba con los 68 puntos proyectados;
- la vista de depuración dibuja la malla y la región, y la tecla F guarda los cuadros de un fallo;
- física: cuatro partículas por pelo, Verlet amortiguado, resorte a la pose y restricción de distancia (PBD); por qué se usa Verlet;
- cada tramo se dibuja como una gaussiana y se acumula con $1-e^{-A}$.

## 6. Tinte en CIELAB y YOLO propio (Kalos, 1:30)

**Pantalla:** lámina «Tinte: el proceso», luego Tinte con la foto de ejemplo en rubio y en negro; cambiar entre «YOLO propio» y «MediaPipe» y mostrar la nota de coincidencia.

**Tiene que quedar claro:**
- por qué CIELAB y no HSV: separa la luminosidad del color, así un pelo negro puede quedar rubio;
- el matte: la máscara cruda de YOLO pasa por dos filtros guiados con la foto como guía; queda suave y sin agujeros (los puntos negros de antes eran huecos de la máscara por donde asomaba el pelo original);
- la luminosidad se recorta al rango del propio pelo (percentiles 3 a 97) y se separa en tres bandas: detalle, mechones finos y sombreado; la base va el 82 % hacia el tinte y las bandas se escalan por cuánto se aclara el pelo;
- el croma baja en las sombras, como un pigmento real;
- YOLOv8n-seg ajustado con Figaro1k y CelebAMask-HQ en Colab, con mAP50 de máscara de 0,968; la app mide la IoU entre YOLO y MediaPipe en cada foto.

## 7. Motor de cortes, combinación y forma de cara (Kalos, 1:45)

**Pantalla:** lámina «Corte: el proceso», la lámina «Cortar el pelo» (Telea frente a pull-push), luego Corte con 2 estilos, la combinación barba + tinte + corte y la ficha.

**Tiene que quedar claro:**
- el problema: hay que quitar pelo y reconstruir lo que había detrás;
- por qué Telea falla (toma color del pelo) y cómo funciona pull-push (pirámide, solo píxeles de fondo seguro);
- el marco de la cabeza en anchos de cabeza; el cráneo como superelipse ajustada a la coronilla; la línea del pelo desde la frente visible o asumida si hay flequillo;
- el pelo corto: color propio, sombreado de Lambert con la luz estimada de la cara;
- forma de la cara: medidas sobre la malla 3D y umbrales calibrados con 419 caras.

## 8. Gaussianas 2D (Gianpier, 1:00)

**Pantalla:** lámina «Gaussianas 2D: el proceso», luego Juegos → Gaussianas con el modo de adivinar; cambiar a «Elipses».

**Tiene que quedar claro:**
- cada gaussiana tiene centro, color y el factor de Cholesky de la inversa de la covarianza (por qué así queda siempre válida);
- gradientes analíticos y Adam escrito a mano, sin PyTorch;
- el PSNR sube unos 8 dB cada vez que el número de gaussianas se multiplica por 10.

## 9. Espejo 3D (Gianpier, 1:15)

**Pantalla:** lámina «Espejo 3D: el proceso», luego 3D → Espejo 3D con barba completa; girar, «Ver cada gaussiana», descargar el `.ply`.

**Tiene que quedar claro:**
- gaussianas construidas desde una foto y la malla 3D (discos tangentes por área 3D, hebras de barba, relieve del entorno); no es un 3DGS entrenado;
- proyección EWA $\Sigma_{2D}=JW\Sigma W^\top J^\top$ en el vertex shader, quad de $\pm3\sigma$, ordenamiento con counting sort y mezcla de atrás hacia adelante;
- el `.ply`: escala y cuaternión, armónicos de grado 0 y opacidad en logit;
- el límite: sin nuca, y el relieve se estira al girar mucho.

## 10. Peluca 3D y laboratorio (Sofía, 1:45)

**Pantalla:** lámina «Peluca 3D: el proceso», luego 3D → Peluca 3D: escaneo de 12 s, Mis pelucas, la peluca 3D; usar color, largo y tijeras. Luego el laboratorio.

**Tiene que quedar claro:**
- la máscara de pelo de cada captura y el ángulo de giro;
- envolvente visual por cortes: en cada altura y dirección, cada vista limita dónde hay pelo; la intersección da el corte real;
- la textura de las vistas que mejor ven cada punto, y la nuca sintetizada;
- la orientación del pelo con el tensor de estructura;
- el estudio: recolorear, cortar por altura y tijeras que eligen las gaussianas más cercanas a la cámara;
- el laboratorio: gaussianas guardadas en el marco local de cada triángulo, que siguen a la cara en vivo.

## 11. Peluca en una vuelta (Gianpier, 0:45)

**Pantalla:** 3D → Peluca 3D, pestaña «Peluca 3D»: «Empezar escaneo 360°» con alguien girando en una silla, o «Usar un video de una vuelta». Mostrar la peluca que sale.

**Tiene que quedar claro:**
- de espaldas no hay cara, así que MediaPipe no da el giro;
- la cabeza se trata como una esfera que gira sobre un eje vertical: cada punto seguido entre dos cuadros vota por un ángulo, Δθ = asin(u₁) − asin(u₀), y se toma la mediana;
- sumar giros acumula error: los cuadros con la cara a la vista fijan el ángulo real y un ajuste por mínimos cuadrados reparte la corrección en el resto de la vuelta;
- de cada tramo de ángulo se elige el mejor cuadro, y esas vistas entran al mismo constructor de la peluca del bloque anterior (`build_hair_splats`).

## 12. Contrarreloj (Gianpier, 0:45)

**Pantalla:** lámina «Contrarreloj: el proceso», luego Juegos → Contrarreloj; jugar una ronda con el dedo.

**Tiene que quedar claro:**
- la máquina corta con el índice extendido y el medio doblado;
- por qué se usa una cápsula entre dos cuadros (a 10 fps el dedo salta);
- el puntaje es limpieza por conservación por 1000, y por qué no se usó IoU.

## 13. Fiesta: cambio de cara, caricatura y fusión (Kalos, 2:30)

**Pantalla:** la app, grupo Fiesta. Kalos y Gianpier frente a la cámara; Sofía maneja la laptop.

| Tiempo del bloque | Mostrar | Decir |
|---|---|---|
| 0:00 – 0:40 | Cambio de cara, «Entre ustedes»: Kalos y Gianpier con la cara cambiada, moviéndose | Cada cara es una malla de 468 puntos. La triangulación se calcula una vez, con nuestro Fortune, sobre una cara promedio de 400 personas, así el triángulo i es la misma parte de la cara en los dos. Cada píxel de destino se lleva a la fuente con la afín de su triángulo (mapeo inverso) y se lee con bilineal. |
| 0:40 – 1:05 | «Una cara para todos» con «La del astronauta»: los dos con la cara del astronauta | El color se iguala con la transferencia de Reinhard en Lab y la cara se pega con una mezcla multibanda: pirámides laplacianas de las dos fotos y gaussiana de la máscara. Por eso no se ve costura. |
| 1:05 – 1:45 | Caricatura: «Caricatura» al 100 %, luego «Narizón» y «Alien» | La caricatura es la fórmula de Brennan: P' = A + (1 + k)(P − A), con A la cara promedio ajustada por mínimos cuadrados (Umeyama). Crece lo que te hace distinto. Un anillo de 28 puntos fijos deja quieto el resto de la foto. |
| 1:45 – 2:30 | Fusión: nombres «Kalos» y «Gianpier», «Foto a los dos en 3 s», mover el slider y «Animar» | Morphing clásico: las dos fotos se deforman a la malla intermedia (1 − t)A + tB y recién ahí se mezclan. Si se mezclaran sin deformar, el hijo tendría cuatro ojos. A la mitad nace Kalpier. |

**Tiene que quedar claro:**
- todo corre en CPU: unos 15 cuadros por segundo en el servidor (cambio de cara 44 ms y caricatura 49 ms por cuadro de 640 × 360 con dos caras);
- lo único que viene de un modelo son los 468 puntos; la triangulación, el warp, el color, la mezcla, la caricatura y el morph son nuestros;
- el límite: con la cabeza muy girada, los triángulos de la mejilla lejana se enciman y esa parte se estira.

## 14. Resultados, límites y cierre (Sofía, 1:00)

**Pantalla:** láminas «Calidad y rendimiento» y «Límites que conocemos».

**Decir:**
- se probó en 26 caras distintas; hay 121 pruebas automáticas; los tiempos van de 0,1 a 2,5 s por foto, y Fiesta corre a unos 15 cuadros por segundo;
- el tinte nuevo se revisó en 8 caras con 7 colores, sin puntos negros;
- límites honestos: oclusiones, pelo que tapa ojos u orejas, el espejo 3D desde una vista, unos 10 fps en vivo, y en Fiesta las poses muy giradas;
- lo siguiente: tinte en vivo con un shader de WebGL.

---

## Producción

- **Grabación:** pantalla y voz con OBS o QuickTime, a 1080p. Cada uno puede grabar su bloque por separado y después se unen en orden (iMovie, DaVinci Resolve o `ffmpeg -f concat`).
- **Antes de empezar:** levantar la app y abrir cada pantalla una vez para que carguen los modelos. Tener a mano la foto de ejemplo y las capturas de `docs/captures/` como respaldo si falla la cámara.
- **Fiesta:** grabar con luz de frente y las dos caras a la misma distancia de la cámara. En Fusión, Kalos a la izquierda de la pantalla (si no, el hijo se llama Gianlos).
- **Exportar:** MP4 (H.264, AAC). Si pasa de unos 500 MB, comprimirlo con HandBrake.
- **Revisar la duración:** debe durar menos de 20:00. `build_zip.py` lo comprueba si `ffprobe` está instalado.
