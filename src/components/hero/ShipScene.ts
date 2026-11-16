import {
  ACESFilmicToneMapping,
  BoxGeometry,
  CanvasTexture,
  Color,
  CylinderGeometry,
  DirectionalLight,
  ExtrudeGeometry,
  Group,
  HemisphereLight,
  InstancedMesh,
  MathUtils,
  Mesh,
  MeshStandardMaterial,
  Object3D,
  PCFShadowMap,
  PerspectiveCamera,
  PlaneGeometry,
  RepeatWrapping,
  Scene,
  SRGBColorSpace,
  ShaderMaterial,
  Shape,
  Vector2,
  Vector3,
  WebGLRenderer,
  type BufferGeometry,
  type Material,
} from "three";

export type SeaTheme = "light" | "dark";

export interface ShipSceneOptions {
  canvas: HTMLCanvasElement;
  container: HTMLElement;
  theme: SeaTheme;
  reducedMotion: boolean;
  lowPower: boolean;
}

/* ------------------------------------------------------------------ */
/* Vessel dimensions (metres). Shared by geometry and the water shader */
/* so foam, wake and hull contact line up exactly.                     */
/* ------------------------------------------------------------------ */
const HALF_L = 96; // half length overall
const HALF_B = 15.5; // half beam
const BOW_LEN = 36; // length of bow taper
const STERN_R = 10; // stern rounding
const FREEBOARD = 8.5;
const SPEED = 11; // m/s — apparent speed of travel
const YAW = 0.5; // heading: bow points up/right on screen

function hullHalfWidth(u: number): number {
  const bowStart = HALF_L - BOW_LEN;
  if (u > bowStart) {
    const t = (u - bowStart) / BOW_LEN;
    return HALF_B * Math.sqrt(Math.max(1 - t * t, 0));
  }
  const sternStart = -HALF_L + STERN_R;
  if (u < sternStart) {
    const t = (sternStart - u) / STERN_R;
    return HALF_B * Math.sqrt(Math.max(1 - t * t * 0.55, 0));
  }
  return HALF_B;
}

interface Palette {
  deep: Color;
  mid: Color;
  sky: Color;
  sun: Color;
  foam: Color;
  aerated: Color;
  sunDir: Vector3;
  whitecap: number;
  spec: number;
  lightColor: Color;
  lightIntensity: number;
  hemiSky: Color;
  hemiGround: Color;
  hemiIntensity: number;
  exposure: number;
}

const PALETTES: Record<SeaTheme, Palette> = {
  dark: {
    deep: new Color("#02070b"),
    mid: new Color("#0a2130"),
    sky: new Color("#25303b"),
    sun: new Color("#e9b273"),
    foam: new Color("#d6dbdf"),
    aerated: new Color("#173a47"),
    sunDir: new Vector3(-0.5, 0.42, -0.76).normalize(),
    whitecap: 0.8,
    spec: 1.0,
    lightColor: new Color("#ffd6a1"),
    lightIntensity: 2.1,
    hemiSky: new Color("#8fa4bb"),
    hemiGround: new Color("#081018"),
    hemiIntensity: 0.55,
    exposure: 0.95,
  },
  light: {
    deep: new Color("#0b4c74"),
    mid: new Color("#1d87b6"),
    sky: new Color("#d3ecf8"),
    sun: new Color("#fff4e2"),
    foam: new Color("#ffffff"),
    aerated: new Color("#63c6dc"),
    sunDir: new Vector3(0.32, 0.86, -0.4).normalize(),
    whitecap: 0.65,
    spec: 0.18,
    lightColor: new Color("#fff3df"),
    lightIntensity: 2.8,
    hemiSky: new Color("#e2f3ff"),
    hemiGround: new Color("#2f6788"),
    hemiIntensity: 1.0,
    exposure: 1.0,
  },
};

/* ----------------------------- Shaders ----------------------------- */

const waterVertex = /* glsl */ `
  varying vec3 vWorld;
  void main() {
    vec4 w = modelMatrix * vec4(position, 1.0);
    vWorld = w.xyz;
    gl_Position = projectionMatrix * viewMatrix * w;
  }
`;

