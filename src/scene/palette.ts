import type { ManifestMesh } from '../types/manifest.ts';

/** Physically-based "look" per anatomical system. Colours stay per mesh (catalogue → manifest); this only says how
 *  a surface reacts to light: fresh cortex has a faint wet sheen, vessels are glossy, CSF and dura are translucent. */
export interface Look {
  roughness: number;
  metalness?: number;
  sheen?: number;
  sheenRoughness?: number;
  sheenColor?: string;
  clearcoat?: number;
  clearcoatRoughness?: number;
  envMapIntensity?: number;
  /** override the manifest opacity (used for the CSF spaces and the translucent shell) */
  opacity?: number;
}

const CORTEX: Look = { roughness: 0.58, sheen: 0.22, sheenRoughness: 0.65, sheenColor: '#f3cdc4', clearcoat: 0.08, clearcoatRoughness: 0.6, envMapIntensity: 0.8 };
const WHITE_MATTER: Look = { roughness: 0.62, sheen: 0.18, sheenRoughness: 0.7, sheenColor: '#fff6e8', envMapIntensity: 0.8 };
const NUCLEUS: Look = { roughness: 0.66, sheen: 0.15, sheenRoughness: 0.7, sheenColor: '#f0d0c8', envMapIntensity: 0.8 };
const NERVE: Look = { roughness: 0.5, sheen: 0.25, sheenRoughness: 0.6, sheenColor: '#fff4c8', clearcoat: 0.05, envMapIntensity: 0.9 };
const VESSEL: Look = { roughness: 0.32, clearcoat: 0.55, clearcoatRoughness: 0.22, envMapIntensity: 1.1 };

export const SYSTEM_LOOK: Record<string, Look> = {
  cerebrum: CORTEX,
  'basal-ganglia': NUCLEUS,
  diencephalon: NUCLEUS,
  brainstem: { ...NUCLEUS, roughness: 0.6, sheen: 0.2 },
  cerebellum: { ...CORTEX, roughness: 0.6, sheen: 0.3 },
  'cranial-nerves': NERVE,
  peripheral: NERVE,
  autonomic: NERVE,
  'spinal-cord': { ...NUCLEUS, roughness: 0.58 },
  arteries: VESSEL,
  venous: { ...VESSEL, roughness: 0.36, clearcoat: 0.45 },
  'ventricles-csf': { roughness: 0.18, clearcoat: 0.6, clearcoatRoughness: 0.15, envMapIntensity: 1.2, opacity: 0.55 },
  meninges: { roughness: 0.72, sheen: 0.1, envMapIntensity: 0.6 },
  tracts: { roughness: 0.55, sheen: 0.1, envMapIntensity: 0.7 },
  'arterial-territories': { roughness: 0.85, envMapIntensity: 0.4 },
  envelope: { roughness: 0.45, sheen: 0.6, sheenRoughness: 0.45, sheenColor: '#f6d6cc', clearcoat: 0.1, clearcoatRoughness: 0.5, envMapIntensity: 0.9, opacity: 0.12 },
};

export function lookFor(m: ManifestMesh): Look {
  if (m.system === 'cerebrum' && m.subsystem === 'white-matter') return WHITE_MATTER;
  if (m.system === 'cerebrum' && m.subsystem === 'limbic') return NUCLEUS;
  if (m.system === 'cerebellum' && m.subsystem === 'deep-nuclei') return NUCLEUS;
  if (m.system === 'cerebellum' && m.id.includes('white-matter')) return WHITE_MATTER;
  if (m.system === 'cerebellum' && m.subsystem === 'peduncles') return WHITE_MATTER;
  return SYSTEM_LOOK[m.system] ?? NUCLEUS;
}
