# Guion del video largo

Duración máxima: **20 minutos**. El plan suma unos 19 minutos. Archivo final: `delivery/videos/video-largo.mp4`.

Cada integrante explica los módulos que hizo, según la tabla de aportes del informe; ajusten los turnos si cambian esa tabla. La rúbrica premia que cada uno **domine y defienda** su parte, así que cada bloque dice qué conceptos tienen que quedar claros. Conviene alternar las diapositivas (`slides/main.pdf`) con la app corriendo.

| # | Tiempo | Quién | Bloque |
|---|---|---|---|
| 1 | 0:00 – 1:00 | Kalos | Problema y equipo |
| 2 | 1:00 – 2:30 | Kalos | Arquitectura y producto |
| 3 | 2:30 – 4:30 | Gianpier | Puntos de la cara y Delaunay de Fortune |
| 4 | 4:30 – 6:30 | Gianpier | Barba con plantillas reales |
| 5 | 6:30 – 8:00 | Gianpier | Modo en vivo y física |
| 6 | 8:00 – 9:45 | Kalos | Tinte en CIELAB y YOLO propio |
| 7 | 9:45 – 12:15 | Kalos | Motor de cortes, combinación y forma de cara |
| 8 | 12:15 – 13:30 | Gianpier | Gaussianas 2D |
| 9 | 13:30 – 15:00 | Gianpier | Espejo 3D |
| 10 | 15:00 – 17:00 | Sofía | Peluca 3D y laboratorio |
| 11 | 17:00 – 18:00 | Sofía | Contrarreloj |
| 12 | 18:00 – 19:00 | Sofía | Resultados, límites y cierre |

---

## 1. Problema y equipo (Kalos, 1:00)

**Pantalla:** portada de las diapositivas, después la lámina «El problema».

**Decir:** elegir un corte o una barba es una decisión a ciegas. Las apps que existen pegan una imagen encima o generan una cara nueva con IA y pierden la identidad. Fresh modela la geometría de la cara y del pelo de la persona y compone sobre la foto original, todo en CPU. Presentar a los tres y qué hizo cada uno.

## 2. Arquitectura y producto (Kalos, 1:30)

**Pantalla:** lámina «Arquitectura», luego la terminal con `docker compose up -d --build app` y el navegador en `localhost:8000`.

**Decir:**
- un solo proceso de FastAPI sirve la interfaz y la API;
- los endpoints son delgados; la lógica gráfica está en `backend/app/core`, un paquete por técnica;
- la interfaz es HTML y JavaScript sin compilación; el 3D es un visor propio en WebGL2;
- 53 pruebas automáticas, integración continua en GitHub y Docker para reproducirlo con un comando.

**Mostrar:** subir una foto una vez y ver que queda cargada en todas las herramientas.

## 3. Puntos de la cara y Delaunay de Fortune (Gianpier, 2:00)

**Pantalla:** lámina de Delaunay, después Barba con «Mostrar la malla de triángulos».

**Tiene que quedar claro:**
- MediaPipe da 478 puntos y es lo único que viene de un modelo; se convierten a los 68 puntos estándar y se agregan 15 bajo la mandíbula;
- qué es Delaunay: ningún punto cae dentro del círculo circunscrito de un triángulo, lo que evita triángulos finos;
- cómo funciona Fortune: línea de barrido, *beach line* de parábolas, evento de sitio y evento de círculo; cada evento de círculo da un triángulo;
- complejidad: el algoritmo es $O(n\log n)$ con un árbol balanceado; nuestra versión guarda la *beach line* en una lista, así que es $O(n^2)$ en el peor caso (3 ms con 83 puntos);
- se validó contra Bowyer–Watson: Fortune encuentra un triángulo fino del borde de la mandíbula que Bowyer–Watson pierde por su supertriángulo;
- los casos degenerados (grilla) se resuelven con una perturbación mínima de los puntos.

## 4. Barba con plantillas reales (Gianpier, 2:00)

**Pantalla:** lámina de la barba y la app aplicando los cuatro estilos.

**Tiene que quedar claro:**
- las 10 plantillas salen de CelebAMask-HQ, con su alfa de pelo y su tono de piel;
- warp afín por triángulo: se resuelve la afín inversa, se recorre cada píxel del triángulo destino, se prueba con baricéntricas y se lee con interpolación bilineal propia;
- recoloreo en YCrCb con un desplazamiento (no un reemplazo), para conservar los pelos;
- las tres capas: multiply (por qué no tapa la luz de la piel), hebras con Bézier y detalle de alta frecuencia (por qué no Poisson).

## 5. Modo en vivo y física (Gianpier, 1:30)

**Pantalla:** En vivo → Barba, luego «Física de barba», moviendo la cabeza.

**Tiene que quedar claro:**
- seguimiento en video y filtro One-Euro contra el temblor;
- la textura anclada a la malla con baricéntricas, para que no «nade»;
- física: cuatro partículas por pelo, Verlet amortiguado, resorte a la pose y restricción de distancia (PBD); por qué se usa Verlet;
- cada tramo se dibuja como una gaussiana y se acumula con $1-e^{-A}$.

## 6. Tinte en CIELAB y YOLO propio (Kalos, 1:45)

