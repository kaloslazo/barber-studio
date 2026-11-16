const TURN_BIN_DEGREES = 12;
const TURN_BINS = 360 / TURN_BIN_DEGREES;
const TURN_INTERVAL_MS = 110;
const TURN_MAX_SECONDS = 60;
const TURN_MIN_COVERAGE = 0.4;
const TURN_DONE_COVERAGE = 0.92;
const TURN_MIN_TURNED = 330;
const TURN_FACE_FRAMES = 8;
const TURN_COUNTDOWN = 3;
const TURN_MILESTONES = [
  [0.25, "Vas bien, sigue girando"],
  [0.5, "Media vuelta, sigue"],
  [0.75, "Ya casi, sigue"],
];
const TURN_REASONS = [
  [/face in view|scan needs the face/i, "No te vi de frente", "Empieza y termina mirando a la cámara, sin taparte la cara."],
  [/silhouettes do not overlap/i, "El pelo no coincidía entre una vista y otra", "Quédate en el centro del cuadro mientras giras, sin acercarte ni alejarte."],
  [/no hair/i, "No encontré pelo", "Que se vea todo el pelo, con luz pareja de frente y sin gorra ni capucha."],
  [/unknown scan session/i, "Se perdió el escaneo", "El servidor se reinició a mitad del giro. Vuelve a empezar."],
  [/part segmenter/i, "Falta un modelo en el servidor", "El segmentador de partes no cargó. Reinicia el servidor."],
  [/failed to fetch|load failed|networkerror|conexión/i, "No hay conexión con el servidor", "Revisa que el servidor siga prendido y vuelve a intentar."],
  [/no face|scan your face/i, "No vi bien tu cara", "Mira de frente con buena luz al empezar y al terminar la vuelta."],
];

const turnStage = document.getElementById("turn-stage");
const turnCanvas = document.getElementById("turn-canvas");
const turnEmpty = document.getElementById("turn-empty");
const turnEmptyTitle = turnEmpty.querySelector(".dz-title");
const turnEmptySub = turnEmpty.querySelector(".dz-sub");
const turnEmptyDefault = [turnEmptyTitle.textContent, turnEmptySub.textContent];
const turnBadge = document.getElementById("turn-badge");
const turnStatus = document.getElementById("turn-status");
const turnPercent = document.getElementById("turn-percent");
const turnVideo = document.getElementById("turn-video");
const turnStart = document.getElementById("turn-start");
const turnStop = document.getElementById("turn-stop");
const turnError = document.getElementById("turn-error");
const turnFileButton = document.getElementById("turn-file-button");
const turnFile = document.getElementById("turn-file");

const turn = {
  stream: null, running: false, counting: false, count: 0, countTimer: null, busy: false, session: "", frames: [], bins: [],
  yaw: 0, coverage: 0, turned: 0, startedAt: 0, timer: null, face: false, sent: 0, lost: 0, fast: 0, milestone: 0, hint: "",
};
const turnCapture = document.createElement("canvas");

freshVoice.bind(document.getElementById("turn-voice"));

function turnWrap(yaw) {
  return ((((yaw + 180) % 360) + 360) % 360) - 180;
}

function turnShowError(message) {
  turnError.textContent = message;
  turnError.hidden = !message;
}

function turnSetHint(text, speak = true) {
  turnBadge.hidden = !text;
  turnBadge.textContent = text || "";
  if (speak && text && text !== turn.hint) freshVoice.say(text, { gap: text === "Más despacio" ? 1800 : 2800 });
  turn.hint = text || "";
}

function turnReason(message) {
  const rule = TURN_REASONS.find(([pattern]) => pattern.test(message || ""));
  return rule ? [rule[1], rule[2]] : ["No se pudo armar la peluca", message || "Vuelve a intentarlo girando más despacio."];
}

