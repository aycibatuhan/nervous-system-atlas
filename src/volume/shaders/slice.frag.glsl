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
uniform float uWindow, uLevel;    // 0..255
uniform float uOverlayOpacity;
uniform float uShowAllLabels;
uniform float uHasLabels, uHasTracts, uHasTerritories;
uniform vec3  uOutlineColor;
uniform ivec3 uAxisU, uAxisV;

in vec3 vWorldPos;

bool inside(ivec3 p) { return all(greaterThanEqual(p, ivec3(0))) && all(lessThan(p, ivec3(uDims))); }

uint flagsAt(ivec3 p) {
  if (!inside(p) || uHasLabels < 0.5) return 0u;
  uint id = texelFetch(uLabels, p, 0).r;
  return texelFetch(uFlags, ivec2(int(id & 255u), int(id >> 8u)), 0).r;
}

void main() {
  vec3 vox = (uWorldToVoxel * vec4(vWorldPos, 1.0)).xyz;
  if (any(lessThan(vox, vec3(-0.5))) || any(greaterThan(vox, uDims - 0.5))) discard;

  float raw = texture(uIntensity, (vox + 0.5) / uDims).r * 255.0;
  float lo = uLevel - uWindow * 0.5;
  float g = clamp((raw - lo) / max(uWindow, 1.0), 0.0, 1.0);
  vec3 color = vec3(g);
  ivec3 p = ivec3(floor(vox + 0.5));

  if (uHasTerritories > 0.5) {
    uint terr = texelFetch(uTerritories, p, 0).r;
    vec4 tc = texelFetch(uTerrLut, ivec2(int(terr), 0), 0);
    color = mix(color, color * 0.35 + tc.rgb * 0.65, tc.a * uOverlayOpacity);
  }
  if (uHasTracts > 0.5) {
    uint tr = texelFetch(uTracts, p, 0).r;
    vec4 tc = texelFetch(uTractLut, ivec2(int(tr), 0), 0);
    color = mix(color, tc.rgb, tc.a * uOverlayOpacity);
  }
  uint fl = 0u;
  if (uHasLabels > 0.5) {
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
  fragColor = vec4(color, 1.0);
}