const waterFragment = /* glsl */ `
  uniform float uTime;
  uniform float uTravel;
  uniform vec2 uFwd;
  uniform vec3 uDeep;
  uniform vec3 uMid;
  uniform vec3 uSky;
  uniform vec3 uSun;
  uniform vec3 uFoam;
  uniform vec3 uAerated;
  uniform vec3 uSunDir;
  uniform vec3 uCamPos;
  uniform float uWhitecap;
  uniform float uSpec;
  uniform float uBob;
  varying vec3 vWorld;

  #define HALF_L ${HALF_L.toFixed(1)}
  #define HALF_B ${HALF_B.toFixed(1)}
  #define BOW_LEN ${BOW_LEN.toFixed(1)}
  #define STERN_R ${STERN_R.toFixed(1)}

  float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
  }
  float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
               mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
  }
  float fbm(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    mat2 m = mat2(1.6, 1.2, -1.2, 1.6);
    for (int i = 0; i < OCTAVES; i++) {
      v += a * noise(p);
      p = m * p;
      a *= 0.5;
    }
    return v;
  }

  // Directional swell + wind sea (deep-water dispersion).
  float swell(vec2 p) {
    float t = uTime;
    float h = 0.0;
    h += 0.95 * sin(dot(p, vec2(0.050, 0.022)) - t * 0.72);
    h += 0.60 * sin(dot(p, vec2(-0.030, 0.068)) - t * 0.83 + 1.3);
    h += 0.36 * sin(dot(p, vec2(0.105, -0.058)) - t * 1.11 + 2.1);
    h += 0.26 * sin(dot(p, vec2(0.074, 0.138)) - t * 1.24 + 4.0);
    h += 0.16 * sin(dot(p, vec2(-0.205, 0.094)) - t * 1.49);
    h += 0.11 * sin(dot(p, vec2(0.170, 0.250)) - t * 1.73 + 0.7);
    return h;
  }

  float hullHalf(float u) {
    float bowStart = HALF_L - BOW_LEN;
    if (u > bowStart) { float t = (u - bowStart) / BOW_LEN; return HALF_B * sqrt(max(1.0 - t * t, 0.0)); }
    float sternStart = -HALF_L + STERN_R;
    if (u < sternStart) { float t = (sternStart - u) / STERN_R; return HALF_B * sqrt(max(1.0 - t * t * 0.55, 0.0)); }
    return HALF_B;
  }

  // Kelvin wake waves: stationary relative to the vessel.
  float wakeHeight(vec2 w) {
    vec2 perp = vec2(-uFwd.y, uFwd.x);
    float u = dot(w, uFwd);
    float v = abs(dot(w, perp));
    float s = HALF_L - u;
    if (s < 0.0) return 0.0;
    float arm = 0.36 * s;
    float decay = exp(-s / 320.0);
    float inside = smoothstep(0.0, 10.0, arm - v) * smoothstep(10.0, 60.0, s);
    float transverse = sin(s * 0.21 + v * 0.03) * 0.55 * inside;
    float g = v - arm;
    float diverging = sin(g * 0.5 - s * 0.05) * 0.9 * exp(-g * g / 520.0);
    return (transverse + diverging) * decay;
  }

  float heightAt(vec2 world, vec2 waterP) {
    return swell(waterP) + wakeHeight(world) + (fbm(waterP * 0.09) - 0.5) * 0.9;
  }

  void main() {
    vec2 world = vWorld.xz;
    vec2 p = world + uFwd * uTravel; // water frame: sea streams past the hull

    // --- surface normal from analytic field + fine ripples
    float e = 0.8;
    float h0 = heightAt(world, p);
    float hx = heightAt(world + vec2(e, 0.0), p + vec2(e, 0.0));
    float hz = heightAt(world + vec2(0.0, e), p + vec2(0.0, e));
    vec3 N = normalize(vec3(-(hx - h0) / e * 1.6, 1.0, -(hz - h0) / e * 1.6));

    vec2 rp = p * 0.55 + vec2(uTime * 0.18, -uTime * 0.11);
    float r0 = fbm(rp);
    float rx = fbm(rp + vec2(0.12, 0.0));
    float rz = fbm(rp + vec2(0.0, 0.12));
    N = normalize(N + vec3(-(rx - r0) * 1.8, 0.0, -(rz - r0) * 1.8));

    // --- vessel-local coordinates
    vec2 perp = vec2(-uFwd.y, uFwd.x);
    float u = dot(world, uFwd);
    float v = dot(world, perp);
    float av = abs(v);
    float dHull = max(av - hullHalf(clamp(u, -HALF_L, HALF_L)), max(u - HALF_L, -HALF_L - u));
    float dOut = max(dHull, 0.0);

    // --- foam texture (advected with the water)
    float n1 = fbm(p * 0.16 + vec2(uTime * 0.04, 0.0));
    float n2 = fbm(p * 0.62 - vec2(0.0, uTime * 0.16));
    float lace = n1 * 0.55 + n2 * 0.45;

    // hull contact foam, heavier towards the bow
    float hullF = exp(-dOut / 2.4) * mix(0.55, 1.15, smoothstep(-HALF_L, HALF_L, u)) * (0.9 + uBob);
    // bow cushion
    float bowF = exp(-dOut / 6.5) * smoothstep(HALF_L - BOW_LEN * 1.2, HALF_L + 2.0, u) * 0.9;

    // Kelvin arms from the bow
    float s = HALF_L - u;
    float arm = 0.36 * s;
    float g = av - arm;
    float wArm = 2.2 + s * 0.03;
    float armF = exp(-g * g / (wArm * wArm)) * smoothstep(8.0, 40.0, s) * exp(-s / 380.0) * 0.85;

    // propeller wash / turbulent centreline wake
    float sw = -HALF_L - u;
    float W = HALF_B * 0.8 + max(sw, 0.0) * 0.075;
    float washF = (0.55 * exp(-max(sw, 0.0) / 260.0) + 0.75 * exp(-max(sw, 0.0) / 40.0))
                  * smoothstep(W, W * 0.2, av) * smoothstep(-6.0, 6.0, sw);
    float wakeEdge = exp(-pow(av - W, 2.0) / 14.0) * smoothstep(0.0, 20.0, sw) * exp(-max(sw, 0.0) / 200.0) * 0.6;

    float F = hullF + bowF + armF + washF + wakeEdge;
    float foam = smoothstep(1.02, 1.32, F + lace * 0.95);
    foam = max(foam, smoothstep(0.95, 1.35, F) * (0.6 + 0.4 * n2));

    // scattered whitecaps on crests
    float n3 = fbm(p * 0.42 + vec2(-uTime * 0.07, uTime * 0.05));
    float crest = smoothstep(1.9, 2.5, h0 + n2 * 0.9) * uWhitecap;
    foam = max(foam, crest * smoothstep(0.6, 0.78, n3) * smoothstep(0.35, 0.75, n2) * 0.7);
    float aer = clamp(washF * 1.1 + armF * 0.35 + hullF * 0.4, 0.0, 1.0);

    // --- shading
    vec3 V = normalize(uCamPos - vWorld);
    vec3 L = normalize(uSunDir);
    float NdV = max(dot(N, V), 0.0);
    float fres = 0.02 + 0.98 * pow(1.0 - NdV, 5.0);
    vec3 R = reflect(-V, N);
    float rl = max(dot(R, L), 0.0);
    float spec = pow(rl, 520.0) * 4.0 + pow(rl, 48.0) * 0.2;
    float diff = max(dot(N, L), 0.0);

    float sss = clamp(h0 * 0.22 + 0.5, 0.0, 1.0);
    vec3 water = mix(uDeep, uMid, sss * 0.55 + n1 * 0.3);
    water = mix(water, uAerated, aer * 0.6);
    vec3 sky = mix(uSky * 0.6, uSky, clamp(R.y, 0.0, 1.0));
    water = mix(water, sky, clamp(fres * 1.4, 0.0, 1.0));
    water *= 0.82 + 0.32 * diff;
    water += uSun * spec * uSpec * (1.0 - foam);
    water *= 1.0 - 0.32 * exp(-dOut / 7.0); // hull occlusion

    vec3 foamCol = uFoam * (0.72 + 0.38 * diff);
    vec3 col = mix(water, foamCol, clamp(foam, 0.0, 1.0));

    gl_FragColor = vec4(col, 1.0);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`;

