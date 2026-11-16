import base64
import hashlib
import io
import json
import threading
import time
import zipfile
from collections import deque
from pathlib import Path

import cv2
import numpy as np
from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, Response

from app.core.compositing.beard import STYLES
from app.core.compositing.haircut import STYLES as HAIRCUT_STYLES
from app.core.coloring.dye import hex_to_bgr
from app.core.compositing.look import apply_look
from app.core.detection.landmarks import MODELS_DIR
from app.core.faces.gallery import listing as gallery_listing
from app.core.faces.session import FaceStudio
from app.core.game.speedrun import TARGETS as GAME_TARGETS
from app.core.lab.session import LabSession
from app.core.pipeline import StylePipeline
from app.core.splatting.face3d import face_scan_debug_image
from app.core.splatting.head3d import to_ply
from app.core.splatting import turn_store

MAX_SIDE = 2048

router = APIRouter(prefix="/api")
pipeline = StylePipeline()
lab = LabSession(pipeline)
studio = FaceStudio()
work_lock = threading.Lock()
LIVE_DEBUG_FRAMES = 60
LIVE_DEBUG_DIR = Path(__file__).resolve().parents[3] / "data" / "live_debug"
live_debug = deque(maxlen=LIVE_DEBUG_FRAMES)


def locked(fn, *args, **kwargs):
    with work_lock:
        return fn(*args, **kwargs)


async def work(fn, *args, **kwargs):
    return await run_in_threadpool(locked, fn, *args, **kwargs)


def decode_image(data):
    buffer = np.frombuffer(data, np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=400, detail="Invalid image file")
    longest = max(image.shape[:2])
    if longest > MAX_SIDE:
        scale = MAX_SIDE / longest
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
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


HAIR_MODELS = ("auto", "yolo", "mediapipe")


@router.get("/health")
def health():
    return {"status": "ok", "yolo": pipeline.yolo_available}


@router.post("/face-shape")
async def face_shape(image: UploadFile = File(...)):
    image_bgr = decode_image(await image.read())
    result = await work(pipeline.face_shape, image_bgr)
    if result is None:
        raise HTTPException(status_code=422, detail="No face detected in the image")
    return result


@router.post("/preview")
async def preview(image: UploadFile = File(...)):
    image_bgr = decode_image(await image.read())
    return encode_png(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY))


@router.post("/dye")
async def dye(
    image: UploadFile = File(...),
    color: str = Form("#7a3ba8"),
    strength: float = Form(0.75),
    beard: bool = Form(False),
    beard_style: str = Form(""),
    model: str = Form("auto"),
):
    if model not in HAIR_MODELS:
        raise HTTPException(status_code=400, detail=f"Unknown hair model: {model}")
    if beard_style and beard_style not in STYLES:
        raise HTTPException(status_code=400, detail=f"Unknown beard style: {beard_style}")
    image_bgr = decode_image(await image.read())
    info = {}
    try:
        result = await work(pipeline.apply_hair_dye, image_bgr, color, strength, beard=beard, model=model, info=info, beard_style=beard_style or None)
    except ValueError as error:
        status = 422 if str(error).startswith("No hair") else 400
        raise HTTPException(status_code=status, detail=str(error))
    if result is None:
        raise HTTPException(status_code=422, detail="No face detected in the image")
    response = encode_png(result)
    response.headers["X-Hair-Model"] = info.get("model", "mediapipe")
    if "agreement" in info:
        response.headers["X-Mask-Agreement"] = f"{info['agreement']:.3f}"
    response.headers["X-Beard-Dyed"] = "1" if info.get("beard") else "0"
    return response


