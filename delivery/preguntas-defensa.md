# Preguntas para la defensa

El criterio que más pesa en la P2 es «Dominio y aporte técnico en Computación Gráfica» (11 de 20 puntos). Para el «Sobresaliente», cada integrante tiene que explicar con rigor los fundamentos, el código, las decisiones y los límites de su parte, y responder preguntas sobre casos límite y sobre cómo modificaría o extendería lo que hizo.

Este archivo junta las preguntas más probables, con una respuesta corta y el archivo donde está cada cosa. Las secciones siguen la tabla de aportes del informe (sección 3.3).

**Cómo usarlo**

1. Cada uno estudia su sección con el código abierto al lado. Si una respuesta no coincide con el código, manda el código.
2. Ensayen en pareja: uno pregunta en desorden y el otro responde sin leer.
3. Respondan en tres pasos: **qué hace**, **por qué así y no de otra forma**, **dónde falla**. Reconocer un límite suma; inventar resta.
4. Si no saben algo, digan cómo lo averiguarían o cómo lo cambiarían.

> **Ojo con el Contrarreloj.** El guion del video largo se lo da a Sofía, pero la tabla de aportes y el historial de git dicen que lo hizo Gianpier. Alineen eso antes de grabar: quien lo presente tiene que poder defenderlo. Aquí está en la sección de Gianpier.

---

## Para todo el equipo (responde Kalos primero)

**¿Qué parte es computación gráfica y qué parte es deep learning?**
Los modelos responden una sola pregunta: dónde están la cara, el pelo y la mano. Son 3 modelos de MediaPipe sin entrenar y un YOLO que entrenamos para el pelo. Todo lo que se ve en pantalla lo calcula código nuestro: Delaunay, warp, tinte, cortes, física, gaussianas 2D y 3D, y el visor WebGL2. En el núcleo hay unas 4000 líneas de gráfica propia contra unas 600 que llaman a modelos (cerca del 87 %). La tabla 1 del informe lo relaciona con cada tema del sílabo.

**¿Por qué no usaron un modelo generativo (GAN o difusión) para el corte o la barba?**
Porque inventa la cara completa: cambia la identidad, la piel y la luz, y necesita GPU. Nosotros modelamos la geometría de la cara y del pelo y componemos sobre la foto original. El resultado es determinista, explicable paso a paso y corre en CPU.

**¿Qué pasa si MediaPipe no encuentra la cara?**
La API responde 422 y la interfaz muestra el mensaje. En vivo se reutilizan los últimos puntos hasta tres cuadros, desplazados por correlación de fase. Sin puntos no hay malla, así que no se aplica ningún estilo: es la única dependencia fuerte.

**¿Cómo saben que funciona?**
Con 54 pruebas automáticas que corren en GitHub Actions en cada cambio, con recorridos completos en Chrome controlado por código y con revisión visual en 26 caras distintas: piel clara, morena y negra; pelo liso, rizado, largo y corto.

**¿Por qué todo en CPU?**
Es una restricción del proyecto: que cualquiera lo reproduzca con `docker compose up`, sin GPU. Todo está vectorizado con NumPy. La GPU solo se usa en el navegador, para el visor 3D.

---

## Gianpier: Delaunay, warp, barba, en vivo, física, gaussianas 2D, espejo 3D y Contrarreloj

### Delaunay con Fortune (`backend/app/core/geometry/delaunay_fortune.py`)

**¿Qué es una triangulación de Delaunay y por qué la usan?**
Es la triangulación en la que ningún punto cae dentro del círculo circunscrito de ningún triángulo. Entre todas las triangulaciones posibles, maximiza el ángulo mínimo, así que evita triángulos muy finos. Un triángulo fino estira mucho la textura al deformarla.

**Explica Fortune.**
Una línea de barrido baja por el plano. Sobre ella se mantiene la *beach line*: una parábola por cada punto ya visitado, con el punto como foco y la línea de barrido como directriz. Hay dos eventos en una cola de prioridad:
- **evento de sitio**: la línea toca un punto nuevo y aparece un arco que parte en dos al arco de arriba;
- **evento de círculo**: un arco se encoge a ancho cero y desaparece.

