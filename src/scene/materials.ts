import * as THREE from 'three';
import type { ManifestMesh } from '../types/manifest.ts';
import { lookFor } from './palette.ts';

export type VisualState = 'normal' | 'hover' | 'selected' | 'dimmed' | 'involved';

export interface AtlasMaterial extends THREE.MeshPhysicalMaterial {
  userData: {
    baseColour: THREE.Color; baseOpacity: number; state: VisualState;
    /** fresnel rim: rgb + strength, shared with the compiled program */
    rim: { value: THREE.Vector4 }; rimPower: { value: number };
  };
}

const RIM_HOVER = new THREE.Color(1.0, 0.96, 0.85);
const RIM_SELECTED = new THREE.Color(1.0, 0.88, 0.4);
const RIM_INVOLVED = new THREE.Color(1.0, 0.5, 0.15);

/** One physical material per mesh: per-system look from the palette, per-mesh colour/opacity from the manifest,
 *  and a fresnel rim (instead of a flat emissive) for hover / selection / involvement. */
export function createMaterial(m: ManifestMesh): AtlasMaterial {
  const colour = new THREE.Color(m.colour);
  const look = lookFor(m);
  const opacity = look.opacity !== undefined && m.opacity >= 1 ? look.opacity : Math.min(m.opacity, look.opacity ?? 1);
  const mat = new THREE.MeshPhysicalMaterial({
    color: colour, roughness: look.roughness, metalness: look.metalness ?? 0,
    sheen: look.sheen ?? 0, sheenRoughness: look.sheenRoughness ?? 0.6, sheenColor: new THREE.Color(look.sheenColor ?? '#ffffff'),
    clearcoat: look.clearcoat ?? 0, clearcoatRoughness: look.clearcoatRoughness ?? 0.4, envMapIntensity: look.envMapIntensity ?? 1,
    transparent: opacity < 1, opacity, side: THREE.FrontSide, depthWrite: opacity >= 1, flatShading: false,
  }) as AtlasMaterial;
  mat.userData = { baseColour: colour, baseOpacity: opacity, state: 'normal', rim: { value: new THREE.Vector4(1, 1, 1, 0) }, rimPower: { value: 2.5 } };
  mat.onBeforeCompile = (shader) => {
    shader.uniforms['uRim'] = mat.userData.rim;
    shader.uniforms['uRimPower'] = mat.userData.rimPower;
    shader.fragmentShader = 'uniform vec4 uRim;\nuniform float uRimPower;\n' + shader.fragmentShader.replace(
      '#include <emissivemap_fragment>',
      `#include <emissivemap_fragment>
      {
        float rimF = pow(1.0 - saturate(dot(normalize(vViewPosition), normal)), uRimPower);
        totalEmissiveRadiance += uRim.rgb * uRim.a * rimF;
      }`);
  };
  mat.customProgramCacheKey = () => 'atlas-physical-rim';
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
  mat.userData.rim.value.set(1, 1, 1, 0); mat.userData.rimPower.value = 2.5;
  mesh.renderOrder = op < 1 ? (op <= 0.2 ? 10 : 5) : 0;
  switch (state) {
    case 'hover':
      mat.userData.rim.value.set(RIM_HOVER.r, RIM_HOVER.g, RIM_HOVER.b, 0.7); mat.userData.rimPower.value = 2.0;
      mat.emissive.copy(base).multiplyScalar(0.08);
      break;
    case 'selected': {
      mat.userData.rim.value.set(RIM_SELECTED.r, RIM_SELECTED.g, RIM_SELECTED.b, 1.8); mat.userData.rimPower.value = 1.6;
      mat.emissive.copy(base).multiplyScalar(0.12).add(new THREE.Color(0.06, 0.05, 0.0));
      // thin shells (envelope, dura) stay see-through when selected
      mat.opacity = op <= 0.3 ? Math.max(op, 0.3) : Math.max(op, 0.95);
      mat.transparent = mat.opacity < 1; mat.depthWrite = mat.opacity >= 0.9; mesh.renderOrder = mat.opacity < 1 ? 6 : 1;
      break;
    }
    case 'dimmed':
      // 2–3 % so stacked parcels never build up into grey fog
      mat.opacity = Math.min(op, 0.03); mat.transparent = true; mat.depthWrite = false; mesh.renderOrder = 5;
      break;
    case 'involved':
      mat.userData.rim.value.set(RIM_INVOLVED.r, RIM_INVOLVED.g, RIM_INVOLVED.b, 1.2); mat.userData.rimPower.value = 1.8;
      mat.emissive.copy(base).multiplyScalar(0.15).add(new THREE.Color(0.08, 0.03, 0));
      mat.opacity = 1; mat.transparent = false; mat.depthWrite = true; mesh.renderOrder = 1;
      break;
  }
  const opaque = !mat.transparent;
  mesh.castShadow = opaque; mesh.receiveShadow = opaque;
  mat.needsUpdate = false;
}