@router.post("/beard")
async def beard(
    image: UploadFile = File(...),
    style: str = Form("full"),
    strength: float = Form(0.9),
):
    if style not in STYLES:
        raise HTTPException(status_code=400, detail=f"Unknown beard style: {style}")
    image_bgr = decode_image(await image.read())
    try:
        result = await work(pipeline.apply_beard, image_bgr, style, strength, strict=True)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
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
    if style not in HAIRCUT_STYLES:
        raise HTTPException(status_code=400, detail=f"Unknown haircut style: {style}")
    image_bgr = decode_image(await image.read())
    try:
        result = await work(pipeline.apply_haircut, image_bgr, style, strength)
    except ValueError as error:
        status = 422 if str(error).startswith(("No hair", "Face turned")) else 400
        raise HTTPException(status_code=status, detail=str(error))
    if result is None:
        raise HTTPException(status_code=422, detail="No face detected in the image")
    return encode_png(result)


@router.post("/mesh")
async def mesh(image: UploadFile = File(...)):
    image_bgr = decode_image(await image.read())
    result = await work(pipeline.face_mesh, image_bgr)
    if result is None:
        raise HTTPException(
            status_code=422, detail="No face detected or landmark model missing"
        )
    return encode_png(result)


@router.get("/models/face_landmarker.task")
async def face_landmarker_model():
    path = MODELS_DIR / "face_landmarker.task"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Face landmarker model not found")
    return FileResponse(path, media_type="application/octet-stream")


@router.post("/transfer/scan")
async def transfer_scan(image: UploadFile = File(...)):
    data = await image.read()
    image_bgr = decode_image(data)
    result, pose, yaw, anchor = await work(pipeline.transfer_scan, image_bgr, frame_key(data))
    response = encode_png(result)
    response.headers["X-Head-Anchor"] = json.dumps(anchor)
    response.headers["X-Head-Pose"] = pose
    response.headers["X-Head-Yaw"] = str(yaw)
    return response


@router.post("/transfer/asset")
async def transfer_asset(image: UploadFile = File(...)):
    image_bgr = decode_image(await image.read())
    result = await work(pipeline.transfer_asset, image_bgr)
    if result is None:
        raise HTTPException(status_code=422, detail="No hair or face detected in the image")
    return encode_png(result)


@router.post("/transfer/tryon")
async def transfer_tryon(image: UploadFile = File(...), reset: bool = Form(False)):
    image_bgr = decode_image(await image.read())
    if reset:
        await work(pipeline.reset_tryon)
    anchor = await work(pipeline.transfer_tryon, image_bgr)
    return JSONResponse(anchor)


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
        mesh = await work(pipeline.reconstruct_transfer_mesh, images, angle_values)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    return JSONResponse(mesh)


def frame_key(data):
    return hashlib.sha1(data).hexdigest()


@router.post("/transfer/face")
async def transfer_face(face_frames: List[UploadFile] = File(...)):
    data = [await frame.read() for frame in face_frames]
    images = [decode_image(item) for item in data]
    try:
        scan = await work(pipeline.face_scan, images, frame_key(b"".join(data)))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    success, encoded = cv2.imencode(".jpg", face_scan_debug_image(scan))
    if not success:
        raise HTTPException(status_code=500, detail="Could not create face scan debug image")
    debug_image = "data:image/jpeg;base64," + base64.b64encode(encoded.tobytes()).decode("ascii")
    return JSONResponse({"views": len(images), "debug_image": debug_image})


@router.post("/transfer/photos")
async def transfer_photos(
    frames: List[UploadFile] = File(...),
    angles: str = Form(""),
    face_frames: List[UploadFile] = File(None),
):
    angle_values = [value.strip() for value in angles.split(",") if value.strip()]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        for index, frame in enumerate(frames):
            angle = angle_values[index] if index < len(angle_values) else str(index)
            archive.writestr(f"hair/hair_{index:02d}_{angle}deg.jpg", await frame.read())
        for index, frame in enumerate(face_frames or []):
            archive.writestr(f"face/face_{index:02d}.jpg", await frame.read())
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=barberstudio_scan_photos.zip"},
    )


