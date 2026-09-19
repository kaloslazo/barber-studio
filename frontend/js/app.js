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

function setLiveMode(mode, activeBtn) {
  liveMode = mode;
  [liveModeDye, liveModeBeard, liveModeMesh].forEach((b) => b.classList.remove("active"));
  activeBtn.classList.add("active");
  liveSwatches.hidden = mode !== "dye";
  liveStyles.hidden = mode !== "beard";
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
      const targetW = 640;
      const scale = targetW / liveVideo.videoWidth;
      liveCanvas.width = targetW;
      liveCanvas.height = Math.round(liveVideo.videoHeight * scale);
      const ctx = liveCanvas.getContext("2d");
      ctx.save();
      ctx.translate(liveCanvas.width, 0);
      ctx.scale(-1, 1);
      ctx.drawImage(liveVideo, 0, 0, liveCanvas.width, liveCanvas.height);
      ctx.restore();
      const blob = await new Promise((resolve) => liveCanvas.toBlob(resolve, "image/jpeg", 0.85));
      const formData = new FormData();
      formData.append("image", blob, "frame.jpg");
      formData.append("mode", liveMode);
      formData.append("color", liveColor);
      formData.append("style", liveStyle);
      formData.append("strength", (liveStrength.value / 100).toString());
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
  setTimeout(liveLoop, 100);
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
let tryonPoseBusy = false;
let tryonAnchor = { x: 0.5, y: 0.32, scale: 0.25 };
let dragStartX = null;
const scanStages = [
  { key: "left90", angle: -90, label: "Turn fully LEFT (90°), then capture", button: "Capture Left 90°" },
  { key: "left60", angle: -60, label: "Turn 60° LEFT, then capture", button: "Capture Left 60°" },
  { key: "left30", angle: -30, label: "Turn 30° LEFT, then capture", button: "Capture Left 30°" },
  { key: "front", angle: 0, label: "Face forward (0°), then capture", button: "Capture Front" },
  { key: "right30", angle: 30, label: "Turn 30° RIGHT, then capture", button: "Capture Right 30°" },
  { key: "right60", angle: 60, label: "Turn 60° RIGHT, then capture", button: "Capture Right 60°" },
  { key: "right90", angle: 90, label: "Turn fully RIGHT (90°), then capture", button: "Capture Right 90°" },
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
      const yawReady = Number.isFinite(detectedYaw) && Math.abs(detectedYaw - stage.angle) <= 12;
      setScanProgress((scanViewIndex / scanStages.length) * 100, yawReady ? `Angle ${Math.round(detectedYaw)}° detected — capturing` : `Turn until the guide reaches ${stage.angle}°`);
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
    card.innerHTML = `<img src="${peluca.previewUrl}" alt="${peluca.name}"><h3>${peluca.name}</h3><p>${peluca.date}</p><button>Apply to Try-On</button>`;
    card.querySelector("button").addEventListener("click", () => selectPeluca(peluca));
    pelucaGrid.appendChild(card);
  });
}

function selectPeluca(peluca) {
  selectedPeluca = peluca;
  selectedPelucaPreview.src = peluca.previewUrl;
  selectedPelucaName.textContent = peluca.name;
  selectedPelucaDate.textContent = `Captured ${peluca.date}`;
  tryonManualRotation = 0;
  tryonDetectedRotation = 0;
  openTransferView("tryon");
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
    const peluca = { mesh, previewUrl: scanViews.front || scanViews.left30, name: `180° Hair Mesh ${pelucas.length + 1}`, date: now.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) };
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
    tryonCamera.textContent = "Start Person B camera";
    tryonPlaceholder.hidden = false;
    return;
  }
  try {
    tryonStream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, facingMode: "user" }, audio: false });
    tryonVideo.srcObject = tryonStream;
    await tryonVideo.play();
    tryonPlaceholder.hidden = true;
    tryonCamera.textContent = "Stop Person B camera";
    tryonPoseLoop();
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
  if (!selectedPeluca || !selectedPeluca.mesh) return;
  const { vertices, faces, color, vertexColors, views } = selectedPeluca.mesh;
  if (views && views.length) {
    renderTexturedPeluca(context, width, height, views);
    return;
  }
  const radians = tryonRotation * Math.PI / 180;
  const cosine = Math.cos(radians);
  const sine = Math.sin(radians);
  const scale = Math.min(width, height) * tryonAnchor.scale;
  const centerX = width * tryonAnchor.x;
  const centerY = height * tryonAnchor.y;
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

