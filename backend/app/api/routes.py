import base64
import json

import cv2
import numpy as np
from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response

from app.core.compositing.beard import STYLES
from app.core.compositing.haircut import STYLES as HAIRCUT_STYLES
from app.core.game.speedrun import TARGETS as GAME_TARGETS
from app.core.compositing.haircut import DISABLED_STYLES as HAIRCUT_DISABLED
from app.core.lab.session import LabSession
from app.core.pipeline import StylePipeline
from app.core.splatting.head3d import to_ply

router = APIRouter(prefix="/api")
pipeline = StylePipeline()
lab = LabSession(pipeline)


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


def encode_jpeg(image, quality=88):
    success, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not success:
        raise HTTPException(status_code=500, detail="Failed to encode result")
    return Response(content=encoded.tobytes(), media_type="image/jpeg")


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


@router.post("/beard")
async def beard(
    image: UploadFile = File(...),
    style: str = Form("full"),
    strength: float = Form(0.9),
):
    if style not in STYLES:
        raise HTTPException(status_code=400, detail=f"Unknown beard style: {style}")
    image_bgr = decode_image(await image.read())
    result = pipeline.apply_beard(image_bgr, style, strength)
    if result is None:
        raise HTTPException(
            status_code=422, detail="No face detected or landmark model missing"
        )
    return encode_png(result)


@router.post("/haircut")
async def haircut(
    image: UploadFile = File(...),
    style: str = Form("low-fade"),
    strength: float = Form(0.9),
):
    if style in HAIRCUT_DISABLED:
        raise HTTPException(
            status_code=400,
            detail=f"Style '{style}' is temporarily disabled during low-fade validation",
        )
    if style not in HAIRCUT_STYLES:
        raise HTTPException(status_code=400, detail=f"Unknown haircut style: {style}")
    image_bgr = decode_image(await image.read())
    try:
        result = pipeline.apply_haircut(image_bgr, style, strength)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    if result is None:
        raise HTTPException(status_code=422, detail="No face detected in the image")
    return encode_png(result)


@router.post("/mesh")
async def mesh(image: UploadFile = File(...)):
    image_bgr = decode_image(await image.read())
    result = pipeline.face_mesh(image_bgr)
    if result is None:
        raise HTTPException(
            status_code=422, detail="No face detected or landmark model missing"
        )
    return encode_png(result)


@router.post("/transfer/scan")
async def transfer_scan(image: UploadFile = File(...)):
    image_bgr = decode_image(await image.read())
    result, pose, yaw = pipeline.transfer_scan(image_bgr)
    response = encode_png(result)
    response.headers["X-Head-Pose"] = pose
    response.headers["X-Head-Yaw"] = str(yaw)
    return response


@router.post("/transfer/asset")
async def transfer_asset(image: UploadFile = File(...)):
    image_bgr = decode_image(await image.read())
    result = pipeline.transfer_asset(image_bgr)
    if result is None:
        raise HTTPException(status_code=422, detail="No hair or face detected in the image")
    return encode_png(result)


@router.post("/transfer/tryon")
async def transfer_tryon(image: UploadFile = File(...), reset: bool = Form(False)):
    image_bgr = decode_image(await image.read())
    if reset:
        pipeline.reset_tryon()
    result, anchor = await run_in_threadpool(pipeline.transfer_tryon, image_bgr)
    response = encode_jpeg(result, 85)
    response.headers["X-Tryon-Anchor"] = json.dumps(anchor)
    return response


@router.post("/transfer/reconstruct")
async def transfer_reconstruct(
    frames: List[UploadFile] = File(...),
    angles: str = Form(...),
):
    angle_values = [float(value) for value in angles.split(",") if value.strip()]
    if len(frames) != len(angle_values) or len(frames) < 3:
        raise HTTPException(status_code=400, detail="Frames and scan angles must match")
    images = [decode_image(await frame.read()) for frame in frames]
    try:
        mesh = pipeline.reconstruct_transfer_mesh(images, angle_values)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    return JSONResponse(mesh)


@router.post("/transfer/splat")
async def transfer_splat(
    frames: List[UploadFile] = File(...),
    angles: str = Form("0"),
    mannequin: str = Form("true"),
    format: str = Form("raw"),
):
    angle_values = [float(value) for value in angles.split(",") if value.strip()]
    if len(frames) != len(angle_values):
        raise HTTPException(status_code=400, detail="Frames and scan angles must match")
    images = [decode_image(await frame.read()) for frame in frames]
    try:
        rows, meta = await run_in_threadpool(pipeline.hair3d, images, angle_values, mannequin != "false")
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    if rows is None:
        raise HTTPException(status_code=422, detail="No hair detected in the captures")
    if format == "ply":
        return Response(
            content=to_ply(rows),
            media_type="application/octet-stream",
            headers={"Content-Disposition": "attachment; filename=barberstudio_peluca.ply"},
        )
    return Response(
        content=rows.tobytes(),
        media_type="application/octet-stream",
        headers={"X-Splat-Count": str(meta["count"]), "X-Splat-Hair": str(meta["hair"]), "X-Splat-Views": str(meta["views"])},
    )


def to_data_url(image, quality=90):
    success, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not success:
        raise HTTPException(status_code=500, detail="Failed to encode result")
    return "data:image/jpeg;base64," + base64.b64encode(encoded.tobytes()).decode("ascii")


