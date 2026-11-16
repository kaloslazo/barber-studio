# Banco de robustez

Las fotos de la NASA salen bien siempre: luz de estudio, de frente y con buena resolución. La cámara de una laptop en un salón no. Este banco prueba cada herramienta de foto (barba, tinte, corte, forma de la cara, espejo 3D) y de Fiesta (caricatura, una cara para todos, cambio de cara, fusión) en 40 casos difíciles.

```bash
cd backend
venv/bin/python ../docs/robustez/robustez.py <CelebAMask-HQ> <Figaro1k/Original/Testing> [salida]
```

Necesita los datasets de `data/` (no van en git). Las hojas de contacto tienen caras de CelebA, así que tampoco se suben.

## Casos

- **CelebAMask-HQ, por atributos y pose:** perfil a la derecha y a la izquierda (giro de más de 32°), cabeza inclinada, lentes, gorra, foto borrosa, flequillo, boca abierta, barba real, calvo.
- **Figaro1k, fotos reales de Flickr:** pelo corto de hombre, rizos, afro, trenzas, rastas, ondulado; varias de espaldas o de perfil.
- **Una cara con diez degradaciones de cámara:** baja resolución (¼), poca luz con ruido, luz lateral, contraluz, movida, JPEG de calidad 12, girada 25°, chica en un cuadro de 1280 × 720, mano delante de la boca, selfie cortada.
- **Varias personas:** dos caras de distinto tamaño en un cuadro grande, una de frente y otra de perfil, una oscura y otra clara, tres personas.

## Resultado del 16 de noviembre

Ningún caso cuelga el servidor ni devuelve un error 500. Lo que se encontró y se arregló:

| Falla | Causa | Arreglo |
|---|---|---|
| Cabeza inclinada 25–30°: barba, tinte y corte decían «no hay cara» | El detector Haar solo ve caras derechas | Si Haar no encuentra la cara, la caja sale de la malla de MediaPipe (`detection/face_detector.py`) |
| Dos personas a un metro de la cámara: solo veía una | El detector de MediaPipe achica la foto a 128 px y pierde caras de menos de ~20 % del ancho | Si faltan caras, se buscan otra vez en recortes cuadrados que se solapan y se juntan (`faces/mesh.py`). Ahora encuentra caras desde el 6–8 % del ancho del cuadro |
| Cambio de cara con alguien de perfil: la mejilla oculta salía estirada | Esos triángulos se ven de canto en la foto donante | Se descartan los triángulos que miran hacia atrás en el destino y, donde la donante muestra un triángulo de canto, se usa su gemelo de la otra mejilla con la foto espejada (`faces/swap.py`) |
| Barba y corte en un perfil completo: manchas sin sentido | Falta media cara | Con más de 50° de giro, la app pide mirar a la cámara |
| Fusión con la cara cerca del borde: cuerpo reflejado | El recorte se salía de la foto | El recorte se desliza (y se achica si hace falta) para quedar dentro |

Lo que sigue siendo un límite: fotos de espaldas o de perfil total (no hay cara que medir, la app lo dice), corte sobre pelo largo de mujer (el fondo que se rellena no siempre convence) y la fusión entre una cara de frente y una de perfil (se ve doble).
