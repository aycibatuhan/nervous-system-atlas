import * as THREE from 'three';
import type { ManifestMesh } from '../types/manifest.ts';

export type VisualState = 'normal' | 'hover' | 'selected' | 'dimmed' | 'involved';

export interface AtlasMaterial extends THREE.MeshStandardMaterial { userData: { baseColour: THREE.Color; baseOpacity: number; state: VisualState } }

export function createMaterial(m: ManifestMesh): AtlasMaterial {
  const colour = new THREE.Color(m.colour);
  const mat = new THREE.MeshStandardMaterial({
    color: colour, roughness: 0.72, metalness: 0.0, transparent: m.opacity < 1, opacity: m.opacity,
    side: THREE.FrontSide, depthWrite: m.opacity >= 1, flatShading: false,
  }) as AtlasMaterial;
  mat.userData = { baseColour: colour, baseOpacity: m.opacity, state: 'normal' };
  return mat;
}

export function applyVisualState(mesh: THREE.Mesh, state: VisualState): void {
  const mat = mesh.material as AtlasMaterial;
  if (mat.userData.state === state) return;
  mat.userData.state = state;
  const base = mat.userData.baseColour; const op = mat.userData.baseOpacity;
  mat.color.copy(base);
  mat.emissive.set(0x000000);
  mat.opacity = op; mat.transparent = op < 1; mat.depthWrite = op >= 1; mat.side = THREE.FrontSide;
  mesh.renderOrder = op < 1 ? 10 : 0;
  switch (state) {
    case 'hover': mat.emissive.copy(base).multiplyScalar(0.28); break;
    case 'selected': mat.emissive.copy(base).multiplyScalar(0.45).add(new THREE.Color(0.12, 0.12, 0.08)); mat.opacity = Math.max(op, 0.95); mat.transparent = mat.opacity < 1; mat.depthWrite = true; mesh.renderOrder = 1; break;
    case 'dimmed': mat.opacity = Math.min(op, 0.08); mat.transparent = true; mat.depthWrite = false; mesh.renderOrder = 5; break;
    case 'involved': mat.emissive.set(0x5a2a00); mat.opacity = Math.max(op, 0.98); mat.transparent = mat.opacity < 1; mat.depthWrite = true; mesh.renderOrder = 1; break;
  }
  mat.needsUpdate = false;
}
