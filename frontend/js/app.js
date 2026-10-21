const API = "/api";

const dropZone = document.getElementById("drop-zone");
const photoInput = document.getElementById("photo-input");
const applyBtn = document.getElementById("apply-btn");
const customColor = document.getElementById("custom-color");
const strengthInput = document.getElementById("strength");
const swatches = document.getElementById("swatches");
const errorBanner = document.getElementById("error-banner");
const compare = document.getElementById("compare");
const originalImage = document.getElementById("original-image");
const resultImage = document.getElementById("result-image");
const dzTitle = dropZone.querySelector(".dz-title");
const dzSub = dropZone.querySelector(".dz-sub");

const PRESETS = [
  { name: "Black", hex: "#1f1f1f" },
  { name: "Blonde", hex: "#d9b04a" },
  { name: "Red", hex: "#b3312c" },
  { name: "Blue", hex: "#2f4fb8" },
  { name: "Green", hex: "#3d8b3d" },
  { name: "Purple", hex: "#7a3ba8" },
  { name: "Pink", hex: "#d95fa6" },
];

let selectedColor = PRESETS[0].hex;
let selectedSwatch = null;
let selectedFile = null;

function showError(message) {
  errorBanner.textContent = message;
  errorBanner.hidden = false;
}

function clearError() {
  errorBanner.hidden = true;
}

function selectSwatch(button) {
  if (selectedSwatch) selectedSwatch.classList.remove("selected");
  selectedSwatch = button;
  button.classList.add("selected");
}

PRESETS.forEach((preset, index) => {
  const button = document.createElement("button");
  button.className = "swatch";
  button.style.background = preset.hex;
  button.title = preset.name;
  button.addEventListener("click", () => {
    selectedColor = preset.hex;
    selectSwatch(button);
  });
  swatches.appendChild(button);
  if (index === 0) selectSwatch(button);
});

customColor.addEventListener("input", () => {
  selectedColor = customColor.value;
  if (selectedSwatch) selectedSwatch.classList.remove("selected");
  selectedSwatch = null;
});

function setFile(file) {
  selectedFile = file;
  clearError();
  originalImage.src = URL.createObjectURL(file);
  compare.hidden = true;
  resultImage.removeAttribute("src");
  applyBtn.disabled = false;
  dzTitle.textContent = file.name;
  dzSub.textContent = "click or drop to change the photo";
}

dropZone.addEventListener("click", () => photoInput.click());

dropZone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    photoInput.click();
  }
});

["dragenter", "dragover"].forEach((type) => {
  dropZone.addEventListener(type, (event) => {
    event.preventDefault();
    dropZone.classList.add("dragging");
  });
});

["dragleave", "drop"].forEach((type) => {
  dropZone.addEventListener(type, (event) => {
    event.preventDefault();
    dropZone.classList.remove("dragging");
  });
});

dropZone.addEventListener("drop", (event) => {
  const file = event.dataTransfer.files[0];
  if (file && file.type.startsWith("image/")) {
    setFile(file);
  }
});

photoInput.addEventListener("change", () => {
  if (photoInput.files.length > 0) {
    setFile(photoInput.files[0]);
  }
});

applyBtn.addEventListener("click", async () => {
  if (!selectedFile) return;
  const formData = new FormData();
  formData.append("image", selectedFile);
  formData.append("color", selectedColor);
  formData.append("strength", (strengthInput.value / 100).toString());
  applyBtn.disabled = true;
  applyBtn.classList.add("loading");
  applyBtn.textContent = "Processing...";
  clearError();
  try {
    const response = await fetch(`${API}/dye`, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `Request failed: ${response.status}`);
    }
    const blob = await response.blob();
    resultImage.src = URL.createObjectURL(blob);
    compare.hidden = false;
  } catch (error) {
    showError(error.message);
  } finally {
    applyBtn.disabled = false;
    applyBtn.classList.remove("loading");
    applyBtn.textContent = "Apply dye";
  }
});

document.querySelectorAll(".menu-item").forEach((item) => {
  item.addEventListener("click", () => {
    document.querySelectorAll(".menu-item").forEach((i) => i.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    item.classList.add("active");
    const panel = document.getElementById(`panel-${item.dataset.panel}`);
    if (panel) panel.classList.add("active");
  });
});

const beardDrop = document.getElementById("beard-drop");
const beardInput = document.getElementById("beard-input");
const beardBtn = document.getElementById("beard-btn");
const beardError = document.getElementById("beard-error");
const beardCompare = document.getElementById("beard-compare");
const beardOriginal = document.getElementById("beard-original");
const beardResult = document.getElementById("beard-result");
const beardStrength = document.getElementById("beard-strength");
const beardMeshToggle = document.getElementById("beard-mesh");
const beardMeshCard = document.getElementById("beard-mesh-card");
const beardMeshImage = document.getElementById("beard-mesh-img");
let beardFile = null;
let beardStyle = "full";

document.querySelectorAll(".style-btn").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".style-btn").forEach((b) => b.classList.remove("active"));
    button.classList.add("active");
    beardStyle = button.dataset.style;
  });
});

function setBeardFile(file) {
  beardFile = file;
  beardError.hidden = true;
  beardOriginal.src = URL.createObjectURL(file);
  beardCompare.hidden = true;
  beardResult.removeAttribute("src");
  beardBtn.disabled = false;
  beardDrop.querySelector(".dz-title").textContent = file.name;
  beardDrop.querySelector(".dz-sub").textContent = "click or drop to change the photo";
}

beardDrop.addEventListener("click", () => beardInput.click());

beardDrop.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    beardInput.click();
  }
});

["dragenter", "dragover"].forEach((type) => {
  beardDrop.addEventListener(type, (event) => {
    event.preventDefault();
    beardDrop.classList.add("dragging");
  });
});

["dragleave", "drop"].forEach((type) => {
  beardDrop.addEventListener(type, (event) => {
    event.preventDefault();
    beardDrop.classList.remove("dragging");
  });
});

beardDrop.addEventListener("drop", (event) => {
  const file = event.dataTransfer.files[0];
  if (file && file.type.startsWith("image/")) {
    setBeardFile(file);
  }
});

beardInput.addEventListener("change", () => {
  if (beardInput.files.length > 0) {
    setBeardFile(beardInput.files[0]);
  }
});

beardBtn.addEventListener("click", async () => {
  if (!beardFile) return;
  const formData = new FormData();
  formData.append("image", beardFile);
  formData.append("style", beardStyle);
  formData.append("strength", (beardStrength.value / 100).toString());  beardBtn.disabled = true;
  beardBtn.textContent = "Processing...";
  beardError.hidden = true;
  try {
    const response = await fetch(`${API}/beard`, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `Request failed: ${response.status}`);
    }
    beardResult.src = URL.createObjectURL(await response.blob());
    beardCompare.hidden = false;
    if (beardMeshToggle.checked) {
      try {
        const meshFormData = new FormData();
        meshFormData.append("image", beardFile);
        const meshResponse = await fetch(`${API}/mesh`, {
          method: "POST",
          body: meshFormData,
        });
        if (meshResponse.ok) {
          beardMeshImage.src = URL.createObjectURL(await meshResponse.blob());
          beardMeshCard.hidden = false;
          beardCompare.classList.add("trio");
        }
      } catch (meshError) {
        beardMeshCard.hidden = true;
        beardCompare.classList.remove("trio");
      }
    } else {
      beardMeshCard.hidden = true;
      beardCompare.classList.remove("trio");
    }
  } catch (error) {
    beardError.textContent = error.message;
    beardError.hidden = false;
  } finally {
    beardBtn.disabled = false;
    beardBtn.textContent = "Apply beard";
  }
});

