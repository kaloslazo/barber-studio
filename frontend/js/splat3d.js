const SPLAT_FLOATS = 13;
const SPLAT_FOVY = (35 * Math.PI) / 180;
const SPLAT_TURNTABLE_SPEED = 0.5;
const SPLAT_NORMAL_CELL = 0.04;
const SPLAT_NORMAL_PASSES = 2;
const SPLAT_SORT_STEP = 0.012;

const SPLAT_VS = `#version 300 es
precision highp float;
layout(location = 0) in vec2 a_corner;
layout(location = 1) in vec3 a_center;
layout(location = 2) in vec3 a_covA;
layout(location = 3) in vec3 a_covB;
layout(location = 4) in vec4 a_color;
layout(location = 5) in vec3 a_normal;
layout(location = 6) in vec3 a_tangent;
uniform mat4 u_view;
uniform mat4 u_proj;
uniform vec2 u_focal;
uniform vec2 u_viewport;
uniform float u_splatScale;
uniform float u_lit;
uniform vec3 u_key;
uniform vec3 u_fill;
out vec4 v_color;
out vec2 v_pos;

void main() {
  vec4 cam = u_view * vec4(a_center, 1.0);
  if (cam.z > -0.05) {
    gl_Position = vec4(0.0, 0.0, 2.0, 1.0);
    return;
  }
  vec4 clip = u_proj * cam;
  mat3 sigma = mat3(a_covA.x, a_covA.y, a_covA.z,
                    a_covA.y, a_covB.x, a_covB.y,
                    a_covA.z, a_covB.y, a_covB.z);
  float z = cam.z;
  mat3 J = mat3(u_focal.x / -z, 0.0, 0.0,
                0.0, u_focal.y / -z, 0.0,
                u_focal.x * cam.x / (z * z), u_focal.y * cam.y / (z * z), 0.0);
  mat3 W = mat3(u_view);
  mat3 T = J * W;
  mat3 cov = T * sigma * transpose(T);
  float a = cov[0][0] + 0.3;
  float b = cov[0][1];
  float c = cov[1][1] + 0.3;
  float mid = 0.5 * (a + c);
  float radius = length(vec2(0.5 * (a - c), b));
  float l1 = mid + radius;
  float l2 = max(mid - radius, 0.1);
  vec2 v1 = abs(b) < 1e-6 ? (a >= c ? vec2(1.0, 0.0) : vec2(0.0, 1.0)) : normalize(vec2(b, l1 - a));
  vec2 v2 = vec2(-v1.y, v1.x);
  vec2 offset = (a_corner.x * v1 * min(sqrt(l1), 512.0) + a_corner.y * v2 * min(sqrt(l2), 512.0)) * u_splatScale;
  vec2 ndc = clip.xy / clip.w + offset / u_viewport * 2.0;
  gl_Position = vec4(ndc, clip.z / clip.w, 1.0);
  v_pos = a_corner;
  vec3 rgb = a_color.rgb;
  if (u_lit > 0.5) {
    vec3 n = normalize(a_normal);
    vec3 t = normalize(a_tangent);
    vec3 eye = normalize(-(transpose(mat3(u_view)) * u_view[3].xyz) - a_center);
    float key = clamp((dot(n, u_key) + 0.35) / 1.35, 0.0, 1.0);
    float fill = clamp((dot(n, u_fill) + 0.35) / 1.35, 0.0, 1.0);
    float tl = dot(t, u_key);
    float te = dot(t, eye);
    float kk = max(tl * te + sqrt(max(1.0 - tl * tl, 0.0)) * sqrt(max(1.0 - te * te, 0.0)), 0.0);
    float spec = pow(kk, 110.0) * smoothstep(0.0, 0.3, key);
    rgb = rgb * (0.38 + 0.78 * key + 0.22 * fill) + vec3(0.10 * spec);
  }
  v_color = vec4(rgb, a_color.a);
}`;

const SPLAT_FS = `#version 300 es
precision highp float;
in vec4 v_color;
in vec2 v_pos;
out vec4 fragColor;

void main() {
  float r2 = dot(v_pos, v_pos);
  if (r2 > 9.0) discard;
  float alpha = v_color.a * exp(-0.5 * r2);
  if (alpha < 0.004) discard;
  fragColor = vec4(v_color.rgb, alpha);
}`;

function unit(x, y, z) {
  const l = Math.hypot(x, y, z);
  return [x / l, y / l, z / l];
}

