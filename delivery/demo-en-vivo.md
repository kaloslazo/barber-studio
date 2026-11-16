# Demo en vivo (exposición final)

Plan para la exposición presencial: unos 12 minutos para los tres, con una versión de 10 al final. Sigue el orden de las diapositivas (`slides/main.tex`): láminas cortas y, justo después de cada tema, la app. Fiesta va al final, porque es lo que más se recuerda.

Cada paso trae una o dos frases técnicas con el tema del sílabo (los números son los de la tabla 1 del informe). El profesor premia una demo entretenida, pero pone la mayor nota en el dominio técnico: el chiste abre la puerta y la frase técnica es lo que se evalúa.

## Quién hace qué

- **Kalos:** abre y cierra, explica tinte, corte y Fiesta, y le pide la cara al profesor.
- **Gianpier:** Delaunay, barba y espejo 3D. Sale en cámara con Kalos en el cambio de cara.
- **Sofía:** maneja la laptop en las demos, presenta la peluca 3D, calidad y límites, y lleva el tiempo. Avisa con la mano a los 10:30.

Cuando Sofía presenta, Kalos maneja la laptop.

## Minuto a minuto

| Tiempo | Quién | Qué pasa |
|---|---|---|
| antes | Sofía | Voluntario y su foto |
| 0:00 – 1:15 | Kalos | Láminas de apertura |
| 1:15 – 2:15 | Gianpier | Láminas de malla y barba |
| 2:15 – 2:45 | Kalos | Láminas de tinte y corte |
| 2:45 – 5:00 | Gianpier y Kalos | Demo 1: el voluntario |
| 5:00 – 6:15 | Gianpier | Demo 2: espejo 3D |
| 6:15 – 7:00 | Sofía | Láminas de la peluca 3D |
| 7:00 – 10:30 | Kalos, Gianpier y Sofía | Demo 3: Fiesta |
| 10:30 – 11:15 | Sofía | Calidad y límites |
| 11:15 – 12:00 | Kalos | Cierre y preguntas |

### Antes de empezar (mientras se conecta el proyector)

- **Hacer:** Sofía pide un voluntario con pelo. Le cuenta que su foto se va a proyectar, que no se guarda y que puede decir que no. Le toma la foto en Inicio → **Tomar foto**, de frente y con luz.
- **Decir:** «Necesitamos a alguien con pelo y sin miedo al rubio».

### 0:00 – 1:15 · Láminas de apertura (Kalos)

- **Láminas:** portada, «El problema», «Qué hace Fresh», «Arquitectura», «Qué es nuestro y qué no» y 10 segundos en «Temas del curso que aplicamos».
- **Decir:** «No generamos una cara nueva: medimos la tuya y componemos sobre tu foto, todo en CPU. Los modelos solo dicen dónde están la cara, el pelo y la mano. Todo lo que se ve lo calcula código nuestro».

### 1:15 – 2:15 · Láminas de malla y barba (Gianpier)

- **Láminas:** «De puntos a malla: Delaunay con Fortune» y «Barba: el proceso».
- **Decir:** «Cada evento de círculo de Fortune es un vértice de Voronoi y un triángulo de Delaunay (6.2.2 y 6.2.5). Con esa malla, una barba real se deforma triángulo por triángulo».

### 2:15 – 2:45 · Láminas de tinte y corte (Kalos)

- **Láminas:** «Tinte: el proceso» y «Corte: el proceso». Una frase por lámina; el resto se ve en la app.

### 2:45 – 5:30 · Demo 1: el voluntario (recortar 30 s del espejo 3D)

1. **Barba (Gianpier, 2:45 – 3:30).** Sofía abre Barba con la foto del voluntario, elige **Completa** y toca **Aplicar barba**. Después, **Mostrar la malla de triángulos**.
   - **Decir:** «Cada píxel de la barba se lleva a la plantilla con la afín inversa de su triángulo, se prueba con baricéntricas y se lee con interpolación bilineal propia (6.1.4 y 6.3.3.1)».
   - **Chiste:** si el estilo tiene la marca «Te queda»: «La app opina que sí. Nosotros no nos metemos».
2. **Tinte (Kalos, 3:30 – 4:10).** **Agregar tinte**. Preguntarle al público el color; si nadie dice nada, rubio.
   - **Decir:** «La máscara de nuestro YOLO pasa por dos filtros guiados y queda suave, sin agujeros (6.4.4 y 6.4.5–6.4.6). En CIELAB movemos la luminosidad hacia la del tinte y conservamos tres bandas de detalle: por eso un pelo oscuro queda rubio sin puntos negros (6.1.1)».
