(() => {
  const BASE = "/api";
  const byId = (id) => document.getElementById(id);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const sharedInput = byId("fiesta-input");

  async function failure(response) {
    const body = await response.json().catch(() => ({}));
    return new Error(body.detail || `La solicitud falló (${response.status})`);
  }

  function showError(banner, error) {
    banner.textContent = error.message || String(error);
    banner.hidden = false;
  }

  function sharedPhoto() {
    if (sharedInput.files[0]) return Promise.resolve(sharedInput.files[0]);
    return new Promise((resolve) => {
      sharedInput.addEventListener("change", () => resolve(sharedInput.files[0] || null), { once: true });
      sharedInput.click();
    });
  }

  function countdown(element, steps) {
    return new Promise((resolve) => {
      let index = 0;
      element.hidden = false;
      element.textContent = steps[0];
      const timer = setInterval(() => {
        index += 1;
        if (index < steps.length) {
          element.textContent = steps[index];
          return;
        }
        clearInterval(timer);
        element.hidden = true;
        resolve();
      }, 800);
    });
  }

  function download(src, name) {
    const link = document.createElement("a");
    link.href = src;
    link.download = name;
    link.click();
  }

  function camera(video) {
    const canvas = document.createElement("canvas");
    let stream = null;
    return {
      get on() {
        return Boolean(stream);
      },
      async start() {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 1280 }, facingMode: "user" },
          audio: false,
        });
        video.srcObject = stream;
        await video.play();
      },
      stop() {
        if (stream) stream.getTracks().forEach((track) => track.stop());
        stream = null;
        video.srcObject = null;
      },
      frame(width = 640, quality = 0.85) {
        const scale = Math.min(1, width / video.videoWidth);
        canvas.width = Math.round(video.videoWidth * scale);
        canvas.height = Math.round(video.videoHeight * scale);
        const ctx = canvas.getContext("2d");
        ctx.save();
        ctx.translate(canvas.width, 0);
        ctx.scale(-1, 1);
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        ctx.restore();
        return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
      },
    };
  }

  function liveTool({ panel, prefix, form, describe, waiting = "" }) {
    const button = byId(`${prefix}-camera`);
    const photoButton = byId(`${prefix}-photo`);
    const stage = byId(`${prefix}-stage`);
    const view = byId(`${prefix}-view`);
    const fps = byId(`${prefix}-fps`);
    const status = byId(`${prefix}-status`);
    const bar = byId(`${prefix}-bar`);
    const banner = byId(`${prefix}-error`);
    const video = document.createElement("video");
    video.muted = true;
    video.playsInline = true;
    const cam = camera(video);
    let running = false;
    let busy = false;
    let shown = null;

    function show(blob) {
      if (shown) URL.revokeObjectURL(shown);
      shown = URL.createObjectURL(blob);
      view.src = shown;
      stage.hidden = false;
    }

    function say(text) {
      status.textContent = text || "";
      status.hidden = !text;
    }

    async function loop() {
      if (!running) return;
      if (!busy && video.videoWidth > 0) {
        busy = true;
        const started = performance.now();
        try {
          const blob = await cam.frame();
          const data = form();
          if (!data) {
            show(blob);
            say(waiting);
          } else {
            data.append("image", blob, "frame.jpg");
            const response = await fetch(`${BASE}/faces/live`, { method: "POST", body: data });
            if (!response.ok) throw await failure(response);
            show(await response.blob());
            say(describe(Number(response.headers.get("X-Faces") || 0)));
            fps.textContent = `${(1000 / (performance.now() - started)).toFixed(1)} fps`;
          }
        } catch (error) {
          showError(banner, error);
          if (/Choose a face/i.test(error.message)) panel.dispatchEvent(new Event("source-lost"));
        } finally {
          busy = false;
        }
      }
      setTimeout(loop, 0);
    }

    async function start() {
      banner.hidden = true;
      try {
        await cam.start();
      } catch (error) {
        showError(banner, new Error(`No se pudo abrir la cámara: ${error.message}`));
        return false;
      }
      running = true;
      bar.hidden = false;
      button.textContent = "Apagar cámara";
      loop();
      return true;
    }

    function stop() {
      running = false;
      cam.stop();
      button.textContent = "Encender cámara";
      fps.textContent = "";
    }

    button.addEventListener("click", () => (running ? stop() : start()));

    photoButton.addEventListener("click", async () => {
      if (running) stop();
      banner.hidden = true;
      const data = form();
      if (!data) {
        showError(banner, new Error("Choose a face to wear first"));
        return;
      }
      const file = await sharedPhoto();
      if (!file) return;
      data.append("image", file);
      photoButton.disabled = true;
      photoButton.textContent = "Procesando…";
      try {
        const response = await fetch(`${BASE}/faces/photo`, { method: "POST", body: data });
        if (!response.ok) throw await failure(response);
        show(await response.blob());
        say("");
        bar.hidden = false;
      } catch (error) {
        showError(banner, error);
      } finally {
        photoButton.disabled = false;
        photoButton.textContent = "Usar tu foto";
      }
    });

    byId(`${prefix}-download`).addEventListener("click", () => {
      if (view.src) download(view.src, `fresh-${prefix}.jpg`);
    });

    new MutationObserver(() => {
      if (!panel.classList.contains("active") && running) stop();
    }).observe(panel, { attributes: true, attributeFilter: ["class"] });

    return { start, stop, cam, video, get running() { return running; } };
  }

  const swapPanel = byId("panel-swap");
  let swapMode = "swap";
  let hasSource = false;
  const sourceImg = byId("swap-source-img");
  const sourceEmpty = byId("swap-source-empty");
  const swapBanner = byId("swap-error");

  const swap = liveTool({
    panel: swapPanel,
    prefix: "swap",
    form() {
      if (swapMode === "wear" && !hasSource) return null;
      const data = new FormData();
      data.append("mode", swapMode);
      return data;
    },
    describe(count) {
      if (count === 0) return "No se ve ninguna cara";
      if (swapMode === "swap" && count < 2) return "Falta la segunda cara";
      return "";
    },
    waiting: "Primero guarden la cara que se van a poner",
  });

  $$("[data-swap-mode]").forEach((button) => button.addEventListener("click", () => {
    $$("[data-swap-mode]").forEach((other) => other.classList.toggle("active", other === button));
    swapMode = button.dataset.swapMode;
    byId("swap-source-field").hidden = swapMode !== "wear";
    byId("swap-hint").textContent = swapMode === "wear"
      ? "Guarden una cara (la del profe queda perfecta) y todos los que aparezcan en la cámara la llevan puesta."
      : "Dos caras de frente y con buena luz. Si son tres, cada uno recibe la cara del que tiene a su derecha.";
  }));

  async function saveSource(blob) {
    swapBanner.hidden = true;
    const data = new FormData();
    data.append("image", blob, "cara.jpg");
    try {
      const response = await fetch(`${BASE}/faces/source`, { method: "POST", body: data });
      if (!response.ok) throw await failure(response);
      if (sourceImg.src) URL.revokeObjectURL(sourceImg.src);
      sourceImg.src = URL.createObjectURL(await response.blob());
      sourceImg.hidden = false;
      sourceEmpty.hidden = true;
      hasSource = true;
    } catch (error) {
      showError(swapBanner, error);
    }
  }

  swapPanel.addEventListener("source-lost", () => {
    hasSource = false;
    sourceImg.hidden = true;
    sourceEmpty.hidden = false;
  });

  byId("swap-source-upload").addEventListener("click", () => byId("swap-source-input").click());
  byId("swap-source-input").addEventListener("change", (event) => {
    const file = event.target.files[0];
    if (file) saveSource(file);
    event.target.value = "";
  });
  byId("swap-source-sample").addEventListener("click", async () => {
    const blob = await fetch("assets/samples/ejemplo.jpg").then((response) => response.blob());
    saveSource(blob);
  });
  byId("swap-source-camera").addEventListener("click", async () => {
    const button = byId("swap-source-camera");
    if (!swap.running && !(await swap.start())) return;
    button.disabled = true;
    await countdown(byId("swap-count"), ["3", "2", "1"]);
    const blob = await swap.cam.frame(1280, 0.92);
    await saveSource(blob);
    button.disabled = false;
  });

  let cariPreset = "caricature";
  const cariAmount = byId("cari-amount");
  liveTool({
    panel: byId("panel-caricature"),
    prefix: "cari",
    form() {
      const data = new FormData();
      data.append("mode", "caricature");
      data.append("preset", cariPreset);
      data.append("amount", (cariAmount.value / 100).toString());
      return data;
    },
    describe(count) {
      return count === 0 ? "No se ve ninguna cara" : "";
    },
  });
  $$("[data-cari-preset]").forEach((button) => button.addEventListener("click", () => {
    $$("[data-cari-preset]").forEach((other) => other.classList.toggle("active", other === button));
    cariPreset = button.dataset.cariPreset;
  }));

  const fusionPanel = byId("panel-fusion");
  const fusionStage = byId("fusion-stage");
  const fusionView = byId("fusion-view");
  const fusionVideo = byId("fusion-video");
  const fusionT = byId("fusion-t");
  const fusionBanner = byId("fusion-error");
  const fusionPlay = byId("fusion-play");
  const fusionSnap = byId("fusion-snap");
  const fusionGo = byId("fusion-go");
  const nameA = byId("fusion-a-name");
  const nameB = byId("fusion-b-name");
  const fusionCam = camera(fusionVideo);
  let fusionSource = "pair";
  let fusionFrames = [];
  let fusionOther = null;
  let playing = null;

  function childName(a, b) {
    const left = a.trim();
    const right = b.trim();
    if (!left || !right) return "";
    const name = left.slice(0, Math.ceil(left.length / 2)) + right.slice(Math.floor(right.length / 2)).toLowerCase();
    return name.charAt(0).toUpperCase() + name.slice(1);
  }

  function renderNames() {
    byId("fusion-name-a").textContent = nameA.value.trim() || "A";
    byId("fusion-name-b").textContent = nameB.value.trim() || "B";
    const child = childName(nameA.value, nameB.value);
    const text = byId("fusion-child");
    text.textContent = "";
    if (child) {
      text.append("A la mitad nace ");
      const strong = document.createElement("strong");
      strong.textContent = child;
      text.append(strong);
    } else {
      text.textContent = "A la mitad, el hijo de los dos";
    }
  }
  [nameA, nameB].forEach((input) => input.addEventListener("input", renderNames));

  function showFrame() {
    if (!fusionFrames.length) return;
    const index = Math.round((fusionT.value / 100) * (fusionFrames.length - 1));
    fusionView.src = fusionFrames[index];
  }
  fusionT.addEventListener("input", () => {
    stopPlaying();
    showFrame();
  });

  function stopPlaying() {
    if (!playing) return;
    cancelAnimationFrame(playing);
    playing = null;
    fusionPlay.textContent = "Animar";
  }

  fusionPlay.addEventListener("click", () => {
    if (playing) {
      stopPlaying();
      return;
    }
    const begin = performance.now();
    fusionPlay.textContent = "Detener";
    const step = (now) => {
      const phase = ((now - begin) / 3200) % 1;
      fusionT.value = Math.round(100 * (0.5 - 0.5 * Math.cos(phase * 2 * Math.PI)));
      showFrame();
      playing = requestAnimationFrame(step);
    };
    playing = requestAnimationFrame(step);
  });

  byId("fusion-download").addEventListener("click", () => {
    if (!fusionView.src) return;
    const child = childName(nameA.value, nameB.value) || "fusion";
    download(fusionView.src, `${child.toLowerCase()}.jpg`);
  });

  $$("[data-fusion-source]").forEach((button) => button.addEventListener("click", () => {
    $$("[data-fusion-source]").forEach((other) => other.classList.toggle("active", other === button));
    fusionSource = button.dataset.fusionSource;
    byId("fusion-two").hidden = fusionSource !== "two";
    fusionSnap.hidden = fusionSource !== "pair";
  }));

  function thumb(button, file) {
    const img = button.querySelector("img");
    if (img.src) URL.revokeObjectURL(img.src);
    img.src = URL.createObjectURL(file);
    img.hidden = false;
  }

  sharedInput.addEventListener("change", () => {
    if (sharedInput.files[0]) thumb(byId("fusion-a"), sharedInput.files[0]);
  });
  byId("fusion-a").addEventListener("click", () => sharedInput.click());
  byId("fusion-b").addEventListener("click", () => byId("fusion-b-input").click());
  byId("fusion-b-input").addEventListener("change", (event) => {
    const file = event.target.files[0];
    if (!file) return;
    fusionOther = file;
    thumb(byId("fusion-b"), file);
  });

  async function fuse(image, other) {
    fusionBanner.hidden = true;
    stopPlaying();
    const data = new FormData();
    data.append("image", image, "a.jpg");
    if (other) data.append("other", other, "b.jpg");
    fusionGo.disabled = true;
    fusionGo.textContent = "Fusionando…";
    try {
      const response = await fetch(`${BASE}/faces/fusion`, { method: "POST", body: data });
      if (!response.ok) throw await failure(response);
      fusionFrames = (await response.json()).frames;
      fusionStage.hidden = false;
      fusionVideo.hidden = true;
      fusionView.hidden = false;
      byId("fusion-slider").hidden = false;
      byId("fusion-bar").hidden = false;
      fusionT.value = 50;
      showFrame();
      renderNames();
    } catch (error) {
      showError(fusionBanner, error);
      fusionVideo.hidden = true;
      fusionView.hidden = false;
      if (!fusionFrames.length) fusionStage.hidden = true;
    } finally {
      fusionGo.disabled = false;
      fusionGo.textContent = "Fusionar";
    }
  }

  fusionGo.addEventListener("click", async () => {
    const image = await sharedPhoto();
    if (!image) return;
    if (fusionSource === "two") {
      if (!fusionOther) {
        showError(fusionBanner, new Error("Falta la foto de la otra persona."));
        return;
      }
      fuse(image, fusionOther);
      return;
    }
    fuse(image, null);
  });

  fusionSnap.addEventListener("click", async () => {
    fusionBanner.hidden = true;
    stopPlaying();
    try {
      await fusionCam.start();
    } catch (error) {
      showError(fusionBanner, new Error(`No se pudo abrir la cámara: ${error.message}`));
      return;
    }
    fusionSnap.disabled = true;
    fusionStage.hidden = false;
    fusionView.hidden = true;
    fusionVideo.hidden = false;
    byId("fusion-slider").hidden = true;
    await countdown(byId("fusion-count"), ["3", "2", "1", "¡Fusión!"]);
    const blob = await fusionCam.frame(1280, 0.92);
    fusionCam.stop();
    fusionSnap.disabled = false;
    await fuse(blob, null);
  });

  new MutationObserver(() => {
    if (fusionPanel.classList.contains("active")) return;
    stopPlaying();
    if (fusionCam.on) fusionCam.stop();
  }).observe(fusionPanel, { attributes: true, attributeFilter: ["class"] });

  renderNames();
})();