**Pantalla:** Tinte con la foto de ejemplo; cambiar entre «YOLO propio» y «MediaPipe» y mostrar la nota de coincidencia.

**Tiene que quedar claro:**
- por qué CIELAB y no HSV: separa la luminosidad del color, así un pelo negro puede quedar rubio;
- la fórmula: luminosidad base hacia el tinte más el detalle de los mechones, con contraste normalizado; el croma baja en las sombras;
- YOLOv8n-seg ajustado con Figaro1k y CelebAMask-HQ en Colab, con mAP50 de máscara de 0,968; filtro guiado para pegar la máscara al borde;
- la app mide la IoU entre YOLO y MediaPipe en cada foto.

## 7. Motor de cortes, combinación y forma de cara (Kalos, 2:30)

**Pantalla:** lámina «Cortar el pelo» (Telea frente a pull-push), luego Corte con 2 o 3 estilos, la combinación barba + tinte + corte y la ficha.

**Tiene que quedar claro:**
- el problema: hay que quitar pelo y reconstruir lo que había detrás;
- por qué Telea falla (toma color del pelo) y cómo funciona pull-push (pirámide, solo píxeles de fondo seguro);
- el marco de la cabeza en anchos de cabeza; el cráneo como superelipse ajustada a la coronilla; la línea del pelo desde la frente visible o asumida si hay flequillo;
- el pelo corto: color propio, sombreado de Lambert con la luz estimada de la cara;
- cada corte cambia dónde empieza la piel (tabla de parámetros);
- forma de la cara: medidas sobre la malla 3D y umbrales calibrados con 419 caras.

## 8. Gaussianas 2D (Gianpier, 1:15)

**Pantalla:** Juegos → Gaussianas con el modo de adivinar; cambiar a «Elipses».

**Tiene que quedar claro:**
- cada gaussiana tiene centro, color y el factor de Cholesky de la inversa de la covarianza (por qué así queda siempre válida);
- gradientes analíticos y Adam escrito a mano, sin PyTorch;
- el PSNR sube unos 8 dB cada vez que el número de gaussianas se multiplica por 10.

## 9. Espejo 3D (Gianpier, 1:30)

**Pantalla:** 3D → Espejo 3D con barba completa; girar, «Ver cada gaussiana», descargar el `.ply`.

**Tiene que quedar claro:**
- gaussianas construidas desde una foto y la malla 3D (discos tangentes por área 3D, hebras de barba, relieve del entorno); no es un 3DGS entrenado;
- proyección EWA $\Sigma_{2D}=JW\Sigma W^\top J^\top$ en el vertex shader, quad de $\pm3\sigma$, ordenamiento con counting sort y mezcla de atrás hacia adelante;
- el `.ply`: escala y cuaternión, armónicos de grado 0 y opacidad en logit;
- el límite: sin nuca, y el relieve se estira al girar mucho.

## 10. Peluca 3D y laboratorio (Sofía, 2:00)

**Pantalla:** 3D → Peluca 3D: escaneo de 12 s, Mis pelucas, la peluca 3D; usar color, largo y tijeras. Luego el laboratorio.

**Tiene que quedar claro:**
- la máscara de pelo de cada captura y el ángulo de giro;
- envolvente visual por cortes: en cada altura y dirección, cada vista limita dónde hay pelo; la intersección da el corte real;
- la textura de las vistas que mejor ven cada punto, y la nuca sintetizada;
- la orientación del pelo con el tensor de estructura;
- el estudio: recolorear, cortar por altura y tijeras que eligen las gaussianas más cercanas a la cámara;
- el laboratorio: gaussianas guardadas en el marco local de cada triángulo, que siguen a la cara en vivo.

## 11. Contrarreloj (Sofía, 1:00)

**Pantalla:** Juegos → Contrarreloj; jugar una ronda con el dedo.

**Tiene que quedar claro:**
- la máquina corta con el índice extendido y el medio doblado;
- por qué se usa una cápsula entre dos cuadros (a 10 fps el dedo salta);
- el puntaje es limpieza por conservación por 1000, y por qué no se usó IoU.

## 12. Resultados, límites y cierre (Sofía, 1:00)

**Pantalla:** láminas «Calidad y rendimiento» y «Límites que conocemos».

**Decir:**
- se probó en 26 caras distintas; hay 53 pruebas automáticas; los tiempos van de 0,1 a 2,5 s por foto;
- límites honestos: oclusiones, pelo que tapa ojos u orejas, el espejo 3D desde una vista, unos 10 fps en vivo;
- lo siguiente: tinte en vivo con un shader de WebGL.

---

## Producción

- **Grabación:** pantalla y voz con OBS o QuickTime, a 1080p. Cada uno puede grabar su bloque por separado y después se unen en orden (iMovie, DaVinci Resolve o `ffmpeg -f concat`).
- **Antes de empezar:** levantar la app y abrir cada pantalla una vez para que carguen los modelos. Tener a mano la foto de ejemplo y las capturas de `docs/captures/` como respaldo si falla la cámara.
- **Exportar:** MP4 (H.264, AAC). Si pasa de unos 500 MB, comprimirlo con HandBrake.
- **Revisar la duración:** debe durar menos de 20:00. `build_zip.py` lo comprueba si `ffprobe` está instalado.