const SPLAT_KEY = unit(0.45, 0.65, 0.75);
const SPLAT_FILL = unit(-0.6, 0.15, -0.5);

function eigenFrame(m, out) {
  const v = [1, 0, 0, 0, 1, 0, 0, 0, 1];
  const a = [m[0], m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8]];
  for (let sweep = 0; sweep < 6; sweep++) {
    for (const [p, q] of [[0, 1], [0, 2], [1, 2]]) {
      const apq = a[p * 3 + q];
      if (Math.abs(apq) < 1e-12) continue;
      const theta = (a[q * 3 + q] - a[p * 3 + p]) / (2 * apq);
      const t = Math.sign(theta || 1) / (Math.abs(theta) + Math.sqrt(theta * theta + 1));
      const c = 1 / Math.sqrt(t * t + 1);
      const s = t * c;
      for (let k = 0; k < 3; k++) {
        const akp = a[k * 3 + p], akq = a[k * 3 + q];
        a[k * 3 + p] = c * akp - s * akq;
        a[k * 3 + q] = s * akp + c * akq;
      }
      for (let k = 0; k < 3; k++) {
        const apk = a[p * 3 + k], aqk = a[q * 3 + k];
        a[p * 3 + k] = c * apk - s * aqk;
        a[q * 3 + k] = s * apk + c * aqk;
      }
      for (let k = 0; k < 3; k++) {
        const vkp = v[k * 3 + p], vkq = v[k * 3 + q];
        v[k * 3 + p] = c * vkp - s * vkq;
        v[k * 3 + q] = s * vkp + c * vkq;
      }
    }
  }
  let lo = 0, hi = 0;
  for (let k = 1; k < 3; k++) {
    if (a[k * 4] < a[lo * 4]) lo = k;
    if (a[k * 4] > a[hi * 4]) hi = k;
  }
  out[0] = v[lo]; out[1] = v[3 + lo]; out[2] = v[6 + lo];
  out[6] = v[hi]; out[7] = v[3 + hi]; out[8] = v[6 + hi];
}

function smoothNormals(data, frames, count) {
  const cell = SPLAT_NORMAL_CELL;
  let minX = Infinity, minY = Infinity, minZ = Infinity, maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
  for (let i = 0; i < count; i++) {
    const o = i * SPLAT_FLOATS;
    minX = Math.min(minX, data[o]); maxX = Math.max(maxX, data[o]);
    minY = Math.min(minY, data[o + 1]); maxY = Math.max(maxY, data[o + 1]);
    minZ = Math.min(minZ, data[o + 2]); maxZ = Math.max(maxZ, data[o + 2]);
  }
  const nx = Math.floor((maxX - minX) / cell) + 4;
  const ny = Math.floor((maxY - minY) / cell) + 4;
  const nz = Math.floor((maxZ - minZ) / cell) + 4;
  const at = (x, y, z) => ((z * ny + y) * nx + x) * 3;
  let grid = new Float32Array(nx * ny * nz * 3);
  const corners = [[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0], [0, 0, 1], [1, 0, 1], [0, 1, 1], [1, 1, 1]];
  const place = (x, y, z) => {
    const gx = (x - minX) / cell + 1, gy = (y - minY) / cell + 1, gz = (z - minZ) / cell + 1;
    const x0 = Math.floor(gx), y0 = Math.floor(gy), z0 = Math.floor(gz);
    return [x0, y0, z0, gx - x0, gy - y0, gz - z0];
  };
  for (let i = 0; i < count; i++) {
    const o = i * SPLAT_FLOATS;
    const [x0, y0, z0, fx, fy, fz] = place(data[o], data[o + 1], data[o + 2]);
    for (const [dx, dy, dz] of corners) {
      const w = (dx ? fx : 1 - fx) * (dy ? fy : 1 - fy) * (dz ? fz : 1 - fz);
      const k = at(x0 + dx, y0 + dy, z0 + dz);
      grid[k] += w * frames[i * 6];
      grid[k + 1] += w * frames[i * 6 + 1];
      grid[k + 2] += w * frames[i * 6 + 2];
    }
  }
  for (let pass = 0; pass < SPLAT_NORMAL_PASSES; pass++) {
    for (let axis = 0; axis < 3; axis++) {
      const out = new Float32Array(grid.length);
      const step = axis === 0 ? 3 : axis === 1 ? nx * 3 : nx * ny * 3;
      for (let z = 1; z < nz - 1; z++) {
        for (let y = 1; y < ny - 1; y++) {
          for (let x = 1; x < nx - 1; x++) {
            const k = at(x, y, z);
            for (let c = 0; c < 3; c++) out[k + c] = (grid[k + c - step] + 2 * grid[k + c] + grid[k + c + step]) / 4;
          }
        }
      }
      grid = out;
    }
  }
  const smooth = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    const o = i * SPLAT_FLOATS;
    const [x0, y0, z0, fx, fy, fz] = place(data[o], data[o + 1], data[o + 2]);
    let sx = 0, sy = 0, sz = 0;
    for (const [dx, dy, dz] of corners) {
      const w = (dx ? fx : 1 - fx) * (dy ? fy : 1 - fy) * (dz ? fz : 1 - fz);
      const k = at(x0 + dx, y0 + dy, z0 + dz);
      sx += w * grid[k]; sy += w * grid[k + 1]; sz += w * grid[k + 2];
    }
    const length = Math.hypot(sx, sy, sz);
    if (length > 1e-4) {
      smooth[i * 3] = sx / length; smooth[i * 3 + 1] = sy / length; smooth[i * 3 + 2] = sz / length;
    } else {
      smooth[i * 3] = frames[i * 6]; smooth[i * 3 + 1] = frames[i * 6 + 1]; smooth[i * 3 + 2] = frames[i * 6 + 2];
    }
  }
  for (let i = 0; i < count; i++) {
    frames[i * 6] = smooth[i * 3]; frames[i * 6 + 1] = smooth[i * 3 + 1]; frames[i * 6 + 2] = smooth[i * 3 + 2];
  }
}