const liveBtn = document.getElementById("live-btn");
const liveVideo = document.getElementById("live-video");
const liveCanvas = document.getElementById("live-canvas");
const liveResult = document.getElementById("live-result");
const liveError = document.getElementById("live-error");
const liveStage = document.getElementById("live-stage");
const liveFps = document.getElementById("live-fps");
const liveStatus = document.getElementById("live-status");
const liveSwatches = document.getElementById("live-swatches");
const liveStyles = document.getElementById("live-styles");
const liveStrength = document.getElementById("live-strength");
const liveModeDye = document.getElementById("live-mode-dye");
const liveModeBeard = document.getElementById("live-mode-beard");
const liveModeMesh = document.getElementById("live-mode-mesh");
const liveModePhysics = document.getElementById("live-mode-physics");
const livePhysicsHint = document.getElementById("live-physics-hint");
const liveLengthField = document.getElementById("live-length-field");
const liveLength = document.getElementById("live-length");

function setLiveMode(mode, activeBtn) {
  liveMode = mode;
  [liveModeDye, liveModeBeard, liveModeMesh, liveModePhysics].forEach((b) => b.classList.remove("active"));
  activeBtn.classList.add("active");
  liveSwatches.hidden = mode !== "dye";
  liveStyles.hidden = mode !== "beard";
  livePhysicsHint.hidden = mode !== "physics";
  liveLengthField.hidden = mode !== "physics";
}

let liveRunning = false;
let liveStream = null;
let liveBusy = false;
let liveMode = "dye";
let liveStyle = "full";
let liveColor = PRESETS[0].hex;

PRESETS.forEach((preset) => {
  const button = document.createElement("button");
  button.className = "swatch";
  button.style.background = preset.hex;
  button.title = preset.name;
  button.addEventListener("click", () => {
    liveColor = preset.hex;
    liveSwatches.querySelectorAll(".swatch").forEach((b) => b.classList.remove("selected"));
    button.classList.add("selected");
  });
  liveSwatches.appendChild(button);
});

liveModeDye.addEventListener("click", () => setLiveMode("dye", liveModeDye));
liveModeBeard.addEventListener("click", () => setLiveMode("beard", liveModeBeard));
liveModeMesh.addEventListener("click", () => setLiveMode("mesh", liveModeMesh));
liveModePhysics.addEventListener("click", () => setLiveMode("physics", liveModePhysics));

document.querySelectorAll("[data-live-style]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("[data-live-style]").forEach((b) => b.classList.remove("active"));
    button.classList.add("active");
    liveStyle = button.dataset.liveStyle;
  });
});

async function liveLoop() {
  if (!liveRunning) return;
  if (!liveBusy && liveVideo.videoWidth > 0) {
    liveBusy = true;
    const started = performance.now();
    try {
      const targetW = liveMode === "beard" ? Math.min(1280, liveVideo.videoWidth) : 640;
      const scale = targetW / liveVideo.videoWidth;
      liveCanvas.width = targetW;
      liveCanvas.height = Math.round(liveVideo.videoHeight * scale);
      const ctx = liveCanvas.getContext("2d");
      ctx.save();
      ctx.translate(liveCanvas.width, 0);
      ctx.scale(-1, 1);
      ctx.drawImage(liveVideo, 0, 0, liveCanvas.width, liveCanvas.height);
      ctx.restore();
      const blob = await new Promise((resolve) => liveCanvas.toBlob(resolve, "image/jpeg", liveMode === "beard" ? 0.92 : 0.85));
      const formData = new FormData();
      formData.append("image", blob, "frame.jpg");
      formData.append("mode", liveMode);
      formData.append("color", liveColor);
      formData.append("style", liveStyle);
      formData.append("strength", (liveStrength.value / 100).toString());
      formData.append("length", (liveLength.value / 100).toString());
      const response = await fetch(`${API}/live`, { method: "POST", body: formData });
      if (response.ok) {
        liveResult.src = URL.createObjectURL(await response.blob());
        const elapsed = (performance.now() - started) / 1000;
        liveFps.textContent = `${(1 / elapsed).toFixed(1)} fps`;
        liveStatus.hidden = response.headers.get("X-Face-Found") !== "0";
      }
    } catch (error) {
      liveError.textContent = error.message;
      liveError.hidden = false;
    } finally {
      liveBusy = false;
    }
  }
  setTimeout(liveLoop, 0);
}

liveBtn.addEventListener("click", async () => {
  liveError.hidden = true;
  if (liveRunning) {
    liveRunning = false;
    liveStream.getTracks().forEach((track) => track.stop());
    liveBtn.textContent = "Start camera";
    return;
  }
  try {
    liveStream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, facingMode: "user" },
      audio: false,
    });
    liveVideo.srcObject = liveStream;
    await liveVideo.play();
    liveStage.hidden = false;
    liveRunning = true;
    liveBtn.textContent = "Stop camera";
    liveLoop();
  } catch (error) {
    liveError.textContent = `Camera unavailable: ${error.message}`;
    liveError.hidden = false;
  }
});

const hcDrop = document.getElementById("hc-drop");
const hcInput = document.getElementById("hc-input");
const hcBtn = document.getElementById("hc-btn");
const hcError = document.getElementById("hc-error");
const hcCompare = document.getElementById("hc-compare");
const hcOriginal = document.getElementById("hc-original");
const hcResult = document.getElementById("hc-result");
const hcStrength = document.getElementById("hc-strength");
let hcFile = null;
let hcStyle = "low-fade";

document.querySelectorAll("[data-hc-style]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("[data-hc-style]").forEach((b) => b.classList.remove("active"));
    button.classList.add("active");
    hcStyle = button.dataset.hcStyle;
  });
});

function setHcFile(file) {
  hcFile = file;
  hcError.hidden = true;
  hcOriginal.src = URL.createObjectURL(file);
  hcCompare.hidden = true;
  hcResult.removeAttribute("src");
  hcBtn.disabled = false;
  hcDrop.querySelector(".dz-title").textContent = file.name;
  hcDrop.querySelector(".dz-sub").textContent = "click or drop to change the photo";
}

hcDrop.addEventListener("click", () => hcInput.click());
hcDrop.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    hcInput.click();
  }
});
["dragenter", "dragover"].forEach((type) => {
  hcDrop.addEventListener(type, (event) => {
    event.preventDefault();
    hcDrop.classList.add("dragging");
  });
});
["dragleave", "drop"].forEach((type) => {
  hcDrop.addEventListener(type, (event) => {
    event.preventDefault();
    hcDrop.classList.remove("dragging");
  });
});
hcDrop.addEventListener("drop", (event) => {
  const file = event.dataTransfer.files[0];
  if (file && file.type.startsWith("image/")) {
    setHcFile(file);
  }
});
hcInput.addEventListener("change", () => {
  if (hcInput.files.length > 0) {
    setHcFile(hcInput.files[0]);
  }
});

hcBtn.addEventListener("click", async () => {
  if (!hcFile) return;
  const formData = new FormData();
  formData.append("image", hcFile);
  formData.append("style", hcStyle);
  formData.append("strength", (hcStrength.value / 100).toString());
  hcBtn.disabled = true;
  hcBtn.textContent = "Processing...";
  hcError.hidden = true;
  try {
    const response = await fetch(`${API}/haircut`, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `Request failed: ${response.status}`);
    }
    hcResult.src = URL.createObjectURL(await response.blob());
    hcCompare.hidden = false;
  } catch (error) {
    hcError.textContent = error.message;
    hcError.hidden = false;
  } finally {
    hcBtn.disabled = false;
    hcBtn.textContent = "Apply cut";
  }
});