**¿Por qué cada evento de círculo es un triángulo de Delaunay?**
Cuando un arco desaparece, el punto donde se juntan sus vecinos está a la misma distancia de los tres sitios y no hay ningún otro sitio más cerca: es un vértice de Voronoi. El círculo con centro ahí que pasa por los tres sitios está vacío, que es justo la definición de triángulo de Delaunay.

**¿Por qué solo agregan el evento de círculo si el giro es en sentido horario (`_cross < 0`)?**
Solo en ese caso los dos puntos de quiebre alrededor del arco del medio se acercan y lo cierran. Con el giro contrario se alejan y el arco nunca desaparece.

**¿Cuándo se invalida un evento de círculo?**
Cuando un sitio nuevo parte el arco (`handle_site`) o cuando desaparece un vecino (`handle_circle`). Se marca `valid = False` en lugar de sacarlo del montículo, y se ignora al salir.

**¿Su implementación es O(n log n)?** *(pregunta trampa)*
No. La cola es un montículo, O(log n) por evento. Pero la *beach line* es una lista doblemente enlazada, y `find_arc_above` la recorre para ubicar el arco sobre un sitio nuevo: O(n) por sitio, O(n²) en el peor caso. Para llegar a O(n log n) hay que guardar los arcos en un árbol balanceado ordenado por los puntos de quiebre. Con 83 puntos tarda 3 ms, menos de la mitad que Bowyer–Watson.

**¿Cómo saben que está bien?**
- Las pruebas generan nubes aleatorias y verifican que ningún punto cae dentro de un círculo circunscrito y que hay 2n − 2 − h triángulos, con h el número de vértices del casco convexo (fórmula de Euler).
- Contra Bowyer–Watson: en 4 de 7 imágenes coinciden. En las otras 3, Fortune da un triángulo más, muy fino, en la mandíbula (puntos 0, 1 y 2, casi colineales). Ese triángulo es válido; Bowyer–Watson lo pierde porque su supertriángulo es finito.

**¿Qué pasa con cuatro puntos sobre el mismo círculo, o con una grilla?** *(caso límite)*
Con varios puntos a la misma altura y cuatro en un mismo círculo, el orden de los eventos se rompe y salían triángulos superpuestos. Antes del barrido se mueve cada punto una distancia aleatoria fija de una millonésima del tamaño de la nube. En una cara no se nota (medio milésimo de píxel). Con eso, una grilla de n × n da exactamente los 2n² − 2 − 4(n − 1) triángulos de la teoría. Con cuatro puntos cocirculares, cualquiera de las dos diagonales es una triangulación de Delaunay válida.

**¿Y con puntos colineales o repetidos?**
La perturbación los separa y podría formar triángulos casi sin área. Por eso, al final se descartan los triángulos sin área en las coordenadas originales. Con puntos colineales devuelve una lista vacía, y con un punto repetido lo ignora. Hay una prueba para cada caso.

### Warp afín (`backend/app/core/geometry/warp.py`)

**¿Cómo deforman la barba de la plantilla a la cara?**
Con la misma triangulación en las dos mallas: cada triángulo de la plantilla va a su triángulo en la cara con una transformación afín, que tres pares de puntos determinan.

**¿Por qué recorren el destino y no el origen (*backward mapping*)?**
Si se recorre el origen y se pinta en el destino, quedan huecos donde el triángulo se agranda. Al recorrer cada píxel del destino y preguntar de dónde leer, todos los píxeles reciben un valor.

**¿Cómo saben si un píxel está dentro del triángulo?**
Con coordenadas baricéntricas: si las tres son ≥ 0, está dentro. Es rasterización por software, como la de una GPU (tema 6.3.3.1).

**¿Por qué interpolación bilineal y no vecino más cercano o bicúbica?**
El vecino más cercano deja escalones. La bicúbica es más lenta y puede pasarse del rango (*overshoot*) en bordes fuertes. La bilineal es continua y barata.

**¿Qué pasa si un triángulo es degenerado (área cero)?**
La matriz de la afín es singular: `np.linalg.solve` falla y ese triángulo se salta. Los píxeles que caen fuera de la imagen de origen se marcan como inválidos y no se pegan.