function turnShortReason() {
  const sent = Math.max(turn.sent, 1);
  if (turn.lost / sent > 0.35) return ["Casi no te vi", "Siéntate un poco más lejos para que entre toda la cabeza con el pelo, y prende una luz de frente."];
  if (turn.fast / sent > 0.25) return ["Giraste muy rápido", "Da la vuelta en unos 15 segundos, como en cámara lenta."];
  if (turn.turned < 90) return ["Casi no giraste", "Gira la silla una vuelta completa: la cámara tiene que verte la nuca y volver a tu cara."];
  return [`Solo vi el ${Math.round(turn.coverage * 100)} % de la vuelta`, "Sigue girando hasta volver a mirar de frente, sin apurarte."];
}

function turnFail(title, detail) {
  document.getElementById("hair3d-stage").hidden = true;
  document.getElementById("wig-studio").hidden = true;
  turnStage.hidden = false;
  turnShowError(`${title}. ${detail}`);
  turnEmpty.hidden = false;
  turnEmpty.classList.add("failed");
  turnEmptyTitle.textContent = title;
  turnEmptySub.textContent = detail;
  turnStatus.textContent = title;
  turnPercent.textContent = "";
  turnStart.textContent = "Intentar de nuevo";
  freshVoice.say(`${title}. ${detail}`, { now: true });
}

function turnResetEmpty() {
  turnEmpty.classList.remove("failed");
  [turnEmptyTitle.textContent, turnEmptySub.textContent] = turnEmptyDefault;
}

function drawTurn() {
  if (!turn.stream) return;
  const w = turnVideo.videoWidth;
  const h = turnVideo.videoHeight;
  if (w > 0) {
    if (turnCanvas.width !== w || turnCanvas.height !== h) {
      turnCanvas.width = w;
      turnCanvas.height = h;
    }
    const context = turnCanvas.getContext("2d");
    context.save();
    context.translate(w, 0);
    context.scale(-1, 1);
    context.drawImage(turnVideo, 0, 0, w, h);
    context.restore();
    drawTurnRing(context, w, h);
    if (turn.counting) drawTurnCount(context, w, h);
  }
  requestAnimationFrame(drawTurn);
}

function drawTurnCount(context, w, h) {
  const size = Math.min(w, h);
  context.save();
  context.fillStyle = "rgba(10, 10, 10, 0.55)";
  context.beginPath();
  context.arc(w / 2, h / 2, size * 0.16, 0, Math.PI * 2);
  context.fill();
  context.fillStyle = "#ffffff";
  context.font = `600 ${Math.round(size * 0.2)}px Figtree, sans-serif`;
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.fillText(String(turn.count), w / 2, h / 2 + size * 0.01);
  context.restore();
}

function drawTurnRing(context, w, h) {
  const cx = w / 2;
  const cy = h / 2;
  const radius = Math.min(w, h) * 0.44;
  const width = Math.max(8, Math.min(w, h) * 0.03);
  const toCanvas = (yaw) => ((-90 - yaw) * Math.PI) / 180;
  context.save();
  context.lineWidth = width;
  context.lineCap = "butt";
  for (let b = 0; b < TURN_BINS; b++) {
    const start = -180 + b * TURN_BIN_DEGREES;
    const covered = turn.bins.includes(b);
    context.strokeStyle = covered ? "rgba(226, 92, 80, 0.95)" : "rgba(255, 255, 255, 0.28)";
    context.beginPath();
    context.arc(cx, cy, radius, toCanvas(start + TURN_BIN_DEGREES - 1), toCanvas(start + 1), true);
    context.stroke();
  }
  if (turn.running) {
    const angle = toCanvas(turn.yaw);
    const tip = [cx + Math.cos(angle) * (radius + width), cy + Math.sin(angle) * (radius + width)];
    const left = [cx + Math.cos(angle + 0.07) * (radius + width * 2.4), cy + Math.sin(angle + 0.07) * (radius + width * 2.4)];
    const right = [cx + Math.cos(angle - 0.07) * (radius + width * 2.4), cy + Math.sin(angle - 0.07) * (radius + width * 2.4)];
    context.fillStyle = "#ffffff";
    context.beginPath();
    context.moveTo(...tip);
    context.lineTo(...left);
    context.lineTo(...right);
    context.closePath();
    context.fill();
  }
  context.restore();
}

