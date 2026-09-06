import * as THREE from 'three';
import type { SceneManager } from '../scene/SceneManager.ts';
import type { MeshRegistry, AtlasMesh } from '../loader/MeshRegistry.ts';

export interface PickHit { id: string | null; point: THREE.Vector3 | null; onSlice: boolean }

export class Picker {
  private ray = new THREE.Raycaster();
  private ndc = new THREE.Vector2();
  private pending: PointerEvent | null = null;
  private down: { x: number; y: number; t: number; moved: boolean } | null = null;
  /** a mouse button is held on the canvas: the pointer is steering the camera, not hovering */
  private dragging = false;
  /** last position seen while hover picking was suppressed, replayed once the camera settles */
  private last: PointerEvent | null = null;
  enabled = true;
  /** extra pickable objects (slice planes); a hit reports point only */
  extra: THREE.Object3D[] = [];
  /** BVH raycasts run since boot (a drag must not add any) — read by the e2e interaction budget test */
  picks = 0;

  /** A press that moves less than this (CSS px) and lasts less than CLICK_MS counts as a click, not an orbit drag. */
  static readonly CLICK_PX = 6;
  static readonly CLICK_MS = 500;

  constructor(private sm: SceneManager, private reg: MeshRegistry,
              private cb: { onHover(hit: PickHit): void; onSelect(hit: PickHit, ev: PointerEvent): void; onFocus?(hit: PickHit, ev: MouseEvent): void }) {
    this.ray.firstHitOnly = true;
    const c = sm.canvas;
    c.addEventListener('pointermove', (e) => {
      this.last = e;
      if (this.dragging && e.buttons === 0) this.dragging = false;   // a pointerup we never saw (tab switch)
      if (!this.hoverAllowed()) { this.pending = null; } else this.pending = e;
      if (this.down && !this.down.moved) {
        const dx = e.clientX - this.down.x, dy = e.clientY - this.down.y;
        if (dx * dx + dy * dy > Picker.CLICK_PX * Picker.CLICK_PX) this.down.moved = true;
      }
    });
    c.addEventListener('pointerdown', (e) => {
      this.dragging = true;
      this.pending = null;
      if (e.button === 0 && e.isPrimary) this.down = { x: e.clientX, y: e.clientY, t: performance.now(), moved: false };
    });
    c.addEventListener('pointerup', (e) => {
      this.dragging = e.buttons !== 0;
      if (!this.down || e.button !== 0) { this.resume(e); return; }
      const d = this.down; this.down = null;
      const dx = e.clientX - d.x, dy = e.clientY - d.y, dt = performance.now() - d.t;
      const isClick = !d.moved && dx * dx + dy * dy <= Picker.CLICK_PX * Picker.CLICK_PX && dt < Picker.CLICK_MS;
      if (isClick && this.enabled) this.cb.onSelect(this.pick(e), e);
      else this.resume(e);
    });
    c.addEventListener('pointercancel', () => { this.down = null; this.dragging = false; });
    c.addEventListener('dblclick', (e) => { if (this.enabled && this.cb.onFocus) this.cb.onFocus(this.pick(e), e); });
    c.addEventListener('pointerleave', () => { this.pending = null; this.last = null; this.cb.onHover({ id: null, point: null, onSlice: false }); });
    // one raycast per animation frame at most, and none while the camera is moving: a BVH raycast
    // over ~600 meshes plus the material/LUT churn a hover change causes would land inside the drag.
    sm.onInteractionChange.add((active) => { if (active) this.pending = null; else if (this.last && !this.dragging) this.pending = this.last; });
    const tick = (): void => {
      if (this.pending && this.enabled && this.hoverAllowed()) { const e = this.pending; this.pending = null; this.cb.onHover(this.pick(e)); }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  private hoverAllowed(): boolean { return !this.dragging && !this.sm.isInteracting(); }

  /** after a drag ends, refresh the hover highlight under the cursor once the camera settles */
  private resume(e: PointerEvent): void { this.last = e; if (!this.dragging) this.pending = e; }

  pick(e: MouseEvent): PickHit {
    this.picks++;
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
