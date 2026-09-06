import { describe, expect, it } from 'vitest';
import * as THREE from 'three';
import { axisExtentMm, gridBoxMm, makeGrid, mmToVoxel, sliceMatrix, unionBoxMm, voxelToMm } from '../src/volume/coords.ts';

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

// second grid: the PAM50 curved-reformat cord MRI (atlas-pam50) at 0.75 mm, entirely below the MNI box
const cord = makeGrid([48, 279, 613], [[0.75, 0, 0, -19.53437], [0, 0.75, 0, -263.79053], [0, 0, 0.75, -511.027806], [0, 0, 0, 1]]);

describe('cord grid (second affine)', () => {
  it('round-trips mm ↔ voxel on its own affine', () => {
    const p = new THREE.Vector3(-3.2, -140.5, -300.25);
    const back = voxelToMm(mmToVoxel(p, cord), cord);
    expect(back.distanceTo(p)).toBeLessThan(1e-6);
    expect(mmToVoxel(new THREE.Vector3(-19.53437, -263.79053, -511.027806), cord).length()).toBeCloseTo(0);
  });
  it('covers the cord and starts below the MNI box', () => {
    const box = gridBoxMm(cord);
    expect(box.min.z).toBeCloseTo(-511.027806);
    expect(box.max.z).toBeCloseTo(-511.027806 + 612 * 0.75);   // -51.0, i.e. it overlaps the MNI floor at -78
    expect(box.max.z).toBeGreaterThan(-78);
    expect(box.min.y).toBeLessThan(-132);                      // and reaches posterior of the MNI y floor
  });
  it('axis extents and slice planes span the union of both grids', () => {
    expect(axisExtentMm('axial', [grid, cord])[0]).toBe(-511);   // ceil(-511.03)
    expect(axisExtentMm('axial', [grid, cord])[1]).toBe(114);
    expect(axisExtentMm('sagittal', [grid, cord])).toEqual([-96, 96]);   // the cord sits inside the MNI x range
    expect(axisExtentMm('axial', grid)).toEqual([-78, 114]);             // brain-only default is unchanged
    const u = unionBoxMm([grid, cord], 0.5);
    const m = sliceMatrix('axial', -300, [grid, cord]);
    const corner = new THREE.Vector3(-0.5, -0.5, 0).applyMatrix4(m);
    expect(corner.x).toBeCloseTo(u.min.x); expect(corner.y).toBeCloseTo(u.min.y); expect(corner.z).toBeCloseTo(-300);
    const far = new THREE.Vector3(0.5, 0.5, 0).applyMatrix4(m);
    expect(far.x).toBeCloseTo(u.max.x); expect(far.y).toBeCloseTo(u.max.y);
  });
});
