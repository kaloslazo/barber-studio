(() => {
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const inicio = document.getElementById("panel-inicio");
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const onInicio = () => !document.hidden && inicio.classList.contains("active");

  const photo = document.querySelector(".probador-foto");
  const layers = $$("img", photo);
  const label = document.getElementById("probador-label");
  const chips = $$(".probador-chip");
  let front = Math.max(0, layers.findIndex((img) => img.classList.contains("on")));
  let token = 0;
  let touched = false;
  let photoVisible = false;

  function ready(img) {
    if (img.complete && img.naturalWidth) return Promise.resolve();
    return new Promise((resolve) => {
      img.addEventListener("load", resolve, { once: true });
      img.addEventListener("error", resolve, { once: true });
    });
  }

  async function show(chip) {
    chips.forEach((other) => other.classList.toggle("active", other === chip));
    const mine = ++token;
    const back = layers[1 - front];
    back.src = `assets/inicio/${chip.dataset.look}.jpg`;
    await ready(back);
    if (mine !== token) return;
    label.textContent = chip.dataset.name;
    back.alt = `Foto de ejemplo: ${chip.dataset.name}`;
    back.removeAttribute("aria-hidden");
    layers[front].alt = "";
    layers[front].setAttribute("aria-hidden", "true");
    back.classList.add("on");
    layers[front].classList.remove("on");
    front = 1 - front;
  }

  chips.forEach((chip) => chip.addEventListener("click", () => {
    touched = true;
    show(chip);
  }));

  new IntersectionObserver((entries) => {
    photoVisible = entries[0].isIntersecting;
  }, { threshold: 0.35 }).observe(photo);

  setInterval(() => {
    if (reduce || touched || !photoVisible || !onInicio()) return;
    const index = chips.findIndex((chip) => chip.classList.contains("active"));
    show(chips[(index + 1) % chips.length]);
  }, 2600);

  const tiles = $$(".tile[data-flip]");
  const shown = new Set();
  const watch = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) shown.add(entry.target);
      else shown.delete(entry.target);
    });
  }, { threshold: 0.4 });
  tiles.forEach((tile) => watch.observe(tile));

  let tick = 0;
  setInterval(() => {
    if (reduce || !onInicio()) return;
    tick += 1;
    tiles.forEach((tile, index) => {
      if (!shown.has(tile) || tile.matches(":hover")) return;
      if ((tick + index) % 2 === 0) tile.classList.toggle("flipped");
    });
  }, 1800);
})();