3. **Corte (Kalos, 4:10 – 4:40).** **Agregar corte** → **Degradado medio**.
   - **Decir:** «Para cortar hay que quitar pelo y reconstruir lo que había detrás. Rellenamos con pull-push usando solo fondo seguro (6.1.3) y el pelo corto se sombrea con Lambert, con la luz de la cara (6.3.3.2)».
4. **Ficha (Kalos, 4:40 – 4:50).** **Ficha para tu barbero** y mostrarla.
   - **Chiste:** «Con esto ya no hay excusa para salir mal de la barbería».
   - **Si el tiempo aprieta:** en vez de barba, tinte y corte por separado, Juegos → **El practicante** → **Primer día** → **Que decida el practicante** hace las tres cosas de una vez con la ficha. **Chiste:** «Es su primer día; tranquilo, en tres semanas crece».
5. **Galería (Kalos, 4:50 – 5:30).** Estilos → **Galería**. Escribir el nombre del voluntario en **Nombre para la placa** y tocar **Entrar a los 7 cuadros**. Pasar por Marx, Nietzsche y Van Gogh. Si el profesor prestó su cara en Fiesta, repetirlo después con su foto: «el profe como Karl Marx».
   - **Chiste:** «Antes de pedir un corte, conviene ver si ya lo usó alguien famoso».
   - **Decir:** «Es el mismo cambio de cara de Fiesta, con el retrato como destino, pero la barba del retrato queda encima. En la foto antigua la cara se vuelve blanco y negro con la misma transferencia de color, y en el Van Gogh la repintamos con el filtro de Kuwahara: cuatro ventanas por píxel, gana la de menor varianza, calculado con imágenes integrales (6.1.2 y 6.3.3.2)».

### 5:00 – 6:15 · Demo 2: espejo 3D (Gianpier)

- **Hacer:** 15 segundos en la lámina «Espejo 3D: el proceso». En la app, 3D → Espejo 3D con la foto del voluntario, **Construir cabeza 3D**. Girar la cabeza con el mouse y tocar **Ver cada gaussiana**.
- **Decir:** «Son más de cien mil gaussianas 3D sobre la malla de MediaPipe. El vertex shader proyecta cada una con EWA y un counting sort las ordena de atrás hacia adelante: el algoritmo del pintor (6.3.1, 6.3.3.3 y 6.3.3.5)».
- **Chiste y límite:** girar hasta la nuca. «Y atrás no hay nada: una foto no ve tu nuca». Reconocer el límite suma.

### 6:15 – 7:00 · Láminas de la peluca 3D (Sofía)

- **Láminas:** «Peluca 3D: el proceso» y «Peluca 3D».
- **Decir:** «Cada vista limita dónde puede haber pelo; la intersección de todas da la forma (envolvente visual). El color sale de las vistas que mejor ven cada punto y la dirección del pelo, del tensor de estructura (6.3.3.2 y 6.4.2)».
- **Gianpier, 10 segundos:** «Y ahora también se escanea con una vuelta en una silla: de espaldas no hay cara, así que el giro sale de los puntos que se siguen entre cuadros».

### 7:00 – 10:30 · Demo 3: Fiesta

Sofía maneja la laptop. Kalos y Gianpier se paran a un metro de la cámara, hombro con hombro.

1. **Entrada (Kalos, 7:00 – 7:10).** «Todo lo anterior era para la barbería. Esto es para después del corte». Sofía abre Fiesta → **Cambio de cara**.

2. **Entre ustedes (7:10 – 8:00).** Sofía toca **Encender cámara**. Kalos y Gianpier quedan con la cara cambiada. Que se muevan, giren un poco y hablen.
   - **Chiste (Kalos):** «Después de un ciclo trabajando juntos, por fin nos ponemos en el lugar del otro».
   - **Decir (Kalos):** «Cada cara es una malla de 468 puntos. La triangulación se calcula una sola vez, con nuestro Fortune, sobre una cara promedio de 400 personas: el triángulo i es la misma parte de la cara en los dos (6.2.5). Cada píxel se lleva a la otra cara con la afín de su triángulo, por mapeo inverso, y se lee con bilineal (6.1.4 y 6.3.3.1)».
   - **Decir (Gianpier):** «El tono se iguala con la transferencia de Reinhard en Lab (6.1.1) y la cara se pega con una mezcla de pirámides laplacianas: el color se mezcla en una franja ancha y el detalle en una angosta, por eso no hay costura (6.1.3)».