const transferSteps = document.querySelectorAll(".transfer-step");
const transferViews = document.querySelectorAll(".transfer-view");
const scanStart = document.getElementById("scan-start");
const scanCapture = document.getElementById("scan-capture");
const scanStop = document.getElementById("scan-stop");
const scanSave = document.getElementById("scan-save");
const scanVideo = document.getElementById("scan-video");
const scanCanvas = document.getElementById("scan-canvas");
const scanResult = document.getElementById("scan-result");
const scanEmpty = document.getElementById("scan-empty");
const scanProgressBar = document.getElementById("scan-progress-bar");
const scanProgressLabel = document.getElementById("scan-progress-label");
const scanProgressValue = document.getElementById("scan-progress-value");
const scanError = document.getElementById("scan-error");
const pelucaGrid = document.getElementById("peluca-grid");
const libraryEmpty = document.getElementById("library-empty");
const tryonVideo = document.getElementById("tryon-video");
const tryonMesh = document.getElementById("tryon-mesh");
const tryonPlaceholder = document.getElementById("tryon-placeholder");
const tryonCamera = document.getElementById("tryon-camera");
const tryonError = document.getElementById("tryon-error");
const selectedPelucaPreview = document.getElementById("selected-peluca-preview");
const selectedPelucaName = document.getElementById("selected-peluca-name");
const selectedPelucaDate = document.getElementById("selected-peluca-date");
const rotationBadge = document.getElementById("rotation-badge");
const poseBadge = document.getElementById("pose-badge");
const tryonStage = document.getElementById("tryon-stage");

let scanStream = null;
let scanRunning = false;
let scanBusy = false;
let scanProgress = 0;
let scanViews = {};
let scanFrames = {};
let scanViewIndex = 0;
let scanAutoCaptureBusy = false;
let pelucas = [];
let selectedPeluca = null;
let tryonStream = null;
let tryonRotation = 0;
let tryonManualRotation = 0;
let tryonDetectedRotation = 0;
let tryonBusy = false;
let tryonReset = true;
let tryonFrame = null;
let tryonAnchor = null;
let tryonMisses = 0;
let dragStartX = null;
const scanStages = [
  { key: "left90", angle: -90, label: "Turn fully LEFT, showing your profile (90°)", button: "Capture Left 90°" },
  { key: "left60", angle: -60, label: "Turn 60° LEFT, then capture", button: "Capture Left 60°" },
  { key: "left30", angle: -30, label: "Turn 30° LEFT, then capture", button: "Capture Left 30°" },
  { key: "front", angle: 0, label: "Face forward (0°), then capture", button: "Capture Front" },
  { key: "right30", angle: 30, label: "Turn 30° RIGHT, then capture", button: "Capture Right 30°" },
  { key: "right60", angle: 60, label: "Turn 60° RIGHT, then capture", button: "Capture Right 60°" },
  { key: "right90", angle: 90, label: "Turn fully RIGHT, showing your profile (90°)", button: "Capture Right 90°" },
];

function openTransferView(view) {
  transferSteps.forEach((button) => button.classList.toggle("active", button.dataset.transferView === view));
  transferViews.forEach((panel) => panel.classList.toggle("active", panel.id === `transfer-${view}`));
}

transferSteps.forEach((button) => button.addEventListener("click", () => openTransferView(button.dataset.transferView)));
document.querySelectorAll("[data-transfer-view]").forEach((button) => {
  if (!button.classList.contains("transfer-step")) {
    button.addEventListener("click", () => openTransferView(button.dataset.transferView));
  }
});

function setScanProgress(value, label) {
  scanProgress = Math.min(100, value);
  scanProgressBar.style.width = `${scanProgress}%`;
  scanProgressValue.textContent = `${Math.round(scanProgress)}%`;
  scanProgressLabel.textContent = label;
}

async function scanLoop() {
  if (!scanRunning) return;
  if (!scanBusy && scanVideo.videoWidth > 0) {
    scanBusy = true;
    try {
      const targetWidth = 720;
      scanCanvas.width = targetWidth;
      scanCanvas.height = Math.round(scanVideo.videoHeight * (targetWidth / scanVideo.videoWidth));
      const context = scanCanvas.getContext("2d");
      context.save();
      context.translate(scanCanvas.width, 0);
      context.scale(-1, 1);
      context.drawImage(scanVideo, 0, 0, scanCanvas.width, scanCanvas.height);
      context.restore();
      const frame = await new Promise((resolve) => scanCanvas.toBlob(resolve, "image/jpeg", 0.88));
      const formData = new FormData();
      formData.append("image", frame, "scan-frame.jpg");
      const response = await fetch(`${API}/transfer/scan`, { method: "POST", body: formData });
      if (!response.ok) throw new Error("Could not identify hair. Keep your full head visible and try again.");
      const detectedYaw = Number(response.headers.get("X-Head-Yaw"));
      scanResult.src = URL.createObjectURL(await response.blob());
      scanResult.hidden = false;
      scanEmpty.hidden = true;
      const stage = scanStages[scanViewIndex];
      const profileReached = Math.abs(stage.angle) === 90 && Math.sign(detectedYaw) === Math.sign(stage.angle) && Math.abs(detectedYaw) >= 72;
      const yawReady = Number.isFinite(detectedYaw) && (Math.abs(detectedYaw - stage.angle) <= 10 || profileReached);
      const turnSide = detectedYaw < 0 ? "left" : "right";
      const turnHint = Number.isFinite(detectedYaw) ? ` — now ${Math.abs(Math.round(detectedYaw))}°${Math.round(detectedYaw) === 0 ? "" : ` ${turnSide}`}` : "";
      setScanProgress((scanViewIndex / scanStages.length) * 100, yawReady ? `${Math.abs(Math.round(detectedYaw))}° ${turnSide} detected — capturing` : `${stage.label}${turnHint}`);
      if (yawReady && !scanAutoCaptureBusy) {
        scanAutoCaptureBusy = true;
        scanCapture.click();
        setTimeout(() => { scanAutoCaptureBusy = false; }, 1200);
      }
    } catch (error) {
      scanError.textContent = error.message;
      scanError.hidden = false;
    } finally {
      scanBusy = false;
    }
  }
  setTimeout(scanLoop, 180);
}

scanStart.addEventListener("click", async () => {
  scanError.hidden = true;
  if (!scanStream) {
    try {
      scanStream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, facingMode: "user" }, audio: false });
      scanVideo.srcObject = scanStream;
      await scanVideo.play();
    } catch (error) {
      scanError.textContent = `Camera unavailable: ${error.message}`;
      scanError.hidden = false;
      return;
    }
  }
  scanRunning = true;
  scanViews = {};
  scanFrames = {};
  scanViewIndex = 0;
  scanAutoCaptureBusy = false;
  scanSave.disabled = true;
  scanStart.disabled = true;
  scanCapture.disabled = false;
  scanStop.disabled = false;
  scanCapture.textContent = scanStages[0].button;
  setScanProgress(0, scanStages[0].label);
  scanLoop();
});

scanStop.addEventListener("click", () => {
  scanRunning = false;
  scanStart.disabled = false;
  scanCapture.disabled = true;
  scanStop.disabled = true;
  scanSave.disabled = Object.keys(scanViews).length !== scanStages.length;
  setScanProgress((Object.keys(scanViews).length / scanStages.length) * 100, "Scan cancelled");
});