/* --------------------------- Scene class --------------------------- */

export class ShipScene {
  private renderer: WebGLRenderer;
  private scene = new Scene();
  private camera = new PerspectiveCamera(32, 1, 10, 6000);
  private water: Mesh<PlaneGeometry, ShaderMaterial>;
  private ship = new Group();
  private shipBody = new Group();
  private sun = new DirectionalLight();
  private hemi = new HemisphereLight();
  private palette: Palette;
  private targetPalette: Palette;
  private paletteMix = 1;
  private fromPalette: Palette;
  private disposables: Array<BufferGeometry | Material | CanvasTexture> = [];
  private raf = 0;
  private running = false;
  private visible = true;
  private time = 0;
  private travel = 0;
  private last = 0;
  private resizeObs: ResizeObserver;
  private interObs: IntersectionObserver;
  private opts: ShipSceneOptions;
  private fwd = new Vector2(Math.cos(YAW), -Math.sin(YAW));

  constructor(opts: ShipSceneOptions) {
    this.opts = opts;
    this.palette = clonePalette(PALETTES[opts.theme]);
    this.fromPalette = clonePalette(this.palette);
    this.targetPalette = PALETTES[opts.theme];

    this.renderer = new WebGLRenderer({
      canvas: opts.canvas,
      antialias: !opts.lowPower,
      alpha: false,
      powerPreference: opts.lowPower ? "low-power" : "high-performance",
    });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, opts.lowPower ? 1 : 1.6));
    this.renderer.toneMapping = ACESFilmicToneMapping;
    this.renderer.outputColorSpace = SRGBColorSpace;
    this.renderer.shadowMap.enabled = !opts.lowPower;
    this.renderer.shadowMap.type = PCFShadowMap;

    this.water = this.buildWater();
    this.scene.add(this.water);
    this.buildShip();
    this.scene.add(this.ship);

    this.sun.castShadow = !opts.lowPower;
    if (this.sun.castShadow) {
      this.sun.shadow.mapSize.set(2048, 2048);
      const c = this.sun.shadow.camera;
      c.left = -120;
      c.right = 120;
      c.top = 120;
      c.bottom = -120;
      c.near = 1;
      c.far = 800;
      this.sun.shadow.bias = -0.0006;
      this.sun.shadow.normalBias = 0.4;
    }
    this.scene.add(this.sun, this.sun.target, this.hemi);
    this.applyPalette();

    this.resizeObs = new ResizeObserver(() => this.resize());
    this.resizeObs.observe(opts.container);
    this.interObs = new IntersectionObserver(([entry]) => {
      this.visible = entry.isIntersecting;
      this.updateLoop();
    });
    this.interObs.observe(opts.container);
    document.addEventListener("visibilitychange", this.onVisibility);

    this.resize();
    this.renderFrame();
    this.updateLoop();
  }

  setTheme(theme: SeaTheme) {
    this.fromPalette = clonePalette(this.palette);
    this.targetPalette = PALETTES[theme];
    this.paletteMix = this.opts.reducedMotion ? 1 : 0;
    if (this.opts.reducedMotion) {
      this.palette = clonePalette(this.targetPalette);
      this.applyPalette();
      this.renderFrame();
    } else if (!this.running) {
      this.paletteMix = 1;
      this.palette = clonePalette(this.targetPalette);
      this.applyPalette();
      this.renderFrame();
    }
  }

  setReducedMotion(reduced: boolean) {
    this.opts.reducedMotion = reduced;
    this.updateLoop();
    this.renderFrame();
  }

  dispose() {
    this.running = false;
    cancelAnimationFrame(this.raf);
    this.resizeObs.disconnect();
    this.interObs.disconnect();
    document.removeEventListener("visibilitychange", this.onVisibility);
    this.disposables.forEach((d) => d.dispose());
    this.scene.traverse((o) => {
      if (o instanceof InstancedMesh) o.dispose();
    });
    this.renderer.dispose();
  }

  /* ------------------------------ loop ------------------------------ */

  private onVisibility = () => this.updateLoop();

  private updateLoop() {
    const shouldRun = this.visible && !document.hidden && !this.opts.reducedMotion;
    if (shouldRun && !this.running) {
      this.running = true;
      this.last = performance.now();
      this.raf = requestAnimationFrame(this.tick);
    } else if (!shouldRun && this.running) {
      this.running = false;
      cancelAnimationFrame(this.raf);
    }
  }

  private tick = (now: number) => {
    if (!this.running) return;
    this.raf = requestAnimationFrame(this.tick);
    const minFrame = this.opts.lowPower ? 1000 / 31 : 0;
    const elapsed = now - this.last;
    if (elapsed < minFrame) return;
    const dt = Math.min(elapsed / 1000, 1 / 20);
    this.last = now;
    this.time += dt;
    this.travel += dt * SPEED;

    if (this.paletteMix < 1) {
      this.paletteMix = Math.min(1, this.paletteMix + dt / 0.9);
      lerpPalette(this.palette, this.fromPalette, this.targetPalette, easeInOut(this.paletteMix));
      this.applyPalette();
    }
    this.renderFrame();
  };

  private renderFrame() {
    const t = this.time;
    // gentle heave, roll and pitch
    this.shipBody.position.y = Math.sin(t * 0.55) * 0.28 + Math.sin(t * 1.3) * 0.06;
    this.shipBody.rotation.x = Math.sin(t * 0.42) * 0.009;
    this.shipBody.rotation.z = Math.sin(t * 0.31 + 1.1) * 0.0045;

    const u = this.water.material.uniforms;
    u.uTime.value = t;
    u.uTravel.value = this.travel;
    u.uBob.value = Math.sin(t * 0.55) * 0.12;
    u.uCamPos.value.copy(this.camera.position);
    this.renderer.render(this.scene, this.camera);
  }

  private resize() {
    const { clientWidth: w, clientHeight: h } = this.opts.container;
    if (!w || !h) return;
    this.renderer.setSize(w, h, false);
    const aspect = w / h;
    this.camera.aspect = aspect;

    // Frame the vessel: centre-right on wide screens, lower-centre on portrait.
    const tanHalf = Math.tan(MathUtils.degToRad(this.camera.fov / 2));
    const shipSpan = 2 * HALF_L * Math.cos(YAW) + 2 * HALF_B;
    const wide = aspect >= 1.05;
    const share = wide ? MathUtils.clamp(0.36 + (aspect - 1) * 0.08, 0.4, 0.52) : 0.88;
    const viewWidth = shipSpan / share;
    const dist = viewWidth / (2 * tanHalf * aspect);
    const viewHeight = 2 * dist * tanHalf;
    const target = new Vector3(
      wide ? -viewWidth * 0.16 : 0,
      0,
      wide ? viewHeight * 0.02 : -viewHeight * 0.3
    );
    const tilt = 0.34;
    this.camera.position.set(target.x, dist * Math.cos(tilt), target.z + dist * Math.sin(tilt));
    this.camera.lookAt(target);
    this.camera.updateProjectionMatrix();
    this.renderFrame();
  }

  private applyPalette() {
    const p = this.palette;
    const u = this.water.material.uniforms;
    u.uDeep.value.copy(p.deep);
    u.uMid.value.copy(p.mid);
    u.uSky.value.copy(p.sky);
    u.uSun.value.copy(p.sun);
    u.uFoam.value.copy(p.foam);
    u.uAerated.value.copy(p.aerated);
    u.uSunDir.value.copy(p.sunDir);
    u.uWhitecap.value = p.whitecap;
    u.uSpec.value = p.spec;
    this.sun.color.copy(p.lightColor);
    this.sun.intensity = p.lightIntensity;
    this.sun.position.copy(p.sunDir).multiplyScalar(400);
    this.hemi.color.copy(p.hemiSky);
    this.hemi.groundColor.copy(p.hemiGround);
    this.hemi.intensity = p.hemiIntensity;
    this.renderer.toneMappingExposure = p.exposure;
  }

  /* ---------------------------- builders ---------------------------- */

  private track<T extends BufferGeometry | Material | CanvasTexture>(item: T): T {
    this.disposables.push(item);
    return item;
  }

  private buildWater() {
    const geo = this.track(new PlaneGeometry(6000, 6000, 1, 1));
    geo.rotateX(-Math.PI / 2);
    const mat = this.track(
      new ShaderMaterial({
        vertexShader: waterVertex,
        fragmentShader: waterFragment,
        defines: { OCTAVES: this.opts.lowPower ? 3 : 5 },
        uniforms: {
          uTime: { value: 0 },
          uTravel: { value: 0 },
          uBob: { value: 0 },
          uFwd: { value: this.fwd.clone() },
          uDeep: { value: new Color() },
          uMid: { value: new Color() },
          uSky: { value: new Color() },
          uSun: { value: new Color() },
          uFoam: { value: new Color() },
          uAerated: { value: new Color() },
          uSunDir: { value: new Vector3() },
          uCamPos: { value: new Vector3() },
          uWhitecap: { value: 1 },
          uSpec: { value: 1 },
        },
      })
    );
    return new Mesh(geo, mat);
  }

  private buildShip() {
    const shadows = !this.opts.lowPower;
    this.ship.rotation.y = YAW;
    this.ship.add(this.shipBody);

    // Hull outline (u along length, v across beam)
    const outline = (scaleB: number, insetU: number) => {
      const shape = new Shape();
      const steps = 64;
      const pts: Array<[number, number]> = [];
      for (let i = 0; i <= steps; i++) {
        const u = -HALF_L + insetU + ((2 * HALF_L - 2 * insetU) * i) / steps;
        pts.push([u, hullHalfWidth(u) * scaleB]);
      }
      shape.moveTo(pts[0][0], -pts[0][1]);
      pts.forEach(([u, w]) => shape.lineTo(u, w));
      for (let i = pts.length - 1; i >= 0; i--) shape.lineTo(pts[i][0], -pts[i][1]);
      return shape;
    };
    const addExtrude = (shape: Shape, depth: number, y: number, color: string, rough = 0.7) => {
      const g = this.track(new ExtrudeGeometry(shape, { depth, bevelEnabled: false, curveSegments: 4 }));
      g.rotateX(-Math.PI / 2);
      const m = this.track(new MeshStandardMaterial({ color, roughness: rough, metalness: 0.15 }));
      const mesh = new Mesh(g, m);
      mesh.position.y = y;
      mesh.receiveShadow = shadows;
      mesh.castShadow = shadows;
      this.shipBody.add(mesh);
      return mesh;
    };

    addExtrude(outline(1.0, 0), 1.6, -0.4, "#6e2219", 0.8); // boot-top band
    addExtrude(outline(0.995, 0.2), FREEBOARD - 1.2, 1.2, "#1e2731", 0.5); // topsides
    addExtrude(outline(0.94, 1.6), 0.5, FREEBOARD, "#4c5650", 0.9); // deck

    const standard = (color: string, rough = 0.6, metal = 0.2) =>
      this.track(new MeshStandardMaterial({ color, roughness: rough, metalness: metal }));
    const box = (w: number, h: number, d: number) => this.track(new BoxGeometry(w, h, d));
    const place = (geo: BufferGeometry, mat: Material, x: number, y: number, z: number) => {
      const mesh = new Mesh(geo, mat);
      mesh.position.set(x, y, z);
      mesh.castShadow = shadows;
      mesh.receiveShadow = shadows;
      this.shipBody.add(mesh);
      return mesh;
    };

    // Containers (40 ft, instanced)
    const cLen = 12.19;
    const cW = 2.44;
    const cH = 2.59;
    const slots: Array<{ x: number; z: number; tiers: number; bay: number }> = [];
    let u = -HALF_L + 33;
    let bay = 0;
    const hatchMat = standard("#2d3438", 0.85, 0.1);
    while (u + cLen < HALF_L - 22) {
      const uc = u + cLen / 2;
      const halfAvail = Math.min(hullHalfWidth(u), hullHalfWidth(u + cLen)) * 0.9;
      const rows = Math.max(0, Math.floor((halfAvail * 2) / (cW + 0.1)));
      const midness = 1 - Math.abs(uc - 5) / HALF_L;
      for (let r = 0; r < rows; r++) {
        const z = (r - (rows - 1) / 2) * (cW + 0.1);
        const base = 2 + Math.round(midness * 3);
        const tiers = Math.max(1, base - (Math.random() < 0.25 ? 1 : 0) - (Math.random() < 0.08 ? 2 : 0));
        if (Math.random() < 0.04) continue;
        slots.push({ x: uc, z, tiers, bay });
      }
      // hatch cover under each bay
      place(box(cLen + 0.6, 0.6, halfAvail * 2 + 0.6), hatchMat, uc, FREEBOARD + 0.55, 0);
      u += cLen + (bay % 2 === 1 ? 2.6 : 0.9);
      bay++;
    }

    const palette = ["#8a2e24", "#a3472a", "#1d4b69", "#2c6a70", "#6c777d", "#c6c0b0", "#3a5838", "#ad7029", "#4a3a58", "#73201f", "#24384f", "#9a9a92"];
    const total = slots.reduce((a, s) => a + s.tiers, 0);
    const tex = this.track(makeCorrugationTexture());
    const cGeo = box(cLen, cH, cW);
    const cMat = standard("#ffffff", 0.72, 0.25);
    cMat.map = tex;
    const containers = new InstancedMesh(cGeo, cMat, total);
    containers.castShadow = shadows;
    containers.receiveShadow = shadows;
    const dummy = new Object3D();
    const col = new Color();
    let i = 0;
    for (const s of slots) {
      for (let t = 0; t < s.tiers; t++) {
        dummy.position.set(s.x, FREEBOARD + 0.85 + cH / 2 + t * (cH + 0.02), s.z);
        dummy.updateMatrix();
        containers.setMatrixAt(i, dummy.matrix);
        // bays loaded in clusters per carrier for a believable stow plan
        const pick = Math.random() < 0.55 ? (s.bay * 3 + Math.floor(s.z / 6) + 12) % palette.length : Math.floor(Math.random() * palette.length);
        col.set(palette[pick]).multiplyScalar(0.85 + Math.random() * 0.25);
        containers.setColorAt(i, col);
        i++;
      }
    }
    containers.instanceMatrix.needsUpdate = true;
    if (containers.instanceColor) containers.instanceColor.needsUpdate = true;
    this.shipBody.add(containers);

    // Accommodation block & bridge near the stern
    const white = standard("#e7e4dc", 0.55, 0.1);
    const whiteShade = standard("#cfcbc1", 0.6, 0.1);
    const dark = standard("#1a1f24", 0.4, 0.4);
    const ax = -HALF_L + 22;
    place(box(14, 7, 24), whiteShade, ax, FREEBOARD + 3.5, 0);
    place(box(12, 7, 22), white, ax + 0.5, FREEBOARD + 10.5, 0);
    place(box(10, 6, 19), white, ax + 1, FREEBOARD + 17, 0);
    place(box(7.5, 2.4, 2 * HALF_B + 1), white, ax + 2.5, FREEBOARD + 21.2, 0); // bridge + wings
    place(box(0.6, 1.4, 2 * HALF_B + 1.05), dark, ax + 6.3, FREEBOARD + 21.2, 0); // window band
    place(box(5, 0.6, 7), standard("#9aa1a6", 0.6, 0.3), ax + 1, FREEBOARD + 22.7, 0); // monkey island
    place(this.track(new CylinderGeometry(0.25, 0.25, 7, 6)), dark, ax + 1, FREEBOARD + 26, 0); // mast
    // funnel
    place(box(7, 11, 6.5), standard("#262b30", 0.5, 0.3), ax - 10, FREEBOARD + 7, 0);
    place(box(7.1, 1.6, 6.6), standard("#b8452b", 0.6, 0.2), ax - 10, FREEBOARD + 11.4, 0);
    place(box(5.4, 0.4, 4.6), standard("#0c0e10", 0.9, 0), ax - 10, FREEBOARD + 12.55, 0);
    // lifeboats
    const boat = standard("#e2681c", 0.5, 0.1);
    place(box(8, 2.2, 3), boat, ax - 1, FREEBOARD + 9, HALF_B - 3);
    place(box(8, 2.2, 3), boat, ax - 1, FREEBOARD + 9, -(HALF_B - 3));
    // forecastle, breakwater and mooring gear
    const fx = HALF_L - 10;
    place(box(14, 1.2, hullHalfWidth(fx) * 1.5), standard("#4a524c", 0.9, 0.1), fx - 2, FREEBOARD + 0.9, 0);
    place(box(1, 3.2, hullHalfWidth(HALF_L - 19) * 1.8), standard("#d9d5cc", 0.6, 0.1), HALF_L - 19.5, FREEBOARD + 1.6, 0); // breakwater
    for (const side of [-1, 1]) {
      place(this.track(new CylinderGeometry(0.9, 0.9, 1.4, 10)), dark, fx - 3, FREEBOARD + 1.9, side * 4.5);
      place(this.track(new CylinderGeometry(0.6, 0.6, 1.2, 10)), standard("#c1442c"), fx + 3, FREEBOARD + 1.8, side * 2.6);
    }
    place(this.track(new CylinderGeometry(0.3, 0.3, 9, 6)), standard("#d9d5cc"), HALF_L - 6, FREEBOARD + 4.5, 0);
    // stern mooring deck
    place(box(8, 0.8, 2 * hullHalfWidth(-HALF_L + 4) * 0.85), standard("#4a524c", 0.9, 0.1), -HALF_L + 5, FREEBOARD + 0.6, 0);
  }
}

