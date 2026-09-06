import * as THREE from 'three';
import vert from './shaders/slice.vert.glsl?raw';
import frag from './shaders/slice.frag.glsl?raw';
import type { Axis } from '../types/state.ts';
import { inPlaneSteps, sliceMatrix, type VolumeGrid } from './coords.ts';

export interface SliceUniforms {
  uIntensity: { value: THREE.Texture | null };
  uLabels: { value: THREE.Texture | null };
  uTracts: { value: THREE.Texture | null };
  uTerritories: { value: THREE.Texture | null };
  uStructLut: { value: THREE.Texture };
  uTractLut: { value: THREE.Texture };
  uTerrLut: { value: THREE.Texture };
  uFlags: { value: THREE.Texture };
  uWorldToVoxel: { value: THREE.Matrix4 };
  uDims: { value: THREE.Vector3 };
  uCord: { value: THREE.Texture | null };
  uCordWorldToVoxel: { value: THREE.Matrix4 };
  uCordDims: { value: THREE.Vector3 };
  uHasCord: { value: number };
  uSpine: { value: THREE.Texture | null };
  uSpineLut: { value: THREE.Texture };
  uHasSpine: { value: number };
  uSpineSel: { value: number };
  uSpineHover: { value: number };
  uWindow: { value: number };
  uLevel: { value: number };
  uOverlayOpacity: { value: number };
  uShowAllLabels: { value: number };
  uHasLabels: { value: number };
  uHasTracts: { value: number };
  uHasTerritories: { value: number };
  uOutlineColor: { value: THREE.Color };
  uLinearOut: { value: number };
}

const dummy3d = (): THREE.Data3DTexture => {
  const t = new THREE.Data3DTexture(new Uint8Array(1), 1, 1, 1);
  t.format = THREE.RedIntegerFormat; t.type = THREE.UnsignedByteType; t.internalFormat = 'R8UI'; t.needsUpdate = true; return t;
};

export function createSliceUniforms(grid: VolumeGrid, cordGrid: VolumeGrid | null, luts: { struct: THREE.Texture; tract: THREE.Texture; terr: THREE.Texture; flags: THREE.Texture; spine: THREE.Texture }): SliceUniforms {
  const dummyI = new THREE.Data3DTexture(new Uint8Array(1), 1, 1, 1); dummyI.format = THREE.RedFormat; dummyI.internalFormat = 'R8'; dummyI.needsUpdate = true;
  return {
    uIntensity: { value: dummyI }, uLabels: { value: dummy3d() }, uTracts: { value: dummy3d() }, uTerritories: { value: dummy3d() },
    uStructLut: { value: luts.struct }, uTractLut: { value: luts.tract }, uTerrLut: { value: luts.terr }, uFlags: { value: luts.flags },
    uWorldToVoxel: { value: grid.inverse.clone() }, uDims: { value: new THREE.Vector3(...grid.dims) },
    uCord: { value: dummyI }, uCordWorldToVoxel: { value: (cordGrid ?? grid).inverse.clone() },
    uCordDims: { value: new THREE.Vector3(...(cordGrid ?? grid).dims) }, uHasCord: { value: 0 },
    uSpine: { value: dummy3d() }, uSpineLut: { value: luts.spine }, uHasSpine: { value: 0 },
    uSpineSel: { value: 0 }, uSpineHover: { value: 0 },
    uWindow: { value: 255 }, uLevel: { value: 127 }, uOverlayOpacity: { value: 0.75 }, uShowAllLabels: { value: 0 },
    uHasLabels: { value: 0 }, uHasTracts: { value: 0 }, uHasTerritories: { value: 0 }, uOutlineColor: { value: new THREE.Color(0xffe066) }, uLinearOut: { value: 0 },
  };
}

export class SlicePlane {
  readonly mesh: THREE.Mesh<THREE.PlaneGeometry, THREE.ShaderMaterial>;
  positionMm = 0;
  private extended = false;

  constructor(readonly axis: Axis, private grids: VolumeGrid[], shared: SliceUniforms) {
    const [u, v] = inPlaneSteps(axis);
    const mat = new THREE.ShaderMaterial({
      glslVersion: THREE.GLSL3, vertexShader: vert, fragmentShader: frag,
      uniforms: { ...shared, uAxisU: { value: new THREE.Vector3().copy(u) }, uAxisV: { value: new THREE.Vector3().copy(v) } } as unknown as Record<string, THREE.IUniform>,
      side: THREE.DoubleSide, transparent: false, depthWrite: true, clipping: false,
    });
    // ivec uniforms: three uploads Vector3 as float; declare as ivec by uploading integer arrays instead
    (mat.uniforms['uAxisU'] as THREE.IUniform).value = new Int32Array([u.x, u.y, u.z]);
    (mat.uniforms['uAxisV'] as THREE.IUniform).value = new Int32Array([v.x, v.y, v.z]);
    this.mesh = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), mat);
    this.mesh.name = `slice-${axis}`;
    this.mesh.renderOrder = -1;
    this.mesh.matrixAutoUpdate = false;
    this.mesh.frustumCulled = false;
    this.mesh.userData = { axis };
    this.setPosition(0);
  }

  setPosition(mm: number): void {
    this.positionMm = mm;
    sliceMatrix(this.axis, mm, this.extended ? this.grids : this.grids[0]!, this.mesh.matrix);
    this.mesh.matrixWorldNeedsUpdate = true;
  }

  /** Grow the plane from the brain box to the union with the cord grid (500 mm taller), and back.
   *  Kept off by default: the plane is shaded per fragment, so the brain-only view must not pay for the cord. */
  setExtended(v: boolean): void {
    if (this.extended === v) return;
    this.extended = v;
    this.setPosition(this.positionMm);
  }

  setVisible(v: boolean): void { this.mesh.visible = v; }

  /** Clipping plane that hides everything on `side` of this slice. */
  clippingPlane(side: 'positive' | 'negative'): THREE.Plane {
    const n = new THREE.Vector3(); const k = this.axis === 'sagittal' ? 0 : this.axis === 'coronal' ? 1 : 2;
    n.setComponent(k, side === 'positive' ? -1 : 1);   // keep the negative side when hiding positive
    return new THREE.Plane(n, side === 'positive' ? this.positionMm : -this.positionMm);
  }
}
