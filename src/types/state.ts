import type { SystemId } from './manifest.ts';
import { getLocale, type Locale } from '../i18n/index.ts';

export type Axis = 'axial' | 'coronal' | 'sagittal';
export type Contrast = 't1w' | 't2w';
export type PresetName = 'lateral-r' | 'lateral-l' | 'medial-r' | 'medial-l' | 'anterior' | 'posterior' | 'superior' | 'inferior';
export type ContentTab = 'overview' | 'anatomy' | 'connections' | 'function' | 'blood' | 'imaging' | 'clinical' | 'pitfalls' | 'citations';

export interface AppState {
  loaded: { manifest: boolean; volume: boolean; labels: boolean; content: boolean; cord: boolean };
  visibleSystems: ReadonlySet<SystemId>;
  hiddenStructures: ReadonlySet<string>;     // per-mesh overrides (hidden although its system is visible)
  shownStructures: ReadonlySet<string>;      // per-mesh overrides (shown although its system is hidden)
  selectedId: string | null;                 // mesh id
  // a structure opened by id with no mesh in this edition (the public edition drops the non-redistributable
  // atlases, so its content still exists while its geometry does not); null whenever selectedId is set
  selectedStructureId: string | null;
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
  panel: { kind: 'quiz'; index: number } | { kind: 'glossary'; id: string | null } | { kind: 'topic'; id: string | null } | { kind: 'about' } | null;
  camera: PresetName | 'custom';
  showNc: boolean;
  quality: 'low' | 'high';
  cordMri: boolean;              // show the PAM50 cord MRI on the slices (loads it on demand)
  cordLevel: number | null;      // PAM50 spinal level id (1 = C1 ... 30 = S5) under the cursor on a cord slice
  locale: Locale;                // interface language; every panel re-renders from this
}

export function initialState(): AppState {
  return {
    loaded: { manifest: false, volume: false, labels: false, content: false, cord: false },
    visibleSystems: new Set<SystemId>(),
    hiddenStructures: new Set(),
    shownStructures: new Set(),
    selectedId: null,
    selectedStructureId: null,
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
    cordMri: false,
    cordLevel: null,
    locale: getLocale(),
  };
}