3. **Una cara para todos, con la cara del profesor (8:00 – 8:50).**
   - **Pedirlo con respeto (Kalos):** «Profe, ¿nos presta su cara diez segundos? Vive solo en la memoria de esta laptop y se borra al apagar el servidor». Si duda, no insistir y pasar al plan B.
   - **Si acepta:** Sofía elige **Una cara para todos** y toca **Sacarla de la cámara**. El profesor se pone solo frente a la cámara; cuenta 3, 2, 1 y la cara queda guardada en el panel. El profesor sale y entran los tres del equipo: todos con su cara. En vivo caben hasta tres caras.
   - **Chiste:** «Ahora sí, el equipo entero piensa como el profe».
   - **Plan B:** **La del astronauta**. «La NASA nos presta un astronauta: dominio público, sin derechos de imagen».
   - **Decir:** «Es el mismo warp: la cara guardada se deforma hasta la malla de cada persona que aparece. Corre a unos 15 cuadros por segundo en CPU: 44 ms por cuadro con dos caras».

4. **Caricatura al voluntario (8:50 – 9:35).** Preguntarle si se anima. Sofía abre **Caricatura**, intensidad al 100 %, **Encender cámara**. Primero **Narizón**, después **Alien** y al final **Caricatura**.
   - **Chiste (con Narizón):** «Esto no es un insulto: es una fórmula de 1985».
   - **Decir (Kalos, con Caricatura):** «Es la fórmula de Brennan: P' = A + (1 + k)(P − A). A es la cara promedio ajustada a tu cara por mínimos cuadrados (Umeyama). Crece justo lo que te hace distinto. Un anillo de 28 puntos fijos deja quieto el resto de la foto (6.3.2)».

5. **Fusión de dos compañeros (9:35 – 10:30).** Pedir dos voluntarios (o el voluntario y un amigo). Sofía abre **Fusión**, **Juntos en una foto**, y escribe los dos **Nombres** tal como se ven en la pantalla, que es un espejo. Toca **Foto a los dos en 3 s**: cuenta 3, 2, 1, «¡Fusión!», y el resultado aparece en un segundo y medio.
   - **Hacer:** mover el control de un extremo al otro, dejarlo en el medio y leer en voz alta el nombre que aparece: «A la mitad nace…». Después, **Animar**.
   - **Chiste:** «Felicidades: es un 480 por 480 y está sano».
   - **Decir (Kalos):** «Es morphing clásico: las dos fotos se deforman a la malla intermedia, (1 − t)A + tB, y recién ahí se mezclan con pesos 1 − t y t (6.1.4). Si se mezclaran sin deformar, el hijo tendría cuatro ojos».

### 10:30 – 11:15 · Calidad y límites (Sofía)

- **Láminas:** «Calidad y rendimiento» y «Límites que conocemos».
- **Decir:** «121 pruebas automáticas en GitHub Actions. Probado en 26 caras. El tinte nuevo se revisó en 8 caras con 7 colores. Límites: una mano delante de la cara, el espejo 3D sin nuca, y en Fiesta, con la cabeza muy girada, el lado lejano de la cara se estira».

### 11:15 – 12:00 · Cierre y preguntas (Kalos)

- **Hacer:** dejar en pantalla el hijo de la fusión mientras responden.
- **Decir:** «Fresh: computación gráfica para elegir tu próximo corte. Y para cambiarte de cara después».

Las láminas que no se muestran («El pipeline completo», «Cortar el pelo», «Ocho cortes», «Combinar», «¿Qué te queda?», en vivo, gaussianas 2D y Contrarreloj) quedan para las preguntas. Si el profesor pide algo de eso, se abre la lámina o la app.

La última lámina, «Demo», todavía lista gaussianas, en vivo y Contrarreloj. Conviene cambiarla por este orden (voluntario, espejo 3D, Fiesta) o saltarla.

## Versión de 10 minutos

- Apertura: 1:00, sin «Temas del curso».
- Espejo 3D: 0:45, sin la lámina.
- Peluca 3D: 0:30, una sola lámina.
- Fiesta: 3:00, sin la caricatura «Narizón» y sin el paso de los tres con la cara del profesor (se queda solo la captura).
- Cierre: 0:15.

## Lista de control

### La noche antes

