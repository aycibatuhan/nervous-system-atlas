import * as THREE from 'three';
import type { Manifest, ManifestMesh, SystemId } from '../types/manifest.ts';
import { DATA_URL } from './manifest.ts';
import { getGltfLoader } from './gltf.ts';
import { createMaterial } from '../scene/materials.ts';

export interface AtlasMesh extends THREE.Mesh { userData: { id: string; system: SystemId; entry: ManifestMesh; lod: boolean } }

const idle: (cb: () => void) => void = typeof requestIdleCallback === 'function' ? (cb) => requestIdleCallback(cb, { timeout: 2000 }) : (cb) => setTimeout(cb, 50);

/** Loads glTF meshes lazily per system, keeps them under `root`, and exposes visibility + picking sets. */
export class MeshRegistry {
  private meshes = new Map<string, AtlasMesh>();
  private pending = new Map<string, Promise<AtlasMesh | null>>();
  private systemLoads = new Map<SystemId, Promise<void>>();
  readonly byId = new Map<string, ManifestMesh>();
  readonly bySystem = new Map<SystemId, ManifestMesh[]>();
  private pickCache: AtlasMesh[] | null = null;
  /** meshes shown as low-detail stand-ins, waiting for their full geometry */
  private upgradeQueue: string[] = [];
  private upgrading = 0;
  /** when false every mesh loads at full detail straight away (tests, screenshots) */
  useLod = true;

  constructor(readonly manifest: Manifest, private root: THREE.Group, private onChange: (id: string) => void) {
    for (const m of manifest.meshes) {
      this.byId.set(m.id, m);
      const list = this.bySystem.get(m.system) ?? [];
      list.push(m); this.bySystem.set(m.system, list);
    }
  }

  get(id: string): AtlasMesh | undefined { return this.meshes.get(id); }
  has(id: string): boolean { return this.meshes.has(id); }
  loaded(): IterableIterator<AtlasMesh> { return this.meshes.values(); }

  async ensure(ids: Iterable<string>): Promise<AtlasMesh[]> {
    const out = await Promise.all(Array.from(ids, (id) => this.load(id)));
    return out.filter((m): m is AtlasMesh => !!m);
  }

  loadSystem(system: SystemId): Promise<void> {
    let p = this.systemLoads.get(system);
    if (!p) {
      const ids = (this.bySystem.get(system) ?? []).map((m) => m.id);
      p = this.pool(ids, 6).then(() => undefined);
      this.systemLoads.set(system, p);
    }
    return p;
  }

  private async pool(ids: string[], width: number): Promise<void> {
    let i = 0;
    const worker = async () => { while (i < ids.length) { const id = ids[i++]!; await this.load(id); } };
    await Promise.all(Array.from({ length: Math.min(width, ids.length) }, worker));
  }

  /** Decode one glb into a bare geometry in MNI millimetres (quantised positions expanded, node matrix baked in). */
  private async loadGeometry(file: string, id: string): Promise<THREE.BufferGeometry> {
    const gltf = await getGltfLoader().loadAsync(DATA_URL + file);
    let found: THREE.Mesh | null = null;
    gltf.scene.traverse((o) => { if (!found && (o as THREE.Mesh).isMesh) found = o as THREE.Mesh; });
    if (!found) throw new Error(`${id}: no mesh in glb`);
    const src = found as THREE.Mesh;
    src.updateWorldMatrix(true, false);
    const srcPos = src.geometry.getAttribute('position');
    const pos = new Float32Array(srcPos.count * 3);
    for (let i = 0; i < srcPos.count; i++) { pos[3 * i] = srcPos.getX(i); pos[3 * i + 1] = srcPos.getY(i); pos[3 * i + 2] = srcPos.getZ(i); }
    const geom = new THREE.BufferGeometry();
    geom.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    const srcNor = src.geometry.getAttribute('normal');
    if (srcNor) {
      const nor = new Float32Array(srcNor.count * 3);
      for (let i = 0; i < srcNor.count; i++) { nor[3 * i] = srcNor.getX(i); nor[3 * i + 1] = srcNor.getY(i); nor[3 * i + 2] = srcNor.getZ(i); }
      geom.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
    }
    if (src.geometry.index) geom.setIndex(src.geometry.index.clone());
    geom.applyMatrix4(src.matrixWorld);
    if (!srcNor) geom.computeVertexNormals();
    src.geometry.dispose();
    (src.material as THREE.Material).dispose();
    geom.computeBoundingBox(); geom.computeBoundingSphere();
    geom.computeBoundsTree();
    return geom;
  }

