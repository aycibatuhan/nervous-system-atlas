import * as THREE from 'three';
import { SceneManager } from './scene/SceneManager.ts';
import { MeshRegistry } from './loader/MeshRegistry.ts';
import { Picker } from './picking/Picker.ts';
import { installBvh } from './picking/bvh.ts';
import { createStore, type Store } from './state/store.ts';
import { initialState, type AppState, type Axis } from './types/state.ts';
import type { LabelsJson, Manifest, ManifestMesh } from './types/manifest.ts';
import { makeGrid, type VolumeGrid } from './volume/coords.ts';
import { Flags, Lut } from './volume/textures.ts';
import { createSliceUniforms, SlicePlane, type SliceUniforms } from './volume/SlicePlane.ts';
import type { SpineLabels } from './volume/spineLabels.ts';
import type { ContentBundle } from './types/content.ts';

/** Everything the actions and UI need to reach. Created once in main.ts. */
export interface App {
  store: Store<AppState>;
  sm: SceneManager;
  manifest: Manifest;
  labels: LabelsJson | null;
  registry: MeshRegistry;
  picker: Picker;
  grid: VolumeGrid;
  cordGrid: VolumeGrid | null;
  grids: VolumeGrid[];
  uniforms: SliceUniforms;
  slices: Record<Axis, SlicePlane>;
  luts: { struct: Lut; tract: Lut; terr: Lut; flags: Flags; spine: Lut };
  /** PAM50 spinal levels on the cord grid; loaded next to the cord MRI, null until then */
  spine: SpineLabels | null;
  content: ContentBundle | null;
  lesion: THREE.Mesh;
}

export function createApp(canvas: HTMLCanvasElement, manifest: Manifest): App {
  installBvh();
  const store = createStore(initialState());
  const sm = new SceneManager(canvas);
  const registry = new MeshRegistry(manifest, sm.meshRoot, () => { sm.requestRender(); });
  const grid = makeGrid(manifest.grid.shape, manifest.grid.affine_ras);
  // the spinal cord MRI (atlas-pam50) sits on a second, much taller grid that starts below the MNI box
  const cordGrid = manifest.grids?.cord ? makeGrid(manifest.grids.cord.shape, manifest.grids.cord.affine_ras) : null;
  const grids = cordGrid ? [grid, cordGrid] : [grid];
  const luts = { struct: new Lut(65536), tract: new Lut(256), terr: new Lut(256), flags: new Flags(), spine: new Lut(256) };
  const uniforms = createSliceUniforms(grid, cordGrid, { struct: luts.struct.tex, tract: luts.tract.tex, terr: luts.terr.tex, flags: luts.flags.tex, spine: luts.spine.tex });
  const slices = {
    axial: new SlicePlane('axial', grids, uniforms), coronal: new SlicePlane('coronal', grids, uniforms), sagittal: new SlicePlane('sagittal', grids, uniforms),
  };
  for (const s of Object.values(slices)) { sm.sliceRoot.add(s.mesh); s.setVisible(false); }
  const lesion = new THREE.Mesh(new THREE.SphereGeometry(1, 32, 24), new THREE.MeshStandardMaterial({ color: 0xff3030, transparent: true, opacity: 0.45, depthWrite: false, emissive: 0x550000 }));
  lesion.visible = false; lesion.renderOrder = 20; sm.overlayRoot.add(lesion);
  const app: App = { store, sm, manifest, labels: null, registry, picker: null as unknown as Picker, grid, cordGrid, grids, uniforms, slices, luts, spine: null, content: null, lesion };
  return app;
}

export function meshEntry(app: App, id: string | null): ManifestMesh | undefined {
  return id ? app.registry.byId.get(id) : undefined;
}