function renderTexturedPeluca(context, width, height, views) {
  const targetYaw = ((tryonRotation + 180) % 360 + 360) % 360 - 180;
  const view = views.reduce((best, candidate) => (
    Math.abs(candidate.angle - targetYaw) < Math.abs(best.angle - targetYaw) ? candidate : best
  ));
  let image = pelucaImages.get(view.image);
  if (!image) {
    image = new Image();
    image.onload = () => renderTryonMesh();
    image.src = view.image;
    pelucaImages.set(view.image, image);
  }
  if (!image.complete || !image.naturalWidth) return;

  const faceWidth = (tryonAnchor.faceWidth || 0.22) * width;
  const faceHeight = (tryonAnchor.faceHeight || 0.32) * height;
  const drawWidth = faceWidth * view.faceSize[0];
  const drawHeight = faceHeight * view.faceSize[1];
  const drawX = tryonAnchor.faceCenterX * width - faceWidth * view.faceCenter[0];
  const drawY = tryonAnchor.faceCenterY * height - faceHeight * view.faceCenter[1];
  context.imageSmoothingEnabled = true;
  context.imageSmoothingQuality = "high";
  context.globalAlpha = 0.98;
  context.drawImage(image, drawX, drawY, drawWidth, drawHeight);
  context.globalAlpha = 1;
}

async function tryonPoseLoop() {
  if (!tryonStream) return;
  if (!tryonPoseBusy && tryonVideo.videoWidth > 0) {
    tryonPoseBusy = true;
    try {
      const poseCanvas = document.createElement("canvas");
      poseCanvas.width = 480;
      poseCanvas.height = Math.round(tryonVideo.videoHeight * (480 / tryonVideo.videoWidth));
      poseCanvas.getContext("2d").drawImage(tryonVideo, 0, 0, poseCanvas.width, poseCanvas.height);
      const frame = await new Promise((resolve) => poseCanvas.toBlob(resolve, "image/jpeg", 0.82));
      const formData = new FormData();
      formData.append("image", frame, "tryon-pose.jpg");
      const response = await fetch(`${API}/transfer/pose`, { method: "POST", body: formData });
      if (!response.ok) throw new Error("Could not read head position");
      const data = await response.json();
      const angles = { front: 0, left: -82, right: 82 };
      if (data.pose in angles) {
        tryonDetectedRotation = Number.isFinite(data.yaw) ? data.yaw : angles[data.pose];
        poseBadge.textContent = `${data.pose[0].toUpperCase()}${data.pose.slice(1)} view tracked`;
        if (data.face) {
          const [x, y, width, height] = data.face;
          tryonAnchor = {
            x: (x + width / 2) / poseCanvas.width,
            y: (y + height * 0.25) / poseCanvas.height,
            scale: Math.min(0.32, Math.max(0.12, (height / poseCanvas.height) / 2.3)),
            faceCenterX: (x + width / 2) / poseCanvas.width,
            faceCenterY: (y + height / 2) / poseCanvas.height,
            faceWidth: width / poseCanvas.width,
            faceHeight: height / poseCanvas.height,
          };
        }
        updateTryonRotation();
      } else {
        poseBadge.textContent = "Keep your profile in frame";
      }
    } catch (error) {
      poseBadge.textContent = "Head tracking unavailable";
    } finally {
      tryonPoseBusy = false;
    }
  }
  setTimeout(tryonPoseLoop, 450);
}

tryonCamera.addEventListener("click", toggleTryonCamera);
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
