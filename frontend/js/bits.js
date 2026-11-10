(() => {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const byId = (id) => document.getElementById(id);
  const inicio = byId("panel-inicio");

  function blurText(el, step = 70) {
    if (!el.dataset.text) el.dataset.text = el.textContent.trim();
    el.textContent = "";
    el.dataset.text.split(/\s+/).forEach((word, index) => {
      const span = document.createElement("span");
      span.className = "bt-word";
      span.textContent = word;
      span.style.animationDelay = `${index * step}ms`;
      el.append(span, document.createTextNode(" "));
    });
  }

  if (!reduce) $$(".page-head h1, .carta-head h2").forEach((el) => blurText(el));

  const rt = byId("rt");
  const LABELS = { full: "Barba completa", goatee: "Candado", mustache: "Bigote", stubble: "Tres días" };

  function rotateTo(word) {
    rt.textContent = "";
    [...word].forEach((char, index) => {
      const span = document.createElement("span");
      span.className = "rt-char";
      span.textContent = char === " " ? " " : char;
      span.style.animationDelay = reduce ? "0ms" : `${index * 24}ms`;
      rt.append(span);
    });
  }

  function countUp(el, target, decimals = 2, duration = 650) {
    const show = (value) => {
      el.textContent = value.toFixed(decimals).replace(".", ",");
    };
    if (reduce) {
      show(target);
      return;
    }
    const start = performance.now();
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration);
      show(target * (1 - Math.pow(1 - t, 3)));
      if (t < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  let autoplay = !reduce;
  const stopAutoplay = () => {
    autoplay = false;
  };
  document.addEventListener("demo:style", (event) => {
    const button = event.detail.button;
    rotateTo(LABELS[button.dataset.demo] || button.querySelector("span").textContent);
    countUp(byId("demo-time"), parseFloat(button.dataset.time.replace(",", ".")));
  });
  document.addEventListener("demo:manual", stopAutoplay);
  const demo = document.querySelector(".hero-demo");
  demo.addEventListener("pointerdown", (event) => {
    if (event.target.closest(".ba-range, .ba-modes")) stopAutoplay();
  });
  setInterval(() => {
    if (!autoplay || document.hidden || !inicio.classList.contains("active")) return;
    const tiles = $$(".demo-style");
    const index = tiles.findIndex((tile) => tile.classList.contains("active"));
    tiles[(index + 1) % tiles.length].click();
  }, 3400);
  rotateTo(rt.textContent.trim());

  const canvas = byId("threads");
  const hero = canvas.parentElement;
  const ctx = canvas.getContext("2d");
  const mouse = { x: -1e4, y: -1e4, tx: -1e4, ty: -1e4 };
  const LINES = 24;
  let width = 0;
  let height = 0;
  let running = false;
  let visible = true;
  let frame = 0;

  function resize() {
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    width = hero.clientWidth;
    height = hero.clientHeight;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function drawThreads(time) {
    ctx.clearRect(0, 0, width, height);
    mouse.x += (mouse.tx - mouse.x) * 0.09;
    mouse.y += (mouse.ty - mouse.y) * 0.09;
    const t = time * 0.00032;
    const radius = 110;
    for (let i = 0; i < LINES; i += 1) {
      const p = i / (LINES - 1);
      const base = height * (0.12 + 0.76 * p);
      ctx.beginPath();
      for (let x = -20; x <= width + 20; x += 12) {
        const nx = x / Math.max(width, 1);
        let y = base
          + Math.sin(nx * 5.1 + t * 2.0 + p * 4.2) * 12 * (0.45 + nx)
          + Math.sin(nx * 12.0 - t * 1.3 + p * 9.0) * 4;
        const dx = x - mouse.x;
        const dy = y - mouse.y;
        const pull = Math.exp(-(dx * dx + dy * dy) / (2 * radius * radius));
        y += (dy >= 0 ? 1 : -1) * pull * 26;
        if (x === -20) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      if (i === 8) ctx.strokeStyle = "rgba(244, 84, 84, 0.45)";
      else if (i === 15) ctx.strokeStyle = "rgba(68, 135, 246, 0.45)";
      else ctx.strokeStyle = `rgba(10, 10, 10, ${0.04 + 0.08 * Math.sin(p * Math.PI)})`;
      ctx.lineWidth = i === 8 || i === 15 ? 1.4 : 1;
      ctx.stroke();
    }
  }

  function loop(time) {
    if (!running) return;
    drawThreads(time);
    frame = requestAnimationFrame(loop);
  }

  function updateThreads() {
    const should = !reduce && visible && !document.hidden && inicio.classList.contains("active");
    if (should && !running) {
      running = true;
      frame = requestAnimationFrame(loop);
    } else if (!should && running) {
      running = false;
      cancelAnimationFrame(frame);
    }
  }

  new ResizeObserver(() => {
    resize();
    if (!running) drawThreads(0);
  }).observe(hero);
  new IntersectionObserver((entries) => {
    visible = entries[0].isIntersecting;
    updateThreads();
  }).observe(hero);
  document.addEventListener("visibilitychange", updateThreads);
  inicio.addEventListener("pointermove", (event) => {
    const rect = hero.getBoundingClientRect();
    mouse.tx = event.clientX - rect.left;
    mouse.ty = event.clientY - rect.top;
  }, { passive: true });
  inicio.addEventListener("pointerleave", () => {
    mouse.tx = -1e4;
    mouse.ty = -1e4;
  });

  new MutationObserver((changes) => {
    changes.forEach((change) => {
      const panel = change.target;
      const opened = panel.classList.contains("panel") && panel.classList.contains("active") && !(change.oldValue || "").includes("active");
      if (!opened) return;
      if (!reduce) $$(".page-head h1", panel).forEach((el) => blurText(el));
      updateThreads();
    });
    updateThreads();
  }).observe(document.querySelector(".content"), { subtree: true, attributes: true, attributeFilter: ["class"], attributeOldValue: true });

  document.addEventListener("pointermove", (event) => {
    const card = event.target.closest(".inspector, .look");
    if (!card) return;
    const rect = card.getBoundingClientRect();
    card.style.setProperty("--mx", `${event.clientX - rect.left}px`);
    card.style.setProperty("--my", `${event.clientY - rect.top}px`);
  }, { passive: true });
})();
