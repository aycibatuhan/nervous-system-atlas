import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { GTAOPass } from 'three/addons/postprocessing/GTAOPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { SMAAPass } from 'three/addons/postprocessing/SMAAPass.js';

export type Quality = 'low' | 'high';

/** World frame = MNI RAS millimetres; +Z is superior, +Y anterior, +X right (subject's right). */
export class SceneManager {
  readonly renderer: THREE.WebGLRenderer;
  readonly scene = new THREE.Scene();
  readonly camera: THREE.PerspectiveCamera;
  readonly controls: OrbitControls;
  readonly meshRoot = new THREE.Group();
  readonly sliceRoot = new THREE.Group();
  readonly overlayRoot = new THREE.Group();
  private dirty = true;
  private raf = 0;
  private readonly keyLight: THREE.DirectionalLight;
  readonly onBeforeRender = new Set<() => void>();
  /** called when the output path changes (screen vs. linear composer); slice shaders use it to pick their encoding */
  readonly onOutputModeChange = new Set<(linear: boolean) => void>();
  /** called when the camera starts / stops moving; the picker uses it to drop hover work during a drag */
  readonly onInteractionChange = new Set<(active: boolean) => void>();
  private composer: EffectComposer | null = null;
  private gtao: GTAOPass | null = null;
  private smaa: SMAAPass | null = null;
  private quality: Quality = 'low';
  /** set while peeling: the AO g-buffer ignores clipping planes, so AO is skipped then */
  aoSuppressed = false;
  /** frames drawn since boot; the e2e interaction test reads it to prove the loop idles */
  renders = 0;

  // ---- interaction budget
  /** ms of stillness after the last camera movement before the full-quality frame is drawn */
  static readonly SETTLE_MS = 120;
  /** ms a flick may coast after the pointer is released before the damping tail is cut off */
  static readonly COAST_MS = 320;
  /** decay per 1/60 s applied to the orbit/pan delta; scaled by the real frame time each frame */
  static readonly DAMPING = 0.2;
  /** share of the outstanding wheel delta spent per 1/60 s (~150 ms to drain) */
  static readonly WHEEL_EASE = 0.28;
  /** wheel deltas below this (px) are trackpad-sized and pass straight through */
  static readonly WHEEL_STEP_PX = 20;
  private interacting = false;
  private pointers = 0;
  private lastMotion = 0;
  private coastStart = 0;
  private lastFrameAt = performance.now();
  private basePixelRatio = 1;
  private wheelAccum = 0;
  private wheelAt = { x: 0, y: 0 };
  private wheelSynthetic = false;

