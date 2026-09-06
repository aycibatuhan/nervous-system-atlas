precision highp float;
precision highp int;
precision highp sampler3D;
precision highp usampler3D;
precision highp usampler2D;

out vec4 fragColor;

uniform sampler3D  uIntensity;
uniform usampler3D uLabels;       // anat, R16UI
uniform usampler3D uTracts;       // R8UI
uniform usampler3D uTerritories;  // R8UI
uniform sampler2D  uStructLut;    // 256x256 RGBA8
uniform sampler2D  uTractLut;     // 256x1
uniform sampler2D  uTerrLut;      // 256x1
uniform usampler2D uFlags;        // 256x256 R8UI
uniform mat4  uWorldToVoxel;
uniform vec3  uDims;
uniform sampler3D uCord;          // spinal cord MRI on its own grid (PAM50 curved reformat), R8
uniform mat4  uCordWorldToVoxel;
uniform vec3  uCordDims;
uniform float uHasCord;
uniform usampler3D uSpine;        // PAM50 spinal levels on the cord grid, R8UI (1 = C1 ... 30 = S5)
uniform sampler2D  uSpineLut;     // 256x1 RGBA8, level id -> ramp colour + tint strength
uniform float uHasSpine;
uniform uint  uSpineSel;          // bit i set: level i belongs to the selected cord segment
uniform uint  uSpineHover;        // bit i set: level i is under the cursor
uniform float uWindow, uLevel;    // 0..255
uniform float uOverlayOpacity;
uniform float uShowAllLabels;
uniform float uHasLabels, uHasTracts, uHasTerritories;
uniform vec3  uOutlineColor;
uniform ivec3 uAxisU, uAxisV;

in vec3 vWorldPos;

bool inside(ivec3 p) { return all(greaterThanEqual(p, ivec3(0))) && all(lessThan(p, ivec3(uDims))); }

// ---- spinal levels (only ever sampled below the MNI box, where the cord volume takes over)
bool spineBit(uint mask, uint lid) { return lid != 0u && lid < 32u && ((mask >> lid) & 1u) != 0u; }

/** 1 if the level at this cord voxel is part of the selected cord segment, else 0 (the outline membership). */
uint spineSelAt(ivec3 p) {
  if (uHasSpine < 0.5) return 0u;
  if (any(lessThan(p, ivec3(0))) || any(greaterThanEqual(p, ivec3(uCordDims)))) return 0u;
  return spineBit(uSpineSel, texelFetch(uSpine, p, 0).r) ? 1u : 0u;
}

uint flagsAt(ivec3 p) {
  if (!inside(p) || uHasLabels < 0.5) return 0u;
  uint id = texelFetch(uLabels, p, 0).r;
  return texelFetch(uFlags, ivec2(int(id & 255u), int(id >> 8u)), 0).r;
}

uniform float uLinearOut;

vec3 srgbToLinear(vec3 c) {
  return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(vec3(0.04045), c));
}
// exact inverse of three.js ACESFilmicToneMapping (exposure 1)
vec3 inverseAces(vec3 y) {
  const mat3 invOut = mat3(vec3(0.643038, 0.059269, 0.005962), vec3(0.311187, 0.931436, 0.063929), vec3(0.045775, 0.009295, 0.930118));
  const mat3 invIn = mat3(vec3(1.764741, -0.147028, -0.036337), vec3(-0.675778, 1.160252, -0.162436), vec3(-0.088963, -0.013224, 1.198773));
  vec3 v = invOut * clamp(y, 0.0, 0.985);
  vec3 a = 1.0 - 0.983729 * v;
  vec3 b = 0.0245786 - 0.4329510 * v;
  vec3 c = -0.000090537 - 0.238081 * v;
  vec3 x = (-b + sqrt(max(b * b - 4.0 * a * c, 0.0))) / (2.0 * a);
  return max(invIn * x, 0.0) * 0.6;
}