**¿Qué pasa si la cabeza gira mucho y un triángulo se da vuelta?**
La afín tiene determinante negativo y la textura de ese triángulo sale espejada. En la foto, la triangulación se calcula sobre los puntos de la cara de destino. En vivo se calcula una vez sobre la malla de referencia y se mantiene, para que no cambie de un cuadro a otro.

### Barba (`backend/app/core/compositing/beard.py`)

**¿Por qué el modo *multiply* y no pegar la barba encima?**
*Multiply* oscurece la piel sin tapar sus luces y sombras: la luz de la foto se sigue viendo a través de la barba. Pegarla encima la vería plana y con la luz de otra persona.

**¿Por qué el color se desplaza y no se reemplaza?**
Un desplazamiento constante en YCrCb mueve toda la nube de color hacia el tono del pelo y conserva su variación interna, que son los pelos. Un reemplazo la aplanaría.

**¿Por qué no Poisson blending?**
Lo probamos. Iguala el brillo con el borde de la región y aclaraba toda la barba. En cambio se transfiere solo la alta frecuencia, plantilla − G_σ(plantilla): los pelos reales sin el brillo ni el color de la otra persona.

**¿Cómo eligen la plantilla?**
Entre las 10 plantillas del estilo pedido, la de croma de piel más parecido al del usuario, en YCrCb.

### En vivo y física (`backend/app/core/detection/one_euro.py`, `compositing/beard_physics.py`)

**¿Por qué el filtro One-Euro y no un promedio móvil?**
Un promedio móvil elimina el temblor pero se queda atrás cuando la cabeza se mueve. El One-Euro sube su frecuencia de corte con la velocidad: suaviza fuerte con la cara quieta y responde rápido cuando se mueve.

**¿Por qué las hebras guardan coordenadas baricéntricas?**
Para que la raíz siga a la piel: en cada cuadro se recalcula con los vértices nuevos del mismo triángulo. Si guardaran píxeles fijos, la barba «nadaría» sobre la cara.

**¿Por qué Verlet y no Euler explícito?**
Euler explícito con resortes rígidos y un paso grande (10 cuadros por segundo) se vuelve inestable y la cadena explota. Verlet es de segundo orden y no guarda la velocidad: la saca de la posición actual y la anterior. Eso permite imponer restricciones moviendo posiciones (PBD), que es estable aunque el paso sea grande.

**¿Qué hace el factor 0,86?**
Es el amortiguamiento: quita energía en cada subpaso. Sin él, la barba oscilaría para siempre.

**¿Para qué las restricciones de distancia?**
Para que cada tramo mantenga su largo. Así la hebra se balancea como un péndulo en vez de estirarse como un elástico. Con dos iteraciones alcanza; más iteraciones la harían más rígida y más cara.

**¿Por qué el pelo se acumula con 1 − e^(−A) sin ordenar?**
Es la ley de Beer–Lambert: muchos pelos superpuestos saturan suavemente. Como solo depende de la suma A, no importa el orden y no hay que ordenar los pelos.

### Gaussianas 2D (`backend/app/core/splatting/gaussian_image.py`)

**¿Por qué guardan el factor de Cholesky de la inversa de la covarianza y no la covarianza?**
Si se optimiza Σ directamente, un paso de gradiente puede dejarla no definida positiva, y entonces deja de ser una gaussiana. Con Σ⁻¹ = L Lᵀ y L triangular inferior, siempre es semidefinida positiva. Además, después de cada paso se fuerza l₁, l₃ ≥ un mínimo: el determinante queda positivo y la gaussiana no crece sin límite.

**Deriva un gradiente.**
Con u = l₁dₓ + l₂d_y, v = l₃d_y y q = u² + v², G = e^(−q/2). Entonces ∂q/∂l₁ = 2u·dₓ, y por la regla de la cadena ∂G/∂l₁ = −½·G·2u·dₓ. Ese valor, multiplicado por el error y el color, se suma sobre los píxeles del parche.

**¿Por qué Adam y no descenso de gradiente simple?**
Los parámetros tienen escalas muy distintas (posición en píxeles, color de 0 a 1, forma). Adam normaliza el paso de cada parámetro con su propio historial y agrega momento.

