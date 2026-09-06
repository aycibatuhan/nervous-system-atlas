import * as THREE from 'three';
import type { Axis } from '../types/state.ts';

export const AXIS_INDEX: Record<Axis, 0 | 1 | 2> = { sagittal: 0, coronal: 1, axial: 2 };

export interface VolumeGrid {
  dims: [number, number, number];
  affine: THREE.Matrix4;    // voxel (i,j,k) -> mm RAS
  inverse: THREE.Matrix4;   // mm -> voxel
}

export function makeGrid(dims: [number, number, number], affineRows: number[][]): VolumeGrid {
  const a = affineRows;
  const affine = new THREE.Matrix4().set(
    a[0]![0]!, a[0]![1]!, a[0]![2]!, a[0]![3]!,
    a[1]![0]!, a[1]![1]!, a[1]![2]!, a[1]![3]!,
    a[2]![0]!, a[2]![1]!, a[2]![2]!, a[2]![3]!,
    0, 0, 0, 1);
  return { dims, affine, inverse: affine.clone().invert() };
}

export function mmToVoxel(mm: THREE.Vector3, g: VolumeGrid, out = new THREE.Vector3()): THREE.Vector3 {
  return out.copy(mm).applyMatrix4(g.inverse);
}

export function voxelToMm(vox: THREE.Vector3, g: VolumeGrid, out = new THREE.Vector3()): THREE.Vector3 {
  return out.copy(vox).applyMatrix4(g.affine);
}

/** Axis-aligned world box a grid covers, from voxel centre 0 to dims-1 (`pad` = 0.5 for the outer voxel faces). */
export function gridBoxMm(g: VolumeGrid, pad = 0): THREE.Box3 {
  const a = voxelToMm(new THREE.Vector3(-pad, -pad, -pad), g);
  const b = voxelToMm(new THREE.Vector3(g.dims[0] - 1 + pad, g.dims[1] - 1 + pad, g.dims[2] - 1 + pad), g);
  return new THREE.Box3(new THREE.Vector3(Math.min(a.x, b.x), Math.min(a.y, b.y), Math.min(a.z, b.z)),
    new THREE.Vector3(Math.max(a.x, b.x), Math.max(a.y, b.y), Math.max(a.z, b.z)));
}

/** Union of the boxes of one or more grids. Several grids exist because the cord MRI sits on its own grid. */
export function unionBoxMm(grids: VolumeGrid | VolumeGrid[], pad = 0): THREE.Box3 {
  const list = Array.isArray(grids) ? grids : [grids];
  const box = gridBoxMm(list[0]!, pad);
  for (const g of list.slice(1)) box.union(gridBoxMm(g, pad));
  return box;
}

/** mm range covered along a world axis (assumes axis-aligned affines, true for the MNI and cord grids). */
export function axisExtentMm(axis: Axis, grids: VolumeGrid | VolumeGrid[]): [number, number] {
  const k = AXIS_INDEX[axis];
  const box = unionBoxMm(grids);
  return [Math.ceil(box.min.getComponent(k)), Math.floor(box.max.getComponent(k))];
}

/** Object matrix for a unit PlaneGeometry (x,y in -0.5..0.5) so it covers the whole slab at `positionMm` along `axis`. */
export function sliceMatrix(axis: Axis, positionMm: number, grids: VolumeGrid | VolumeGrid[], out = new THREE.Matrix4()): THREE.Matrix4 {
  const k = AXIS_INDEX[axis];
  const box = unionBoxMm(grids, 0.5);
  const min = box.min.clone();
  const max = box.max.clone();
  const size = max.clone().sub(min);
  const center = min.clone().add(max).multiplyScalar(0.5);
  center.setComponent(k, positionMm);
  // plane local axes: u, v span the two in-plane world axes
  const u = new THREE.Vector3(); const v = new THREE.Vector3(); const n = new THREE.Vector3();
  if (axis === 'axial') { u.set(1, 0, 0); v.set(0, 1, 0); n.set(0, 0, 1); }
  else if (axis === 'coronal') { u.set(1, 0, 0); v.set(0, 0, 1); n.set(0, -1, 0); }
  else { u.set(0, 1, 0); v.set(0, 0, 1); n.set(1, 0, 0); }
  const su = axis === 'sagittal' ? size.y : size.x;
  const sv = axis === 'axial' ? size.y : size.z;
  out.makeBasis(u.multiplyScalar(su), v.multiplyScalar(sv), n);
  out.setPosition(center);
  return out;
}

/** In-plane voxel step vectors for the outline shader. */
export function inPlaneSteps(axis: Axis): [THREE.Vector3, THREE.Vector3] {
  if (axis === 'axial') return [new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, 1, 0)];
  if (axis === 'coronal') return [new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, 0, 1)];
  return [new THREE.Vector3(0, 1, 0), new THREE.Vector3(0, 0, 1)];
}
