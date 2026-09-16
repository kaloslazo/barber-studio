# Plan de Implementación — Simulador de Barbería
### Funcionalidad: Poner Barba · CS4016 Computación Gráfica · UTEC

---

## Temas del Sílabo Aplicados

| Tema | Código | Aplicación |
|------|--------|------------|
| Representaciones de imágenes | 6.1.2 | Manipulación de píxeles para componer el overlay de barba |
| Sampling | 6.1.3 | Muestreo de la región facial para detectar mandíbula y mentón |
| Interpolación | 6.1.4 | Interpolación bilineal para escalar el sprite de barba |
| **Quadtrees / Kd-Trees** | **6.2.4** ⭐ | **Particionamiento espacial adaptativo de la región facial** |
| Detección de bordes | 6.4.2 | Canny/Sobel para suavizar la transición barba–piel |
| Extracción y matching de features | 6.4.3 | Landmarks faciales de mandíbula y labio como anclas del overlay |
| Introducción a OpenCV | 6.4.4 | Librería central: lectura, operaciones de visión, canales RGBA |
| Detección de objetos / YOLO | 6.4.5 | Detección del rostro antes de aplicar los landmarks |

> ⭐ **6.2.4 Quadtrees** es el conector principal con el tema actual del curso.

---

## Stack Tecnológico

```
Python 3.x
├── opencv-python       → visión computacional, composición      (6.4.4)
├── mediapipe           → 68 landmarks faciales                  (6.4.3, 6.4.5)
├── numpy               → operaciones matriciales sobre imágenes (6.1.2)
└── Quadtree (impl. propia) → particionamiento espacial          (6.2.4) ⭐
```

Instalación:
```bash
pip install opencv-python mediapipe numpy
```

---

## Fase 1 — Detección del Rostro
> Temas: `6.4.4` `6.4.5`

**Output:** Coordenadas del bounding box + 68 landmarks faciales

```python
import cv2
import mediapipe as mp
import numpy as np

def detectar_rostro_y_landmarks(imagen_path):
    img = cv2.imread(imagen_path)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    mp_face_mesh = mp.solutions.face_mesh
    with mp_face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1) as face_mesh:
        results = face_mesh.process(img_rgb)

    if not results.multi_face_landmarks:
        raise ValueError("No se detectó ningún rostro")

    h, w = img.shape[:2]
    landmarks = results.multi_face_landmarks[0].landmark

    # Convertir a coordenadas de píxel
    puntos = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]

    # Índices relevantes para la barba (mandíbula + labio superior)
    # MediaPipe: contorno mandíbula ≈ índices 0-16 del mesh canónico
    # Ajustar según el modelo de 468 puntos de MediaPipe
    MANDIBULA = [234, 93, 132, 58, 172, 136, 150, 149, 176, 148,
                 152, 377, 400, 378, 379, 365, 397, 288, 361, 454]
    LABIO_SUP = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291]

    zona_barba = [puntos[i] for i in MANDIBULA + LABIO_SUP]

    return img, puntos, zona_barba
```

---

## Fase 2 — Particionamiento Espacial con Quadtree
> Tema: `6.2.4` ⭐ — **El conector principal con el sílabo**

**Output:** Máscara binaria adaptativa de la región de barba

**Justificación del Quadtree:**
- La densidad de detección varía: alta en bordes de mandíbula, baja en zonas planas
- No se evalúan todos los píxeles, sólo las celdas activas → eficiencia espacial
- Las celdas hoja forman directamente la máscara de overlay → integra geometría (6.2) con visión (6.4)

```python
class QuadtreeNode:
    def __init__(self, x, y, w, h):
        self.x, self.y = x, y      # esquina superior izquierda
        self.w, self.h = w, h      # dimensiones de la celda
        self.hijos = []            # NW, NE, SW, SE
        self.es_hoja = True
        self.activo = False        # True si la celda está en la zona de barba

    def subdividir(self):
        hw, hh = self.w // 2, self.h // 2
        self.hijos = [
            QuadtreeNode(self.x,      self.y,      hw, hh),  # NW
            QuadtreeNode(self.x + hw, self.y,      hw, hh),  # NE
            QuadtreeNode(self.x,      self.y + hh, hw, hh),  # SW
            QuadtreeNode(self.x + hw, self.y + hh, hw, hh),  # SE
        ]
        self.es_hoja = False


def punto_en_poligono(px, py, poligono):
    """Ray casting algorithm"""
    n = len(poligono)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = poligono[i]
        xj, yj = poligono[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def celda_intersecta_zona(nodo, zona_barba):
    """Verifica si alguna esquina de la celda está dentro del polígono"""
    esquinas = [
        (nodo.x, nodo.y),
        (nodo.x + nodo.w, nodo.y),
        (nodo.x, nodo.y + nodo.h),
        (nodo.x + nodo.w, nodo.y + nodo.h),
    ]
    return any(punto_en_poligono(px, py, zona_barba) for px, py in esquinas)


def construir_quadtree(nodo, zona_barba, min_size=8):
    """
    Subdivide recursivamente si la celda intersecta la zona de barba
    y es mayor al tamaño mínimo.
    """
    if not celda_intersecta_zona(nodo, zona_barba):
        return  # celda fuera de la zona, no subdividir

    if nodo.w <= min_size or nodo.h <= min_size:
        nodo.activo = True  # celda hoja dentro de la zona → pertenece a la barba
        return

    nodo.subdividir()
    for hijo in nodo.hijos:
        construir_quadtree(hijo, zona_barba, min_size)


def obtener_hojas_activas(nodo):
    """Retorna todas las celdas hoja activas (zona de barba)"""
    if nodo.es_hoja:
        return [nodo] if nodo.activo else []
    hojas = []
    for hijo in nodo.hijos:
        hojas.extend(obtener_hojas_activas(hijo))
    return hojas


def generar_mascara(img_shape, zona_barba, min_size=8):
    h, w = img_shape[:2]
    raiz = QuadtreeNode(0, 0, w, h)
    construir_quadtree(raiz, zona_barba, min_size)

    mascara = np.zeros((h, w), dtype=np.uint8)
    hojas = obtener_hojas_activas(raiz)
    for celda in hojas:
        mascara[celda.y:celda.y+celda.h, celda.x:celda.x+celda.w] = 255

    return mascara
```

