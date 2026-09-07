// Contract with pipeline/atlas_pipeline/manifest.py (public/data/manifest.json)
export type SystemId =
  | 'cerebrum' | 'basal-ganglia' | 'diencephalon' | 'brainstem' | 'cerebellum' | 'cranial-nerves' | 'spinal-cord'
  | 'peripheral' | 'autonomic' | 'ventricles-csf' | 'meninges' | 'arteries' | 'arterial-territories' | 'venous' | 'tracts' | 'envelope';

export type LabelVolumeKey = 'anat' | 'tract' | 'vascular' | 'vascular2';

export interface ManifestMesh {
  id: string;
  structureId: string;
  name: string;
  system: SystemId;
  subsystem: string | null;
  side: 'left' | 'right' | 'midline' | 'bilateral';
  source: string;
  license: string;
  nc: boolean;
  alignment: 'native-mni' | 'nlin6-identity' | 'registered-similarity' | 'registered-affine';
  file: string;
  bytes: number;
  triangles: number;
  compression: 'meshopt' | 'draco' | 'none';
  colour: string;
  opacity: number;
  visible: boolean;
  bbox: [[number, number, number], [number, number, number]];
  centroid: [number, number, number];
  labels: Partial<Record<LabelVolumeKey, number[]>>;
  ontology: Record<string, unknown>;
  /** low-detail stand-in loaded first; the full mesh replaces it in idle time */
  lod?: { file: string; bytes: number; triangles: number };
  /** set when the shape was constructed rather than exported from a source atlas; the value is the method */
  derived?: string;
}

export interface VolumeFile {
  file: string;
  dtype: 'uint8' | 'uint16';
  shape: [number, number, number];
  bytes_raw: number;
  bytes_gz: number;
  window?: number;
  level?: number;
  spacing?: [number, number, number];
  lut?: string;
  /** set on volumes that do not live on the MNI brain grid (the cord MRI has its own affine) */
  space?: 'cord';
  origin_ras?: [number, number, number];
  affine_ras?: number[][];
}

/** A volume grid other than the 193x229x193 brain box. */
export interface ExtraGrid {
  shape: [number, number, number];
  spacing: [number, number, number];
  origin_ras: [number, number, number];
  affine_ras: number[][];
  source: string;
  license: string;
  reformat?: Record<string, unknown>;
}

/** One licence in manifest.licenses (from the `licenses` table of pipeline/config/sources.yaml). */
export interface ManifestLicense {
  name: string;
  url: string;
  attribution: string;
  nc: boolean;
  /** the licence forbids passing derived files on, so they never ship in the public edition */
  noRedistribution?: boolean;
  /** path of the verbatim licence text, relative to public/data/ */
  text: string;
}

/** One dataset in manifest.sources (from the `sources` list of pipeline/config/sources.yaml). */
export interface ManifestSource {
  /** human-readable dataset name; older manifests only carry the id */
  name?: string;
  license: string;
  citation: string;
  /** first download URL, i.e. where the dataset was fetched from */
  url?: string;
  urls?: string[];
  /** the provider needs a click-through, so the pipeline cannot download it */
  manual?: boolean;
  files: Record<string, string | null>;
}

export interface Manifest {
  schema: 1;
  generated: string;
  space: 'MNI152NLin2009cAsym';
  /** "private" while non-redistributable data is in the build, "public" for the shareable edition; absent = private */
  edition?: 'private' | 'public';
  grid: { shape: [number, number, number]; spacing: [number, number, number]; origin_ras: [number, number, number]; affine_ras: number[][] };
  volumes: Record<string, VolumeFile>;
  /** extra volume grids; `cord` is the curved-reformat cord MRI (PAM50 in the private edition, the
   *  composed template in the public one), absent until atlas-pam50 / atlas-cord-public has run */
  grids?: { cord?: ExtraGrid };
  transforms: Record<string, unknown>;
  systems: { id: SystemId; name: string; colour: string; defaultVisible: boolean }[];
  licenses: Record<string, ManifestLicense>;
  sources: Record<string, ManifestSource>;
  meshes: ManifestMesh[];
}

export interface LabelEntry { meshId: string; structureId: string; name: string; colour: string; system: SystemId; atlas?: string }

/** One spinal level in the cord grid's LUT (labels_spine.json / labels_spine_public.json). */
export interface SpineLevelEntry {
  name: string;                 // "C5"
  region: 'cervical' | 'thoracic' | 'lumbar' | 'sacral';
  regionName: string;           // "Cervical cord (C1-C8)"
  meshId: string;               // the derived.py cord segment block that contains this level
  structureId: string;
  system: SystemId;
  colour: string;               // per-region rostral -> caudal ramp
  zMm?: [number, number];       // world z range of the level on our centreline
  arcMm?: [number, number];     // arc length range along the centreline
  // true when the level was not measured on an image: the public edition's composed cord MRI places the
  // levels below the last rootlet-measured one by the classical cord-segment-to-vertebra rule on the
  // Z-Anatomy vertebral column (atlas-cord-public), and the readout says so.
  estimated?: boolean;
}

export interface SpineRegionEntry { name: string; meshId: string; structureId: string; system: SystemId; levels: string[]; colour: string }

/** Contract with pipeline/atlas_pipeline/pam50.py; referenced from manifest.volumes.labels_spine.lut. */
export interface SpineLabelsJson {
  space: string;
  volume: 'labels_spine';
  source: string;
  note: string;
  regions: Record<string, SpineRegionEntry>;
  lut: Record<string, SpineLevelEntry>;
}

export interface LabelsJson {
  volumes: Record<string, VolumeFile>;
  lut: Record<LabelVolumeKey, Record<string, LabelEntry>>;
  byMesh: Record<string, Partial<Record<LabelVolumeKey, number[]>>>;
}