@router.post("/gaussians")
async def gaussians(
    image: UploadFile = File(...),
    count: int = Form(200),
    face_crop: bool = Form(True),
    beard: str = Form("none"),
):
    if not 10 <= count <= 5000:
        raise HTTPException(status_code=400, detail="count must be between 10 and 5000")
    if beard != "none" and beard not in STYLES:
        raise HTTPException(status_code=400, detail=f"Unknown beard style: {beard}")
    image_bgr = decode_image(await image.read())
    result = await run_in_threadpool(
        pipeline.gaussian_portrait, image_bgr, count, face_crop, None if beard == "none" else beard,
    )
    return JSONResponse({
        "count": count,
        "psnr": round(result["psnr"], 2),
        "seconds": round(result["seconds"], 2),
        "iterations": result["iterations"],
        "render": to_data_url(result["render"]),
        "ellipses": to_data_url(result["ellipses"]),
        "target": to_data_url(result["target"]),
    })


@router.post("/game/start")
async def game_start(target: str = Form("goatee")):
    if target not in GAME_TARGETS:
        raise HTTPException(status_code=400, detail=f"Unknown target: {target}")
    pipeline.start_game(target)
    return JSONResponse({"target": target})


@router.post("/game/frame")
async def game_frame(
    image: UploadFile = File(...),
    pointer_x: float = Form(-1.0),
    pointer_y: float = Form(-1.0),
    pointer_down: bool = Form(False),
    use_hand: bool = Form(True),
):
    image_bgr = decode_image(await image.read())
    h, w = image_bgr.shape[:2]
    if w > 640:
        scale = 640 / w
        image_bgr = cv2.resize(image_bgr, (640, int(h * scale)))
        h, w = image_bgr.shape[:2]
    pointer = None
    if 0.0 <= pointer_x <= 1.0 and 0.0 <= pointer_y <= 1.0:
        pointer = (pointer_x * w, pointer_y * h)
    result, stats = pipeline.game_frame(image_bgr, pointer, use_hand, pointer_down=pointer_down)
    return JSONResponse({"image": to_data_url(result, 85), **stats})


@router.post("/head3d")
async def head3d(image: UploadFile = File(...), beard: str = Form("none"), format: str = Form("raw")):
    if beard != "none" and beard not in STYLES:
        raise HTTPException(status_code=400, detail=f"Unknown beard style: {beard}")
    image_bgr = decode_image(await image.read())
    rows, meta = await run_in_threadpool(pipeline.head3d, image_bgr, None if beard == "none" else beard)
    if rows is None:
        raise HTTPException(status_code=422, detail="No face detected or landmark model missing")
    if format == "ply":
        return Response(
            content=to_ply(rows),
            media_type="application/octet-stream",
            headers={"Content-Disposition": "attachment; filename=barberstudio_head.ply"},
        )
    return Response(
        content=rows.tobytes(),
        media_type="application/octet-stream",
        headers={"X-Splat-Count": str(meta["count"]), "X-Splat-Beard": str(meta["beard"])},
    )


@router.post("/live")
async def live(
    image: UploadFile = File(...),
    mode: str = Form("dye"),
    color: str = Form("#7a3ba8"),
    style: str = Form("full"),
    strength: float = Form(0.75),
    length: float = Form(1.0),
):
    if mode not in ("dye", "beard", "mesh", "physics"):
        raise HTTPException(status_code=400, detail=f"Unknown live mode: {mode}")
    image_bgr = decode_image(await image.read())
    h, w = image_bgr.shape[:2]
    if mode == "beard":
        if w > 1280:
            image_bgr = cv2.resize(image_bgr, (1280, int(h * 1280 / w)), interpolation=cv2.INTER_AREA)
        result = pipeline.apply_beard_live_hd(image_bgr, style, strength)
        response = encode_jpeg(result if result is not None else image_bgr, 90)
        response.headers["X-Face-Found"] = "0" if result is None else "1"
        return response
    if w > 640:
        scale = 640 / w
        image_bgr = cv2.resize(image_bgr, (640, int(h * scale)))
    if mode == "beard":
        result = pipeline.apply_beard(image_bgr, style, strength, live=True)
    elif mode == "physics":
        result = pipeline.apply_beard_physics(image_bgr, strength, length=float(np.clip(length, 0.4, 2.0)))
    elif mode == "mesh":
        result = pipeline.face_mesh(image_bgr)
    else:
        result = pipeline.apply_hair_dye(image_bgr, color, strength)
    response = encode_jpeg(result if result is not None else image_bgr)
    response.headers["X-Face-Found"] = "0" if result is None else "1"
    return response


@router.post("/lab/build")
async def lab_build(frames: List[UploadFile] = File(...), beard: str = Form("none")):
    if beard != "none" and beard not in STYLES:
        raise HTTPException(status_code=400, detail=f"Unknown beard style: {beard}")
    if not 1 <= len(frames) <= 16:
        raise HTTPException(status_code=400, detail="Send between 1 and 16 frames")
    images = [decode_image(await frame.read()) for frame in frames]
    result = await run_in_threadpool(lab.build, images, None if beard == "none" else beard)
    if result is None:
        raise HTTPException(status_code=422, detail="No face found in the scan frames")
    return JSONResponse(result)


@router.post("/lab/mesh")
async def lab_mesh(image: UploadFile = File(...)):
    image_bgr = decode_image(await image.read())
    return JSONResponse({"mesh": lab.live_mesh(image_bgr)})