function perspective(fovy, aspect, near, far) {
  const f = 1 / Math.tan(fovy / 2);
  const nf = 1 / (near - far);
  return new Float32Array([f / aspect, 0, 0, 0, 0, f, 0, 0, 0, 0, (far + near) * nf, -1, 0, 0, 2 * far * near * nf, 0]);
}

function orbitView(yaw, pitch, distance) {
  const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
  const r = [cy, 0, -sy, sy * sp, cp, cy * sp, sy * cp, -sp, cy * cp];
  return new Float32Array([r[0], r[3], r[6], 0, r[1], r[4], r[7], 0, r[2], r[5], r[8], 0, 0, 0, -distance, 1]);
}

function splatFrames(data, n) {
  const frames = new Float32Array(n * 6);
  if (!n) return frames;
  let cx = 0, cy = 0, cz = 0;
  for (let i = 0; i < n; i++) {
    cx += data[i * SPLAT_FLOATS];
    cy += data[i * SPLAT_FLOATS + 1];
    cz += data[i * SPLAT_FLOATS + 2];
  }
  cx /= n; cy /= n; cz /= n;
  const m = new Float64Array(9);
  const v = new Float64Array(9);
  for (let i = 0; i < n; i++) {
    const o = i * SPLAT_FLOATS;
    m[0] = data[o + 3]; m[1] = m[3] = data[o + 4]; m[2] = m[6] = data[o + 5];
    m[4] = data[o + 6]; m[5] = m[7] = data[o + 7]; m[8] = data[o + 8];
    eigenFrame(m, v);
    let nx = v[0], ny = v[1], nz = v[2];
    if (nx * (data[o] - cx) + ny * (data[o + 1] - cy) + nz * (data[o + 2] - cz) < 0) {
      nx = -nx; ny = -ny; nz = -nz;
    }
    frames[i * 6] = nx; frames[i * 6 + 1] = ny; frames[i * 6 + 2] = nz;
    frames[i * 6 + 3] = v[6]; frames[i * 6 + 4] = v[7]; frames[i * 6 + 5] = v[8];
  }
  smoothNormals(data, frames, n);
  return frames;
}

function easeOutBack(t) {
  const c1 = 1.4;
  return 1 + (c1 + 1) * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
}