**¿Por qué aquí no se ordenan las gaussianas y en 3D sí?**
En 2D la imagen es una suma de gaussianas: no hay oclusión, y el orden no cambia el resultado. En 3D una gaussiana tapa a otra, y la mezcla con alfa depende del orden de profundidad.

**¿Qué pasa al multiplicar por 10 las gaussianas?**
El PSNR sube unos 8 dB. Se inicializan con más probabilidad donde hay bordes (0,35 + |∇I|), que es un muestreo por importancia.

### Espejo 3D (`backend/app/core/splatting/head3d.py`, `frontend/js/splat3d.js`)

**¿Es 3D Gaussian Splatting?**
Es su parte de render, escrita desde cero: proyección EWA, orden y mezcla. Las gaussianas no se entrenan desde varias vistas: se construyen desde una foto y la malla 3D de MediaPipe. Por eso no hay nuca y el relieve se estira con giros de más de unos 40°.

**Explica Σ₂D = J W Σ Wᵀ Jᵀ.**
W rota la gaussiana al sistema de la cámara. J es la jacobiana de la proyección en perspectiva en el centro de la gaussiana: aproxima la proyección por una afín en esa zona. Una gaussiana bajo una afín sigue siendo gaussiana, con esa covarianza.

**¿Para qué suman 0,3·I?**
Es un filtro pasa-bajos. Garantiza que cada gaussiana cubra al menos cerca de un píxel en pantalla y evita el *aliasing* de gaussianas muy chicas o muy lejanas.

**¿Por qué el cuadrilátero de ±3σ?**
Contiene el 99,7 % de la gaussiana. Fuera de él el aporte es despreciable, así que no hace falta dibujarlo.

**¿Cómo ordenan y por qué counting sort?**
Se cuantiza la profundidad de cada gaussiana en 65 536 casillas y se ordena con counting sort: O(N + K), sin comparaciones. Se hace en JavaScript, solo cuando cambia la vista, porque WebGL2 no tiene *compute shaders* para ordenar en la GPU. Es el algoritmo del pintor: se dibuja de atrás hacia adelante.

**¿Qué limitación tiene ordenar por el centro?** *(caso límite)*
Dos gaussianas grandes que se cruzan no tienen un orden correcto en todos sus píxeles, y al girar puede haber saltos (*popping*). Es la misma aproximación que usa 3DGS.

**¿Por qué discos tangentes y por qué por área 3D?**
La covarianza R·diag(s², s², (0,4s)²)·Rᵀ aplana cada gaussiana sobre la superficie. Se reparten por área 3D y no por área en la foto para no dejar con pocas gaussianas las zonas que miran de lado, como los costados de la nariz.

**¿Qué guarda el `.ply`?**
Posición, escala en logaritmo, rotación como cuaternión, color como armónico esférico de grado 0, f = (c − 0,5)/0,2821, y opacidad en logit. Es el formato de 3DGS, así que abre en visores externos.

### Contrarreloj (`backend/app/core/game/speedrun.py`)

**¿Por qué una cápsula y no un punto?**
A 10 cuadros por segundo el dedo salta decenas de píxeles entre cuadros. Probar solo el punto actual deja pelos sin cortar. Se cortan las hebras a menos de 0,05 de ancho de cara del segmento recorrido p₀p₁: se proyecta el punto sobre el segmento, se limita t a [0, 1] y se mide la distancia.

**¿Cuándo corta la máquina?**
Con el índice extendido y el dedo medio doblado, según los puntos de la mano de MediaPipe.

**¿Por qué el puntaje es limpieza × conservación y no IoU?**
Sin tocar nada, la IoU con el objetivo ya daba 0,72 para el candado. El producto premia afeitar todo lo de afuera sin cortar lo de adentro: si uno de los dos es 0, el puntaje es 0.

---

## Kalos: arquitectura, tinte, YOLO, motor de cortes, forma de cara y tinte de barba

### Arquitectura (`backend/app/api/routes.py`, `backend/app/core/pipeline.py`)

**¿Cómo está organizado el servidor?**
En tres niveles. La API valida, decodifica y limita la imagen a 2048 px; no tiene lógica gráfica. `StylePipeline` carga los modelos una vez y encadena cara, puntos, geometría y segmentación. Cada técnica vive en su propio paquete de `core/`, sin depender de la API, y eso es lo que prueban los tests.