- [ ] Construir y levantar: `docker compose up -d --build app` (la primera vez tarda unos minutos). Sin Docker: `./run.sh`.
- [ ] Correr las pruebas: `cd backend && venv/bin/python -m pytest tests/ -q` (121).
- [ ] Ensayar la demo completa una vez con el reloj, en el mismo orden.
- [ ] Carpeta en el escritorio con fotos de respaldo: `frontend/assets/samples/ejemplo.jpg` (Scott Horowitz, NASA), `frontend/assets/samples/muestra.jpg` (Frank Rubio, NASA), una foto del equipo con dos o tres caras de frente y una foto de cada uno. Solo retratos de la NASA o caras propias.
- [ ] Video de respaldo en la laptop, sin depender de internet: `delivery/videos/video-largo.mp4`, con el bloque de Fiesta en 16:00.
- [ ] Cargador y adaptador para el proyector.

### 30 minutos antes

- [ ] El servidor corre: `docker compose ps` y `curl -s localhost:8000/api/health`.
- [ ] Chrome en `http://localhost:8000`, con el permiso de la cámara concedido (candado de la barra de direcciones → Cámara → Permitir).
- [ ] Calentar una vez cada herramienta: Barba, Tinte con YOLO, Corte, Espejo 3D, Cambio de cara, Caricatura y Fusión. La primera llamada carga los modelos.
- [ ] Cerrar Zoom, Meet, Teams, FaceTime y Photo Booth: se quedan con la cámara.
- [ ] No molestar activado y la pantalla sin bloqueo (`caffeinate -d` en una terminal).
- [ ] Proyector en modo espejo. Ajustar el zoom de Chrome (cmd − / cmd +) hasta que se vea el panel completo.
- [ ] Luz de frente: prender las luces de adelante. Si el salón está oscuro, una lámpara o la linterna de un celular detrás de la laptop, apuntando a las caras.
- [ ] La laptop a la altura de la cara (sobre una caja o libros), con espacio para que dos personas se paren a un metro.
- [ ] Las diapositivas abiertas y la app en otra ventana; probar el cambio con cmd + tab.

### 5 minutos antes

- [ ] Voluntario elegido, con permiso para proyectar su foto, y la foto tomada en Inicio.
- [ ] El video de respaldo abierto en QuickTime y en pausa.

## Plan B

| Si pasa esto | Hacer esto |
|---|---|
| La cámara no enciende | Candado de la barra → Cámara → Permitir, y recargar. Cerrar las apps que usan la cámara. Si no hay caso, Fiesta con **Usar tu foto** y las fotos de respaldo: la del equipo para el cambio de cara y **Dos fotos** para la fusión. |
| «No se ve ninguna cara» | Más luz de frente, acercarse, mirar de frente, sacarse la gorra y la mano de la cara. |
| «Falta la segunda cara» | Hombro con hombro, a la misma distancia de la cámara, sin taparse. |
| «La cara está muy de perfil» | Barba y corte en foto piden mirar a la cámara (más de 50° de giro). Tomar la foto de nuevo, de frente. |
| Una de las dos caras no aparece | La app busca caras chicas en recortes, pero cada cara debe ocupar al menos un 8 % del ancho del cuadro (medido): a menos de metro y medio de la laptop. |
| La fusión pide dos caras | Repetir **Foto a los dos en 3 s** con las dos caras de frente y del mismo tamaño. Si no sale, **Dos fotos**. |
| El nombre del hijo sale al revés | Cambiar los dos nombres de lugar: van como se ven en la pantalla. Se actualiza al escribir. |
| El profesor prefiere no prestar su cara | **La del astronauta** o la cara del voluntario. No insistir. |
| «Primero guarden la cara que se van a poner» | La cara guardada se perdió (se reinició el servidor). Volver a guardarla. |
| Va lento | Cerrar otras apps. Pasar a **Usar tu foto**: una foto tarda menos de medio segundo. |
| El servidor no responde | `docker compose restart app` (o volver a correr `./run.sh`) y seguir con las láminas mientras levanta. La primera llamada vuelve a cargar los modelos. Si no levanta, el video de respaldo. |
| Se cae el wifi del salón | No afecta: todo corre en `localhost`. Solo usan internet las fuentes de Google (tienen respaldo local) y la malla que se dibuja encima durante el escaneo de la peluca. |
| El voluntario no tiene pelo visible | Sacarse la gorra, o usar la foto de ejemplo. Si está rapado, el aviso sugiere la Peluca 3D: también sirve como chiste. |
| El proyector corta la pantalla | cmd − en Chrome hasta que se vea todo. |

## Cuidado con las caras de los demás

- Preguntar antes de proyectar, caricaturizar o fusionar a alguien, y aceptar un no sin insistir.
- Fiesta no guarda nada en disco: la cara guardada vive en la memoria del servidor hasta que se apaga. No tocar **Descargar** con caras de otros salvo que lo pidan.
- Los chistes son sobre la técnica o sobre nosotros, nunca sobre el aspecto de alguien.
