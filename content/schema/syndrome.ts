import { z } from 'zod';
import { Citation, Id, ImagingHint, MniRef, PathologyImaging, Side, Status } from './common.ts';

export const Deficit = z.object({
  modality: z.enum(['motor', 'sensory-pain-temp', 'sensory-vibration-proprioception', 'sensory-light-touch', 'visual-field', 'visual-acuity',
    'oculomotor', 'pupil', 'auditory', 'vestibular', 'cerebellar', 'autonomic', 'language', 'cognitive', 'neglect', 'cranial-nerve', 'bulbar',
    'sphincter', 'reflex', 'gait', 'consciousness', 'pain', 'other']),
  side: Side,
  distribution: z.string(),
  sign: z.string(),
  substrate: z.string().optional(),       // structure / pathway id responsible
});

export const Syndrome = z.object({
  kind: z.literal('syndrome'),
  id: Id,
  name: z.string(),
  eponyms: z.array(z.string()).default([]),
  category: z.enum(['vascular', 'lacunar', 'compressive', 'herniation', 'csf-pressure', 'demyelinating', 'traumatic', 'infectious', 'neoplastic',
    'degenerative', 'entrapment', 'radiculopathy', 'plexopathy', 'neuromuscular', 'metabolic-toxic', 'congenital', 'functional-pattern', 'neuro-ophthalmic', 'otologic']),
  tier: z.enum(['core', 'extended']),
  localisation: z.object({
    structures: z.array(z.string()).min(1), side: Side, level: z.string().optional(),
    arteryId: z.string().optional(), territoryId: z.string().optional(),
  }),
  lesionMarker: z.object({
    kind: z.enum(['sphere', 'territory', 'segment', 'nerve', 'structures']),
    mni: MniRef.optional(), radiusMm: z.number().optional(), meshIds: z.array(z.string()).optional(),
  }),
  presentation: z.string().min(80),
  deficits: z.array(Deficit).min(2),
  reasoning: z.string().min(300),
  imagingFindings: z.array(PathologyImaging).min(1),
  imagingHint: ImagingHint.optional(),
  commonCauses: z.array(z.string()).min(1),
  mimics: z.array(z.object({ name: z.string(), howToDistinguish: z.string() })).min(1),
  management: z.array(z.string()).max(6).default([]),
  examSequence: z.array(z.string()).optional(),
  cameraPreset: z.enum(['lateral-r', 'lateral-l', 'medial-r', 'medial-l', 'anterior', 'posterior', 'superior', 'inferior']).optional(),
  citations: z.array(Citation).min(1),
  status: Status,
});
export type Syndrome = z.infer<typeof Syndrome>;

export const GlossaryTerm = z.object({
  kind: z.literal('glossary'), id: Id, term: z.string(), definition: z.string().min(30).max(700),
  related: z.array(z.string()).default([]), citations: z.array(Citation).default([]),
});
export const QuizItem = z.object({
  kind: z.literal('quiz'), id: Id, type: z.enum(['localise', 'identify', 'imaging', 'mechanism']),
  vignette: z.string().min(80), stem: z.string(),
  options: z.array(z.object({ key: z.enum(['A', 'B', 'C', 'D', 'E']), text: z.string() })).min(4),
  answer: z.enum(['A', 'B', 'C', 'D', 'E']), explanation: z.string().min(80),
  targets: z.object({ structureIds: z.array(z.string()).default([]), syndromeIds: z.array(z.string()).default([]), pathwayIds: z.array(z.string()).default([]) }),
  highlightOnReveal: z.array(z.string()).default([]), difficulty: z.enum(['1', '2', '3']), citations: z.array(Citation).min(1), original: z.literal(true),
});
