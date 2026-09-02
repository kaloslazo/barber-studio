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
const liveSwatches = document.getElementById("live-swatches");
const liveStyles = document.getElementById("live-styles");
const liveStrength = document.getElementById("live-strength");
const liveModeDye = document.getElementById("live-mode-dye");
const liveModeBeard = document.getElementById("live-mode-beard");

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

liveModeDye.addEventListener("click", () => {
  liveMode = "dye";
  liveModeDye.classList.add("active");
  liveModeBeard.classList.remove("active");
  liveSwatches.hidden = false;
  liveStyles.hidden = true;
});

liveModeBeard.addEventListener("click", () => {
  liveMode = "beard";
  liveModeBeard.classList.add("active");
  liveModeDye.classList.remove("active");
  liveSwatches.hidden = true;
  liveStyles.hidden = false;
});

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
