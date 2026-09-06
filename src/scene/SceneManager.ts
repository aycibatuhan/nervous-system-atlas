import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

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

  constructor(readonly canvas: HTMLCanvasElement) {
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, powerPreference: 'high-performance', preserveDrawingBuffer: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.NoToneMapping;
    this.renderer.localClippingEnabled = true;
    this.scene.background = new THREE.Color(0x14161a);
    this.camera = new THREE.PerspectiveCamera(35, 1, 1, 3000);
    this.camera.up.set(0, 0, 1);
    this.camera.position.set(-420, 0, 20);
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.target.set(0, -18, 10);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.12;
    this.controls.minDistance = 30;
    this.controls.maxDistance = 1500;
    this.controls.addEventListener('change', () => this.requestRender());
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x445566, 1.1));
    this.keyLight = new THREE.DirectionalLight(0xffffff, 1.6);
    this.camera.add(this.keyLight);
    this.keyLight.position.set(120, 180, 240);
    this.scene.add(this.camera);
    this.scene.add(this.meshRoot, this.sliceRoot, this.overlayRoot);
    this.meshRoot.name = 'meshes'; this.sliceRoot.name = 'slices'; this.overlayRoot.name = 'overlay';
    new ResizeObserver(() => this.resize()).observe(canvas.parentElement ?? canvas);
    this.resize();
    this.loop();
  }

  resize(): void {
    const el = this.canvas.parentElement ?? this.canvas;
    const w = Math.max(1, el.clientWidth); const h = Math.max(1, el.clientHeight);
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.requestRender();
  }

  requestRender(): void { this.dirty = true; }

  private loop = (): void => {
    this.raf = requestAnimationFrame(this.loop);
    const moved = this.controls.update();
    if (this.dirty || moved) {
      this.dirty = false;
      for (const fn of this.onBeforeRender) fn();
      this.renderer.render(this.scene, this.camera);
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
    for (const fn of this.onBeforeRender) fn();
    this.renderer.render(this.scene, this.camera);
    return new Promise((res) => this.canvas.toBlob(res, 'image/png'));
  }

  dispose(): void {
    cancelAnimationFrame(this.raf);
    this.controls.dispose();
    this.renderer.dispose();
  }
}