function turnHint(info) {
  const seconds = (performance.now() - turn.startedAt) / 1000;
  if (!info.head) return "No te veo: siéntate en el centro del cuadro";
  if (!turn.face && seconds > 3 && turn.turned < 15) return "Mira de frente a la cámara";
  if (info.fast) return "Más despacio";
  if (turn.turned < 20) return "Gira despacio hacia un lado";
  if (turn.coverage >= TURN_DONE_COVERAGE && !info.face) return "Ahora vuelve a mirar de frente";
  return "Sigue girando";
}

async function turnSend() {
  if (!turn.running || turn.busy || turnVideo.videoWidth === 0) return;
  turn.busy = true;
  try {
    const scale = Math.min(1, 720 / turnVideo.videoWidth);
    turnCapture.width = Math.round(turnVideo.videoWidth * scale);
    turnCapture.height = Math.round(turnVideo.videoHeight * scale);
    turnCapture.getContext("2d").drawImage(turnVideo, 0, 0, turnCapture.width, turnCapture.height);
    const blob = await new Promise((resolve) => turnCapture.toBlob(resolve, "image/jpeg", 0.88));
    const formData = new FormData();
    formData.append("session", turn.session);
    formData.append("image", blob, "turn.jpg");
    const response = await fetch(`${API}/turn/frame`, { method: "POST", body: formData });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `El escaneo falló (${response.status})`);
    }
    const info = await response.json();
    if (!turn.running) return;
    turn.frames[info.index] = blob;
    turn.yaw = info.yaw;
    turn.bins = info.bins;
    turn.coverage = info.coverage;
    turn.turned = info.turned;
    turn.face = info.face;
    turn.sent += 1;
    if (!info.head) turn.lost += 1;
    if (info.fast) turn.fast += 1;
    turnPercent.textContent = `${Math.round(info.coverage * 100)} %`;
    turnStatus.textContent = `${turn.frames.length} cuadros · giraste ${Math.round(info.turned)}°`;
    const next = TURN_MILESTONES[turn.milestone];
    if (next && turn.coverage >= next[0] && info.head && !info.fast) {
      turn.milestone += 1;
      freshVoice.say(next[1], { now: true });
      turn.hint = next[1];
    }
    turnSetHint(turnHint(info));
    const seconds = (performance.now() - turn.startedAt) / 1000;
    const closed = turn.coverage >= TURN_DONE_COVERAGE && turn.turned >= TURN_MIN_TURNED && info.face;
    if (closed || seconds > TURN_MAX_SECONDS) finishTurn();
  } catch (error) {
    stopTurn(true);
    const [title, detail] = turnReason(error.message);
    turnFail(title, detail);
  } finally {
    turn.busy = false;
  }
}

async function startTurn() {
  turnShowError("");
  if (turn.running || turn.counting) return;
  if (!turn.stream) {
    try {
      turn.stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, facingMode: "user" }, audio: false });
      turnVideo.srcObject = turn.stream;
      await turnVideo.play();
    } catch (error) {
      turnShowError(`No se pudo abrir la cámara: ${error.message}`);
      turn.stream = null;
      return;
    }
  }
  turnStage.hidden = false;
  document.getElementById("hair3d-stage").hidden = true;
  document.getElementById("wig-studio").hidden = true;
  turnResetEmpty();
  turnEmpty.hidden = true;
  Object.assign(turn, { bins: [], yaw: 0, coverage: 0, turned: 0, counting: true, count: TURN_COUNTDOWN, hint: "" });
  turnStart.disabled = true;
  turnStop.disabled = false;
  turnStatus.textContent = "Acomódate…";
  turnPercent.textContent = "";
  turnSetHint("Siéntate y mira de frente", false);
  freshVoice.say("Siéntate y mira de frente. Empezamos en tres, dos, uno.", { now: true });
  requestAnimationFrame(drawTurn);
  turn.countTimer = setInterval(() => {
    turn.count -= 1;
    if (turn.count > 0) return;
    clearInterval(turn.countTimer);
    turn.counting = false;
    beginTurn();
  }, 1000);
}