class SplatViewer {
  constructor(canvas) {
    this.canvas = canvas;
    const gl = canvas.getContext("webgl2", { antialias: false, premultipliedAlpha: false, preserveDrawingBuffer: true });
    if (!gl) throw new Error("WebGL2 is not available in this browser");
    this.gl = gl;
    this.yaw = 0;
    this.pitch = 0;
    this.distance = 1.9;
    this.autoRotate = false;
    this.turntable = false;
    this.dragging = false;
    this.onManual = null;
    this.lastTime = 0;
    this.splatScale = 1;
    this.lighting = false;
    this.tool = null;
    this.count = 0;
    this.dirty = true;
    this.lastSortKey = "";
    this.frames = 0;
    this.fps = 0;
    this.fpsClock = performance.now();
    this.revealStart = 0;
    this.revealT = 1;
    this.instanceBytes = 0;
    this.frameBytes = 0;
    this.buckets = new Uint32Array(65536);
    this.program = this.compile();
    this.setupBuffers();
    this.bindControls();
    canvas.addEventListener("webglcontextlost", (event) => {
      event.preventDefault();
      this.lost = true;
    });
    canvas.addEventListener("webglcontextrestored", () => {
      this.lost = false;
      this.program = this.compile();
      this.setupBuffers();
      this.instanceBytes = 0;
      this.frameBytes = 0;
      if (this.data) this.computeFrames();
      this.lastSortKey = "";
      this.dirty = true;
    });
    requestAnimationFrame((t) => this.loop(t));
  }