/* ----------------------------- helpers ----------------------------- */

function makeCorrugationTexture() {
  const c = document.createElement("canvas");
  c.width = 128;
  c.height = 8;
  const ctx = c.getContext("2d")!;
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, 128, 8);
  for (let x = 0; x < 128; x += 4) {
    ctx.fillStyle = "rgba(0,0,0,0.18)";
    ctx.fillRect(x, 0, 1.4, 8);
    ctx.fillStyle = "rgba(255,255,255,0.35)";
    ctx.fillRect(x + 2, 0, 0.8, 8);
  }
  ctx.fillStyle = "rgba(0,0,0,0.25)";
  ctx.fillRect(0, 0, 3, 8);
  ctx.fillRect(125, 0, 3, 8);
  const t = new CanvasTexture(c);
  t.wrapS = RepeatWrapping;
  t.colorSpace = SRGBColorSpace;
  return t;
}

function clonePalette(p: Palette): Palette {
  return {
    ...p,
    deep: p.deep.clone(),
    mid: p.mid.clone(),
    sky: p.sky.clone(),
    sun: p.sun.clone(),
    foam: p.foam.clone(),
    aerated: p.aerated.clone(),
    sunDir: p.sunDir.clone(),
    lightColor: p.lightColor.clone(),
    hemiSky: p.hemiSky.clone(),
    hemiGround: p.hemiGround.clone(),
  };
}

