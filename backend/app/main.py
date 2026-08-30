import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

app = FastAPI(title="BarberStudio API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/preview")
async def preview(image: UploadFile = File(...)):
    data = await image.read()
    buffer = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image file")
    processed = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    success, encoded = cv2.imencode(".png", processed)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to encode result")
    return Response(content=encoded.tobytes(), media_type="image/png")