  compile() {
    const gl = this.gl;
    const shader = (type, source) => {
      const s = gl.createShader(type);
      gl.shaderSource(s, source);
      gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
      return s;
    };
    const program = gl.createProgram();
    gl.attachShader(program, shader(gl.VERTEX_SHADER, SPLAT_VS));
    gl.attachShader(program, shader(gl.FRAGMENT_SHADER, SPLAT_FS));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program));
    this.uniforms = {};
    ["u_view", "u_proj", "u_focal", "u_viewport", "u_splatScale", "u_lit", "u_key", "u_fill"].forEach((name) => {
      this.uniforms[name] = gl.getUniformLocation(program, name);
    });
    return program;
  }

  setupBuffers() {
    const gl = this.gl;
    this.vao = gl.createVertexArray();
    gl.bindVertexArray(this.vao);
    const quad = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, quad);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-3, -3, 3, -3, 3, 3, -3, 3]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    this.instances = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, this.instances);
    const stride = SPLAT_FLOATS * 4;
    [[1, 3, 0], [2, 3, 3], [3, 3, 6], [4, 4, 9]].forEach(([loc, size, offset]) => {
      gl.enableVertexAttribArray(loc);
      gl.vertexAttribPointer(loc, size, gl.FLOAT, false, stride, offset * 4);
      gl.vertexAttribDivisor(loc, 1);
    });
    this.frameBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, this.frameBuffer);
    [[5, 0], [6, 3]].forEach(([loc, offset]) => {
      gl.vertexAttribPointer(loc, 3, gl.FLOAT, false, 24, offset * 4);
      gl.vertexAttribDivisor(loc, 1);
    });
    const index = gl.createBuffer();
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, index);
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array([0, 1, 2, 0, 2, 3]), gl.STATIC_DRAW);
    gl.bindVertexArray(null);
  }

  bindControls() {
    let dragging = false;
    let tooling = false;
    let lastX = 0;
    let lastY = 0;
    this.canvas.addEventListener("pointerdown", (event) => {
      this.canvas.setPointerCapture(event.pointerId);
      if (this.tool && !event.shiftKey) {
        tooling = true;
        this.tool.down(event);
        return;
      }
      dragging = true;
      this.dragging = true;
      if (this.onManual) this.onManual();
      lastX = event.clientX;
      lastY = event.clientY;
    });
    this.canvas.addEventListener("pointermove", (event) => {
      if (this.tool) this.tool.hover(event);
      if (tooling) {
        this.tool.move(event);
        return;
      }
      if (!dragging) return;
      this.yaw += (event.clientX - lastX) * 0.008;
      this.pitch = Math.max(-1.2, Math.min(1.2, this.pitch + (event.clientY - lastY) * 0.008));
      lastX = event.clientX;
      lastY = event.clientY;
      this.dirty = true;
    });
    ["pointerup", "pointercancel"].forEach((type) => this.canvas.addEventListener(type, () => {
      if (tooling && this.tool) this.tool.up();
      dragging = false;
      this.dragging = false;
      tooling = false;
    }));
    this.canvas.addEventListener("pointerleave", () => {
      if (this.tool) this.tool.leave();
    });
    this.canvas.addEventListener("wheel", (event) => {
      event.preventDefault();
      this.distance = Math.max(0.8, Math.min(6, this.distance * (1 + event.deltaY * 0.001)));
      this.dirty = true;
    }, { passive: false });
  }

  load(buffer, frames = null) {
    this.data = new Float32Array(buffer);
    this.count = Math.floor(this.data.length / SPLAT_FLOATS);
    this.givenFrames = frames;
    if (!this.sorted || this.sorted.length !== this.data.length) this.sorted = new Float32Array(this.data.length);
    if (!this.order || this.order.length !== this.count) {
      this.depthKeys = new Uint32Array(this.count);
      this.order = new Uint32Array(this.count);
      this.depths = new Float32Array(this.count);
    }
    this.lastSortKey = "";
    this.dirty = true;
    this.computeFrames();
  }

  setLighting(on) {
    this.lighting = on;
    this.computeFrames();
    this.lastSortKey = "";
    this.dirty = true;
  }

  computeFrames() {
    const gl = this.gl;
    gl.bindVertexArray(this.vao);
    [5, 6].forEach((loc) => (this.lighting && this.count ? gl.enableVertexAttribArray(loc) : gl.disableVertexAttribArray(loc)));
    gl.bindVertexArray(null);
    if (!this.lighting || !this.count) return;
    const given = this.givenFrames && this.givenFrames.length === this.count * 6;
    this.surfaceFrames = given ? this.givenFrames : splatFrames(this.data, this.count);
    if (!this.surfaceSorted || this.surfaceSorted.length !== this.surfaceFrames.length) this.surfaceSorted = new Float32Array(this.surfaceFrames.length);
  }

  reveal(duration = 1100) {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    this.revealStart = performance.now();
    this.revealDuration = duration;
    this.revealT = 0;
    this.dirty = true;
  }

  setSplatScale(scale) {
    this.splatScale = scale;
    this.dirty = true;
  }

  setView(yaw, pitch, distance) {
    this.yaw = yaw;
    this.pitch = pitch;
    if (distance) this.distance = distance;
    this.dirty = true;
  }

  screenPoints(limit) {
    const n = Math.min(limit, this.count);
    const data = this.data;
    const width = this.canvas.clientWidth;
    const height = this.canvas.clientHeight;
    const f = 1 / Math.tan(SPLAT_FOVY / 2);
    const view = orbitView(this.yaw, this.pitch, this.distance);
    const out = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      const o = i * SPLAT_FLOATS;
      const x = data[o], y = data[o + 1], z = data[o + 2];
      const cx = view[0] * x + view[4] * y + view[8] * z + view[12];
      const cy = view[1] * x + view[5] * y + view[9] * z + view[13];
      const depth = -(view[2] * x + view[6] * y + view[10] * z + view[14]);
      out[i * 3] = (1 + (f * height / width) * cx / depth) * 0.5 * width;
      out[i * 3 + 1] = (1 - f * cy / depth) * 0.5 * height;
      out[i * 3 + 2] = depth;
    }
    return out;
  }

  sort(view) {
    const n = this.count;
    const data = this.data;
    const keys = this.depthKeys;
    let min = Infinity;
    let max = -Infinity;
    if (!this.depths || this.depths.length !== n) this.depths = new Float32Array(n);
    const depths = this.depths;
    for (let i = 0; i < n; i++) {
      const o = i * SPLAT_FLOATS;
      const d = view[2] * data[o] + view[6] * data[o + 1] + view[10] * data[o + 2];
      depths[i] = d;
      if (d < min) min = d;
      if (d > max) max = d;
    }
    const buckets = 65536;
    const scale = (buckets - 1) / Math.max(max - min, 1e-6);
    const counts = this.buckets;
    counts.fill(0);
    for (let i = 0; i < n; i++) {
      keys[i] = ((depths[i] - min) * scale) | 0;
      counts[keys[i]]++;
    }
    for (let i = 1; i < buckets; i++) counts[i] += counts[i - 1];
    for (let i = n - 1; i >= 0; i--) this.order[--counts[keys[i]]] = i;
    const out = this.sorted;
    for (let k = 0; k < n; k++) {
      const src = this.order[k] * SPLAT_FLOATS;
      out.set(data.subarray(src, src + SPLAT_FLOATS), k * SPLAT_FLOATS);
    }
    const gl = this.gl;
    gl.bindBuffer(gl.ARRAY_BUFFER, this.instances);
    if (out.byteLength !== this.instanceBytes) {
      gl.bufferData(gl.ARRAY_BUFFER, out, gl.DYNAMIC_DRAW);
      this.instanceBytes = out.byteLength;
    } else {
      gl.bufferSubData(gl.ARRAY_BUFFER, 0, out);
    }
    if (this.lighting && this.surfaceFrames) {
      const frames = this.surfaceFrames;
      const sorted = this.surfaceSorted;
      for (let k = 0; k < n; k++) {
        const src = this.order[k] * 6;
        const dst = k * 6;
        sorted[dst] = frames[src]; sorted[dst + 1] = frames[src + 1]; sorted[dst + 2] = frames[src + 2];
        sorted[dst + 3] = frames[src + 3]; sorted[dst + 4] = frames[src + 4]; sorted[dst + 5] = frames[src + 5];
      }
      gl.bindBuffer(gl.ARRAY_BUFFER, this.frameBuffer);
      if (sorted.byteLength !== this.frameBytes) {
        gl.bufferData(gl.ARRAY_BUFFER, sorted, gl.DYNAMIC_DRAW);
        this.frameBytes = sorted.byteLength;
      } else {
        gl.bufferSubData(gl.ARRAY_BUFFER, 0, sorted);
      }
    }
  }

  loop(time) {
    if (this.autoRotate) {
      if (this.turntable) {
        if (!this.dragging) this.yaw += Math.min(0.1, Math.max(0, (time - this.lastTime) / 1000)) * SPLAT_TURNTABLE_SPEED;
      } else {
        this.yaw = Math.sin(time / 2200) * 0.75;
      }
      this.dirty = true;
    }
    this.lastTime = time;
    if (this.revealStart) {
      this.revealT = Math.min(1, Math.max(0, (time - this.revealStart) / this.revealDuration));
      if (this.revealT >= 1) this.revealStart = 0;
      this.dirty = true;
    }
    if (this.dirty && this.count > 0 && !this.lost) {
      this.draw();
      this.dirty = false;
    }
    this.frames++;
    if (time - this.fpsClock > 1000) {
      this.fps = (this.frames * 1000) / (time - this.fpsClock);
      this.frames = 0;
      this.fpsClock = time;
    }
    requestAnimationFrame((t) => this.loop(t));
  }

  draw() {
    const gl = this.gl;
    const canvas = this.canvas;
    const dpr = window.devicePixelRatio || 1;
    const width = Math.round(canvas.clientWidth * dpr);
    const height = Math.round(canvas.clientHeight * dpr);
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }
    const fovy = SPLAT_FOVY;
    const t = this.revealT;
    const yaw = this.yaw - (1 - (1 - Math.pow(1 - t, 3))) * 1.1;
    const view = orbitView(yaw, this.pitch, this.distance);
    const key = `${Math.round(yaw / SPLAT_SORT_STEP)}:${Math.round(this.pitch / SPLAT_SORT_STEP)}:${this.count}`;
    if (key !== this.lastSortKey) {
      this.sort(view);
      this.lastSortKey = key;
    }
    gl.viewport(0, 0, width, height);
    gl.clearColor(0.98, 0.98, 0.973, 1);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.disable(gl.DEPTH_TEST);
    gl.enable(gl.BLEND);
    gl.blendFuncSeparate(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA, gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    gl.useProgram(this.program);
    const focal = height / (2 * Math.tan(fovy / 2));
    gl.uniformMatrix4fv(this.uniforms.u_view, false, view);
    gl.uniformMatrix4fv(this.uniforms.u_proj, false, perspective(fovy, width / height, 0.05, 50));
    gl.uniform2f(this.uniforms.u_focal, focal, focal);
    gl.uniform2f(this.uniforms.u_viewport, width, height);
    gl.uniform1f(this.uniforms.u_splatScale, this.splatScale * Math.max(0.001, easeOutBack(t)));
    gl.uniform1f(this.uniforms.u_lit, this.lighting && this.surfaceFrames ? 1 : 0);
    gl.uniform3f(this.uniforms.u_key, ...SPLAT_KEY);
    gl.uniform3f(this.uniforms.u_fill, ...SPLAT_FILL);
    gl.bindVertexArray(this.vao);
    gl.drawElementsInstanced(gl.TRIANGLES, 6, gl.UNSIGNED_SHORT, 0, this.count);
    gl.bindVertexArray(null);
  }
}

window.SplatViewer = SplatViewer;
window.splatFrames = splatFrames;