scanCapture.addEventListener("click", async () => {
  if (!scanRunning || scanViewIndex >= scanStages.length || scanVideo.videoWidth === 0) return;
  const stage = scanStages[scanViewIndex];
  scanCapture.disabled = true;
  scanCapture.textContent = "Saving view...";
  try {
    const captureCanvas = document.createElement("canvas");
    captureCanvas.width = 720;
    captureCanvas.height = Math.round(scanVideo.videoHeight * (720 / scanVideo.videoWidth));
    const context = captureCanvas.getContext("2d");
    context.save();
    context.translate(captureCanvas.width, 0);
    context.scale(-1, 1);
    context.drawImage(scanVideo, 0, 0, captureCanvas.width, captureCanvas.height);
    context.restore();
    const frame = await new Promise((resolve) => captureCanvas.toBlob(resolve, "image/jpeg", 0.92));
    scanFrames[stage.key] = frame;
    const formData = new FormData();
    formData.append("image", frame, `${stage.key}-hair.jpg`);
    const response = await fetch(`${API}/transfer/asset`, { method: "POST", body: formData });
    if (!response.ok) throw new Error("The hair profile could not be captured. Keep your full hair in frame and try again.");
    scanViews[stage.key] = URL.createObjectURL(await response.blob());
    scanViewIndex += 1;
    setScanProgress((scanViewIndex / scanStages.length) * 100, scanViewIndex === scanStages.length ? "180° scan complete — ready to reconstruct" : scanStages[scanViewIndex].label);
    if (scanViewIndex === scanStages.length) {
      scanRunning = false;
      scanStart.disabled = false;
      scanStop.disabled = true;
      scanCapture.disabled = true;
      scanSave.disabled = false;
    } else {
      scanCapture.disabled = false;
      scanCapture.textContent = scanStages[scanViewIndex].button;
    }
  } catch (error) {
    scanError.textContent = error.message;
    scanError.hidden = false;
    scanCapture.disabled = false;
    scanCapture.textContent = stage.button;
  }
});

function renderLibrary() {
  pelucaGrid.innerHTML = "";
  libraryEmpty.hidden = pelucas.length > 0;
  pelucas.forEach((peluca) => {
    const card = document.createElement("article");
    card.className = "card peluca-card";
    card.innerHTML = `<img src="${peluca.previewUrl}" alt="${peluca.name}"><h3>${peluca.name}</h3><p>${peluca.date}</p><div class="card-actions"><button data-action="tryon">Apply to Try-On</button><button class="quiet-button" data-action="splat">View 3D</button></div>`;
    card.querySelector('[data-action="tryon"]').addEventListener("click", () => selectPeluca(peluca));
    card.querySelector('[data-action="splat"]').addEventListener("click", () => {
      selectPeluca(peluca, "splat");
      buildHair3dFromPeluca();
    });
    pelucaGrid.appendChild(card);
  });
}

function selectPeluca(peluca, view = "tryon") {
  selectedPeluca = peluca;
  hair3dPelucaName.textContent = peluca.name;
  hair3dScan.disabled = !peluca.frames;
  selectedPelucaPreview.src = peluca.previewUrl;
  selectedPelucaName.textContent = peluca.name;
  selectedPelucaDate.textContent = `Captured ${peluca.date}`;
  tryonManualRotation = 0;
  tryonDetectedRotation = 0;
  openTransferView(view);
  updateTryonRotation();
}

scanSave.addEventListener("click", async () => {
  if (Object.keys(scanViews).length !== scanStages.length) return;
  scanSave.disabled = true;
  scanSave.textContent = "Saving...";
  try {
    const formData = new FormData();
    scanStages.forEach((stage) => formData.append("frames", scanFrames[stage.key], `${stage.key}.jpg`));
    formData.append("angles", scanStages.map((stage) => stage.angle).join(","));
    const response = await fetch(`${API}/transfer/reconstruct`, { method: "POST", body: formData });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || "Could not reconstruct the 3D hair mesh");
    }
    const mesh = await response.json();
    const now = new Date();
    const peluca = { mesh, frames: scanStages.map((stage) => scanFrames[stage.key]), angles: scanStages.map((stage) => stage.angle), previewUrl: scanViews.front || scanViews.left30, name: `180° Hair Mesh ${pelucas.length + 1}`, date: now.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) };
    pelucas.unshift(peluca);
    renderLibrary();
    selectPeluca(peluca);
  } catch (error) {
    scanError.textContent = error.message;
    scanError.hidden = false;
  } finally {
    scanSave.textContent = "Save as Peluca";
    scanSave.disabled = false;
  }
});

async function toggleTryonCamera() {
  tryonError.hidden = true;
  if (tryonStream) {
    tryonStream.getTracks().forEach((track) => track.stop());
    tryonStream = null;
    tryonVideo.srcObject = null;
    tryonFrame = null;
    tryonAnchor = null;
    tryonCamera.textContent = "Start Person B camera";
    tryonPlaceholder.hidden = false;
    poseBadge.textContent = "Waiting for camera";
    renderTryonMesh();
    return;
  }
  try {
    tryonStream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, facingMode: "user" }, audio: false });
    tryonVideo.srcObject = tryonStream;
    await tryonVideo.play();
    tryonPlaceholder.hidden = true;
    tryonCamera.textContent = "Stop Person B camera";
    poseBadge.textContent = "Preparing bald preview...";
    tryonReset = true;
    tryonLoop();
  } catch (error) {
    tryonError.textContent = `Camera unavailable: ${error.message}`;
    tryonError.hidden = false;
  }
}

function updateTryonRotation() {
  tryonRotation = tryonDetectedRotation + tryonManualRotation;
  const normalized = ((tryonRotation % 360) + 360) % 360;
  rotationBadge.textContent = `${Math.round(normalized)}°`;
  renderTryonMesh();
}

function renderTryonMesh() {
  const context = tryonMesh.getContext("2d");
  const width = tryonMesh.clientWidth;
  const height = tryonMesh.clientHeight;
  if (!width || !height) return;
  const ratio = window.devicePixelRatio || 1;
  if (tryonMesh.width !== Math.round(width * ratio) || tryonMesh.height !== Math.round(height * ratio)) {
    tryonMesh.width = Math.round(width * ratio);
    tryonMesh.height = Math.round(height * ratio);
  }
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.clearRect(0, 0, width, height);
  if (!tryonFrame) return;
  const cover = Math.max(width / tryonFrame.width, height / tryonFrame.height);
  context.translate((width - tryonFrame.width * cover) / 2, (height - tryonFrame.height * cover) / 2);
  context.scale(cover, cover);
  context.drawImage(tryonFrame.bitmap, 0, 0);
  if (!selectedPeluca || !selectedPeluca.mesh || !tryonAnchor) return;
  const { views } = selectedPeluca.mesh;
  if (views && views.length) {
    renderTexturedPeluca(context, views);
  } else {
    renderMeshPeluca(context);
  }
}

function renderMeshPeluca(context) {
  const { vertices, faces, color, vertexColors } = selectedPeluca.mesh;
  const radians = tryonRotation * Math.PI / 180;
  const cosine = Math.cos(radians);
  const sine = Math.sin(radians);
  const scale = tryonAnchor.faceWidth * 1.1;
  const centerX = tryonAnchor.center[0];
  const centerY = tryonAnchor.center[1] - tryonAnchor.faceWidth * 0.45;
  const projected = vertices.map(([x, y, z]) => {
    const rx = x * cosine + z * sine;
    const rz = -x * sine + z * cosine;
    const perspective = 1 / (1 + rz * 0.32);
    return [centerX + rx * scale * perspective, centerY + y * scale * perspective, rz];
  });
  const triangles = faces.map((face) => ({ face, depth: (projected[face[0]][2] + projected[face[1]][2] + projected[face[2]][2]) / 3 }));
  triangles.sort((a, b) => a.depth - b.depth);
  context.globalAlpha = 0.9;
  triangles.forEach(({ face, depth }) => {
    const a = projected[face[0]];
    const b = projected[face[1]];
    const c = projected[face[2]];
    const light = Math.max(0.42, Math.min(1, 0.78 + depth * 0.16));
    const samples = vertexColors ? face.map((index) => vertexColors[index]) : [color, color, color];
    const rgb = samples.reduce((total, sample) => total.map((value, index) => value + sample[index]), [0, 0, 0]).map((value) => value / samples.length);
    context.fillStyle = `rgb(${Math.round(rgb[0] * light)}, ${Math.round(rgb[1] * light)}, ${Math.round(rgb[2] * light)})`;
    context.beginPath();
    context.moveTo(a[0], a[1]);
    context.lineTo(b[0], b[1]);
    context.lineTo(c[0], c[1]);
    context.closePath();
    context.fill();
  });
  context.globalAlpha = 1;
}