@router.post("/turn/frame")
async def turn_frame(session: str = Form(...), image: UploadFile = File(...)):
    frame = decode_image(await image.read())
    try:
        return await work(pipeline.turn_frame, session, frame)
    except ValueError as error:
        raise HTTPException(status_code=503, detail=str(error))


@router.post("/turn/solve")
async def turn_solve(session: str = Form(...), bin_degrees: float = Form(12.0)):
    found = pipeline.turn_sessions.get(session, create=False)
    if found is None:
        raise HTTPException(status_code=404, detail="Unknown scan session")
    try:
        yaw, picks, fraction, bins = found.solve(bin_degrees)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    return {
        "yaws": [float(value) for value in yaw],
        "picks": [int(index) for index in picks],
        "coverage": float(fraction),
        "bins": [int(value) for value in bins],
        "frames": len(yaw),
    }


@router.post("/turn/video")
async def turn_video(video: UploadFile = File(...)):
    path = await turn_store.spool(video)
    try:
        result = await work(pipeline.turn_video, path)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    finally:
        turn_store.discard(path)
    result["frames"] = ["data:image/jpeg;base64," + base64.b64encode(frame).decode("ascii") for frame in result["frames"]]
    result["face_frames"] = ["data:image/jpeg;base64," + base64.b64encode(frame).decode("ascii") for frame in result["face_frames"]]
    return result


@router.post("/transfer/splat")
async def transfer_splat(
    frames: List[UploadFile] = File(...),
    angles: str = Form("0"),
    mannequin: str = Form("true"),
    format: str = Form("raw"),
    head: str = Form("mannequin"),
    turn: str = Form("false"),
    face_mirror: str = Form("false"),
    face_frames: List[UploadFile] = File(None),
    heads: str = Form("one"),
):
    both = heads == "both"
    angle_values = [float(value) for value in angles.split(",") if value.strip()]
    if len(frames) != len(angle_values):
        raise HTTPException(status_code=400, detail="Frames and scan angles must match")
    data = [await frame.read() for frame in frames]
    images = [decode_image(item) for item in data]
    faces, face_key = None, None
    if head == "face":
        if not face_frames:
            raise HTTPException(status_code=400, detail="Scan your face first in 3D Peluca > Your face")
        face_data = [await frame.read() for frame in face_frames]
        faces, face_key = [decode_image(item) for item in face_data], frame_key(b"".join(face_data) + face_mirror.encode())
        if face_mirror == "true":
            faces = [cv2.flip(face, 1) for face in faces]
    try:
        if turn == "true":
            turn_store.save(data, angle_values)
            rows, meta = await work(pipeline.hair3d_turn, images, angle_values, mannequin != "false", faces, face_key, both=both)
        else:
            rows, meta = await work(
                pipeline.hair3d, images, angle_values, mannequin != "false", faces, [frame_key(item) for item in data], face_key, both=both,
            )
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
        headers={
            "X-Splat-Count": str(meta["count"]), "X-Splat-Hair": str(meta["hair"]), "X-Splat-Views": str(meta["views"]),
            "X-Splat-Face": str(meta.get("face", 0)), "X-Splat-Mannequin": str(meta.get("mannequin", 0)), "X-Splat-Body": str(meta.get("body", 0)),
        },
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
    result = await work(
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
    await work(pipeline.start_game, target)
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
    result, stats = await work(pipeline.game_frame, image_bgr, pointer, use_hand, pointer_down=pointer_down)
    return JSONResponse({"image": to_data_url(result, 85), **stats})


@router.post("/head3d")
async def head3d(image: UploadFile = File(...), beard: str = Form("none"), format: str = Form("raw")):
    if beard != "none" and beard not in STYLES:
        raise HTTPException(status_code=400, detail=f"Unknown beard style: {beard}")
    image_bgr = decode_image(await image.read())
    rows, meta = await work(pipeline.head3d, image_bgr, None if beard == "none" else beard)
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
    debug: str = Form("0"),
):
    if mode not in ("dye", "beard", "mesh", "physics"):
        raise HTTPException(status_code=400, detail=f"Unknown live mode: {mode}")
    raw = await image.read()
    image_bgr = decode_image(raw)
    h, w = image_bgr.shape[:2]
    if mode == "beard":
        if w > 1280:
            image_bgr = cv2.resize(image_bgr, (1280, int(h * 1280 / w)), interpolation=cv2.INTER_AREA)
        info = {} if debug == "1" else None
        result = await work(pipeline.apply_beard_live_hd, image_bgr, style, strength, 640, info)
        response = encode_jpeg(result if result is not None else image_bgr, 90)
        response.headers["X-Face-Found"] = "0" if result is None or (info and not info.get("face", True)) else "1"
        if info is not None:
            clean = info.pop("clean", None)
            live_debug.append({"input": raw, "output": response.body, "style": style, "info": info,
                               "clean": None if clean is None else encode_jpeg(clean, 90).body})
        return response
    if w > 640:
        scale = 640 / w
        image_bgr = cv2.resize(image_bgr, (640, int(h * scale)))
    if mode == "beard":
        result = await work(pipeline.apply_beard, image_bgr, style, strength, live=True)
    elif mode == "physics":
        result = await work(pipeline.apply_beard_physics, image_bgr, strength, length=float(np.clip(length, 0.4, 2.0)))
    elif mode == "mesh":
        result = await work(pipeline.face_mesh, image_bgr)
    else:
        try:
            result = await work(pipeline.apply_hair_dye, image_bgr, color, strength, live=True)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error))
    response = encode_jpeg(result if result is not None else image_bgr)
    response.headers["X-Face-Found"] = "0" if result is None else "1"
    return response