function beginTurn() {
  Object.assign(turn, {
    running: true, busy: false, session: `t${Date.now()}`, frames: [], bins: [], yaw: 0, coverage: 0, turned: 0,
    startedAt: performance.now(), face: false, sent: 0, lost: 0, fast: 0, milestone: 0, hint: "",
  });
  turnStatus.textContent = "Escaneando…";
  turnPercent.textContent = "0 %";
  turnSetHint("Gira despacio hacia un lado", false);
  freshVoice.say("Ahora gira despacio hacia un lado", { now: true });
  turn.timer = setInterval(turnSend, TURN_INTERVAL_MS);
}

function stopTurn(releaseCamera = true) {
  turn.running = false;
  turn.counting = false;
  clearInterval(turn.timer);
  clearInterval(turn.countTimer);
  turnStart.disabled = false;
  turnStop.disabled = true;
  turnSetHint("", false);
  if (releaseCamera && turn.stream) {
    turn.stream.getTracks().forEach((track) => track.stop());
    turn.stream = null;
    turnVideo.srcObject = null;
  }
}

function turnGap(bins) {
  const covered = new Set(bins);
  let best = null;
  let run = null;
  for (let i = 0; i < TURN_BINS * 2; i++) {
    const b = i % TURN_BINS;
    if (!covered.has(b)) {
      run = run || { start: i, length: 0 };
      run.length += 1;
      if (!best || run.length > best.length) best = { ...run };
    } else {
      run = null;
    }
    if (best && best.length >= TURN_BINS) break;
  }
  if (!best || best.length < 2) return "";
  const middle = turnWrap(-180 + (best.start + best.length / 2) * TURN_BIN_DEGREES);
  const where = Math.abs(middle) > 130 ? "la nuca" : Math.abs(middle) < 40 ? "el frente" : "un costado";
  return `no se vio ${where} (${Math.min(best.length, TURN_BINS) * TURN_BIN_DEGREES}°)`;
}

function evenly(list, count) {
  if (list.length <= count) return list;
  return Array.from({ length: count }, (_, i) => list[Math.round((i * (list.length - 1)) / (count - 1))]);
}

function turnUseFace(frames) {
  const ownFace = Boolean(faceScan && faceScan.webcam);
  if (!ownFace) faceScan = frames.length ? { frames } : null;
  const withFace = Boolean(faceScan && faceScan.frames.length);
  hair3dMyFace.disabled = !withFace;
  hair3dMyFace.checked = withFace;
  hair3dMannequin.checked = true;
  syncHeadChoice();
  updateScanPhotos();
  return { ownFace, withFace };
}

async function turnBuild(source, label, withFace) {
  freshVoice.say("Listo. Ahora armo tu peluca, dame unos segundos.", { now: true });
  let built = await buildHair3d(source, label);
  let faceless = false;
  if (built !== true && withFace) {
    hair3dMyFace.checked = false;
    syncHeadChoice();
    built = await buildHair3d({ ...source, note: `${source.note} · en el maniquí: tu cara no salió` }, label);
    faceless = built === true;
  }
  if (built !== true) {
    const [title, detail] = turnReason(built);
    turnFail(title, detail);
    return false;
  }
  turnStage.hidden = true;
  turnStart.textContent = "Escanear de nuevo";
  turnStatus.textContent = "Peluca lista";
  freshVoice.say(faceless
    ? "Tu peluca está lista, pero en el maniquí: tu cara no salió bien. Prueba escanear tu cara aparte."
    : "Tu peluca está lista. Gírala con el mouse o con el dedo.", { now: true });
  return true;
}