const pelucaImages = new Map();

function pelucaImage(view) {
  let image = pelucaImages.get(view.image);
  if (!image) {
    image = new Image();
    image.onload = () => renderTryonMesh();
    image.src = view.image;
    pelucaImages.set(view.image, image);
  }
  return image.complete && image.naturalWidth ? image : null;
}

function drawPelucaView(context, view, alpha) {
  const image = pelucaImage(view);
  if (!image || alpha <= 0.01) return;
  const faceWidth = tryonAnchor.faceWidth;
  const [centerX, centerY] = tryonAnchor.center;
  context.save();
  context.translate(centerX, centerY);
  context.rotate(((tryonAnchor.roll || 0) - (view.roll || 0)) * Math.PI / 180);
  context.globalAlpha = alpha;
  context.drawImage(
    image,
    -faceWidth * view.faceCenter[0],
    -faceWidth * view.faceCenter[1],
    faceWidth * view.faceSize[0],
    faceWidth * view.faceSize[1],
  );
  context.restore();
}

function renderTexturedPeluca(context, views) {
  const targetYaw = ((tryonRotation + 180) % 360 + 360) % 360 - 180;
  const sorted = [...views].sort((a, b) => a.angle - b.angle);
  let lower = sorted[0];
  let upper = sorted[sorted.length - 1];
  for (let index = 0; index < sorted.length - 1; index += 1) {
    if (targetYaw >= sorted[index].angle && targetYaw <= sorted[index + 1].angle) {
      lower = sorted[index];
      upper = sorted[index + 1];
      break;
    }
  }
  if (targetYaw <= sorted[0].angle) upper = lower;
  if (targetYaw >= sorted[sorted.length - 1].angle) lower = upper;
  const span = upper.angle - lower.angle;
  const t = span > 0 ? (targetYaw - lower.angle) / span : 0;
  const blend = Math.min(1, Math.max(0, (t - 0.3) / 0.4));
  const weight = blend * blend * (3 - 2 * blend);
  context.imageSmoothingEnabled = true;
  context.imageSmoothingQuality = "high";
  drawPelucaView(context, lower, 1);
  if (upper !== lower) drawPelucaView(context, upper, weight);
}

function tryonFrameBlob() {
  const frameCanvas = document.createElement("canvas");
  frameCanvas.width = 640;
  frameCanvas.height = Math.round(tryonVideo.videoHeight * (640 / tryonVideo.videoWidth));
  const context = frameCanvas.getContext("2d");
  context.translate(frameCanvas.width, 0);
  context.scale(-1, 1);
  context.drawImage(tryonVideo, 0, 0, frameCanvas.width, frameCanvas.height);
  return new Promise((resolve) => frameCanvas.toBlob(resolve, "image/jpeg", 0.85));
}

async function tryonLoop() {
  if (!tryonStream) return;
  if (!tryonBusy && tryonVideo.videoWidth > 0) {
    tryonBusy = true;
    try {
      const formData = new FormData();
      formData.append("image", await tryonFrameBlob(), "tryon-frame.jpg");
      formData.append("reset", tryonReset ? "true" : "false");
      tryonReset = false;
      const response = await fetch(`${API}/transfer/tryon`, { method: "POST", body: formData });
      if (!response.ok) throw new Error("Could not process the Person B frame");
      const anchor = JSON.parse(response.headers.get("X-Tryon-Anchor") || "{}");
      const bitmap = await createImageBitmap(await response.blob());
      if (!tryonStream) return;
      if (tryonFrame) tryonFrame.bitmap.close();
      tryonFrame = { bitmap, width: bitmap.width, height: bitmap.height };
      if (anchor.center) {
        tryonMisses = 0;
        tryonAnchor = anchor;
        tryonDetectedRotation = anchor.yaw;
        poseBadge.textContent = `${anchor.pose[0].toUpperCase()}${anchor.pose.slice(1)} view tracked`;
      } else {
        tryonMisses += 1;
        if (tryonMisses > 4) tryonAnchor = null;
        poseBadge.textContent = "Keep your face in frame";
      }
      updateTryonRotation();
    } catch (error) {
      poseBadge.textContent = "Head tracking unavailable";
    } finally {
      tryonBusy = false;
    }
  }
  requestAnimationFrame(tryonLoop);
}

tryonCamera.addEventListener("click", toggleTryonCamera);

const hair3dPelucaName = document.getElementById("hair3d-peluca-name");
const hair3dScan = document.getElementById("hair3d-scan");
const hair3dDrop = document.getElementById("hair3d-drop");
const hair3dInput = document.getElementById("hair3d-input");
const hair3dMannequin = document.getElementById("hair3d-mannequin");
const hair3dAuto = document.getElementById("hair3d-auto");
const hair3dSplats = document.getElementById("hair3d-splats");
const hair3dReset = document.getElementById("hair3d-reset");
const hair3dPly = document.getElementById("hair3d-ply");
const hair3dError = document.getElementById("hair3d-error");
const hair3dStage = document.getElementById("hair3d-stage");
const hair3dCanvas = document.getElementById("hair3d-canvas");
const hair3dStats = document.getElementById("hair3d-stats");
const hair3dFps = document.getElementById("hair3d-fps");
let hair3dViewer = null;
let hair3dModel = null;
let hair3dSource = null;

function hair3dForm(source, extra = {}) {
  const formData = new FormData();
  source.frames.forEach((frame, index) => formData.append("frames", frame, `view-${index}.jpg`));
  formData.append("angles", source.angles.join(","));
  Object.entries(extra).forEach(([key, value]) => formData.append(key, value));
  return formData;
}

function showHair3d() {
  if (!hair3dModel) return;
  const hairBytes = hair3dModel.hair * SPLAT_FLOATS * 4;
  hair3dViewer.load(hair3dMannequin.checked ? hair3dModel.buffer : hair3dModel.buffer.slice(0, hairBytes));
  hair3dViewer.autoRotate = hair3dAuto.checked;
  hair3dViewer.setSplatScale(hair3dSplats.checked ? 0.32 : 1);
}

async function buildHair3d(source, label) {
  hair3dError.hidden = true;
  hair3dScan.disabled = true;
  hair3dPly.disabled = true;
  hair3dStats.textContent = `Building ${label}...`;
  hair3dStage.hidden = false;
  const started = performance.now();
  try {
    const response = await fetch(`${API}/transfer/splat`, { method: "POST", body: hair3dForm(source) });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `Request failed: ${response.status}`);
    }
    hair3dModel = {
      buffer: await response.arrayBuffer(),
      hair: Number(response.headers.get("X-Splat-Hair")),
      views: Number(response.headers.get("X-Splat-Views")),
    };
    hair3dSource = source;
    if (!hair3dViewer) {
      hair3dViewer = new SplatViewer(hair3dCanvas);
      hair3dViewer.setView(0, 0.1, 2.1);
      setInterval(() => {
        hair3dFps.textContent = hair3dViewer.autoRotate ? `${hair3dViewer.fps.toFixed(0)} fps` : "";
      }, 1000);
    }
    showHair3d();
    const seconds = ((performance.now() - started) / 1000).toFixed(1);
    const views = hair3dModel.views === 1 ? "1 photo" : `${hair3dModel.views} angles`;
    hair3dStats.textContent = `${label} · ${hair3dModel.hair.toLocaleString()} hair Gaussians from ${views} · built in ${seconds}s`;
    hair3dPly.disabled = false;
  } catch (error) {
    hair3dError.textContent = error.message;
    hair3dError.hidden = false;
    hair3dStats.textContent = "--";
  } finally {
    hair3dScan.disabled = !(selectedPeluca && selectedPeluca.frames);
  }
}

