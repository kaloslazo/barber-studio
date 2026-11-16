(() => {
  const byId = (id) => document.getElementById(id);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const input = byId("practicante-input");
  const go = byId("apprentice-go");
  const banner = byId("apprentice-error");
  const compare = byId("apprentice-compare");
  const before = byId("apprentice-before");
  const after = byId("apprentice-after");
  const bar = byId("apprentice-bar");
  const quote = byId("apprentice-quote");
  const reelBeard = byId("reel-beard");
  const reelColor = byId("reel-color");
  const reelCut = byId("reel-cut");

  const BEARDS = [["full", "Completa"], ["goatee", "Candado"], ["mustache", "Bigote"], ["stubble", "Tres días"]];
  const CUTS = [["low-fade", "Degradado bajo"], ["mid-fade", "Degradado medio"], ["high-fade", "Degradado alto"], ["taper", "Taper"], ["undercut", "Undercut"], ["hard-part", "Raya marcada"], ["crew", "Crew cut"], ["buzz", "Rapado"]];
  const WILD = [["#3d8b3d", "Verde"], ["#d95fa6", "Rosado"], ["#2f4fb8", "Azul"], ["#7a3ba8", "Morado"], ["#b3312c", "Rojo"], ["#d9b04a", "Rubio"]];
  const NATURAL = [["#1f1f1f", "Negro"], ["#5a3a22", "Castaño"], ["#8a5a3b", "Castaño claro"]];
  const NO_DYE = ["", "Sin tinte"];
  const FIRST_DAY = [
    "Confía en mí. En TikTok está de moda.",
    "Si no te gusta, en tres semanas crece.",
    "Es mi primer día, pero tengo buena mano.",
    "No mires el espejo hasta que termine.",
    "Lo vi en Pinterest y quería probarlo con alguien.",
    "Tranquilo, en tu casa igual te van a querer.",
    "Mi profesor de la academia dijo que así se hace.",
  ];
  const HINTS = {
    first: "Elige al azar entre todas las barbas, colores y cortes. Sin garantía.",
    learned: "Mide la forma de tu cara en la malla 3D y elige entre lo que te favorece. Tinte solo en tonos naturales, y a veces ninguno.",
  };
  let mode = "first";
  let photoUrl = null;
  let afterUrl = null;
  let last = null;

  const pick = (list) => list[Math.floor(Math.random() * list.length)];
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  async function failure(response) {
    const body = await response.json().catch(() => ({}));
    return new Error(body.detail || `La solicitud falló (${response.status})`);
  }

  function showBeard([, name]) {
    reelBeard.textContent = name;
  }

  function showColor([hex, name]) {
    reelColor.querySelector("i").style.background = hex || "transparent";
    reelColor.querySelector("i").classList.toggle("empty", !hex);
    reelColor.querySelector("b").textContent = name;
  }

  function showCut([, name]) {
    reelCut.textContent = name;
  }

  function spin(values, show) {
    let index = Math.floor(Math.random() * values.length);
    const timer = setInterval(() => {
      index = (index + 1) % values.length;
      show(values[index]);
    }, 70);
    return (final) => {
      clearInterval(timer);
      show(final);
    };
  }

  function setPhoto(file) {
    if (photoUrl) URL.revokeObjectURL(photoUrl);
    photoUrl = URL.createObjectURL(file);
    byId("apprentice-photo").src = photoUrl;
    byId("apprentice-photo").hidden = false;
    byId("apprentice-photo-empty").hidden = true;
  }

  input.addEventListener("change", () => {
    if (input.files[0]) setPhoto(input.files[0]);
  });
  byId("apprentice-upload").addEventListener("click", () => input.click());

  function choosePhoto() {
    if (input.files[0]) return Promise.resolve(input.files[0]);
    return new Promise((resolve) => {
      input.addEventListener("change", () => resolve(input.files[0] || null), { once: true });
      input.click();
    });
  }

  $$("[data-apprentice-mode]").forEach((button) => button.addEventListener("click", () => {
    $$("[data-apprentice-mode]").forEach((other) => other.classList.toggle("active", other === button));
    mode = button.dataset.apprenticeMode;
    byId("apprentice-hint").textContent = HINTS[mode];
  }));

  async function decide(file) {
    if (mode === "first") {
      return { beard: pick(BEARDS), color: pick(WILD), cut: pick(CUTS), line: pick(FIRST_DAY) };
    }
    const data = new FormData();
    data.append("image", file);
    const response = await fetch("/api/face-shape", { method: "POST", body: data });
    if (!response.ok) throw await failure(response);
    const shape = await response.json();
    const beardKey = pick(shape.beard);
    const cutKey = pick(shape.haircut);
    return {
      beard: BEARDS.find(([key]) => key === beardKey),
      color: Math.random() < 0.4 ? NO_DYE : pick(NATURAL),
      cut: CUTS.find(([key]) => key === cutKey),
      line: `Tu cara es ${shape.label.toLowerCase()}. ${shape.why}`,
    };
  }

  go.addEventListener("click", async () => {
    banner.hidden = true;
    const file = await choosePhoto();
    if (!file) return;
    go.disabled = true;
    go.textContent = "Decidiendo…";
    const stops = [spin(BEARDS, showBeard), spin([...WILD, ...NATURAL], showColor), spin(CUTS, showCut)];
    try {
      const choice = await decide(file);
      const data = new FormData();
      data.append("image", file);
      data.append("beard", choice.beard[0]);
      data.append("color", choice.color[0]);
      data.append("cut", choice.cut[0]);
      const request = fetch("/api/look", { method: "POST", body: data });
      await wait(900);
      stops[0](choice.beard);
      await wait(500);
      stops[1](choice.color);
      const response = await request;
      if (!response.ok) throw await failure(response);
      const blob = await response.blob();
      await wait(400);
      stops[2](choice.cut);
      if (afterUrl) URL.revokeObjectURL(afterUrl);
      afterUrl = URL.createObjectURL(blob);
      before.src = photoUrl || URL.createObjectURL(file);
      after.src = afterUrl;
      compare.hidden = false;
      bar.hidden = false;
      const skipped = (response.headers.get("X-Skipped") || "").split(",").filter(Boolean);
      const excuse = skipped.length ? " No encontró pelo que teñir o cortar, así que se lo saltó." : "";
      quote.textContent = `«${choice.line}»${excuse}`;
      quote.hidden = false;
      const beardNote = window.freshLooks ? window.freshLooks.beardNote(choice.beard[0]) : "";
      const cutNote = window.freshLooks ? window.freshLooks.cutNote(choice.cut[0]) : "";
      last = {
        tool: "apprentice",
        title: `Look del practicante: ${choice.beard[1].toLowerCase()}, ${choice.color[1].toLowerCase()}, ${choice.cut[1].toLowerCase()}`,
        meta: mode === "first" ? "Primer día" : "Ya aprendió",
        details: [["Barba", choice.beard[1], beardNote], ["Tinte", choice.color[1], choice.color[0] ? `Referencia ${choice.color[0].toUpperCase()}` : ""], ["Corte", choice.cut[1], cutNote]],
        before: before.src,
        after: afterUrl,
      };
    } catch (error) {
      stops.forEach((stop) => stop(["", "—"]));
      reelColor.querySelector("b").textContent = "—";
      banner.textContent = error.message;
      banner.hidden = false;
    } finally {
      go.disabled = false;
      go.textContent = "Que decida el practicante";
    }
  });

  byId("apprentice-save").addEventListener("click", () => {
    if (last && window.freshLooks) window.freshLooks.save(last);
  });
  byId("apprentice-ficha").addEventListener("click", async () => {
    if (!last || !window.freshLooks) return;
    await window.freshLooks.ficha(last);
    window.freshLooks.toast("Ficha descargada");
  });
  byId("apprentice-download").addEventListener("click", () => {
    if (!afterUrl) return;
    const link = document.createElement("a");
    link.href = afterUrl;
    link.download = "fresh-practicante.png";
    link.click();
  });
})();
