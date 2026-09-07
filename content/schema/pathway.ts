import { z } from 'zod';
import { Citation, Id, ImagingBlock, MniRef, Side, Status } from './common.ts';

export const Pathway = z.object({
  kind: z.literal('pathway'),
  id: Id,
  name: z.string(),
  synonyms: z.array(z.string()).default([]),
  // Turkish edition: display names per locale (tr = the FIPAT Latin term, as in Turkish medical teaching) and
  // per-locale search synonyms (Wikidata Turkish label, Turkish Wikipedia title and redirects); written by tools/i18n/terms.py apply
  names: z.object({ tr: z.string().min(2).optional() }).optional(),
  synonymsByLang: z.object({ tr: z.array(z.string()).default([]) }).optional(),
  type: z.enum(['ascending', 'descending', 'cerebellar', 'basal-ganglia', 'visual', 'auditory', 'vestibular', 'olfactory', 'gustatory',
    'limbic', 'autonomic', 'oculomotor', 'reflex', 'association', 'commissural']),
  modality: z.string(),
  summary: z.string().min(60),
  origin: z.object({ structures: z.array(z.string()).min(1), note: z.string() }),
  neuronChain: z.array(z.object({ order: z.number().int(), cellBody: z.string(), synapse: z.string() })).min(1),
  decussation: z.object({ level: z.string(), structureId: z.string().optional(), note: z.string() }).nullable(),
  waypoints: z.array(z.object({
    order: z.number().int(), structureId: z.string(), meshId: z.string().optional(), mni: MniRef.optional(),
    sideRelativeToOrigin: z.enum(['ipsilateral', 'contralateral', 'bilateral']), note: z.string().optional(),
  })).min(3),
  termination: z.string(),
  somatotopy: z.string().optional(),
  meshIds: z.array(z.string()).default([]),
  lesionEffectsByLevel: z.array(z.object({ level: z.string(), effects: z.string(), side: Side })).min(2),
  imaging: ImagingBlock.partial({ pathology: true }).optional(),
  clinical: z.object({ pearls: z.array(z.string()).min(1), syndromes: z.array(Id).default([]) }),
  citations: z.array(Citation).min(1),
  status: Status,
});
export type Pathway = z.infer<typeof Pathway>;
