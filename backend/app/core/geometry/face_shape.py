import numpy as np

FOREHEAD = (54, 284)
CHEEKBONES = (234, 454)
JAW = (172, 397)
LENGTH = (10, 152)

TYPICAL = {
    "length": (1.219, 0.057),
    "forehead": (0.857, 0.029),
    "jaw": (0.805, 0.024),
    "angle": (135.2, 2.5),
}

SHAPES = {
    "ovalada": {
        "label": "Ovalada",
        "why": "Proporciones parejas: casi todo te queda. Un degradado medio mantiene ese equilibrio.",
        "haircut": ["mid-fade", "taper", "hard-part"],
        "beard": ["stubble", "goatee"],
        "avoid": [],
    },
    "redonda": {
        "label": "Redonda",
        "why": "Lados cortos y algo de altura arriba alargan la cara; el candado afina el mentón.",
        "haircut": ["high-fade", "undercut", "hard-part"],
        "beard": ["goatee", "full"],
        "avoid": ["buzz"],
    },
    "cuadrada": {
        "label": "Cuadrada",
        "why": "La mandíbula ya marca. Un degradado bajo y barba corta la suavizan sin endurecerla más.",
        "haircut": ["low-fade", "taper", "crew"],
        "beard": ["stubble", "full"],
        "avoid": [],
    },
    "alargada": {
        "label": "Alargada",
        "why": "Mejor sin mucha altura ni lados muy rapados; la barba completa da ancho abajo.",
        "haircut": ["low-fade", "taper", "crew"],
        "beard": ["full", "mustache"],
        "avoid": ["high-fade", "undercut"],
    },
    "corazon": {
        "label": "Corazón",
        "why": "Frente ancha y mentón angosto: la barba completa equilibra la parte de abajo.",
        "haircut": ["taper", "mid-fade", "crew"],
        "beard": ["full", "stubble"],
        "avoid": ["high-fade"],
    },
}


def _distance(mesh, pair):
    return float(np.linalg.norm(mesh[pair[0]] - mesh[pair[1]]))


def _jaw_angle(mesh, upper, corner, chin=152):
    a = mesh[upper] - mesh[corner]
    b = mesh[chin] - mesh[corner]
    cosine = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-6)
    return float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))


def measure(mesh):
    """Face proportions from the 3D MediaPipe mesh, as ratios to the
    cheekbone width so they do not depend on distance or image size."""
    mesh = np.asarray(mesh, np.float32)
    cheeks = max(_distance(mesh, CHEEKBONES), 1e-6)
    return {
        "length": _distance(mesh, LENGTH) / cheeks,
        "forehead": _distance(mesh, FOREHEAD) / cheeks,
        "jaw": _distance(mesh, JAW) / cheeks,
        "angle": (_jaw_angle(mesh, 234, 172) + _jaw_angle(mesh, 454, 397)) / 2.0,
    }


def classify(ratios):
    """Shape from how far each proportion sits from a typical face,
    measured in typical spreads (calibrated on 419 CelebAMask-HQ faces)."""
    z = {key: (ratios[key] - mean) / spread for key, (mean, spread) in TYPICAL.items()}
    if z["length"] > 1.0 and z["jaw"] < 0.5:
        return "alargada"
    if z["forehead"] > 0.6 and z["jaw"] < -0.6:
        return "corazon"
    if z["jaw"] > 0.4 and z["length"] < 0.6:
        return "cuadrada" if z["angle"] < -0.3 else "redonda"
    if z["length"] < -0.9:
        return "redonda"
    return "ovalada"


def face_shape(mesh):
    ratios = measure(mesh)
    shape = classify(ratios)
    advice = SHAPES[shape]
    return {
        "shape": shape,
        "label": advice["label"],
        "why": advice["why"],
        "haircut": advice["haircut"],
        "beard": advice["beard"],
        "avoid": advice["avoid"],
        "ratios": {key: round(value, 3) for key, value in ratios.items()},
    }
