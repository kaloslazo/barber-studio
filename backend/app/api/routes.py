import cv2
import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from app.core.pipeline import StylePipeline

router = APIRouter(prefix="/api")
pipeline = StylePipeline()


def decode_image(data):
    buffer = np.frombuffer(data, np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=400, detail="Invalid image file")
    return image


def encode_png(image):
    success, encoded = cv2.imencode(".png", image)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to encode result")
    return Response(content=encoded.tobytes(), media_type="image/png")


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/preview")
async def preview(image: UploadFile = File(...)):
    image_bgr = decode_image(await image.read())
    return encode_png(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY))


@router.post("/dye")
async def dye(
    image: UploadFile = File(...),
    color: str = Form("#7a3ba8"),
    strength: float = Form(0.75),
):
    image_bgr = decode_image(await image.read())
    try:
        result = pipeline.apply_hair_dye(image_bgr, color, strength)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    if result is None:
        raise HTTPException(status_code=422, detail="No face detected in the image")
    return encode_png(result)