function buildHair3dFromPeluca() {
  if (!selectedPeluca || !selectedPeluca.frames) return;
  buildHair3d({ frames: selectedPeluca.frames, angles: selectedPeluca.angles }, selectedPeluca.name);
}

hair3dScan.addEventListener("click", buildHair3dFromPeluca);
hair3dDrop.addEventListener("click", () => hair3dInput.click());
hair3dDrop.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    hair3dInput.click();
  }
});
["dragenter", "dragover"].forEach((type) => {
  hair3dDrop.addEventListener(type, (event) => {
    event.preventDefault();
    hair3dDrop.classList.add("dragging");
  });
});
["dragleave", "drop"].forEach((type) => {
  hair3dDrop.addEventListener(type, (event) => {
    event.preventDefault();
    hair3dDrop.classList.remove("dragging");
  });
});
function setHair3dFile(file) {
  hair3dDrop.querySelector(".dz-title").textContent = file.name;
  hair3dDrop.querySelector(".dz-sub").textContent = "click or drop to change the photo";
  buildHair3d({ frames: [file], angles: [0] }, file.name);
}
hair3dDrop.addEventListener("drop", (event) => {
  const file = event.dataTransfer.files[0];
  if (file && file.type.startsWith("image/")) setHair3dFile(file);
});
hair3dInput.addEventListener("change", () => {
  if (hair3dInput.files.length > 0) setHair3dFile(hair3dInput.files[0]);
});
hair3dMannequin.addEventListener("change", showHair3d);
hair3dAuto.addEventListener("change", () => {
  if (hair3dViewer) hair3dViewer.autoRotate = hair3dAuto.checked;
});
hair3dSplats.addEventListener("change", () => {
  if (hair3dViewer) hair3dViewer.setSplatScale(hair3dSplats.checked ? 0.32 : 1);
});
hair3dReset.addEventListener("click", () => {
  if (hair3dViewer) hair3dViewer.setView(0, 0.1, 2.1);
});
hair3dPly.addEventListener("click", async () => {
  if (!hair3dSource) return;
  hair3dPly.disabled = true;
  hair3dPly.textContent = "Exporting...";
  try {
    const form = hair3dForm(hair3dSource, { format: "ply", mannequin: hair3dMannequin.checked ? "true" : "false" });
    const response = await fetch(`${API}/transfer/splat`, { method: "POST", body: form });
    if (!response.ok) throw new Error(`Export failed: ${response.status}`);
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = "barberstudio_peluca.ply";
    link.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    hair3dError.textContent = error.message;
    hair3dError.hidden = false;
  } finally {
    hair3dPly.disabled = false;
    hair3dPly.textContent = "Download .ply";
  }
});
document.getElementById("rotate-left").addEventListener("click", () => { tryonManualRotation -= 20; updateTryonRotation(); });
document.getElementById("rotate-right").addEventListener("click", () => { tryonManualRotation += 20; updateTryonRotation(); });
document.getElementById("switch-peluca").addEventListener("click", () => openTransferView("library"));
tryonStage.addEventListener("pointerdown", (event) => { dragStartX = event.clientX; tryonStage.setPointerCapture(event.pointerId); });
tryonStage.addEventListener("pointermove", (event) => {
  if (dragStartX === null) return;
  tryonManualRotation += (event.clientX - dragStartX) * 0.7;
  dragStartX = event.clientX;
  updateTryonRotation();
});
tryonStage.addEventListener("pointerup", () => { dragStartX = null; });
tryonStage.addEventListener("pointercancel", () => { dragStartX = null; });

const splatDrop = document.getElementById("splat-drop");
const splatInput = document.getElementById("splat-input");
const splatBtn = document.getElementById("splat-btn");
const splatError = document.getElementById("splat-error");
const splatGrid = document.getElementById("splat-grid");
const splatCrop = document.getElementById("splat-crop");
const splatGuess = document.getElementById("splat-guess");
const splatGuessBar = document.getElementById("splat-guess-bar");
const splatGuessBtn = document.getElementById("splat-guess-btn");
const splatGuessText = document.getElementById("splat-guess-text");
const splatScore = document.getElementById("splat-score");
const SPLAT_STAGES = [20, 60, 200, 600, 2000];
let splatFile = null;
let splatView = "render";
let splatBeard = "none";
let splatShown = 0;
let splatRunning = false;
let splatTarget = null;

document.querySelectorAll("[data-splat-view]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("[data-splat-view]").forEach((b) => b.classList.remove("active"));
    button.classList.add("active");
    splatView = button.dataset.splatView;
    splatGrid.querySelectorAll("img[data-render]").forEach((img) => {
      img.src = img.dataset[splatView];
    });
  });
});

document.querySelectorAll("[data-splat-beard]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("[data-splat-beard]").forEach((b) => b.classList.remove("active"));
    button.classList.add("active");
    splatBeard = button.dataset.splatBeard;
  });
});

function setSplatFile(file) {
  splatFile = file;
  splatError.hidden = true;
  splatGrid.innerHTML = "";
  splatBtn.disabled = false;
  splatDrop.querySelector(".dz-title").textContent = file.name;
  splatDrop.querySelector(".dz-sub").textContent = "click or drop to change the photo";
}

splatDrop.addEventListener("click", () => splatInput.click());
splatDrop.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    splatInput.click();
  }
});
["dragenter", "dragover"].forEach((type) => {
  splatDrop.addEventListener(type, (event) => {
    event.preventDefault();
    splatDrop.classList.add("dragging");
  });
});
["dragleave", "drop"].forEach((type) => {
  splatDrop.addEventListener(type, (event) => {
    event.preventDefault();
    splatDrop.classList.remove("dragging");
  });
});
splatDrop.addEventListener("drop", (event) => {
  const file = event.dataTransfer.files[0];
  if (file && file.type.startsWith("image/")) setSplatFile(file);
});
splatInput.addEventListener("change", () => {
  if (splatInput.files.length > 0) setSplatFile(splatInput.files[0]);
});

function splatCard(title) {
  const card = document.createElement("div");
  card.className = "card splat-card pending";
  card.innerHTML = `<h3>${title}</h3><img alt="${title}"><p class="meta">fitting...</p>`;
  splatGrid.appendChild(card);
  return card;
}

function revealSplatTarget() {
  if (!splatTarget || splatGrid.querySelector(".splat-original")) return;
  const card = splatCard("Original");
  card.classList.add("splat-original");
  card.classList.remove("pending");
  card.querySelector("img").src = splatTarget;
  card.querySelector(".meta").textContent = "the photo the Gaussians are fitting";
}

splatGuessBtn.addEventListener("click", () => {
  if (splatShown === 0) return;
  const points = Math.max(50, Math.round(1000 * (1 - Math.log(splatShown) / Math.log(SPLAT_STAGES[SPLAT_STAGES.length - 1] * 1.5))));
  splatScore.textContent = `${points} pts`;
  splatGuessText.textContent = `You recognized it with ${splatShown} Gaussians!`;
  splatGuessBtn.disabled = true;
  revealSplatTarget();
});