  /** Swap a stand-in for its full geometry (called from the idle queue or `ensureFull`). */
  private async upgrade(id: string): Promise<void> {
    const mesh = this.meshes.get(id);
    if (!mesh || !mesh.userData.lod) return;
    try {
      const geom = await this.loadGeometry(mesh.userData.entry.file, id);
      const cur = this.meshes.get(id);
      if (cur !== mesh || !mesh.userData.lod) { geom.disposeBoundsTree?.(); geom.dispose(); return; }
      mesh.geometry.disposeBoundsTree?.(); mesh.geometry.dispose();
      mesh.geometry = geom; mesh.userData.lod = false;
      this.pickCache = null;
      this.onChange(id);
    } catch (e) { console.error(`failed to upgrade ${id}`, e); }
  }

  private pumpUpgrades(): void {
    while (this.upgrading < 2 && this.upgradeQueue.length) {
      const id = this.upgradeQueue.shift()!;
      this.upgrading++;
      idle(() => { void this.upgrade(id).finally(() => { this.upgrading--; this.pumpUpgrades(); }); });
    }
  }

  /** Make sure a mesh is at full detail now (selected / focused structures jump the queue). */
  async ensureFull(id: string): Promise<AtlasMesh | null> {
    const mesh = await this.load(id);
    if (mesh && mesh.userData.lod) { this.upgradeQueue = this.upgradeQueue.filter((x) => x !== id); await this.upgrade(id); }
    return mesh;
  }

  /** Bytes fetched for the first paint of a set of ids (stand-ins where they exist). */
  firstPaintBytes(ids: Iterable<string>): number {
    let n = 0;
    for (const id of ids) { const e = this.byId.get(id); if (e) n += this.useLod && e.lod ? e.lod.bytes : e.bytes; }
    return n;
  }

  load(id: string): Promise<AtlasMesh | null> {
    const existing = this.meshes.get(id);
    if (existing) return Promise.resolve(existing);
    let p = this.pending.get(id);
    if (p) return p;
    const entry = this.byId.get(id);
    if (!entry) return Promise.resolve(null);
    const useLod = this.useLod && !!entry.lod;
    p = this.loadGeometry(useLod ? entry.lod!.file : entry.file, id).then((geom) => {
      const mesh = new THREE.Mesh(geom, createMaterial(entry)) as unknown as AtlasMesh;
      mesh.name = id;
      mesh.userData = { id, system: entry.system, entry, lod: useLod };
      mesh.visible = false;
      mesh.frustumCulled = true;
      this.root.add(mesh);
      this.meshes.set(id, mesh);
      this.pending.delete(id);
      this.pickCache = null;
      this.onChange(id);
      if (useLod) { this.upgradeQueue.push(id); this.pumpUpgrades(); }
      return mesh;
    }).catch((e) => { console.error(`failed to load ${id}`, e); this.pending.delete(id); return null; });
    this.pending.set(id, p);
    return p;
  }

  setVisible(id: string, v: boolean): void {
    const m = this.meshes.get(id);
    if (m && m.visible !== v) { m.visible = v; this.pickCache = null; }
  }

  /** World-space bounds of every visible loaded mesh (falls back to the manifest brain box). */
  sceneBounds(): THREE.Box3 {
    const box = new THREE.Box3();
    for (const m of this.meshes.values()) if (m.visible) box.expandByObject(m);
    if (box.isEmpty()) box.set(new THREE.Vector3(-75, -110, -75), new THREE.Vector3(75, 80, 90));
    return box;
  }

  pickables(): AtlasMesh[] {
    if (!this.pickCache) this.pickCache = Array.from(this.meshes.values()).filter((m) => m.visible);
    return this.pickCache;
  }

  invalidatePickCache(): void { this.pickCache = null; }

  unloadSystem(system: SystemId): void {
    for (const m of this.bySystem.get(system) ?? []) {
      const mesh = this.meshes.get(m.id);
      if (!mesh) continue;
      this.root.remove(mesh);
      mesh.geometry.disposeBoundsTree?.();
      mesh.geometry.dispose();
      (mesh.material as THREE.Material).dispose();
      this.meshes.delete(m.id);
    }
    this.systemLoads.delete(system);
    this.pickCache = null;
  }
}
