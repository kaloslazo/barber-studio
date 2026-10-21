(() => {
  const LAB_API = "/api";
  const MODEL_FLOATS = 17;
  const SIDE_A = 234;
  const SIDE_B = 454;

  class AvatarViewer extends SplatViewer {
    setModel(model) {
      this.tris = new Int32Array(model.triangles);
      this.model = new Float32Array(Uint8Array.from(atob(model.gaussians), (c) => c.charCodeAt(0)).buffer);
      this.n = this.model.length / MODEL_FLOATS;
      this.instances32 = new Float32Array(this.n * SPLAT_FLOATS);
      this.triFrames = new Float32Array((this.tris.length / 3) * 9);
      this.data = this.instances32;
      this.count = this.n;
      this.sorted = new Float32Array(this.instances32.length);
      this.depthKeys = new Uint32Array(this.n);
      this.order = new Uint32Array(this.n);
      this.updateMesh(model.mesh);
    }

    updateMesh(mesh) {
      const tris = this.tris;
      const F = this.triFrames;
      for (let t = 0; t < tris.length / 3; t++) {
        const a = tris[3 * t] * 3, b = tris[3 * t + 1] * 3, c = tris[3 * t + 2] * 3;
        let ux = mesh[b] - mesh[a], uy = mesh[b + 1] - mesh[a + 1], uz = mesh[b + 2] - mesh[a + 2];
        const vx = mesh[c] - mesh[a], vy = mesh[c + 1] - mesh[a + 1], vz = mesh[c + 2] - mesh[a + 2];
        let nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
        const ul = Math.hypot(ux, uy, uz) || 1, nl = Math.hypot(nx, ny, nz) || 1;
        ux /= ul; uy /= ul; uz /= ul; nx /= nl; ny /= nl; nz /= nl;
        const ex = ny * uz - nz * uy, ey = nz * ux - nx * uz, ez = nx * uy - ny * ux;
        const o = 9 * t;
        F[o] = ux; F[o + 1] = ex; F[o + 2] = nx;
        F[o + 3] = uy; F[o + 4] = ey; F[o + 5] = ny;
        F[o + 6] = uz; F[o + 7] = ez; F[o + 8] = nz;
      }
      const s = Math.hypot(
        mesh[SIDE_A * 3] - mesh[SIDE_B * 3], mesh[SIDE_A * 3 + 1] - mesh[SIDE_B * 3 + 1], mesh[SIDE_A * 3 + 2] - mesh[SIDE_B * 3 + 2],
      );
      const s2 = s * s;
      const M = this.model;
      const out = this.instances32;
      for (let i = 0; i < this.n; i++) {
        const g = i * MODEL_FLOATS;
        const t = M[g];
        const ia = tris[3 * t] * 3, ib = tris[3 * t + 1] * 3, ic = tris[3 * t + 2] * 3;
        const w0 = M[g + 1], w1 = M[g + 2], w2 = M[g + 3];
        const ox = M[g + 4], oy = M[g + 5], oz = M[g + 6];
        const r = 9 * t;
        const R00 = F[r], R01 = F[r + 1], R02 = F[r + 2];
        const R10 = F[r + 3], R11 = F[r + 4], R12 = F[r + 5];
        const R20 = F[r + 6], R21 = F[r + 7], R22 = F[r + 8];
        const o = i * SPLAT_FLOATS;
        out[o] = w0 * mesh[ia] + w1 * mesh[ib] + w2 * mesh[ic] + (R00 * ox + R01 * oy + R02 * oz) * s;
        out[o + 1] = w0 * mesh[ia + 1] + w1 * mesh[ib + 1] + w2 * mesh[ic + 1] + (R10 * ox + R11 * oy + R12 * oz) * s;
        out[o + 2] = w0 * mesh[ia + 2] + w1 * mesh[ib + 2] + w2 * mesh[ic + 2] + (R20 * ox + R21 * oy + R22 * oz) * s;
        const cxx = M[g + 7], cxy = M[g + 8], cxz = M[g + 9], cyy = M[g + 10], cyz = M[g + 11], czz = M[g + 12];
        const m00 = R00 * cxx + R01 * cxy + R02 * cxz, m01 = R00 * cxy + R01 * cyy + R02 * cyz, m02 = R00 * cxz + R01 * cyz + R02 * czz;
        const m10 = R10 * cxx + R11 * cxy + R12 * cxz, m11 = R10 * cxy + R11 * cyy + R12 * cyz, m12 = R10 * cxz + R11 * cyz + R12 * czz;
        const m20 = R20 * cxx + R21 * cxy + R22 * cxz, m21 = R20 * cxy + R21 * cyy + R22 * cyz, m22 = R20 * cxz + R21 * cyz + R22 * czz;
        out[o + 3] = (m00 * R00 + m01 * R01 + m02 * R02) * s2;
        out[o + 4] = (m00 * R10 + m01 * R11 + m02 * R12) * s2;
        out[o + 5] = (m00 * R20 + m01 * R21 + m02 * R22) * s2;
        out[o + 6] = (m10 * R10 + m11 * R11 + m12 * R12) * s2;
        out[o + 7] = (m10 * R20 + m11 * R21 + m12 * R22) * s2;
        out[o + 8] = (m20 * R20 + m21 * R21 + m22 * R22) * s2;
        out[o + 9] = M[g + 13];
        out[o + 10] = M[g + 14];
        out[o + 11] = M[g + 15];
        out[o + 12] = M[g + 16];
      }
      this.lastSortKey = "";
      this.dirty = true;
    }
  }

  const cameraBtn = document.getElementById("lab-camera");
  const scanBtn = document.getElementById("lab-scan");
  const filesInput = document.getElementById("lab-files");
  const buildBtn = document.getElementById("lab-build");
  const liveBtn = document.getElementById("lab-live");
  const errorBanner = document.getElementById("lab-error");
  const video = document.getElementById("lab-video");
  const prompt = document.getElementById("lab-prompt");
  const framesText = document.getElementById("lab-frames");
  const metricsTable = document.getElementById("lab-metrics");
  const canvas = document.getElementById("lab-canvas");
  const stats = document.getElementById("lab-stats");
  const capture = document.getElementById("lab-capture");
  let stream = null;
  let frames = [];
  let beard = "none";
  let viewer = null;
  let live = false;
  let busy = false;
  let liveCount = 0;
  let liveClock = performance.now();

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  function showError(message) {
    errorBanner.textContent = message;
    errorBanner.hidden = false;
  }

  function grab(width, quality) {
    const w = Math.min(width, video.videoWidth);
    capture.width = w;
    capture.height = Math.round(video.videoHeight * (w / video.videoWidth));
    const ctx = capture.getContext("2d");
    ctx.save();
    ctx.translate(capture.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0, capture.width, capture.height);
    ctx.restore();
    return new Promise((resolve) => capture.toBlob(resolve, "image/jpeg", quality));
  }

  document.querySelectorAll("[data-lab-beard]").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll("[data-lab-beard]").forEach((b) => b.classList.remove("active"));
      button.classList.add("active");
      beard = button.dataset.labBeard;
    });
  });

  document.querySelectorAll("[data-lab-view]").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll("[data-lab-view]").forEach((b) => b.classList.remove("active"));
      button.classList.add("active");
      if (viewer) viewer.setView(parseFloat(button.dataset.labView), 0.05, 1.9);
    });
  });

  cameraBtn.addEventListener("click", async () => {
    errorBanner.hidden = true;
    if (stream) {
      live = false;
      stream.getTracks().forEach((track) => track.stop());
      stream = null;
      cameraBtn.textContent = "Start camera";
      scanBtn.disabled = true;
      liveBtn.textContent = "Live avatar";
      return;
    }
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, facingMode: "user" }, audio: false });
      video.srcObject = stream;
      await video.play();
      cameraBtn.textContent = "Stop camera";
      scanBtn.disabled = false;
      liveBtn.disabled = !viewer;
    } catch (error) {
      showError(`Camera unavailable: ${error.message}`);
    }
  });

  scanBtn.addEventListener("click", async () => {
    if (!stream) return;
    scanBtn.disabled = true;
    frames = [];
    const plan = [
      ["Look straight at the camera", 2],
      ["Slowly turn your head LEFT", 3],
      ["Slowly turn your head RIGHT", 3],
    ];
    prompt.hidden = false;
    for (const [text, shots] of plan) {
      prompt.textContent = text;
      for (let k = 0; k < shots; k++) {
        await sleep(780);
        frames.push(await grab(1024, 0.92));
        framesText.textContent = `${frames.length} views captured`;
      }
    }
    prompt.textContent = "Done!";
    await sleep(600);
    prompt.hidden = true;
    scanBtn.disabled = false;
    buildBtn.disabled = false;
  });

  filesInput.addEventListener("change", () => {
    frames = Array.from(filesInput.files).slice(0, 16);
    framesText.textContent = `${frames.length} photos selected`;
    buildBtn.disabled = frames.length === 0;
  });

  function showMetrics(metrics) {
    const body = metricsTable.querySelector("tbody");
    body.innerHTML = "";
    const held = metrics.held_out_psnr || {};
    [["Single view color", "single_view"], ["Multi-view fusion", "fused"], ["Fusion + optimization", "optimized"]].forEach(([label, key]) => {
      const row = document.createElement("tr");
      row.innerHTML = `<td>${label}</td><td>${metrics.train_psnr[key]}</td><td>${held[key] ?? "—"}</td>`;
      body.appendChild(row);
    });
    metricsTable.hidden = false;
  }

  buildBtn.addEventListener("click", async () => {
    if (frames.length === 0) return;
    errorBanner.hidden = true;
    buildBtn.disabled = true;
    buildBtn.classList.add("loading");
    buildBtn.textContent = "Building (~15 s)...";
    const started = performance.now();
    try {
      const formData = new FormData();
      frames.forEach((blob, i) => formData.append("frames", blob, `view_${i}.jpg`));
      formData.append("beard", beard);
      const response = await fetch(`${LAB_API}/lab/build`, { method: "POST", body: formData });
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || `Request failed: ${response.status}`);
      }
      const model = await response.json();
      if (!viewer) {
        viewer = new AvatarViewer(canvas);
        window.labViewer = viewer;
      }
      viewer.setModel(model);
      viewer.setView(0, 0.05, 1.9);
      showMetrics(model.metrics);
      const seconds = ((performance.now() - started) / 1000).toFixed(1);
      stats.textContent = `${model.count.toLocaleString()} anchored Gaussians (${model.beard.toLocaleString()} beard) · ${model.metrics.views} views · built in ${seconds}s`;
      liveBtn.disabled = !stream;
    } catch (error) {
      showError(error.message);
    } finally {
      buildBtn.disabled = false;
      buildBtn.classList.remove("loading");
      buildBtn.textContent = "Build head";
    }
  });

  async function liveLoop() {
    if (!live || !stream || !viewer) return;
    if (!busy) {
      busy = true;
      try {
        const formData = new FormData();
        formData.append("image", await grab(480, 0.8), "frame.jpg");
        const response = await fetch(`${LAB_API}/lab/mesh`, { method: "POST", body: formData });
        if (response.ok) {
          const data = await response.json();
          if (data.mesh) {
            viewer.updateMesh(data.mesh);
            liveCount++;
          }
        }
        const now = performance.now();
        if (now - liveClock > 1000) {
          stats.textContent = `Live avatar · ${((liveCount * 1000) / (now - liveClock)).toFixed(1)} fps · ${viewer.count.toLocaleString()} Gaussians`;
          liveCount = 0;
          liveClock = now;
        }
      } catch (error) {
        showError(error.message);
      } finally {
        busy = false;
      }
    }
    setTimeout(liveLoop, 0);
  }

  liveBtn.addEventListener("click", () => {
    if (!viewer || !stream) return;
    live = !live;
    liveBtn.textContent = live ? "Stop avatar" : "Live avatar";
    if (live) liveLoop();
  });
})();