splatBtn.addEventListener("click", async () => {
  if (!splatFile || splatRunning) return;
  splatRunning = true;
  splatGrid.innerHTML = "";
  splatError.hidden = true;
  splatShown = 0;
  splatTarget = null;
  splatScore.textContent = "";
  splatGuessText.textContent = "Press the button as soon as you recognize the face. Fewer Gaussians, more points.";
  splatGuessBar.hidden = !splatGuess.checked;
  splatGuessBtn.disabled = !splatGuess.checked;
  splatBtn.disabled = true;
  splatBtn.classList.add("loading");
  try {
    for (const count of SPLAT_STAGES) {
      const card = splatCard(`${count} Gaussians`);
      splatBtn.textContent = `Fitting ${count}...`;
      const formData = new FormData();
      formData.append("image", splatFile);
      formData.append("count", count.toString());
      formData.append("face_crop", splatCrop.checked ? "true" : "false");
      formData.append("beard", splatBeard);
      const response = await fetch(`${API}/gaussians`, { method: "POST", body: formData });
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        card.remove();
        throw new Error(error.detail || `Request failed: ${response.status}`);
      }
      const data = await response.json();
      const img = card.querySelector("img");
      img.dataset.render = data.render;
      img.dataset.ellipses = data.ellipses;
      img.src = data[splatView];
      card.classList.remove("pending");
      card.querySelector(".meta").textContent = `PSNR ${data.psnr} dB · ${data.iterations} steps · ${data.seconds}s`;
      splatTarget = data.target;
      splatShown = count;
    }
    if (!splatGuess.checked || splatGuessBtn.disabled) revealSplatTarget();
    if (splatGuess.checked && !splatGuessBtn.disabled) {
      splatGuessText.textContent = "Last stage reached. Do you recognize it now?";
    }
  } catch (error) {
    splatError.textContent = error.message;
    splatError.hidden = false;
  } finally {
    splatRunning = false;
    splatBtn.disabled = false;
    splatBtn.classList.remove("loading");
    splatBtn.textContent = "Start";
  }
});

const gameCameraBtn = document.getElementById("game-camera");
const gameStartBtn = document.getElementById("game-start");
const gameError = document.getElementById("game-error");
const gameStage = document.getElementById("game-stage");
const gameResult = document.getElementById("game-result");
const gameVideo = document.getElementById("game-video");
const gameCanvas = document.getElementById("game-canvas");
const gameHand = document.getElementById("game-hand");
const gameName = document.getElementById("game-name");
const gameTime = document.getElementById("game-time");
const gameScore = document.getElementById("game-score");
const gameClean = document.getElementById("game-clean");
const gameKeep = document.getElementById("game-keep");
const gameTool = document.getElementById("game-tool");
const gameFinal = document.getElementById("game-final");
const gameBoard = document.getElementById("game-board");
const gameOverlay = document.getElementById("game-overlay");
const GAME_SECONDS = 30;
const BOARD_KEY = "barberstudio-speedrun-board";
let gameTarget = "goatee";
let gameStream = null;
let gameRunning = false;
let gameBusy = false;
let gameDeadline = 0;
let gameInRound = false;
let gameLast = null;
const gamePointer = { x: -1, y: -1, down: false };

function readBoard() {
  try {
    return JSON.parse(localStorage.getItem(BOARD_KEY) || "[]");
  } catch (error) {
    return [];
  }
}

function writeBoard(board) {
  try {
    localStorage.setItem(BOARD_KEY, JSON.stringify(board));
  } catch (error) {
    return;
  }
}

function renderBoard() {
  const board = readBoard();
  gameBoard.innerHTML = "";
  if (board.length === 0) {
    const empty = document.createElement("li");
    empty.textContent = "No rounds yet";
    gameBoard.appendChild(empty);
    return;
  }
  board.forEach((entry) => {
    const item = document.createElement("li");
    item.textContent = `${entry.name} · ${entry.score} (${entry.target})`;
    gameBoard.appendChild(item);
  });
}

function rankFor(score) {
  if (score >= 900) return "Master barber!";
  if (score >= 750) return "Pro barber";
  if (score >= 500) return "Apprentice";
  return "Keep practicing";
}

document.querySelectorAll("[data-game-target]").forEach((button) => {
  button.addEventListener("click", async () => {
    if (gameInRound) return;
    document.querySelectorAll("[data-game-target]").forEach((b) => b.classList.remove("active"));
    button.classList.add("active");
    gameTarget = button.dataset.gameTarget;
    if (gameRunning) await startGameSession();
  });
});

async function startGameSession() {
  const formData = new FormData();
  formData.append("target", gameTarget);
  const response = await fetch(`${API}/game/start`, { method: "POST", body: formData });
  if (!response.ok) throw new Error(`Could not start the game (${response.status})`);
}

function updatePointer(event) {
  const rect = gameResult.getBoundingClientRect();
  gamePointer.x = (event.clientX - rect.left) / rect.width;
  gamePointer.y = (event.clientY - rect.top) / rect.height;
}

gameResult.addEventListener("pointerdown", (event) => {
  gamePointer.down = true;
  updatePointer(event);
  gameResult.setPointerCapture(event.pointerId);
});
gameResult.addEventListener("pointermove", updatePointer);
["pointerup", "pointercancel"].forEach((type) => {
  gameResult.addEventListener(type, () => {
    gamePointer.down = false;
  });
});
gameResult.addEventListener("pointerleave", () => {
  if (!gamePointer.down) {
    gamePointer.x = -1;
    gamePointer.y = -1;
  }
});

function flashOverlay(text, ms) {
  gameOverlay.textContent = text;
  gameOverlay.hidden = false;
  return new Promise((resolve) => setTimeout(() => {
    gameOverlay.hidden = true;
    resolve();
  }, ms));
}

function finishRound() {
  gameInRound = false;
  flashOverlay("TIME!", 1400);
  gameStartBtn.disabled = false;
  gameStartBtn.textContent = "Start round";
  const score = gameLast ? gameLast.score : 0;
  gameFinal.textContent = `Final score: ${score} · ${rankFor(score)}`;
  gameFinal.hidden = false;
  const name = (gameName.value || "Barber").trim().slice(0, 16) || "Barber";
  const board = readBoard();
  board.push({ name, score, target: gameTarget });
  board.sort((a, b) => b.score - a.score);
  writeBoard(board.slice(0, 5));
  renderBoard();
}

async function gameLoop() {
  if (!gameRunning) return;
  if (gameInRound) {
    const left = Math.max(0, (gameDeadline - performance.now()) / 1000);
    gameTime.textContent = left.toFixed(1);
    if (left <= 0) finishRound();
  }
  if (!gameBusy && gameVideo.videoWidth > 0) {
    gameBusy = true;
    try {
      const targetW = 640;
      gameCanvas.width = targetW;
      gameCanvas.height = Math.round(gameVideo.videoHeight * (targetW / gameVideo.videoWidth));
      const ctx = gameCanvas.getContext("2d");
      ctx.save();
      ctx.translate(gameCanvas.width, 0);
      ctx.scale(-1, 1);
      ctx.drawImage(gameVideo, 0, 0, gameCanvas.width, gameCanvas.height);
      ctx.restore();
      const blob = await new Promise((resolve) => gameCanvas.toBlob(resolve, "image/jpeg", 0.85));
      const formData = new FormData();
      formData.append("image", blob, "frame.jpg");
      formData.append("pointer_x", gamePointer.x.toString());
      formData.append("pointer_y", gamePointer.y.toString());
      formData.append("pointer_down", gameInRound && gamePointer.down ? "true" : "false");
      formData.append("use_hand", gameInRound && gameHand.checked ? "true" : "false");
      const response = await fetch(`${API}/game/frame`, { method: "POST", body: formData });
      if (response.ok) {
        const data = await response.json();
        gameResult.src = data.image;
        if (gameInRound) {
          gameLast = data;
          gameScore.textContent = data.score;
          gameClean.textContent = `${Math.round(data.clean * 100)}%`;
          gameKeep.textContent = `${Math.round(data.keep * 100)}%`;
        }
        gameTool.hidden = !(gameInRound && data.tool === "none");
      }
    } catch (error) {
      gameError.textContent = error.message;
      gameError.hidden = false;
    } finally {
      gameBusy = false;
    }
  }
  setTimeout(gameLoop, 0);
}

