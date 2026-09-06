import type { SystemId } from './manifest.ts';

export type Axis = 'axial' | 'coronal' | 'sagittal';
export type Contrast = 't1w' | 't2w';
export type PresetName = 'lateral-r' | 'lateral-l' | 'medial-r' | 'medial-l' | 'anterior' | 'posterior' | 'superior' | 'inferior';
export type ContentTab = 'overview' | 'anatomy' | 'connections' | 'function' | 'blood' | 'imaging' | 'clinical' | 'pitfalls' | 'citations';

export interface AppState {
  loaded: { manifest: boolean; volume: boolean; labels: boolean; content: boolean };
  visibleSystems: ReadonlySet<SystemId>;
  hiddenStructures: ReadonlySet<string>;     // per-mesh overrides (hidden although its system is visible)
  shownStructures: ReadonlySet<string>;      // per-mesh overrides (shown although its system is hidden)
  selectedId: string | null;                 // mesh id
  hoverId: string | null;
  contentTab: ContentTab;
  slices: { axial: number; coronal: number; sagittal: number; visible: Record<Axis, boolean>; pinned: boolean };
  contrast: Contrast;
  windowLevel: { window: number; level: number };
  overlay: { opacity: number; showAllLabels: boolean; territory: boolean; tracts: boolean };
  peel: Partial<Record<Axis, 'positive' | 'negative'>>;
  syndrome: { id: string; step: number } | null;
  involved: ReadonlySet<string>;             // meshes involved in the active syndrome
  stepHighlight: ReadonlySet<string>;        // meshes spotlighted for the current deficit step
  lesionSide: 'l' | 'r' | null;              // demo side for lateralised syndromes
  panel: { kind: 'quiz'; index: number } | { kind: 'glossary'; id: string | null } | { kind: 'topic'; id: string | null } | null;
  camera: PresetName | 'custom';
  showNc: boolean;
  quality: 'low' | 'high';
}

export function initialState(): AppState {
  return {
    loaded: { manifest: false, volume: false, labels: false, content: false },
    visibleSystems: new Set<SystemId>(),
    hiddenStructures: new Set(),
    shownStructures: new Set(),
    selectedId: null,
    hoverId: null,
    contentTab: 'overview',
    slices: { axial: 10, coronal: -18, sagittal: 0, visible: { axial: true, coronal: false, sagittal: false }, pinned: false },
    contrast: 't1w',
    windowLevel: { window: 255, level: 127 },
    overlay: { opacity: 0.75, showAllLabels: false, territory: false, tracts: false },
    peel: {},
    syndrome: null,
    involved: new Set(),
    stepHighlight: new Set(),
    lesionSide: null,
    panel: null,
    camera: 'lateral-l',
    showNc: true,
    quality: 'low',
  };
}
