(() => {
  const byId = (id) => document.getElementById(id);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

  const toastEl = byId("toast");
  let toastTimer = null;
  function toast(message) {
    toastEl.textContent = message;
    toastEl.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toastEl.hidden = true;
    }, 2600);
  }

  const menuItems = $$(".menu-item");
  const groupTabs = $$(".group-tab");
  const subnav = byId("subnav");
  const lastInGroup = { inicio: "inicio", estilos: "beard", "3d": "mirror", juegos: "speedrun", looks: "looks" };
  let fromHistory = false;

  function syncNav(item) {
    const group = item.dataset.group;
    const panel = item.dataset.panel;
    lastInGroup[group] = panel;
    groupTabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.group === group));
    menuItems.forEach((other) => other.classList.toggle("is-hidden", other.dataset.group !== group));
    subnav.hidden = menuItems.filter((other) => other.dataset.group === group).length < 2;
    document.body.dataset.group = group;
    if (panel === "looks" || panel === "inicio") renderLooks();
    if (!fromHistory && location.hash !== `#${panel}`) history.pushState(null, "", `#${panel}`);
    window.scrollTo({ top: 0 });
  }

  function go(panel) {
    const item = menuItems.find((candidate) => candidate.dataset.panel === panel);
    if (item) item.click();
  }

  menuItems.forEach((item) => item.addEventListener("click", () => syncNav(item)));
  groupTabs.forEach((tab) => tab.addEventListener("click", () => go(lastInGroup[tab.dataset.group])));
  document.addEventListener("click", (event) => {
    const target = event.target.closest("[data-go]");
    if (target) go(target.dataset.go);
  });
  window.addEventListener("popstate", () => {
    fromHistory = true;
    go(location.hash.slice(1) || "inicio");
    fromHistory = false;
  });

  const PHOTO_INPUTS = ["beard-input", "photo-input", "hc-input", "mirror-input", "splat-input"];
  const sharedInput = byId("shared-input");
  const chip = byId("photo-chip");
  const chipImg = byId("photo-chip-img");
  const chipText = byId("photo-chip-text");
  let syncing = false;
  let goAfterUpload = null;
  let chain = null;
  let chaining = false;

  function sharePhoto(file, sourceId) {
    if (!file || !file.type.startsWith("image/")) return;
    if (!chaining && chain) {
      URL.revokeObjectURL(chain.origin);
      chain = null;
      renderChain();
    }
    syncing = true;
    PHOTO_INPUTS.forEach((id) => {
      if (id === sourceId) return;
      const input = byId(id);
      const transfer = new DataTransfer();
      transfer.items.add(file);
      input.files = transfer.files;
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
    syncing = false;
    if (!chaining) requestFit(file);
    if (chipImg.src) URL.revokeObjectURL(chipImg.src);
    chipImg.src = URL.createObjectURL(file);
    chipText.textContent = "Tu foto";
    chip.title = "Cambiar la foto";
  }

  const LOADED = "Foto cargada en Barba, Tinte, Corte, Espejo 3D y Gaussianas";

  PHOTO_INPUTS.forEach((id) => {
    const input = byId(id);
    input.addEventListener("change", () => {
      if (!syncing && input.files[0]) {
        sharePhoto(input.files[0], id);
        toast(LOADED);
      }
    });
    const zone = input.closest(".drop-zone");
    zone.addEventListener("drop", (event) => {
      const file = event.dataTransfer.files[0];
      if (file) sharePhoto(file, id);
    });
  });

  chip.addEventListener("click", () => sharedInput.click());
  sharedInput.addEventListener("change", () => {
    const file = sharedInput.files[0];
    if (!file) return;
    sharePhoto(file, null);
    sharedInput.value = "";
    if (goAfterUpload) {
      go(goAfterUpload);
      goAfterUpload = null;
    }
    toast(LOADED);
  });

  $$("[data-upload]").forEach((button) => button.addEventListener("click", () => {
    goAfterUpload = "beard";
    sharedInput.click();
  }));

  async function useSample(goTo) {
    try {
      const blob = await fetch("assets/samples/muestra.jpg").then((response) => response.blob());
      sharePhoto(new File([blob], "foto-de-ejemplo.jpg", { type: "image/jpeg" }), null);
      if (goTo) go(goTo);
      toast("Foto de ejemplo cargada");
    } catch (error) {
      toast("No se pudo cargar la foto de ejemplo");
    }
  }

  $$("[data-sample]").forEach((button) => button.addEventListener("click", (event) => {
    event.stopPropagation();
    useSample(button.closest("#panel-inicio") ? "beard" : null);
  }));

  const camModal = byId("cam-modal");
  const camVideo = byId("cam-video");
  const camCount = byId("cam-count");
  const camShot = byId("cam-shot");
  const camError = byId("cam-error");
  let camStream = null;
  let camTimer = null;
  let camGo = null;

  function closeCamera() {
    clearInterval(camTimer);
    camTimer = null;
    camCount.hidden = true;
    if (camStream) camStream.getTracks().forEach((track) => track.stop());
    camStream = null;
    camVideo.srcObject = null;
    camModal.hidden = true;
    document.body.classList.remove("modal-open");
    camShot.disabled = false;
  }

  async function openCamera(goTo) {
    camGo = goTo;
    camError.hidden = true;
    camShot.disabled = true;
    camModal.hidden = false;
    document.body.classList.add("modal-open");
    try {
      camStream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 960 }, facingMode: "user" },
        audio: false,
      });
      camVideo.srcObject = camStream;
      await camVideo.play();
      camShot.disabled = false;
      camShot.focus();
    } catch (error) {
      camError.textContent = `No se pudo abrir la cámara: ${error.message}`;
      camError.hidden = false;
    }
  }

  function capture() {
    const width = camVideo.videoWidth;
    const height = camVideo.videoHeight;
    if (!width || !height) {
      closeCamera();
      return;
    }
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    ctx.translate(width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(camVideo, 0, 0, width, height);
    canvas.toBlob((blob) => {
      closeCamera();
      if (!blob) return;
      sharePhoto(new File([blob], "foto-camara.jpg", { type: "image/jpeg" }), null);
      if (camGo) go(camGo);
      toast("Foto tomada. Ya está en todas las herramientas");
    }, "image/jpeg", 0.92);
  }

  camShot.addEventListener("click", () => {
    if (camTimer) return;
    let left = 3;
    camShot.disabled = true;
    camCount.textContent = left;
    camCount.hidden = false;
    camTimer = setInterval(() => {
      left -= 1;
      if (left > 0) {
        camCount.textContent = left;
        return;
      }
      clearInterval(camTimer);
      camTimer = null;
      capture();
    }, 1000);
  });
  byId("cam-cancel").addEventListener("click", closeCamera);
  byId("cam-close").addEventListener("click", closeCamera);
  camModal.addEventListener("click", (event) => {
    if (event.target === camModal) closeCamera();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !camModal.hidden) closeCamera();
  });
  $$("[data-change]").forEach((button) => button.addEventListener("click", (event) => {
    event.stopPropagation();
    button.closest(".drop-zone").querySelector('input[type="file"]').click();
  }));
  $$("[data-camera]").forEach((button) => button.addEventListener("click", (event) => {
    event.stopPropagation();
    openCamera(button.closest("#panel-inicio") ? "beard" : null);
  }));

  $$(".drop-zone").forEach((zone) => {
    const input = zone.querySelector('input[type="file"]');
    const preview = zone.querySelector(".dz-preview");
    if (!input || !preview || input.multiple) return;
    const show = (file) => {
      if (!file || !file.type.startsWith("image/")) return;
      if (preview.src) URL.revokeObjectURL(preview.src);
      preview.src = URL.createObjectURL(file);
      zone.classList.add("has-photo");
    };
    input.addEventListener("change", () => show(input.files[0]));
    zone.addEventListener("drop", (event) => show(event.dataTransfer.files[0]));
  });

  $$("output[data-for]").forEach((output) => {
    const input = byId(output.dataset.for);
    if (!input) return;
    const unit = output.dataset.unit || "";
    const render = () => {
      const min = Number(input.min || 0);
      const max = Number(input.max || 100);
      input.style.setProperty("--fill", `${((Number(input.value) - min) / (max - min)) * 100}%`);
      output.textContent = `${input.value}${unit}`;
    };
    input.addEventListener("input", render);
    render();
  });

  $$(".ba").forEach((ba) => {
    const range = ba.querySelector(".ba-range");
    const modes = document.createElement("div");
    modes.className = "ba-modes";
    modes.innerHTML = `<button type="button" data-pos="100">Antes</button><button type="button" data-pos="50" data-icon="arrows-horizontal">Comparar</button><button type="button" data-pos="0">Después</button>`;
    const bar = ba.nextElementSibling;
    if (bar && bar.classList.contains("result-bar")) bar.prepend(modes);
    else ba.after(modes);
    const update = () => {
      ba.style.setProperty("--pos", `${range.value}%`);
      const value = Number(range.value);
      ba.classList.toggle("edge", value === 0 || value === 100);
      $$("button", modes).forEach((button) => {
        const target = Number(button.dataset.pos);
        const on = target === 50 ? value > 0 && value < 100 : value === target;
        button.classList.toggle("active", on);
      });
    };
    range.addEventListener("input", () => {
      ba.classList.remove("animate");
      update();
    });
    modes.addEventListener("click", (event) => {
      const button = event.target.closest("button");
      if (!button) return;
      ba.classList.add("animate");
      range.value = button.dataset.pos;
      update();
    });
    update();
  });

  const demoAfter = byId("demo-after");
  function showDemo(button) {
    $$(".demo-style").forEach((other) => other.classList.toggle("active", other === button));
    demoAfter.src = `assets/samples/demo-${button.dataset.demo}.jpg`;
    byId("demo-name").textContent = button.querySelector("span").textContent;
    byId("demo-time").textContent = button.dataset.time;
    document.dispatchEvent(new CustomEvent("demo:style", { detail: { button } }));
  }
  $$(".demo-style").forEach((button) => button.addEventListener("click", (event) => {
    if (event.isTrusted) document.dispatchEvent(new Event("demo:manual"));
    showDemo(button);
  }));

  $$(".palette").forEach((palette) => {
    const custom = palette.querySelector(".swatch-custom");
    custom.querySelector("input").addEventListener("input", () => custom.classList.add("selected"));
    palette.addEventListener("click", (event) => {
      if (event.target.closest("button.swatch")) custom.classList.remove("selected");
    });
  });

  const liveSwatches = byId("live-swatches");
  if (liveSwatches && !liveSwatches.querySelector(".selected")) {
    const first = liveSwatches.querySelector(".swatch");
    if (first) first.classList.add("selected");
  }

  const meshToggle = byId("beard-mesh");
  const meshTargets = [
    { img: byId("beard-original"), caption: byId("beard-original").closest("figure").querySelector("figcaption") },
    { img: document.querySelector("#beard-drop .dz-preview"), caption: null },
  ];
  let meshFile = null;
  let meshCache = { file: null, url: null };

  async function meshUrl(file) {
    if (meshCache.file === file && meshCache.url) return meshCache.url;
    const form = new FormData();
    form.append("image", file);
    const response = await fetch("/api/mesh", { method: "POST", body: form });
    if (!response.ok) throw new Error(String(response.status));
    if (meshCache.url) URL.revokeObjectURL(meshCache.url);
    meshCache = { file, url: URL.createObjectURL(await response.blob()) };
    return meshCache.url;
  }

  function hideMesh() {
    meshTargets.forEach(({ img, caption }) => {
      if (img.dataset.original) img.src = img.dataset.original;
      delete img.dataset.original;
      if (caption) caption.textContent = "Antes";
    });
  }

  async function syncMesh() {
    if (!meshToggle.checked || !meshFile) {
      hideMesh();
      return;
    }
    try {
      const url = await meshUrl(meshFile);
      if (!meshToggle.checked) return;
      meshTargets.forEach(({ img, caption }) => {
        if (!img.dataset.original) img.dataset.original = img.src;
        img.src = url;
        if (caption) caption.textContent = "Malla";
      });
    } catch (error) {
      meshToggle.checked = false;
      hideMesh();
      toast("No pudimos dibujar la malla en esta foto");
    }
  }

  function setMeshFile(file) {
    if (!file || !file.type.startsWith("image/")) return;
    meshFile = file;
    meshTargets.forEach(({ img }) => delete img.dataset.original);
    setTimeout(syncMesh, 0);
  }

  meshToggle.addEventListener("change", syncMesh);
  byId("beard-input").addEventListener("change", () => setMeshFile(byId("beard-input").files[0]));
  byId("beard-drop").addEventListener("drop", (event) => setMeshFile(event.dataTransfer.files[0]));

  const TOOLS = {
    dye: { panel: "panel-dye", before: "original-image", after: "result-image" },
    beard: { panel: "panel-beard", before: "beard-original", after: "beard-result" },
    haircut: { panel: "panel-haircut", before: "hc-original", after: "hc-result" },
  };

  function activeText(selector) {
    const button = document.querySelector(selector);
    return button ? button.textContent.trim() : "";
  }

  const BEARD_NOTES = {
    full: "Peine 4 (12 mm) parejo; cuello y mejillas a navaja",
    goatee: "Peine 3 en bigote y mentón; mejillas a 0",
    mustache: "Tijera en el bigote; el resto a 0",
    stubble: "Máquina 1 (3 mm) en toda la barba",
  };
  const CUT_NOTES = {
    "low-fade": "Máquina 0 en patillas y nuca, 1 y 2 hacia arriba; tijera arriba",
    "mid-fade": "Máquina 0 hasta la sien, 1 y 2 encima; tijera arriba",
    "high-fade": "Máquina 0 hasta lo alto de los lados, 1 en la unión; tijera arriba",
    taper: "Máquina 1 en patillas y nuca, 2 y 3 a los lados; tijera arriba",
    undercut: "Máquina 0,5 pareja en lados y nuca, sin degradar; arriba largo",
    "hard-part": "Degradado medio (0 a 2) y raya marcada a navaja al costado",
    crew: "Máquina 2 a los lados y 4 arriba, más largo adelante",
  };

  function buzzNote(level) {
    if (level >= 85) return "Máquina 1 (3 mm) en toda la cabeza";
    if (level >= 60) return "Máquina 2 (6 mm) en toda la cabeza";
    return "Máquina 3 (9 mm) en toda la cabeza";
  }

  function toHex(color) {
    const parts = (color.match(/\d+/g) || []).slice(0, 3).map(Number);
    if (parts.length !== 3) return "";
    return `#${parts.map((value) => value.toString(16).padStart(2, "0")).join("").toUpperCase()}`;
  }

  function describe(tool) {
    if (tool === "dye") {
      const custom = document.querySelector("#panel-dye .swatch-custom.selected");
      const picked = document.querySelector("#swatches .swatch.selected");
      const color = custom ? byId("custom-color").value.toUpperCase() : (picked ? picked.querySelector("span").textContent : "Negro");
      const hex = custom ? color : (picked ? toHex(picked.querySelector("i").style.background) : "");
      const level = byId("strength").value;
      const beard = byId("dye-beard").checked;
      const order = `${custom ? `Color ${color}` : color} al ${level} %${beard ? ", con barba" : ""}`;
      const note = [hex && `Referencia ${hex}`, beard && "incluye la barba"].filter(Boolean).join(" · ");
      return {
        title: custom ? "Tinte personalizado" : `Tinte ${color.toLowerCase()}`,
        order,
        note,
        details: [["Tinte", order, note]],
        meta: `Intensidad ${level} %`,
      };
    }
    if (tool === "beard") {
      const active = document.querySelector("#style-group .style-btn.active");
      const style = active ? active.textContent.trim() : "Completa";
      const level = byId("beard-strength").value;
      const order = `${style}, densidad ${level} %`;
      const note = BEARD_NOTES[active ? active.dataset.style : "full"] || "";
      return {
        title: `Barba ${style.toLowerCase()}`,
        style: active ? active.dataset.style : "full",
        order,
        note,
        details: [["Barba", order, note]],
        meta: `Densidad ${level} %`,
      };
    }
    const active = document.querySelector("#hc-style-group .style-btn.active");
    const cut = active ? active.textContent.trim() : "Degradado bajo";
    const key = active ? active.dataset.hcStyle : "low-fade";
    const level = Number(byId("hc-strength").value);
    const order = `${cut} al ${level} %`;
    const note = key === "buzz" ? buzzNote(level) : CUT_NOTES[key] || "";
    return {
      title: cut,
      order,
      note,
      details: [["Corte", order, note]],
      meta: `Intensidad ${level} %`,
    };
  }

  function updateOrder(tool) {
    const target = document.querySelector(`[data-order="${tool}"]`);
    if (target) target.textContent = describe(tool).order;
  }

  const lastResult = {};
  Object.entries(TOOLS).forEach(([tool, conf]) => {
    const panel = byId(conf.panel);
    ["click", "input"].forEach((type) => panel.addEventListener(type, () => updateOrder(tool)));
    updateOrder(tool);
    byId(conf.after).addEventListener("load", () => {
      const before = byId(conf.before);
      const own = describe(tool);
      const after = byId(conf.after).src;
      if (!chain) {
        lastResult[tool] = { ...own, before: before.dataset.original || before.src, after };
        return;
      }
      const steps = [...chain.steps, { tool, title: own.title, order: own.order, note: own.note, style: own.style }];
      lastResult[tool] = {
        title: steps.map((step) => step.title).join(" + "),
        order: own.order,
        meta: steps.map((step) => SERVICE[step.tool]).join(" + "),
        details: steps.map((step) => [SERVICE[step.tool], step.order, step.note]),
        before: chain.origin,
        after,
      };
      before.src = chain.origin;
    });
  });

  const narrow = window.matchMedia("(max-width: 900px)");
  const resultWatcher = new MutationObserver((changes) => {
    changes.forEach((change) => {
      const el = change.target;
      if (!el.hidden && narrow.matches && el.closest(".panel.active")) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  });
  $$(".result").forEach((el) => resultWatcher.observe(el, { attributes: true, attributeFilter: ["hidden"] }));

  const BUSY = { "apply-btn": "panel-dye", "beard-btn": "panel-beard", "hc-btn": "panel-haircut", "mirror-btn": "panel-mirror" };
  Object.entries(BUSY).forEach(([buttonId, panelId]) => {
    const button = byId(buttonId);
    const panel = byId(panelId);
    const check = () => panel.classList.toggle("is-busy", /^(Procesando|Construyendo)/.test(button.textContent.trim()));
    new MutationObserver(check).observe(button, { childList: true, characterData: true, subtree: true });
  });

  const ICON_STATES = [
    [/…$/, "loader-2"],
    [/^Apagar/, "camera-off"],
    [/^Detener/, "player-stop"],
  ];
  function syncIcon(button) {
    if (!button.dataset.iconIdle) button.dataset.iconIdle = button.dataset.icon;
    const text = button.textContent.trim();
    const state = ICON_STATES.find(([pattern]) => pattern.test(text));
    const icon = state ? state[1] : button.dataset.iconIdle;
    if (button.dataset.icon !== icon) button.dataset.icon = icon;
    button.classList.toggle("is-working", icon === "loader-2");
  }
  $$("button[data-icon]:not(.group-tab, .menu-item, .photo-chip)").forEach((button) => {
    new MutationObserver(() => syncIcon(button)).observe(button, { childList: true, characterData: true, subtree: true });
  });

  const MESSAGES = [
    [/^Invalid image file.*$/i, "El archivo no es una imagen válida."],
    [/^No hair detected in the image.*$/i, "No encontramos pelo en la foto. Usa una foto de frente, con el pelo a la vista y buena luz."],
    [/^Failed to encode result.*$/i, "No se pudo generar el resultado."],
    [/^No face detected.*$/i, "No encontramos una cara en la foto. Usa una foto de frente y con buena luz."],
    [/^Unknown beard style: (.*)$/i, "Estilo de barba desconocido: $1"],
    [/^.*temporarily disabled.*$/i, "Ese corte todavía no está disponible."],
    [/^Unknown haircut style: (.*)$/i, "Corte desconocido: $1"],
    [/^Face landmarker model not found.*$/i, "Falta el modelo de puntos faciales en el servidor."],
    [/^No hair or face detected.*$/i, "No encontramos pelo ni cara en la foto."],
    [/^Frames and scan angles must match.*$/i, "Las capturas y los ángulos no coinciden."],
    [/^Scan your face first.*$/i, "Primero escanea tu cara en «Tu cara», dentro de Peluca 3D."],
    [/^No hair detected in the captures.*$/i, "No encontramos pelo en las capturas."],
    [/^count must be between.*$/i, "La cantidad debe estar entre 10 y 5000."],
    [/^Unknown target: (.*)$/i, "Objetivo desconocido: $1"],
    [/^Unknown live mode: (.*)$/i, "Modo en vivo desconocido: $1"],
    [/^Send between 1 and 16 frames.*$/i, "Envía entre 1 y 16 fotos."],
    [/^No face found in the scan frames.*$/i, "No encontramos tu cara en las capturas."],
    [/^(Failed to fetch|Load failed|NetworkError.*)$/i, "No hay conexión con el servidor."],
    [/^No se pudo abrir la cámara: .*(permission|denied|notallowed).*/i, "No se pudo abrir la cámara: no diste permiso."],
    [/^No se pudo abrir la cámara: .*(notfound|not found|device).*/i, "No se pudo abrir la cámara: no encontramos ninguna."],
  ];

  $$(".banner").forEach((banner) => {
    new MutationObserver(() => {
      const text = banner.textContent.trim();
      const rule = MESSAGES.find(([pattern]) => pattern.test(text));
      if (!rule) return;
      const next = text.replace(rule[0], rule[1]);
      if (next !== text) banner.textContent = next;
    }).observe(banner, { childList: true, characterData: true, subtree: true });
  });

  fetch("/api/health").then((response) => response.json()).then((health) => {
    byId("dye-model-field").hidden = !health.yolo;
  }).catch(() => null);

  $$("[data-dye-model]").forEach((button) => {
    button.addEventListener("click", () => {
      $$("[data-dye-model]").forEach((other) => other.classList.toggle("active", other === button));
    });
  });

  const STORE = "barberstudio-looks-v1";
  const formatDate = new Intl.DateTimeFormat("es-PE", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

  function loadLooks() {
    try {
      return JSON.parse(localStorage.getItem(STORE)) || [];
    } catch (error) {
      return [];
    }
  }

  function storeLooks(looks) {
    const list = looks.slice();
    while (list.length) {
      try {
        localStorage.setItem(STORE, JSON.stringify(list));
        return list;
      } catch (error) {
        list.pop();
      }
    }
    try {
      localStorage.removeItem(STORE);
    } catch (error) {
      return [];
    }
    return [];
  }

  function loadImage(src) {
    return new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = reject;
      image.src = src;
    });
  }

  async function thumbnail(src, max = 560) {
    const image = await loadImage(src);
    const scale = Math.min(1, max / Math.max(image.naturalWidth, image.naturalHeight));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(image.naturalWidth * scale);
    canvas.height = Math.round(image.naturalHeight * scale);
    canvas.getContext("2d").drawImage(image, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", 0.86);
  }

  function slug(text) {
    return text.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
  }

  function saveBlob(blob, name) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
  }

  async function downloadImage(src, title) {
    const blob = await fetch(src).then((response) => response.blob());
    const ext = blob.type.includes("png") ? "png" : "jpg";
    saveBlob(blob, `fresh-${slug(title)}.${ext}`);
  }

  function drawCover(ctx, image, x, y, w, h) {
    const scale = Math.max(w / image.naturalWidth, h / image.naturalHeight);
    const sw = w / scale;
    const sh = h / scale;
    const sx = (image.naturalWidth - sw) / 2;
    const sy = (image.naturalHeight - sh) / 2;
    ctx.drawImage(image, sx, sy, sw, sh, x, y, w, h);
  }

  function drawPanel(ctx, image, x, y, w, h, label) {
    ctx.save();
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, 28);
    ctx.clip();
    ctx.fillStyle = "#0A0A0A";
    ctx.fillRect(x, y, w, h);
    drawCover(ctx, image, x, y, w, h);
    ctx.restore();
    ctx.font = '500 22px Figtree, Arial, sans-serif';
    const width = ctx.measureText(label).width + 36;
    ctx.fillStyle = "rgba(10, 10, 10, 0.62)";
    ctx.beginPath();
    ctx.roundRect(x + 20, y + h - 62, width, 42, 21);
    ctx.fill();
    ctx.fillStyle = "#FFFFFF";
    ctx.fillText(label, x + 38, y + h - 34);
  }

  async function makeFicha(look) {
    await Promise.all([
      document.fonts.load('76px "Libre Caslon Display"'),
      document.fonts.load('500 22px "Figtree"'),
      document.fonts.load('600 18px "Figtree"'),
    ]).catch(() => null);
    const [before, after] = await Promise.all([loadImage(look.before), loadImage(look.after)]);
    const W = 1080;
    const H = 1350;
    const canvas = document.createElement("canvas");
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#FAFAF8";
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = "#0A0A0A";
    ctx.font = '44px "Libre Caslon Display", Georgia, serif';
    ctx.fillText("Fresh", 72, 108);
    ctx.font = '500 22px Figtree, Arial, sans-serif';
    ctx.fillStyle = "#6A6A69";
    ctx.textAlign = "right";
    ctx.fillText(formatDate.format(new Date(look.ts)), W - 72, 104);
    ctx.textAlign = "left";
    ctx.fillStyle = "#0A0A0A";
    ctx.fillRect(72, 138, W - 144, 3);
    ctx.font = '76px "Libre Caslon Display", Georgia, serif';
    ctx.fillText("Ficha para tu barbero", 72, 236);
    const panelW = (W - 144 - 24) / 2;
    drawPanel(ctx, before, 72, 284, panelW, 540, "Antes");
    drawPanel(ctx, after, 72 + panelW + 24, 284, panelW, 540, "Después");
    let y = 900;
    const noted = look.details.some((row) => row[2]);
    look.details.forEach(([label, value, note]) => {
      ctx.fillStyle = "#6A6A69";
      ctx.font = '600 18px Figtree, Arial, sans-serif';
      ctx.fillText(label.toUpperCase(), 72, y);
      ctx.fillStyle = "#0A0A0A";
      ctx.font = '40px "Libre Caslon Display", Georgia, serif';
      ctx.textAlign = "right";
      ctx.fillText(value, W - 72, y + 6);
      if (note) {
        ctx.fillStyle = "#6A6A69";
        ctx.font = '500 21px Figtree, Arial, sans-serif';
        ctx.fillText(note, W - 72, y + 42);
      }
      ctx.textAlign = "left";
      ctx.strokeStyle = "#BDBDBA";
      ctx.setLineDash([6, 6]);
      ctx.beginPath();
      ctx.moveTo(72, y + (noted ? 64 : 34));
      ctx.lineTo(W - 72, y + (noted ? 64 : 34));
      ctx.stroke();
      ctx.setLineDash([]);
      y += noted ? 104 : 84;
    });
    ctx.fillStyle = "#0A0A0A";
    ctx.fillRect(72, H - 120, W - 144, 3);
    ctx.font = '500 24px Figtree, Arial, sans-serif';
    ctx.fillText("Muéstrale esta ficha a tu barbero.", 72, H - 66);
    ctx.fillStyle = "#6A6A69";
    ctx.textAlign = "right";
    ctx.fillText("Hecho con Fresh", W - 72, H - 66);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
    saveBlob(blob, `ficha-${slug(look.title)}.png`);
  }

  async function saveLook(tool) {
    const result = lastResult[tool];
    if (!result) return;
    const [before, after] = await Promise.all([thumbnail(result.before), thumbnail(result.after)]);
    const look = { id: Date.now().toString(36), tool, title: result.title, meta: result.meta, details: result.details, ts: Date.now(), before, after };
    const saved = storeLooks([look, ...loadLooks()].slice(0, 24));
    renderLooks();
    toast(saved.length ? `${result.title}: guardado en Mis looks` : "No queda espacio para guardar más looks");
  }

  $$(".result-bar").forEach((bar) => {
    const tool = bar.dataset.tool;
    bar.addEventListener("click", async (event) => {
      const button = event.target.closest("button");
      if (!button || !lastResult[tool]) return;
      const result = lastResult[tool];
      button.disabled = true;
      try {
        if (button.hasAttribute("data-save")) await saveLook(tool);
        if (button.hasAttribute("data-download")) await downloadImage(result.after, result.title);
        if (button.hasAttribute("data-ficha")) {
          await makeFicha({ ...result, ts: Date.now() });
          toast("Ficha descargada");
        }
      } catch (error) {
        toast("No se pudo completar");
      } finally {
        button.disabled = false;
      }
    });
  });

  const SERVICE = { beard: "Barba", dye: "Tinte", haircut: "Corte" };
  const NEXT = { beard: "la barba", dye: "el tinte", haircut: "el corte" };

  function renderChain() {
    $$("[data-chain-note]").forEach((note) => {
      note.hidden = !chain;
      if (chain) note.querySelector("strong").textContent = chain.steps.map((step) => step.title).join(" + ");
    });
    const beardStep = chain ? [...chain.steps].reverse().find((step) => step.tool === "beard") : null;
    byId("panel-dye").dataset.beardStyle = beardStep ? beardStep.style : "";
  }

  async function chainTo(tool, target) {
    const result = lastResult[tool];
    const blob = await (await fetch(result.after)).blob();
    if (!chain) {
      const origin = await (await fetch(result.before)).blob();
      chain = { origin: URL.createObjectURL(origin), originBlob: origin, steps: [] };
    }
    const own = describe(tool);
    chain.steps = [...chain.steps, { tool, title: own.title, order: own.order, note: own.note, style: own.style }];
    const name = `${slug(chain.steps.map((step) => step.title).join(" "))}.jpg`;
    chaining = true;
    try {
      sharePhoto(new File([blob], name, { type: blob.type || "image/jpeg" }), null);
    } finally {
      chaining = false;
    }
    renderChain();
    go(target);
    toast(`${result.title}: listo. Ahora elige ${NEXT[target]}`);
  }

  $$(".chain-bar").forEach((bar) => {
    const tool = bar.dataset.tool;
    bar.addEventListener("click", async (event) => {
      const button = event.target.closest("[data-chain]");
      if (!button || !lastResult[tool]) return;
      button.disabled = true;
      try {
        await chainTo(tool, button.dataset.chain);
      } catch (error) {
        toast("No se pudo combinar");
      } finally {
        button.disabled = false;
      }
    });
  });

  document.addEventListener("click", (event) => {
    if (!event.target.closest("[data-unchain]") || !chain) return;
    const file = new File([chain.originBlob], "foto-original.jpg", { type: chain.originBlob.type || "image/jpeg" });
    sharePhoto(file, null);
    toast("Volviste a tu foto original");
  });

  const FIT_PANELS = [
    { panel: "panel-beard", key: "beard", group: "#style-group", attr: "style" },
    { panel: "panel-haircut", key: "haircut", group: "#hc-style-group", attr: "hcStyle" },
  ];
  let fit = null;
  let fitRequest = 0;

  function renderFit() {
    FIT_PANELS.forEach(({ panel, key, group, attr }) => {
      const card = document.querySelector(`#${panel} [data-fit]`);
      const buttons = $$(`${group} .style-btn`);
      buttons.forEach((button) => delete button.dataset.fit);
      card.hidden = !fit;
      if (!fit) return;
      card.querySelector("[data-fit-label]").textContent = fit.label.toLowerCase();
      card.querySelector("[data-fit-why]").textContent = fit.why;
      const picks = card.querySelector("[data-fit-picks]");
      picks.textContent = "";
      fit[key].forEach((style) => {
        const target = buttons.find((button) => button.dataset[attr] === style);
        if (!target) return;
        target.dataset.fit = "";
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "fit-pick";
        chip.textContent = target.textContent.trim();
        chip.addEventListener("click", () => target.click());
        picks.append(chip);
      });
    });
  }

  async function requestFit(file) {
    const ticket = ++fitRequest;
    fit = null;
    renderFit();
    const form = new FormData();
    form.append("image", file);
    try {
      const response = await fetch("/api/face-shape", { method: "POST", body: form });
      if (!response.ok || ticket !== fitRequest) return;
      fit = await response.json();
      renderFit();
    } catch (error) {
      fit = null;
    }
  }

  function lookCard(look, compact) {
    const card = document.createElement("article");
    card.className = "card look";
    const media = document.createElement("button");
    media.type = "button";
    media.className = "look-media";
    media.setAttribute("aria-label", "Cambiar entre antes y después");
    media.innerHTML = `<img class="after" alt=""><img class="before" alt=""><span data-icon="eye">Después</span>`;
    media.querySelector(".after").src = look.after;
    media.querySelector(".before").src = look.before;
    media.addEventListener("click", () => {
      const showing = media.classList.toggle("show-before");
      media.querySelector("span").textContent = showing ? "Antes" : "Después";
    });
    const info = document.createElement("div");
    info.className = "look-info";
    const title = document.createElement("p");
    title.className = "look-title";
    title.textContent = look.title;
    const meta = document.createElement("p");
    meta.className = "look-meta";
    meta.textContent = `${look.meta} · ${formatDate.format(new Date(look.ts))}`;
    info.append(title, meta);
    card.append(media, info);
    if (!compact) {
      const actions = document.createElement("div");
      actions.className = "look-actions";
      actions.innerHTML = `<button type="button" class="quiet-button" data-ficha data-icon="receipt">Ficha</button><button type="button" class="quiet-button icon-only" data-download data-icon="download" aria-label="Descargar" title="Descargar"></button><button type="button" class="quiet-button icon-only" data-delete data-icon="trash" aria-label="Borrar" title="Borrar"></button>`;
      actions.addEventListener("click", async (event) => {
        const button = event.target.closest("button");
        if (!button) return;
        if (button.hasAttribute("data-ficha")) {
          await makeFicha(look);
          toast("Ficha descargada");
        }
        if (button.hasAttribute("data-download")) await downloadImage(look.after, look.title);
        if (button.hasAttribute("data-delete")) {
          storeLooks(loadLooks().filter((item) => item.id !== look.id));
          renderLooks();
          toast("Look borrado");
        }
      });
      card.append(actions);
    }
    return card;
  }

  function renderLooks() {
    const looks = loadLooks();
    const grid = byId("looks-grid");
    const recent = byId("recent-grid");
    grid.replaceChildren(...looks.map((look) => lookCard(look, false)));
    recent.replaceChildren(...looks.slice(0, 4).map((look) => lookCard(look, true)));
    byId("looks-empty").hidden = looks.length > 0;
    byId("recent-looks").hidden = looks.length === 0;
    byId("looks-clear").hidden = looks.length === 0;
    const count = byId("looks-count");
    count.hidden = looks.length === 0;
    count.textContent = looks.length;
  }

  byId("looks-clear").addEventListener("click", () => {
    if (!window.confirm("¿Borrar todos tus looks guardados?")) return;
    storeLooks([]);
    renderLooks();
    toast("Se borraron tus looks");
  });

  renderLooks();
  const startPanel = location.hash.slice(1);
  if (startPanel && menuItems.some((item) => item.dataset.panel === startPanel)) {
    fromHistory = true;
    go(startPanel);
    fromHistory = false;
  } else {
    fromHistory = true;
    syncNav(menuItems.find((item) => item.dataset.panel === "inicio"));
    fromHistory = false;
  }
})();