@router.post("/live/debug/save")
def live_debug_save():
    if not live_debug:
        raise HTTPException(status_code=409, detail="No debug frames yet: turn on Depurar with the camera running")
    folder = LIVE_DEBUG_DIR / time.strftime("%Y%m%d-%H%M%S")
    folder.mkdir(parents=True, exist_ok=True)
    meta = []
    for index, item in enumerate(list(live_debug)):
        (folder / f"{index:03d}_in.jpg").write_bytes(item["input"])
        (folder / f"{index:03d}_out.jpg").write_bytes(item["output"])
        if item["clean"]:
            (folder / f"{index:03d}_clean.jpg").write_bytes(item["clean"])
        meta.append({"frame": index, "style": item["style"], **item["info"]})
    if pipeline.live_reference_frame is not None:
        (folder / "reference.jpg").write_bytes(encode_jpeg(pipeline.live_reference_frame, 95).body)
    (folder / "meta.json").write_text(json.dumps(meta, indent=1))
    return {"folder": str(folder), "frames": len(meta)}


@router.post("/lab/build")
async def lab_build(frames: List[UploadFile] = File(...), beard: str = Form("none")):
    if beard != "none" and beard not in STYLES:
        raise HTTPException(status_code=400, detail=f"Unknown beard style: {beard}")
    if not 1 <= len(frames) <= 16:
        raise HTTPException(status_code=400, detail="Send between 1 and 16 frames")
    images = [decode_image(await frame.read()) for frame in frames]
    result = await work(lab.build, images, None if beard == "none" else beard)
    if result is None:
        raise HTTPException(status_code=422, detail="No face found in the scan frames")
    return JSONResponse(result)


@router.post("/lab/mesh")
async def lab_mesh(image: UploadFile = File(...)):
    image_bgr = decode_image(await image.read())
    return JSONResponse({"mesh": await work(lab.live_mesh, image_bgr)})


async def read_optional(upload):
    if upload is None:
        return None
    data = await upload.read()
    return decode_image(data) if data else None


