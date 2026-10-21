const SPLAT_FLOATS = 13;

const SPLAT_VS = `#version 300 es
precision highp float;
layout(location = 0) in vec2 a_corner;
layout(location = 1) in vec3 a_center;
layout(location = 2) in vec3 a_covA;
layout(location = 3) in vec3 a_covB;
layout(location = 4) in vec4 a_color;
uniform mat4 u_view;
uniform mat4 u_proj;
uniform vec2 u_focal;
uniform vec2 u_viewport;
uniform float u_splatScale;
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
  v_color = a_color;
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
    this.splatScale = 1;
    this.count = 0;
    this.dirty = true;
    this.lastSortKey = "";
    this.frames = 0;
    this.fps = 0;
    this.fpsClock = performance.now();
    this.program = this.compile();
    this.setupBuffers();
    this.bindControls();
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
    ["u_view", "u_proj", "u_focal", "u_viewport", "u_splatScale"].forEach((name) => {
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
    const index = gl.createBuffer();
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, index);
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array([0, 1, 2, 0, 2, 3]), gl.STATIC_DRAW);
    gl.bindVertexArray(null);
  }

  bindControls() {
    let dragging = false;
    let lastX = 0;
    let lastY = 0;
    this.canvas.addEventListener("pointerdown", (event) => {
      dragging = true;
      lastX = event.clientX;
      lastY = event.clientY;
      this.canvas.setPointerCapture(event.pointerId);
    });
    this.canvas.addEventListener("pointermove", (event) => {
      if (!dragging) return;
      this.yaw += (event.clientX - lastX) * 0.008;
      this.pitch = Math.max(-1.2, Math.min(1.2, this.pitch + (event.clientY - lastY) * 0.008));
      lastX = event.clientX;
      lastY = event.clientY;
      this.dirty = true;
    });
    ["pointerup", "pointercancel"].forEach((type) => this.canvas.addEventListener(type, () => (dragging = false)));
    this.canvas.addEventListener("wheel", (event) => {
      event.preventDefault();
      this.distance = Math.max(0.8, Math.min(6, this.distance * (1 + event.deltaY * 0.001)));
      this.dirty = true;
    }, { passive: false });
  }

  load(buffer) {
    this.data = new Float32Array(buffer);
    this.count = Math.floor(this.data.length / SPLAT_FLOATS);
    this.sorted = new Float32Array(this.data.length);
    this.depthKeys = new Uint32Array(this.count);
    this.order = new Uint32Array(this.count);
    this.lastSortKey = "";
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

  sort(view) {
    const n = this.count;
    const data = this.data;
    const keys = this.depthKeys;
    let min = Infinity;
    let max = -Infinity;
    const depths = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const o = i * SPLAT_FLOATS;
      const d = view[2] * data[o] + view[6] * data[o + 1] + view[10] * data[o + 2];
      depths[i] = d;
      if (d < min) min = d;
      if (d > max) max = d;
    }
    const buckets = 65536;
    const scale = (buckets - 1) / Math.max(max - min, 1e-6);
    const counts = new Uint32Array(buckets);
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
    gl.bufferData(gl.ARRAY_BUFFER, out, gl.DYNAMIC_DRAW);
  }

  loop(time) {
    if (this.autoRotate) {
      this.yaw = Math.sin(time / 2200) * 0.75;
      this.dirty = true;
    }
    if (this.dirty && this.count > 0) {
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
    const fovy = (35 * Math.PI) / 180;
    const view = orbitView(this.yaw, this.pitch, this.distance);
    const key = `${this.yaw.toFixed(3)}:${this.pitch.toFixed(3)}:${this.count}`;
    if (key !== this.lastSortKey) {
      this.sort(view);
      this.lastSortKey = key;
    }
    gl.viewport(0, 0, width, height);
    gl.clearColor(0.97, 0.965, 0.955, 1);
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
    gl.uniform1f(this.uniforms.u_splatScale, this.splatScale);
    gl.bindVertexArray(this.vao);
    gl.drawElementsInstanced(gl.TRIANGLES, 6, gl.UNSIGNED_SHORT, 0, this.count);
    gl.bindVertexArray(null);
  }
}

window.SplatViewer = SplatViewer;
