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

export interface Manifest {
  schema: 1;
  generated: string;
  space: 'MNI152NLin2009cAsym';
  grid: { shape: [number, number, number]; spacing: [number, number, number]; origin_ras: [number, number, number]; affine_ras: number[][] };
  volumes: Record<string, VolumeFile>;
  /** extra volume grids; `cord` is the PAM50 curved-reformat cord MRI, absent until atlas-pam50 has run */
  grids?: { cord?: ExtraGrid };
  transforms: Record<string, unknown>;
  systems: { id: SystemId; name: string; colour: string; defaultVisible: boolean }[];
  licenses: Record<string, { name: string; url: string; attribution: string; nc: boolean; text: string }>;
  sources: Record<string, { license: string; citation: string; files: Record<string, string | null> }>;
  meshes: ManifestMesh[];
}

export interface LabelEntry { meshId: string; structureId: string; name: string; colour: string; system: SystemId; atlas?: string }

export interface LabelsJson {
  volumes: Record<string, VolumeFile>;
  lut: Record<LabelVolumeKey, Record<string, LabelEntry>>;
  byMesh: Record<string, Partial<Record<LabelVolumeKey, number[]>>>;
}
