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
        faces = self.cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80)
        )
        if len(faces):
            x, y, w, h = max(faces, key=lambda f: float(f[2]) * float(f[3]))
            return "front", (int(x), int(y), int(w), int(h))
        profiles = self.profile_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=4, minSize=(70, 70)
        )
        if len(profiles):
            x, y, w, h = max(profiles, key=lambda f: float(f[2]) * float(f[3]))
            return "left", (int(x), int(y), int(w), int(h))
        flipped = cv2.flip(gray, 1)
        profiles = self.profile_cascade.detectMultiScale(
            flipped, scaleFactor=1.1, minNeighbors=4, minSize=(70, 70)
        )
        if len(profiles):
            x, y, w, h = max(profiles, key=lambda f: float(f[2]) * float(f[3]))
            return "right", (int(gray.shape[1] - x - w), int(y), int(w), int(h))
        return "unknown", None
