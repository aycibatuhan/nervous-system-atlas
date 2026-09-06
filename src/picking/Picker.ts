import * as THREE from 'three';
import type { SceneManager } from '../scene/SceneManager.ts';
import type { MeshRegistry, AtlasMesh } from '../loader/MeshRegistry.ts';

export interface PickHit { id: string | null; point: THREE.Vector3 | null; onSlice: boolean }

export class Picker {
  private ray = new THREE.Raycaster();
  private ndc = new THREE.Vector2();
  private pending: PointerEvent | null = null;
  private down: { x: number; y: number; t: number } | null = null;
  enabled = true;
  /** extra pickable objects (slice planes); a hit reports point only */
  extra: THREE.Object3D[] = [];

  constructor(private sm: SceneManager, private reg: MeshRegistry,
              private cb: { onHover(hit: PickHit): void; onSelect(hit: PickHit, ev: PointerEvent): void }) {
    this.ray.firstHitOnly = true;
    const c = sm.canvas;
    c.addEventListener('pointermove', (e) => { this.pending = e; });
    c.addEventListener('pointerdown', (e) => { if (e.button === 0) this.down = { x: e.clientX, y: e.clientY, t: performance.now() }; });
    c.addEventListener('pointerup', (e) => {
      if (!this.down || e.button !== 0) return;
      const dx = e.clientX - this.down.x, dy = e.clientY - this.down.y, dt = performance.now() - this.down.t;
      this.down = null;
      if (dx * dx + dy * dy < 25 && dt < 400 && this.enabled) this.cb.onSelect(this.pick(e), e);
    });
    c.addEventListener('pointerleave', () => { this.cb.onHover({ id: null, point: null, onSlice: false }); });
    sm.onBeforeRender.add(() => { if (this.pending && this.enabled) { const e = this.pending; this.pending = null; this.cb.onHover(this.pick(e)); } });
    const tick = () => { if (this.pending && this.enabled) { const e = this.pending; this.pending = null; this.cb.onHover(this.pick(e)); } requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  }

  pick(e: PointerEvent): PickHit {
    const r = this.sm.canvas.getBoundingClientRect();
    this.ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    this.ray.setFromCamera(this.ndc, this.sm.camera);
    const objs: THREE.Object3D[] = [...this.reg.pickables(), ...this.extra.filter((o) => o.visible)];
    const hits = this.ray.intersectObjects(objs, false);
    if (!hits.length) return { id: null, point: null, onSlice: false };
    // prefer an opaque mesh over a translucent one hit first along the same ray
    let hit = hits[0]!;
    const mat = (hit.object as THREE.Mesh).material as THREE.Material | undefined;
    if (mat && mat.transparent && mat.opacity < 0.5 && hits.length > 1) {
      const better = hits.find((h) => { const m = (h.object as THREE.Mesh).material as THREE.Material | undefined; return !m || !m.transparent || m.opacity >= 0.5; });
      if (better) hit = better;
    }
    const obj = hit.object as AtlasMesh;
    const onSlice = this.extra.includes(hit.object);
    return { id: onSlice ? null : obj.userData.id, point: hit.point.clone(), onSlice };
  }
}
