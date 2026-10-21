import cv2


class FaceDetector:
    def __init__(self):
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.cascade = cv2.CascadeClassifier(cascade_path)
        profile_path = cv2.data.haarcascades + "haarcascade_profileface.xml"
        self.profile_cascade = cv2.CascadeClassifier(profile_path)
        if self.cascade.empty():
            raise RuntimeError("Failed to load Haar cascade model")

    def largest_face(self, image_bgr):
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        faces = self.cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80)
        )
        if len(faces) == 0:
            return None
        x, y, w, h = max(faces, key=lambda f: float(f[2]) * float(f[3]))
        return int(x), int(y), int(w), int(h)

    def pose(self, image_bgr):
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        scale = min(1.0, 400.0 / gray.shape[1])
        if scale < 1.0:
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

        def box(found):
            x, y, w, h = max(found, key=lambda f: float(f[2]) * float(f[3]))
            return tuple(int(round(value / scale)) for value in (x, y, w, h))

        faces = self.cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(int(80 * scale), int(80 * scale))
        )
        if len(faces):
            return "front", box(faces)
        size = (int(70 * scale), int(70 * scale))
        profiles = self.profile_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=size)
        if len(profiles):
            return "left", box(profiles)
        flipped = cv2.flip(gray, 1)
        profiles = self.profile_cascade.detectMultiScale(flipped, scaleFactor=1.1, minNeighbors=4, minSize=size)
        if len(profiles):
            x, y, w, h = box(profiles)
            return "right", (image_bgr.shape[1] - x - w, y, w, h)
        return "unknown", None