**¿Por qué un solo proceso?**
El modo en vivo, la peluca y el juego guardan estado entre cuadros. Con dos procesos, cada cuadro caía en uno distinto y el juego alternaba entre dos partidas. Cada llamada al pipeline corre en un hilo aparte detrás de un candado: el servidor sigue respondiendo mientras procesa y los modelos nunca se usan desde dos hilos a la vez.

**¿Cómo lo harían para muchos usuarios?** *(extensión)*
El estado se guarda por sesión, con un identificador del cliente, en Redis o en memoria por clave. Así se pueden levantar varios procesos detrás de un balanceador.

### Tinte en CIELAB (`backend/app/core/coloring/dye.py`)

**¿Por qué CIELAB y no HSV?**
En HSV, cambiar el tono conserva el brillo, así que un pelo negro nunca queda rubio. CIELAB separa la luminosidad (L*) del color (a*, b*) y es aproximadamente uniforme en percepción. Se puede mover la luminosidad base hacia la del tinte y conservar el detalle de cada mechón.

**Explica la fórmula de la luminosidad.**
L se separa en sombreado (G_σ(L) − media) y detalle (L − G_σ(L)). La nueva luminosidad es una base, 0,72·L_tinte + 0,28·media, más k·(0,8·sombreado + 1,2·detalle). El factor k = clip(20/s_L, 0,9, 1,8) normaliza el contraste: un pelo negro liso, con poco contraste, gana detalle; uno muy contrastado no se exagera.

**¿Por qué baja el croma en las sombras?**
Así se comporta un pigmento real: en una zona oscura el color se ve menos saturado. Sin eso, las sombras quedan de un color chillón.

**¿Qué pasa con un pelo blanco o canoso? ¿Y si la persona es calva?** *(casos límite)*
Blanco: tiene poco contraste, así que k sube hasta 1,8 y la base lo lleva al tono del tinte. Calvo: la máscara de pelo queda vacía y la API responde 422 con «No hair».

### YOLO y segmentación (`backend/training/`, `backend/app/core/segmentation/`)

**¿Qué entrenaron exactamente?**
Un ajuste fino de YOLOv8n-seg, preentrenado en COCO, con 9450 imágenes de Figaro1k y CelebAMask-HQ convertidas a polígonos. Se entrenó en Colab con una T4, unas 3,5 h. Llegó a un mAP50 de máscara de 0,968: con un umbral de IoU de 0,5, la precisión media es de 96,8 %.

**Si es un modelo, ¿dónde está la gráfica?**
YOLO es el tema 6.4.5–6.4.6 del sílabo, pero en el proyecto es secundario: es un selector dentro del tinte, y sin él la app usa MediaPipe. Sobre la máscara sí hay procesamiento propio:
- filtro guiado para pegarla al borde;
- descarte de los píxeles que se parecen más al fondo;
- medición de la IoU entre los dos modelos en cada foto.

**¿Qué hace el filtro guiado?**
Supone que, en cada ventana, la salida es una función lineal de la foto guía: q = a·I + b. Así la máscara copia los bordes de la foto y no cruza los bordes fuertes. Es un suavizado que respeta los bordes y corre en O(N).

### Motor de cortes (`backend/app/core/compositing/haircut.py`)

**¿Cuál es el problema de cortar el pelo?**
Hay que quitar pelo y reconstruir lo que había detrás (fondo y cuero cabelludo). Hay que saber dónde termina la cabeza y dónde empieza la línea del pelo aunque haya flequillo. Y hay que hacer crecer pelo corto con la luz de la foto.

**¿Por qué pull-push y no Telea?**
Telea propaga el color de todo el borde del hueco, y ese borde incluye pelo: arrastraba pelo al fondo («pelo fantasma»). En pull-push uno elige qué píxeles cuentan como conocidos, y solo cuentan los de fondo seguro (p_fondo > 0,6, o > 0,9 cerca del pelo).

**Explica pull-push.**
- **Pull**: se arma una pirámide. En cada nivel, cada píxel es el promedio de los cuatro de abajo, ponderado por su peso (0 si es desconocido).
- **Push**: de arriba hacia abajo, cada nivel fino rellena sus huecos con el nivel grueso, mezclando según su peso (clip(2w, 0, 1)).

