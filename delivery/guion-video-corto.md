# Guion del video corto (pitch)

Duración máxima: **1:30**. El texto tiene unas 210 palabras: leído con calma dura 1:20 y deja margen. Archivo final: `delivery/videos/video-corto.mp4`.

Lo puede narrar una sola voz. En pantalla va la app real corriendo en `http://localhost:8000`, grabada en 1080p, con la foto de ejemplo o un retrato de la NASA.

| Tiempo | En pantalla | Narración |
|---|---|---|
| 0:00 – 0:10 | Inicio de Fresh: la palabra roja va cambiando de estilo | «Cortarse el pelo o dejarse la barba es una decisión a ciegas: el resultado se ve cuando ya está hecho.» |
| 0:10 – 0:22 | Subir una foto. Barba → Completa → Aplicar. Mover el comparador | «Fresh te deja probarlo antes, sobre tu propia foto o con la cámara. No genera una cara nueva: modela la tuya.» |
| 0:22 – 0:35 | Activar «Mostrar la malla de triángulos» | «Con los puntos de la cara armamos una malla de Delaunay con nuestro algoritmo de Fortune, y deformamos barbas reales triángulo por triángulo.» |
| 0:35 – 0:47 | Agregar tinte → rojo, con barba. Agregar corte → Degradado medio | «El tinte trabaja en CIELAB para no perder los mechones. Para los cortes quitamos el pelo, reconstruimos lo que había detrás y hacemos crecer pelo corto con la luz de tu foto.» |
| 0:47 – 0:55 | Mostrar «Tu cara» y la ficha para el barbero | «Te sugiere estilos según la forma de tu cara y te da una ficha para llevar a la barbería.» |
| 0:55 – 1:10 | Espejo 3D girando, luego «Ver cada gaussiana». Corte rápido a la barba con física en vivo | «Tu cabeza en 3D, hecha de más de cien mil gaussianas con un visor propio en WebGL. Y una barba con física que se mueve contigo.» |
| 1:10 – 1:22 | Contrarreloj: alguien afeita con el dedo | «Hasta un juego para afeitar con el dedo frente a la cámara.» |
| 1:22 – 1:30 | Portada con el nombre y el equipo | «Fresh. Computación gráfica para elegir tu próximo corte. Kalos, Sofía y Gianpier, CS4016.» |

## Antes de grabar

- Levantar la app con `docker compose up -d --build app` y probar cada pantalla una vez: la primera carga de los modelos tarda.
- Luz de frente, fondo liso y la cámara a la altura de la cara.
- Grabar la pantalla con QuickTime (macOS) u OBS a 1080p, y la voz aparte o encima.
- Exportar en MP4 (H.264). Si pesa más de 150 MB, comprimirlo con HandBrake (preset «Fast 1080p30»).
- Comprobar que dura menos de 1:30: el script `build_zip.py` lo revisa si `ffprobe` está instalado.
