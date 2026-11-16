(() => {
  const byId = (id) => document.getElementById(id);
  const input = byId("galeria-input");
  const wall = byId("gallery-wall");
  const view = byId("gallery-view");
  const title = byId("gallery-title");
  const meta = byId("gallery-meta");
  const credit = byId("gallery-credit");
  const ask = byId("gallery-ask");
  const nameInput = byId("gallery-name");
  const go = byId("gallery-go");
  const banner = byId("gallery-error");
  const bar = byId("gallery-bar");
  const photo = byId("gallery-photo");
  const photoEmpty = byId("gallery-photo-empty");
  const WOOD = "#2b1d14";
  const MAT = "#efe7d6";
  const BRASS = "#d9bf86";
  let portraits = [];
  let current = null;
  let results = {};

  function plaqueTitle(entry) {
    const name = nameInput.value.trim();
    return name ? `${name} como ${entry.name}` : entry.name;
  }

  function render() {
    const entry = portraits.find((item) => item.key === current);
    if (!entry) return;
    view.src = results[entry.key] || `assets/galeria/${entry.key}.jpg`;
    title.textContent = plaqueTitle(entry);
    meta.textContent = `${entry.year} · ${entry.style}`;
    credit.textContent = `${entry.painting ? "Pintura" : "Foto"} original: ${entry.author}. Dominio público.`;
    ask.textContent = `«${entry.ask.charAt(0).toUpperCase()}${entry.ask.slice(1)}, como ${entry.short}».`;
    wall.querySelectorAll(".gallery-thumb").forEach((thumb) => thumb.classList.toggle("active", thumb.dataset.key === entry.key));
    bar.hidden = !results[entry.key];
  }

  function select(key) {
    current = key;
    render();
  }

  function buildWall() {
    wall.textContent = "";
    portraits.forEach((entry) => {
      const thumb = document.createElement("button");
      thumb.type = "button";
      thumb.className = "gallery-thumb";
      thumb.dataset.key = entry.key;
      const img = document.createElement("img");
      img.src = results[entry.key] || `assets/galeria/${entry.key}.jpg`;
      img.alt = entry.name;
      const label = document.createElement("span");
      label.textContent = entry.short;
      thumb.append(img, label);
      thumb.addEventListener("click", () => select(entry.key));
      wall.appendChild(thumb);
    });
  }

  function showPhoto(file) {
    if (photo.src) URL.revokeObjectURL(photo.src);
    photo.src = URL.createObjectURL(file);
    photo.hidden = false;
    photoEmpty.hidden = true;
    results = {};
    buildWall();
    render();
  }

  input.addEventListener("change", () => {
    if (input.files[0]) showPhoto(input.files[0]);
  });
  byId("gallery-upload").addEventListener("click", () => input.click());
  nameInput.addEventListener("input", render);

  function choosePhoto() {
    if (input.files[0]) return Promise.resolve(input.files[0]);
    return new Promise((resolve) => {
      input.addEventListener("change", () => resolve(input.files[0] || null), { once: true });
      input.click();
    });
  }

  go.addEventListener("click", async () => {
    banner.hidden = true;
    const file = await choosePhoto();
    if (!file) return;
    const data = new FormData();
    data.append("image", file);
    go.disabled = true;
    go.textContent = "Entrando a los cuadros…";
    try {
      const response = await fetch("/api/gallery", { method: "POST", body: data });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `La solicitud falló (${response.status})`);
      }
      (await response.json()).results.forEach((item) => {
        results[item.key] = item.image;
      });
      buildWall();
      render();
    } catch (error) {
      banner.textContent = error.message;
      banner.hidden = false;
    } finally {
      go.disabled = false;
      go.textContent = "Entrar a los 7 cuadros";
    }
  });

  function wrapLines(ctx, text, width) {
    const words = text.split(" ");
    const lines = [];
    let line = "";
    words.forEach((word) => {
      const next = line ? `${line} ${word}` : word;
      if (ctx.measureText(next).width > width && line) {
        lines.push(line);
        line = word;
      } else {
        line = next;
      }
    });
    if (line) lines.push(line);
    return lines;
  }

  byId("gallery-download").addEventListener("click", async () => {
    const entry = portraits.find((item) => item.key === current);
    if (!entry || !results[entry.key]) return;
    await document.fonts.ready;
    const picture = await new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = reject;
      image.src = results[entry.key];
    });
    const frame = 46;
    const mat = 38;
    const width = picture.width + 2 * (frame + mat);
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    ctx.font = "44px 'Libre Caslon Display', Georgia, serif";
    const lines = wrapLines(ctx, plaqueTitle(entry), picture.width * 0.8);
    const plaque = 70 + lines.length * 52;
    canvas.width = width;
    canvas.height = picture.height + 2 * (frame + mat) + plaque + 40;
    ctx.fillStyle = WOOD;
    ctx.fillRect(0, 0, canvas.width, picture.height + 2 * (frame + mat));
    ctx.fillStyle = MAT;
    ctx.fillRect(frame, frame, picture.width + 2 * mat, picture.height + 2 * mat);
    ctx.drawImage(picture, frame + mat, frame + mat);
    ctx.fillStyle = "#faf8f4";
    ctx.fillRect(0, picture.height + 2 * (frame + mat), canvas.width, plaque + 40);
    const top = picture.height + 2 * (frame + mat) + 20;
    ctx.fillStyle = BRASS;
    ctx.fillRect(width * 0.1, top, width * 0.8, plaque);
    ctx.fillStyle = WOOD;
    ctx.textAlign = "center";
    ctx.font = "44px 'Libre Caslon Display', Georgia, serif";
    lines.forEach((line, index) => ctx.fillText(line, width / 2, top + 54 + index * 52));
    ctx.font = "24px 'Figtree', Arial, sans-serif";
    ctx.fillText(`${entry.year} · ${entry.style}`, width / 2, top + plaque - 22);
    const link = document.createElement("a");
    link.href = canvas.toDataURL("image/jpeg", 0.92);
    link.download = `${plaqueTitle(entry).toLowerCase().replace(/[^a-z0-9áéíóúñü]+/gi, "-")}.jpg`;
    link.click();
  });

  fetch("/api/gallery")
    .then((response) => response.json())
    .then((list) => {
      portraits = list;
      if (!portraits.length) return;
      current = portraits[0].key;
      buildWall();
      render();
    })
    .catch(() => {});
})();