El costo es O(N): N + N/4 + N/16 + … = 4N/3.

**¿Por qué el cráneo es una superelipse de exponente 2,15?**
Con exponente 2 es una elipse, y con exponentes grandes se acerca a un rectángulo. 2,15 deja la parte de arriba un poco más plana, como un cráneo real. La altura se ajusta a cada persona con la coronilla medida y la línea del pelo.

**¿Cómo encuentran la línea del pelo si hay flequillo?** *(caso límite)*
Desde las cejas se sube mientras haya piel de la cara. Si se ven al menos 0,2 de ancho de cabeza de frente, ese borde es la línea real. Si no, hay flequillo y se asume una frente típica de 0,30 de ancho de cabeza, según las proporciones de Farkas.

**¿Cómo se ilumina el pelo corto?**
Con Lambert. La normal sale de tratar el cráneo como un elipsoide. La luz se estima con la diferencia de brillo entre las dos mitades de la cara, más una componente desde arriba. El sombreado es s = 0,62 + 0,38·max(0, n·l). No se usa Phong porque el pelo corto es mate: el brillo especular no aporta.

**¿Por qué trabajan a 420 px de ancho de cabeza?**
Así los parámetros valen igual para cualquier foto y el tiempo no depende del tamaño. Al volver a la resolución original se suma la alta frecuencia de la foto en las zonas que no cambiaron, para no perder nitidez.

**¿Qué hace la intensidad del corte?**
Indica qué tan corto: cambia la densidad del pelo corto, ρ₀ = 0,92·(1,1 − 0,4·t). Más intensidad deja ver más cuero cabelludo. No es una mezcla con la foto.

**¿Dónde falla?** *(límites)*
- Si un flequillo largo tapa un ojo, quedan mechones, porque nunca se toca el polígono de la cara.
- Si el pelo tapaba las orejas, el rapado pone pelo donde irían.
- Con gorra no hay cabeza que medir.

**¿Cómo agregarían un corte nuevo?** *(extensión)*
Se agrega una entrada en `STYLES` con dónde empieza la piel, dónde el pelo corto y la densidad mínima y máxima, y un botón en la interfaz. Las pruebas recorren todos los estilos de `STYLES` y verifican que ninguno toque la cara.

### Forma de cara, tinte de barba y combinación

**¿Cómo clasifican la forma de la cara?**
Con medidas de la malla 3D (largo, frente y mandíbula, divididas por el ancho de los pómulos) y el ángulo de la mandíbula. Como las proporciones humanas varían poco, un umbral fijo pondría a casi todos en la misma clase. Cada medida se expresa como desviación z respecto de 419 caras de CelebAMask-HQ, y se aplican reglas en orden. Es una heurística, no un diagnóstico.

**¿Por qué dividir por el ancho de los pómulos?**
Para que no importe la distancia a la cámara ni el tamaño de la foto: son proporciones.

**¿Cómo encuentran la barba real para teñirla?**
Un píxel es barba si:
- es más oscuro que la piel de la propia persona;
- tiene textura de pelo (desviación local alta);
- es menos rojo que la piel.

El borde recto de la mandíbula también tiene textura, pero se descarta con la coherencia del tensor de estructura: un borde recto tiene coherencia cerca de 1, y la barba tiene trazos en todas direcciones.

**¿Cómo se combinan barba, tinte y corte?**
El resultado de cada paso es la foto del siguiente. El tinte recibe el estilo de la barba que puso la app y usa su máscara directamente. El corte toma el color del pelo ya teñido.

---

## Sofía: peluca 3D y laboratorio

### Escaneo y máscara (`backend/app/core/segmentation/transfer_mask.py`)

**¿Cómo saben el ángulo de cada captura?**
De la pose de la cabeza que da MediaPipe, en grados reales. De perfil completo, MediaPipe pierde la cara y se usa un detector de perfil, que da ±82°.

**¿Cómo sale la máscara de pelo de cada captura?**
Combina el segmentador, la distancia de color al pelo de la persona y una elipse de la cabeza. Cada fuente sola falla en algún caso; juntas se corrigen.