---

## Fase 3 — Overlay de la Barba
> Temas: `6.1.2` `6.1.4`

**Output:** Imagen con barba superpuesta y correctamente escalada

```python
def aplicar_barba(img, zona_barba, sprite_path, mascara):
    """
    Escala el sprite PNG (RGBA) sobre la región definida por los landmarks
    y lo compone sobre la imagen original.
    """
    sprite = cv2.imread(sprite_path, cv2.IMREAD_UNCHANGED)  # canal alpha incluido

    # Calcular bounding box de la zona de barba
    xs = [p[0] for p in zona_barba]
    ys = [p[1] for p in zona_barba]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    ancho_zona = x_max - x_min
    alto_zona  = y_max - y_min

    # Escalar sprite al tamaño de la zona (interpolación bilineal → 6.1.4)
    sprite_escalado = cv2.resize(sprite, (ancho_zona, alto_zona),
                                 interpolation=cv2.INTER_LINEAR)

    # Separar canales del sprite
    b, g, r, alpha = cv2.split(sprite_escalado)
    sprite_bgr = cv2.merge([b, g, r])

    # Región de interés en la imagen original
    roi = img[y_min:y_max, x_min:x_max]

    # Aplicar máscara del Quadtree sobre el alpha del sprite
    mascara_roi = mascara[y_min:y_max, x_min:x_max]
    alpha_final = cv2.bitwise_and(alpha, mascara_roi)

    # Composición alpha blending
    alpha_norm = alpha_final.astype(float) / 255.0
    for c in range(3):
        roi[:, :, c] = (alpha_norm * sprite_bgr[:, :, c] +
                        (1 - alpha_norm) * roi[:, :, c]).astype(np.uint8)

    img[y_min:y_max, x_min:x_max] = roi
    return img
```

---

## Fase 4 — Suavizado de Bordes
> Temas: `6.4.2` `6.1.3`

**Output:** Imagen final con transición natural barba–piel

```python
def suavizar_mascara(mascara, radio_blur=15):
    """
    Aplica Gaussian Blur sobre el borde de la máscara para
    suavizar la transición barba–piel (6.1.3 Sampling / 6.4.2 Bordes)
    """
    # Asegurar radio impar
    if radio_blur % 2 == 0:
        radio_blur += 1
    mascara_suave = cv2.GaussianBlur(mascara, (radio_blur, radio_blur), 0)
    return mascara_suave


def refinar_con_canny(img_gray, mascara):
    """
    Usa Canny para detectar el contorno del rostro y
    ajustar los bordes de la máscara (6.4.2)
    """
    bordes = cv2.Canny(img_gray, threshold1=50, threshold2=150)
    mascara_refinada = cv2.bitwise_and(mascara, cv2.bitwise_not(bordes))
    return mascara_refinada
```

---

## Pipeline Completo

```python
def pipeline_barba(imagen_path, sprite_path, output_path):
    # Fase 1 — Detección
    img, landmarks, zona_barba = detectar_rostro_y_landmarks(imagen_path)

    # Fase 2 — Quadtree
    mascara = generar_mascara(img.shape, zona_barba, min_size=8)

    # Fase 4 (antes de overlay) — suavizar máscara
    mascara = suavizar_mascara(mascara, radio_blur=21)

    # Fase 3 — Overlay
    img_resultado = aplicar_barba(img.copy(), zona_barba, sprite_path, mascara)

    # Guardar resultado
    cv2.imwrite(output_path, img_resultado)
    print(f"Resultado guardado en {output_path}")
    return img_resultado


# Uso
pipeline_barba(
    imagen_path="foto_usuario.jpg",
    sprite_path="sprites/barba_corta.png",  # PNG con canal alpha
    output_path="resultado_barba.jpg"
)
```

---

## Estructura de Archivos Sugerida

```
proyecto_barberia/
├── main.py                  ← pipeline completo
├── quadtree.py              ← implementación del Quadtree (Fase 2)
├── deteccion.py             ← detección de rostro y landmarks (Fase 1)
├── overlay.py               ← composición de la barba (Fase 3)
├── procesamiento.py         ← suavizado y bordes (Fase 4)
├── sprites/
│   ├── barba_corta.png
│   ├── barba_larga.png
│   └── bigote.png
└── tests/
    └── test_quadtree.py
```

---

## Resumen de Temas por Fase

| Fase | Descripción | Temas Sílabo |
|------|-------------|--------------|
| 1 | Detección de rostro y landmarks | 6.4.4, 6.4.5 |
| 2 | Quadtree → máscara espacial | **6.2.4** ⭐ |
| 3 | Overlay con interpolación | 6.1.2, 6.1.4 |
| 4 | Suavizado y detección de bordes | 6.1.3, 6.4.2 |

---

*CS4016 Computación Gráfica · UTEC*