async def run_faces(image_bgr, mode, preset, amount, live=False, other=None):
    try:
        return await work(studio.apply, image_bgr, mode, preset, amount, live, other)
    except LookupError as error:
        raise HTTPException(status_code=409, detail=str(error))
    except ValueError as error:
        status = 422 if str(error).startswith("No face") else 400
        raise HTTPException(status_code=status, detail=str(error))


@router.post("/faces/source")
async def faces_source(image: UploadFile = File(...)):
    image_bgr = decode_image(await image.read())
    face = await work(studio.set_source, image_bgr)
    if face is None:
        raise HTTPException(status_code=422, detail="No face detected in the image")
    return encode_jpeg(face)


@router.post("/faces/photo")
async def faces_photo(
    image: UploadFile = File(...),
    other: UploadFile = File(None),
    mode: str = Form("swap"),
    preset: str = Form("caricature"),
    amount: float = Form(0.8),
):
    image_bgr = decode_image(await image.read())
    other_bgr = await read_optional(other)
    result, count = await run_faces(image_bgr, mode, preset, amount, other=other_bgr)
    if count == 0:
        raise HTTPException(status_code=422, detail="No face detected in the image")
    if mode == "swap" and other_bgr is None and count < 2:
        raise HTTPException(status_code=422, detail="Need two faces in the photo")
    response = encode_png(result)
    response.headers["X-Faces"] = str(count)
    return response


@router.post("/faces/live")
async def faces_live(
    image: UploadFile = File(...),
    mode: str = Form("swap"),
    preset: str = Form("caricature"),
    amount: float = Form(0.8),
):
    image_bgr = decode_image(await image.read())
    h, w = image_bgr.shape[:2]
    if w > 640:
        image_bgr = cv2.resize(image_bgr, (640, int(h * 640 / w)), interpolation=cv2.INTER_AREA)
    result, count = await run_faces(image_bgr, mode, preset, amount, live=True)
    response = encode_jpeg(result, 85)
    response.headers["X-Faces"] = str(count)
    return response


@router.post("/faces/fusion")
async def faces_fusion(image: UploadFile = File(...), other: UploadFile = File(None), steps: int = Form(13)):
    image_bgr = decode_image(await image.read())
    other_bgr = await read_optional(other)
    try:
        frames = await work(studio.fusion, image_bgr, other_bgr, int(np.clip(steps, 3, 25)))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    return JSONResponse({"frames": [to_data_url(frame, 88) for frame in frames]})


@router.get("/gallery")
def gallery_list():
    return gallery_listing()


@router.post("/gallery")
async def gallery(image: UploadFile = File(...), key: str = Form("")):
    image_bgr = decode_image(await image.read())
    try:
        results = await work(studio.gallery, image_bgr, key or None)
    except ValueError as error:
        status = 422 if str(error).startswith("No face") else 400
        raise HTTPException(status_code=status, detail=str(error))
    return JSONResponse({"results": [{"key": name, "image": to_data_url(picture, 88)} for name, picture in results]})


@router.post("/look")
async def look(
    image: UploadFile = File(...),
    beard: str = Form(""),
    color: str = Form(""),
    cut: str = Form(""),
):
    if beard and beard not in STYLES:
        raise HTTPException(status_code=400, detail=f"Unknown beard style: {beard}")
    if cut and cut not in HAIRCUT_STYLES:
        raise HTTPException(status_code=400, detail=f"Unknown haircut style: {cut}")
    if color:
        try:
            hex_to_bgr(color)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error))
    image_bgr = decode_image(await image.read())
    try:
        result, skipped = await work(apply_look, pipeline, image_bgr, beard or None, color or None, cut or None)
    except ValueError as error:
        status = 422 if str(error).startswith("No face") else 400
        raise HTTPException(status_code=status, detail=str(error))
    response = encode_png(result)
    response.headers["X-Skipped"] = ",".join(skipped)
    return response