### Forma: *visual hull* (`backend/app/core/splatting/hair3d.py`)

**¿Qué es una envolvente visual?**
Es la intersección de los conos que forman las siluetas vistas desde cada cámara. Todo lo que está en el objeto cae dentro de todas las siluetas, así que la intersección lo contiene.

**¿Por qué por cortes y no con vóxeles?**
Una grilla de vóxeles cuesta O(n³) en memoria y tiempo. Por rebanadas, cada altura es un problema 2D: para 360 direcciones, cada captura dice dónde empieza y dónde termina el pelo, y se intersecan intervalos.

**¿Qué no puede reconstruir?** *(límite clásico)*
Las concavidades: un hueco que ninguna silueta muestra queda relleno. Tampoco las direcciones que ninguna captura vio; esas siguen una forma de cabeza (tan ancha como la vista más frontal, nunca delante de la cara).

### Textura y dirección del pelo

**¿Cómo eligen el color de cada punto?**
De las capturas que mejor lo ven, mezcladas según qué tan de frente lo ven, para que no haya costuras. La nuca nunca se ve: recibe el color del último pelo que vio cada perfil, con estrías verticales.

**¿Para qué el tensor de estructura?**
Para saber hacia dónde va el pelo. La orientación dominante es θ = ½·atan2(2J_xy, J_xx − J_yy), que es la dirección del gradiente. El pelo va perpendicular a ella, y cada gaussiana se alarga en esa dirección. Donde no hay orientación clara, se alarga hacia abajo.

### Estudio y prueba en vivo

**¿Cómo funcionan las tijeras?**
Cada gaussiana se proyecta a la pantalla con la misma cámara del visor. Dentro del radio del pincel se eliminan solo las más cercanas a la cámara, para no cortar el pelo de atrás. Los cortes se pueden deshacer.

**¿Cómo cambian el largo?**
Se eliminan las gaussianas por debajo de una altura.

**¿Cómo se prueba la peluca sobre otra persona?**
El navegador sigue la cabeza con MediaPipe en JavaScript. El servidor quita el pelo propio de esa persona (`compositing/bald.py`): el fondo se aprende de cuadros anteriores o se rellena, y el cuero cabelludo se sombrea a partir de la piel de la cara.

### Laboratorio (`backend/app/core/lab/avatar.py`)

**¿Cómo sigue el avatar a la cara?**
Cada gaussiana guarda su triángulo, sus coordenadas baricéntricas, un desplazamiento y una covarianza en el marco local del triángulo. En cada cuadro se rearma el marco con la malla nueva y la gaussiana lo sigue (`triangle_frames` y `world` en `avatar.py`).

**¿Cómo es ese marco local?**
Ortonormal: e₁ es la primera arista normalizada, n es la normal (producto vectorial de dos aristas) y e₂ = n × e₁. Con R = [e₁ e₂ n] y s el ancho de la cara:
- posición = suma de baricéntricas × vértices + R·desplazamiento·s;
- covarianza = R·Σ_local·Rᵀ·s².

**¿Por qué ortonormal y no las aristas tal cual?** *(decisión)*
Una rotación conserva la forma de la gaussiana: solo la gira con la piel. Con las aristas sin normalizar, en un triángulo fino o muy estirado la gaussiana se cizallaría. La escala general la da el ancho de la cara.

**¿Dónde falla?** *(casos límite)*
- Giros muy rápidos, que dejan las capturas borrosas.
- Pelo del mismo color que el fondo.
- Gorras, porque no se ve el pelo.
- Pelo muy corto, con poca silueta.

---

## Preguntas de extensión (cualquiera puede recibirlas)

- **Tinte a 30 cuadros por segundo:** pasar la fórmula de CIELAB a un *fragment shader* y segmentar en el navegador con MediaPipe en JavaScript.
- **Cabeza completa en el espejo:** optimizar las gaussianas con varias vistas, como en 3DGS entrenado.
- **Fortune en O(n log n):** guardar la *beach line* en un árbol balanceado.
- **Varios usuarios en vivo:** estado por sesión.
- **Oclusiones (una mano delante de la cara):** segmentar la mano con el modelo de manos y no dibujar la barba encima.
