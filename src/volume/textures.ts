import * as THREE from 'three';
import type { VolumeData } from './VolumeSource.ts';

export function makeIntensityTexture(v: VolumeData): THREE.Data3DTexture {
  const t = new THREE.Data3DTexture(v.data as Uint8Array, v.dims[0], v.dims[1], v.dims[2]);
  t.format = THREE.RedFormat; t.type = THREE.UnsignedByteType; t.internalFormat = 'R8';
  t.minFilter = THREE.LinearFilter; t.magFilter = THREE.LinearFilter;
  t.wrapS = t.wrapT = t.wrapR = THREE.ClampToEdgeWrapping;
  t.unpackAlignment = 1; t.needsUpdate = true;
  return t;
}

export function makeLabelTexture(v: VolumeData): THREE.Data3DTexture {
  const is16 = v.data instanceof Uint16Array;
  const t = new THREE.Data3DTexture(v.data, v.dims[0], v.dims[1], v.dims[2]);
  t.format = THREE.RedIntegerFormat; t.type = is16 ? THREE.UnsignedShortType : THREE.UnsignedByteType;
  t.internalFormat = is16 ? 'R16UI' : 'R8UI';
  t.minFilter = THREE.NearestFilter; t.magFilter = THREE.NearestFilter;
  t.wrapS = t.wrapT = t.wrapR = THREE.ClampToEdgeWrapping;
  t.unpackAlignment = is16 ? 2 : 1; t.needsUpdate = true;
  return t;
}

/** 256x256 RGBA8 lookup: label id -> (u = id & 255, v = id >> 8). Alpha = tint strength. */
export class Lut {
  readonly tex: THREE.DataTexture;
  readonly data: Uint8Array;
  constructor(readonly size: 256 | 65536 = 65536) {
    const w = 256, h = size / 256;
    this.data = new Uint8Array(w * h * 4);
    this.tex = new THREE.DataTexture(this.data, w, h, THREE.RGBAFormat, THREE.UnsignedByteType);
    this.tex.minFilter = THREE.NearestFilter; this.tex.magFilter = THREE.NearestFilter; this.tex.needsUpdate = true;
  }
  clear(): void { this.data.fill(0); this.tex.needsUpdate = true; }
  set(id: number, colour: THREE.Color | string, alpha: number): void {
    const c = colour instanceof THREE.Color ? colour : new THREE.Color(colour);
    const o = id * 4;
    this.data[o] = Math.round(c.r * 255); this.data[o + 1] = Math.round(c.g * 255); this.data[o + 2] = Math.round(c.b * 255); this.data[o + 3] = Math.round(alpha * 255);
    this.tex.needsUpdate = true;
  }
}

/** 256x256 R8UI flags: bit0 selected, bit1 involved, bit2 hovered. */
export class Flags {
  readonly tex: THREE.DataTexture;
  readonly data = new Uint8Array(65536);
  constructor() {
    this.tex = new THREE.DataTexture(this.data, 256, 256, THREE.RedIntegerFormat, THREE.UnsignedByteType);
    this.tex.internalFormat = 'R8UI';
    this.tex.minFilter = THREE.NearestFilter; this.tex.magFilter = THREE.NearestFilter; this.tex.unpackAlignment = 1; this.tex.needsUpdate = true;
  }
  clear(): void { this.data.fill(0); this.tex.needsUpdate = true; }
  or(id: number, bit: number): void { this.data[id] = (this.data[id]! | bit) & 255; this.tex.needsUpdate = true; }
}
