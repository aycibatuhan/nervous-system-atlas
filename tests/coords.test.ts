import { describe, expect, it } from 'vitest';
import * as THREE from 'three';
import { axisExtentMm, makeGrid, mmToVoxel, sliceMatrix, voxelToMm } from '../src/volume/coords.ts';

const grid = makeGrid([193, 229, 193], [[1, 0, 0, -96], [0, 1, 0, -132], [0, 0, 1, -78], [0, 0, 0, 1]]);

describe('MNI 2009c grid', () => {
  it('round-trips mm ↔ voxel', () => {
    const p = new THREE.Vector3(12.5, -40, 33);
    const back = voxelToMm(mmToVoxel(p, grid), grid);
    expect(back.distanceTo(p)).toBeLessThan(1e-9);
    expect(mmToVoxel(new THREE.Vector3(0, 0, 0), grid).toArray()).toEqual([96, 132, 78]);
  });
  it('axis extents', () => {
    expect(axisExtentMm('axial', grid)).toEqual([-78, 114]);
    expect(axisExtentMm('coronal', grid)).toEqual([-132, 96]);
    expect(axisExtentMm('sagittal', grid)).toEqual([-96, 96]);
  });
  it('slice plane covers the slab', () => {
    const m = sliceMatrix('axial', 10, grid);
    const corner = new THREE.Vector3(-0.5, -0.5, 0).applyMatrix4(m);
    expect(corner.x).toBeCloseTo(-96.5); expect(corner.y).toBeCloseTo(-132.5); expect(corner.z).toBeCloseTo(10);
    const c2 = new THREE.Vector3(0.5, 0.5, 0).applyMatrix4(m);
    expect(c2.x).toBeCloseTo(96.5); expect(c2.y).toBeCloseTo(96.5);
    const s = sliceMatrix('sagittal', -24, grid);
    expect(new THREE.Vector3(0, 0, 0).applyMatrix4(s).x).toBeCloseTo(-24);
  });
});