function lerpPalette(out: Palette, a: Palette, b: Palette, t: number) {
  out.deep.lerpColors(a.deep, b.deep, t);
  out.mid.lerpColors(a.mid, b.mid, t);
  out.sky.lerpColors(a.sky, b.sky, t);
  out.sun.lerpColors(a.sun, b.sun, t);
  out.foam.lerpColors(a.foam, b.foam, t);
  out.aerated.lerpColors(a.aerated, b.aerated, t);
  out.sunDir.lerpVectors(a.sunDir, b.sunDir, t).normalize();
  out.lightColor.lerpColors(a.lightColor, b.lightColor, t);
  out.hemiSky.lerpColors(a.hemiSky, b.hemiSky, t);
  out.hemiGround.lerpColors(a.hemiGround, b.hemiGround, t);
  out.whitecap = MathUtils.lerp(a.whitecap, b.whitecap, t);
  out.spec = MathUtils.lerp(a.spec, b.spec, t);
  out.lightIntensity = MathUtils.lerp(a.lightIntensity, b.lightIntensity, t);
  out.hemiIntensity = MathUtils.lerp(a.hemiIntensity, b.hemiIntensity, t);
  out.exposure = MathUtils.lerp(a.exposure, b.exposure, t);
}

function easeInOut(t: number) {
  return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
}