  constructor(readonly canvas: HTMLCanvasElement) {
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, powerPreference: 'high-performance', preserveDrawingBuffer: true });
    this.basePixelRatio = Math.min(window.devicePixelRatio, 2);
    this.renderer.setPixelRatio(this.basePixelRatio);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 0.85;
    this.renderer.localClippingEnabled = true;
    this.renderer.shadowMap.enabled = false;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.scene.background = new THREE.Color(0x14161a);
    this.camera = new THREE.PerspectiveCamera(35, 1, 1, 3000);
    this.camera.up.set(0, 0, 1);
    this.camera.position.set(-420, 0, 20);
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.target.set(0, -18, 10);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = SceneManager.DAMPING;
    this.controls.minDistance = 30;
    this.controls.maxDistance = 1500;
    this.controls.zoomToCursor = true;
    this.controls.rotateSpeed = 1;
    this.controls.panSpeed = 1;
    this.controls.screenSpacePanning = true;
    this.controls.mouseButtons = { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.PAN };
    this.controls.touches = { ONE: THREE.TOUCH.ROTATE, TWO: THREE.TOUCH.DOLLY_PAN };
    // keep keyboard shortcuts working after the user interacts with the 3D view, and keep a drag alive
    // once the cursor leaves the canvas (pointer capture; OrbitControls' own listeners sit on the document)
    canvas.addEventListener('pointerdown', (e) => {
      canvas.focus({ preventScroll: true });
      this.pointers++;
      try { canvas.setPointerCapture(e.pointerId); } catch { /* synthetic events have no capture */ }
    });
    const release = (): void => { this.pointers = Math.max(0, this.pointers - 1); this.coastStart = performance.now(); };
    canvas.addEventListener('pointerup', release);
    canvas.addEventListener('pointercancel', release);
    // a drag interrupted by a tab switch never delivers pointerup: do not get stuck in cheap frames
    window.addEventListener('blur', () => { if (this.pointers) { this.pointers = 0; this.coastStart = performance.now(); } });
    // only real camera movement enters interaction mode — a plain click must not drop a frame of quality
    this.controls.addEventListener('change', () => { this.beginInteraction(); this.requestRender(); });
    this.controls.addEventListener('end', () => { this.coastStart = performance.now(); });
    this.bindWheel();

    // ---- lighting: image-based ambient + hemisphere + camera-parented key (shadow) / fill / rim
    const pmrem = new THREE.PMREMGenerator(this.renderer);
    this.scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    this.scene.environmentIntensity = 0.35;
    pmrem.dispose();
    this.scene.add(new THREE.HemisphereLight(0xfff3e8, 0x3c414a, 0.35));
    this.keyLight = new THREE.DirectionalLight(0xfff5ea, 1.25);
    this.keyLight.position.set(150, 220, 280);
    this.keyLight.castShadow = false;
    this.keyLight.shadow.mapSize.set(2048, 2048);
    this.keyLight.shadow.bias = -0.0004;
    this.keyLight.shadow.normalBias = 0.6;
    this.keyLight.shadow.radius = 4;
    const sc = this.keyLight.shadow.camera; sc.left = -190; sc.right = 190; sc.top = 190; sc.bottom = -190; sc.near = 1; sc.far = 2500;
    const fill = new THREE.DirectionalLight(0xdfe8ff, 0.4); fill.position.set(-320, -90, 40);
    const rim = new THREE.DirectionalLight(0xffffff, 0.6); rim.position.set(-80, 160, -900);
    this.camera.add(this.keyLight, fill, rim);
    this.scene.add(this.camera);
    this.scene.add(this.meshRoot, this.sliceRoot, this.overlayRoot);
    this.meshRoot.name = 'meshes'; this.sliceRoot.name = 'slices'; this.overlayRoot.name = 'overlay';
    new ResizeObserver(() => this.resize()).observe(canvas.parentElement ?? canvas);
    this.resize();
    this.loop();
  }

  getQuality(): Quality { return this.quality; }

  /** True while the camera is moving (drag, wheel, tween) — cheap frames, no hover picking. */
  isInteracting(): boolean { return this.interacting; }

  /** high = ambient occlusion + soft key-light shadow + SMAA through a linear composer; low = direct MSAA render. */
  setQuality(q: Quality): void {
    if (q === this.quality) return;
    this.quality = q;
    if (q === 'high') {
      const size = this.renderer.getDrawingBufferSize(new THREE.Vector2());
      this.composer = new EffectComposer(this.renderer);
      this.composer.setPixelRatio(this.basePixelRatio);
      this.composer.addPass(new RenderPass(this.scene, this.camera));
      this.gtao = new GTAOPass(this.scene, this.camera, size.x, size.y);
      this.gtao.output = GTAOPass.OUTPUT.Default;
      this.gtao.blendIntensity = 0.9;
      // world units are millimetres: radius/thickness must be brain-sized (the defaults assume metres)
      this.gtao.updateGtaoMaterial({ radius: 16, distanceExponent: 1, thickness: 10, scale: 1.1, samples: 16, distanceFallOff: 1, screenSpaceRadius: false });
      this.gtao.updatePdMaterial({ lumaPhi: 10, depthPhi: 2, normalPhi: 3, radius: 4, radiusExponent: 1, rings: 2, samples: 12 });
      // translucent surfaces (envelope, CSF, dimmed parcels) must not write the AO g-buffer
      const g = this.gtao as unknown as { _overrideVisibility(): void; _visibilityCache: THREE.Object3D[] };
      const orig = g._overrideVisibility.bind(this.gtao);
      g._overrideVisibility = () => {
        orig();
        this.scene.traverse((o) => {
          const m = (o as THREE.Mesh).material as THREE.Material | undefined;
          if (o.visible && m && m.transparent && m.opacity < 0.999) { o.visible = false; g._visibilityCache.push(o); }
        });
      };
      this.composer.addPass(this.gtao);
      this.composer.addPass(new OutputPass());
      this.smaa = new SMAAPass();
      this.smaa.enabled = !this.interacting;
      this.composer.addPass(this.smaa);
      this.renderer.shadowMap.enabled = true;
      this.renderer.shadowMap.autoUpdate = !this.interacting;
      this.keyLight.castShadow = true;
      for (const fn of this.onOutputModeChange) fn(true);
    } else {
      this.composer?.dispose(); this.composer = null; this.gtao = null; this.smaa = null;
      this.renderer.shadowMap.enabled = false;
      this.renderer.shadowMap.autoUpdate = true;
      this.keyLight.castShadow = false;
      for (const fn of this.onOutputModeChange) fn(false);
    }
    this.scene.traverse((o) => { const m = (o as THREE.Mesh).material as THREE.Material | undefined; if (m) m.needsUpdate = true; });
    this.resize();
    this.applyBudget(this.interacting);
    // compile both composer variants now: with GTAO/SMAA off the OutputPass renders straight to the
    // screen, a different program. Without this the first drag after switching to 'high' stalls ~250 ms.
    if (this.composer && this.gtao && this.smaa) {
      const smaa = this.smaa.enabled;
      this.gtao.enabled = false; this.smaa.enabled = false;
      this.composer.render();
      this.gtao.enabled = !this.aoSuppressed; this.smaa.enabled = smaa;
      this.composer.render();
    }
  }

  resize(): void {
    const el = this.canvas.parentElement ?? this.canvas;
    const w = Math.max(1, el.clientWidth); const h = Math.max(1, el.clientHeight);
    this.renderer.setSize(w, h, false);
    this.composer?.setSize(w, h);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.requestRender();
  }

  requestRender(): void { this.dirty = true; }

  // ---- interaction mode -------------------------------------------------

  private beginInteraction(): void {
    this.lastMotion = performance.now();
    if (this.interacting) return;
    this.interacting = true;
    this.applyBudget(true);
    for (const fn of this.onInteractionChange) fn(true);
  }

  private endInteraction(): void {
    if (!this.interacting) return;
    this.interacting = false;
    this.applyBudget(false);
    for (const fn of this.onInteractionChange) fn(false);
    this.dirty = true;
  }

  /**
   * Cheap frames while the camera moves. In 'high' the composer stays in the loop and only the
   * costly passes (GTAO, SMAA) and the shadow-map update are switched off — swapping to a direct
   * render would change the output colour space and recompile every material (~1.4 s for 600 meshes).
   * In 'low' there is no composer, so the saving comes from a <=1x pixel ratio on HiDPI screens.
   */
  private applyBudget(on: boolean): void {
    const pr = on && this.quality === 'low' ? Math.min(this.basePixelRatio, 1) : this.basePixelRatio;
    if (this.renderer.getPixelRatio() !== pr) {
      this.renderer.setPixelRatio(pr);
      const el = this.canvas.parentElement ?? this.canvas;
      this.renderer.setSize(Math.max(1, el.clientWidth), Math.max(1, el.clientHeight), false);
    }
    if (this.quality === 'high') {
      if (this.smaa) this.smaa.enabled = !on;          // GTAO is switched per frame in render()
      this.renderer.shadowMap.autoUpdate = !on;
      if (!on) this.renderer.shadowMap.needsUpdate = true;
    }
  }

  /**
   * Wheel zoom is eased: a notch is spent over ~150 ms instead of jumping in one frame.
   * Intercepted on the viewport in the capture phase, then replayed to OrbitControls in
   * fractions so its zoom-to-cursor maths stays in charge.
   */
  private bindWheel(): void {
    const host = this.canvas.parentElement ?? this.canvas;
    host.addEventListener('wheel', (e) => {
      const we = e as WheelEvent;
      if (this.wheelSynthetic || we.target !== this.canvas) return;
      if (we.ctrlKey) return;                                   // pinch gesture: leave it to OrbitControls
      const px = we.deltaMode === 1 ? we.deltaY * 16 : we.deltaMode === 2 ? we.deltaY * 100 : we.deltaY;
      if (Math.abs(px) < SceneManager.WHEEL_STEP_PX && this.wheelAccum === 0) return;   // trackpad: already smooth
      we.preventDefault(); we.stopPropagation();
      this.wheelAccum += px;
      this.wheelAt = { x: we.clientX, y: we.clientY };
      this.beginInteraction();
      this.requestRender();
    }, { capture: true, passive: false });
  }

  private drainWheel(dt: number): void {
    if (this.wheelAccum === 0) return;
    const k = Math.min(1, 1 - Math.pow(1 - SceneManager.WHEEL_EASE, dt * 60));
    let step = this.wheelAccum * k;
    this.wheelAccum -= step;
    if (Math.abs(this.wheelAccum) < 0.5) { step += this.wheelAccum; this.wheelAccum = 0; }
    this.wheelSynthetic = true;
    try {
      this.canvas.dispatchEvent(new WheelEvent('wheel', { deltaY: step, deltaMode: 0, clientX: this.wheelAt.x, clientY: this.wheelAt.y, bubbles: true, cancelable: true }));
    } finally { this.wheelSynthetic = false; }
  }

  private render(): void {
    this.renders++;
    for (const fn of this.onBeforeRender) fn();
    if (this.composer && this.gtao) {
      this.gtao.enabled = !this.aoSuppressed && !this.interacting;
      this.composer.render();
    } else {
      this.renderer.render(this.scene, this.camera);
    }
  }

  private loop = (): void => {
    this.raf = requestAnimationFrame(this.loop);
    const now = performance.now();
    const dt = Math.min(0.25, Math.max(0.001, (now - this.lastFrameAt) / 1000));
    this.lastFrameAt = now;
    this.drainWheel(dt);
    // frame-rate independent damping: the same decay per second at 30, 60 or 120 Hz.
    // Once a flick has coasted for COAST_MS the remaining delta is spent in one frame so the view stops.
    const coasted = this.pointers === 0 && this.coastStart > 0 && now - this.coastStart > SceneManager.COAST_MS;
    this.controls.dampingFactor = coasted ? 1 : Math.min(1, 1 - Math.pow(1 - SceneManager.DAMPING, dt * 60));
    const moved = this.controls.update(dt);
    if (this.interacting && this.pointers === 0 && this.wheelAccum === 0 && now - this.lastMotion > SceneManager.SETTLE_MS) this.endInteraction();
    if (this.dirty || moved) {
      this.dirty = false;
      this.render();
    }
  };

  /** Fit the camera distance to a bounding box, keeping the current view direction. */
  fitToBox(box: THREE.Box3, animate = true): void {
    const size = box.getSize(new THREE.Vector3()).length();
    const center = box.getCenter(new THREE.Vector3());
    const dist = Math.max(60, size / (2 * Math.tan((this.camera.fov * Math.PI) / 360)) * 1.15);
    const dir = this.camera.position.clone().sub(this.controls.target).normalize();
    this.moveCamera(center.clone().add(dir.multiplyScalar(dist)), center, animate ? 350 : 0);
  }

  private tween: { from: THREE.Vector3; to: THREE.Vector3; tFrom: THREE.Vector3; tTo: THREE.Vector3; start: number; ms: number } | null = null;

  moveCamera(position: THREE.Vector3, target: THREE.Vector3, ms = 350): void {
    if (ms <= 0) { this.camera.position.copy(position); this.controls.target.copy(target); this.controls.update(); this.requestRender(); return; }
    this.tween = { from: this.camera.position.clone(), to: position.clone(), tFrom: this.controls.target.clone(), tTo: target.clone(), start: performance.now(), ms };
    const step = () => {
      if (!this.tween) return;
      const k = Math.min(1, (performance.now() - this.tween.start) / this.tween.ms);
      const e = 1 - Math.pow(1 - k, 3);
      this.camera.position.lerpVectors(this.tween.from, this.tween.to, e);
      this.controls.target.lerpVectors(this.tween.tFrom, this.tween.tTo, e);
      this.controls.update();
      this.requestRender();
      if (k < 1) requestAnimationFrame(step); else this.tween = null;
    };
    requestAnimationFrame(step);
  }

  screenshot(): Promise<Blob | null> {
    this.endInteraction();      // never capture a half-resolution interaction frame
    this.render();
    return new Promise((res) => this.canvas.toBlob(res, 'image/png'));
  }

  dispose(): void {
    cancelAnimationFrame(this.raf);
    this.composer?.dispose();
    this.controls.dispose();
    this.renderer.dispose();
  }
}
