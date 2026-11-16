const freshFx = (() => {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function countNumbers(el, { from = 0, duration = 750 } = {}) {
    if (reduce || !el) return;
    const template = el.textContent;
    const numbers = [...template.matchAll(/\d[\d,]*(?:\.\d+)?/g)].filter((match) => match.index >= from).map((match) => {
      const raw = match[0];
      const decimals = raw.includes(".") ? raw.split(".")[1].length : 0;
      return { raw, at: match.index, value: parseFloat(raw.replace(/,/g, "")), decimals, grouped: raw.includes(",") };
    });
    if (!numbers.length) return;
    const format = (n, value) => {
      const fixed = value.toFixed(n.decimals);
      if (!n.grouped) return fixed;
      const [whole, part] = fixed.split(".");
      return whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",") + (part ? `.${part}` : "");
    };
    const start = performance.now();
    const tick = (now) => {
      if (el.textContent !== el.dataset.fxLast && el.dataset.fxLast !== undefined) return;
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      let text = "";
      let cursor = 0;
      numbers.forEach((n) => {
        text += template.slice(cursor, n.at) + format(n, n.value * eased);
        cursor = n.at + n.raw.length;
      });
      text += template.slice(cursor);
      el.textContent = text;
      el.dataset.fxLast = text;
      if (t < 1) requestAnimationFrame(tick);
      else delete el.dataset.fxLast;
    };
    delete el.dataset.fxLast;
    requestAnimationFrame(tick);
  }

  function place(group, thumb, animate) {
    const active = group.querySelector(":scope > .active");
    if (!active || !active.offsetWidth) {
      thumb.style.opacity = "0";
      return;
    }
    thumb.style.transition = animate && !reduce ? "" : "none";
    thumb.style.opacity = "1";
    thumb.style.width = `${active.offsetWidth}px`;
    thumb.style.height = `${active.offsetHeight}px`;
    thumb.style.transform = `translate(${active.offsetLeft}px, ${active.offsetTop}px)`;
  }

  function slide(group) {
    if (!group) return;
    let thumb = group.querySelector(":scope > .seg-thumb");
    const first = !thumb;
    if (first) {
      thumb = document.createElement("span");
      thumb.className = "seg-thumb";
      thumb.setAttribute("aria-hidden", "true");
      group.prepend(thumb);
      group.classList.add("has-thumb");
      new ResizeObserver(() => place(group, thumb, false)).observe(group);
      new MutationObserver(() => place(group, thumb, true)).observe(group, { subtree: true, attributes: true, attributeFilter: ["class"] });
    }
    place(group, thumb, !first);
  }

  const falls = new Map();

  function overlayFor(host, reference) {
    let fall = falls.get(host);
    if (!fall) {
      const canvas = document.createElement("canvas");
      canvas.className = "hair-fall";
      canvas.setAttribute("aria-hidden", "true");
      host.append(canvas);
      fall = { canvas, strands: [], running: false, last: 0 };
      falls.set(host, fall);
    }
    const dpr = window.devicePixelRatio || 1;
    const width = reference.clientWidth;
    const height = reference.clientHeight;
    Object.assign(fall.canvas.style, { left: `${reference.offsetLeft}px`, top: `${reference.offsetTop}px`, width: `${width}px`, height: `${height}px` });
    if (fall.canvas.width !== Math.round(width * dpr) || fall.canvas.height !== Math.round(height * dpr)) {
      fall.canvas.width = Math.round(width * dpr);
      fall.canvas.height = Math.round(height * dpr);
    }
    fall.dpr = dpr;
    fall.height = height;
    return fall;
  }

  function hairFall(host, reference, seeds) {
    if (reduce || !host || !reference || !seeds.length) return;
    const fall = overlayFor(host, reference);
    seeds.forEach((seed) => {
      const spread = seed.spread || 1;
      fall.strands.push({
        x: seed.x, y: seed.y,
        vx: (Math.random() - 0.5) * 120 * spread, vy: -40 - Math.random() * 90 * spread,
        angle: Math.random() * Math.PI, spin: (Math.random() - 0.5) * 9,
        length: 7 + Math.random() * 10, bend: (Math.random() - 0.5) * 7,
        color: seed.color, age: 0, life: 1.1 + Math.random() * 0.7,
      });
    });
    if (fall.strands.length > 900) fall.strands.splice(0, fall.strands.length - 900);
    if (!fall.running) {
      fall.running = true;
      fall.last = performance.now();
      requestAnimationFrame((time) => step(fall, time));
    }
  }

  function step(fall, time) {
    const dt = Math.min(0.05, (time - fall.last) / 1000);
    fall.last = time;
    const context = fall.canvas.getContext("2d");
    context.setTransform(fall.dpr, 0, 0, fall.dpr, 0, 0);
    context.clearRect(0, 0, fall.canvas.width, fall.canvas.height);
    context.lineCap = "round";
    context.lineWidth = 1.4;
    fall.strands = fall.strands.filter((s) => s.age < s.life && s.y < fall.height + 30);
    fall.strands.forEach((s) => {
      s.age += dt;
      s.vy += 1100 * dt;
      s.vx *= 0.985;
      s.x += s.vx * dt;
      s.y += s.vy * dt;
      s.angle += s.spin * dt;
      const fade = s.age > s.life - 0.4 ? Math.max(0, (s.life - s.age) / 0.4) : 1;
      const dx = Math.cos(s.angle) * s.length * 0.5;
      const dy = Math.sin(s.angle) * s.length * 0.5;
      const [r, g, b] = s.color;
      context.strokeStyle = `rgba(${r}, ${g}, ${b}, ${0.95 * fade})`;
      context.beginPath();
      context.moveTo(s.x - dx, s.y - dy);
      context.quadraticCurveTo(s.x - dy * s.bend * 0.12, s.y + dx * s.bend * 0.12, s.x + dx, s.y + dy);
      context.stroke();
    });
    if (fall.strands.length) {
      requestAnimationFrame((next) => step(fall, next));
    } else {
      fall.running = false;
      context.clearRect(0, 0, fall.canvas.width, fall.canvas.height);
    }
  }

  return { countNumbers, slide, hairFall, reduce };
})();