void main() {
  vec3 vox = (uWorldToVoxel * vec4(vWorldPos, 1.0)).xyz;
  bool inMni = all(greaterThanEqual(vox, vec3(-0.5))) && all(lessThanEqual(vox, uDims - 0.5));

  float raw;
  bool inCord = false;
  ivec3 cp = ivec3(0);
  if (inMni) {
    raw = texture(uIntensity, (vox + 0.5) / uDims).r * 255.0;
  } else if (uHasCord > 0.5) {
    // below the foramen magnum the MNI template has no data; the cord volume takes over on its own grid
    vec3 cv = (uCordWorldToVoxel * vec4(vWorldPos, 1.0)).xyz;
    if (any(lessThan(cv, vec3(-0.5))) || any(greaterThan(cv, uCordDims - 0.5))) discard;
    raw = texture(uCord, (cv + 0.5) / uCordDims).r * 255.0;
    if (raw <= 0.0) discard;   // outside the reformatted tube: keep the plane transparent, not black
    cp = ivec3(floor(cv + 0.5));
    inCord = true;
  } else {
    discard;
  }
  float lo = uLevel - uWindow * 0.5;
  float g = clamp((raw - lo) / max(uWindow, 1.0), 0.0, 1.0);
  vec3 color = vec3(g);
  ivec3 p = ivec3(floor(vox + 0.5));

  if (inMni && uHasTerritories > 0.5) {
    uint terr = texelFetch(uTerritories, p, 0).r;
    vec4 tc = texelFetch(uTerrLut, ivec2(int(terr), 0), 0);
    color = mix(color, color * 0.35 + tc.rgb * 0.65, tc.a * uOverlayOpacity);
  }
  if (inMni && uHasTracts > 0.5) {
    uint tr = texelFetch(uTracts, p, 0).r;
    vec4 tc = texelFetch(uTractLut, ivec2(int(tr), 0), 0);
    color = mix(color, tc.rgb, tc.a * uOverlayOpacity);
  }
  uint fl = 0u;
  if (inMni && uHasLabels > 0.5) {
    uint id = texelFetch(uLabels, p, 0).r;
    ivec2 lc = ivec2(int(id & 255u), int(id >> 8u));
    vec4 sc = texelFetch(uStructLut, lc, 0);
    fl = texelFetch(uFlags, lc, 0).r;
    float a = sc.a * max(uShowAllLabels, float((fl & 7u) != 0u));
    color = mix(color, sc.rgb, a * uOverlayOpacity);
    // outline of selected (bit0) / involved (bit1) structures: any in-plane neighbour with a different flag
    uint me = fl & 3u;
    uint nb0 = flagsAt(p + uAxisU) & 3u, nb1 = flagsAt(p - uAxisU) & 3u, nb2 = flagsAt(p + uAxisV) & 3u, nb3 = flagsAt(p - uAxisV) & 3u;
    bool edge = (me != nb0) || (me != nb1) || (me != nb2) || (me != nb3);
    if (edge && (me != 0u || nb0 != 0u || nb1 != 0u || nb2 != 0u || nb3 != 0u)) {
      bool sel = ((me | nb0 | nb1 | nb2 | nb3) & 1u) != 0u;
      color = sel ? uOutlineColor : vec3(1.0, 0.55, 0.15);
    }
  }
  // spinal levels: the cord grid's own label volume, on the same overlay opacity / "all labels" controls as
  // the anatomical labels, with the selected cord segment outlined exactly the way a selected structure is
  if (inCord && uHasSpine > 0.5) {
    uint lid = texelFetch(uSpine, cp, 0).r;
    vec4 sc = texelFetch(uSpineLut, ivec2(int(lid), 0), 0);
    uint me = spineSelAt(cp);
    float on = max(uShowAllLabels, float(me != 0u || spineBit(uSpineHover, lid)));
    color = mix(color, sc.rgb, sc.a * uOverlayOpacity * on);
    uint nb0 = spineSelAt(cp + uAxisU), nb1 = spineSelAt(cp - uAxisU), nb2 = spineSelAt(cp + uAxisV), nb3 = spineSelAt(cp - uAxisV);
    bool edge = (me != nb0) || (me != nb1) || (me != nb2) || (me != nb3);
    if (edge && (me | nb0 | nb1 | nb2 | nb3) != 0u) color = uOutlineColor;
  }
  if (uLinearOut > 0.5) {
    // the composer's OutputPass will apply ACES + sRGB; pre-invert both so the MRI window/level is reproduced exactly
    color = inverseAces(srgbToLinear(color));
  }
  fragColor = vec4(color, 1.0);
}