gameCameraBtn.addEventListener("click", async () => {
  gameError.hidden = true;
  if (gameRunning) {
    gameRunning = false;
    gameInRound = false;
    gameStream.getTracks().forEach((track) => track.stop());
    gameCameraBtn.textContent = "Start camera";
    gameStartBtn.disabled = true;
    return;
  }
  try {
    gameStream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, facingMode: "user" },
      audio: false,
    });
    gameVideo.srcObject = gameStream;
    await gameVideo.play();
    await startGameSession();
    gameStage.hidden = false;
    gameRunning = true;
    gameCameraBtn.textContent = "Stop camera";
    gameStartBtn.disabled = false;
    gameLoop();
  } catch (error) {
    gameError.textContent = `Camera unavailable: ${error.message}`;
    gameError.hidden = false;
  }
});

gameStartBtn.addEventListener("click", async () => {
  if (!gameRunning || gameInRound) return;
  try {
    await startGameSession();
  } catch (error) {
    gameError.textContent = error.message;
    gameError.hidden = false;
    return;
  }
  gameLast = null;
  gameFinal.hidden = true;
  gameScore.textContent = "0";
  gameClean.textContent = "0%";
  gameKeep.textContent = "100%";
  gameTime.textContent = GAME_SECONDS.toFixed(1);
  gameStartBtn.disabled = true;
  gameStartBtn.textContent = "Get ready...";
  for (const step of ["3", "2", "1"]) await flashOverlay(step, 700);
  flashOverlay("GO!", 500);
  gameDeadline = performance.now() + GAME_SECONDS * 1000;
  gameInRound = true;
  gameStartBtn.textContent = "Shaving...";
});

renderBoard();

const mirrorDrop = document.getElementById("mirror-drop");
const mirrorInput = document.getElementById("mirror-input");
const mirrorBtn = document.getElementById("mirror-btn");
const mirrorError = document.getElementById("mirror-error");
const mirrorStage = document.getElementById("mirror-stage");
const mirrorCanvas = document.getElementById("mirror-canvas");
const mirrorStats = document.getElementById("mirror-stats");
const mirrorFps = document.getElementById("mirror-fps");
const mirrorAuto = document.getElementById("mirror-auto");
const mirrorReset = document.getElementById("mirror-reset");
const mirrorSplats = document.getElementById("mirror-splats");
const mirrorPly = document.getElementById("mirror-ply");
let mirrorFile = null;
let mirrorBeard = "none";
let mirrorViewer = null;

document.querySelectorAll("[data-mirror-beard]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("[data-mirror-beard]").forEach((b) => b.classList.remove("active"));
    button.classList.add("active");
    mirrorBeard = button.dataset.mirrorBeard;
  });
});

function setMirrorFile(file) {
  mirrorFile = file;
  mirrorError.hidden = true;
  mirrorBtn.disabled = false;
  mirrorPly.disabled = false;
  mirrorDrop.querySelector(".dz-title").textContent = file.name;
  mirrorDrop.querySelector(".dz-sub").textContent = "click or drop to change the photo";
}

mirrorDrop.addEventListener("click", () => mirrorInput.click());
mirrorDrop.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    mirrorInput.click();
  }
});
["dragenter", "dragover"].forEach((type) => {
  mirrorDrop.addEventListener(type, (event) => {
    event.preventDefault();
    mirrorDrop.classList.add("dragging");
  });
});
["dragleave", "drop"].forEach((type) => {
  mirrorDrop.addEventListener(type, (event) => {
    event.preventDefault();
    mirrorDrop.classList.remove("dragging");
  });
});
mirrorDrop.addEventListener("drop", (event) => {
  const file = event.dataTransfer.files[0];
  if (file && file.type.startsWith("image/")) setMirrorFile(file);
});
mirrorInput.addEventListener("change", () => {
  if (mirrorInput.files.length > 0) setMirrorFile(mirrorInput.files[0]);
});

mirrorAuto.addEventListener("change", () => {
  if (mirrorViewer) mirrorViewer.autoRotate = mirrorAuto.checked;
});

mirrorPly.addEventListener("click", async () => {
  if (!mirrorFile) return;
  mirrorPly.disabled = true;
  mirrorPly.textContent = "Exporting...";
  try {
    const formData = new FormData();
    formData.append("image", mirrorFile);
    formData.append("beard", mirrorBeard);
    formData.append("format", "ply");
    const response = await fetch(`${API}/head3d`, { method: "POST", body: formData });
    if (!response.ok) throw new Error(`Export failed: ${response.status}`);
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = "barberstudio_head.ply";
    link.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    mirrorError.textContent = error.message;
    mirrorError.hidden = false;
  } finally {
    mirrorPly.disabled = false;
    mirrorPly.textContent = "Download .ply";
  }
});

mirrorSplats.addEventListener("change", () => {
  if (mirrorViewer) mirrorViewer.setSplatScale(mirrorSplats.checked ? 0.32 : 1);
});

mirrorReset.addEventListener("click", () => {
  if (mirrorViewer) mirrorViewer.setView(0, 0, 1.9);
});

mirrorBtn.addEventListener("click", async () => {
  if (!mirrorFile) return;
  mirrorError.hidden = true;
  mirrorBtn.disabled = true;
  mirrorBtn.classList.add("loading");
  mirrorBtn.textContent = "Building...";
  const started = performance.now();
  try {
    const formData = new FormData();
    formData.append("image", mirrorFile);
    formData.append("beard", mirrorBeard);
    const response = await fetch(`${API}/head3d`, { method: "POST", body: formData });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `Request failed: ${response.status}`);
    }
    const buffer = await response.arrayBuffer();
    mirrorStage.hidden = false;
    if (!mirrorViewer) {
      mirrorViewer = new SplatViewer(mirrorCanvas);
      window.splatViewer = mirrorViewer;
      setInterval(() => {
        mirrorFps.textContent = mirrorViewer.autoRotate ? `${mirrorViewer.fps.toFixed(0)} fps` : "";
      }, 1000);
    }
    mirrorViewer.load(buffer);
    mirrorViewer.autoRotate = mirrorAuto.checked;
    mirrorViewer.setSplatScale(mirrorSplats.checked ? 0.32 : 1);
    const count = Number(response.headers.get("X-Splat-Count"));
    const beard = Number(response.headers.get("X-Splat-Beard"));
    const seconds = ((performance.now() - started) / 1000).toFixed(1);
    mirrorStats.textContent = `${count.toLocaleString()} Gaussians (${beard.toLocaleString()} beard) · built in ${seconds}s`;
  } catch (error) {
    mirrorError.textContent = error.message;
    mirrorError.hidden = false;
  } finally {
    mirrorBtn.disabled = false;
    mirrorBtn.classList.remove("loading");
    mirrorBtn.textContent = "Build 3D head";
  }
});