async function finishTurn() {
  if (turn.counting) {
    stopTurn(true);
    turnStatus.textContent = "Listo para escanear";
    turnEmpty.hidden = false;
    freshVoice.stop();
    return;
  }
  if (!turn.running) return;
  const session = turn.session;
  const frames = turn.frames.slice();
  stopTurn(true);
  if (turn.coverage < TURN_MIN_COVERAGE) {
    const [title, detail] = turnShortReason();
    turnFail(title, detail);
    return;
  }
  turnStatus.textContent = "Resolviendo los ángulos…";
  try {
    const formData = new FormData();
    formData.append("session", session);
    const response = await fetch(`${API}/turn/solve`, { method: "POST", body: formData });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `No se pudo resolver el giro (${response.status})`);
    }
    const solved = await response.json();
    const picks = solved.picks.filter((index) => frames[index]);
    const yaws = picks.map((index) => turnWrap(solved.yaws[index]));
    const frontal = picks.filter((index, i) => Math.abs(yaws[i]) <= 50).sort((a, b) => Math.abs(turnWrap(solved.yaws[a])) - Math.abs(turnWrap(solved.yaws[b])));
    const { ownFace } = turnUseFace(evenly(frontal, TURN_FACE_FRAMES).map((index) => frames[index]));
    turnStatus.textContent = `Giro resuelto: ${Math.round(solved.coverage * 100)} % de la vuelta, ${picks.length} vistas. Armando la peluca…`;
    turnPercent.textContent = "";
    const gap = turnGap(solved.bins);
    const note = `${Math.round(solved.coverage * 100)} % de la vuelta${gap ? `, ${gap}` : ""} · ${ownFace ? "cara de tu escaneo de 8 vistas" : "cara de este giro"}`;
    await turnBuild({ frames: picks.map((index) => frames[index]), angles: yaws.map((yaw) => yaw.toFixed(2)), turn: true, note }, "Peluca 360", Boolean(faceScan));
  } catch (error) {
    const [title, detail] = turnReason(error.message);
    turnFail(title, detail);
  }
}

turnStart.addEventListener("click", startTurn);
turnStop.addEventListener("click", finishTurn);

async function useTurnVideo(file) {
  turnShowError("");
  if (turn.running || turn.counting) stopTurn(true);
  turnStage.hidden = false;
  document.getElementById("hair3d-stage").hidden = true;
  document.getElementById("wig-studio").hidden = true;
  turnResetEmpty();
  turnEmpty.hidden = false;
  turnStart.disabled = true;
  turnFileButton.disabled = true;
  turnPercent.textContent = "";
  turnStatus.textContent = `Procesando ${file.name}… puede tardar cerca de un minuto`;
  try {
    const formData = new FormData();
    formData.append("video", file, file.name);
    const response = await fetch(`${API}/turn/video`, { method: "POST", body: formData });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `No se pudo leer el video (${response.status})`);
    }
    const result = await response.json();
    const blobs = await Promise.all(result.frames.map((url) => fetch(url).then((r) => r.blob())));
    const frontal = result.yaws.map((yaw, i) => i).filter((i) => Math.abs(result.yaws[i]) <= 50).sort((a, b) => Math.abs(result.yaws[a]) - Math.abs(result.yaws[b]));
    const closeUps = result.face_frames && result.face_frames.length >= 3
      ? await Promise.all(result.face_frames.map((url) => fetch(url).then((r) => r.blob())))
      : null;
    const { ownFace } = turnUseFace(closeUps || evenly(frontal, TURN_FACE_FRAMES).map((i) => blobs[i]));
    const gap = turnGap(result.bins);
    const note = `${Math.round(result.coverage * 100)} % de la vuelta${gap ? `, ${gap}` : ""} · ${ownFace ? "cara de tu escaneo de 8 vistas" : "cara del video"}`;
    turnStatus.textContent = `Video leído: ${result.sampled} cuadros, ${blobs.length} vistas. Armando la peluca…`;
    await turnBuild({ frames: blobs, angles: result.yaws.map((yaw) => yaw.toFixed(2)), turn: true, note }, "Peluca 360 (video)", Boolean(faceScan));
  } catch (error) {
    const [title, detail] = turnReason(error.message);
    turnFail(title, detail);
  } finally {
    turnStart.disabled = false;
    turnFileButton.disabled = false;
    turnFile.value = "";
  }
}

turnFileButton.addEventListener("click", () => turnFile.click());
turnFile.addEventListener("change", () => {
  if (turnFile.files && turnFile.files[0]) useTurnVideo(turnFile.files[0]);
});
