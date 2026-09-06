import * as THREE from 'three';
import type { SceneManager } from './SceneManager.ts';
import type { PresetName } from '../types/state.ts';

export const PRESETS: { id: PresetName; label: string; key: string; dir: [number, number, number] }[] = [
  { id: 'lateral-l', label: 'Lateral (L)', key: '1', dir: [-1, 0, 0] },
  { id: 'lateral-r', label: 'Lateral (R)', key: '2', dir: [1, 0, 0] },
  { id: 'anterior', label: 'Anterior', key: '3', dir: [0, 1, 0] },
  { id: 'posterior', label: 'Posterior', key: '4', dir: [0, -1, 0] },
  { id: 'superior', label: 'Superior', key: '5', dir: [0, -0.02, 1] },   // slight posterior tilt keeps anterior at the top
  { id: 'inferior', label: 'Inferior', key: '6', dir: [0, -0.02, -1] },
  { id: 'medial-l', label: 'Medial (L)', key: '7', dir: [1, 0, 0] },
  { id: 'medial-r', label: 'Medial (R)', key: '8', dir: [-1, 0, 0] },
];

export function applyPreset(name: PresetName, sm: SceneManager, target: THREE.Vector3, animate = true): void {
  const p = PRESETS.find((x) => x.id === name)!;
  const dist = sm.camera.position.distanceTo(sm.controls.target) || 420;
  const dir = new THREE.Vector3(...p.dir).normalize();
  sm.moveCamera(target.clone().add(dir.multiplyScalar(dist)), target, animate ? 400 : 0);
}
