import { z } from 'zod';
import { Citation, Id, PathologyImaging, Status } from './common.ts';

/** A clinical topic that is not a single structure, pathway or syndrome: development and malformations,
 *  CSF physiology and the blood–brain barrier, neurotransmitter systems, sleep/EEG, epilepsy and headache
 *  localization, dementia patterns, neuromuscular patterns, pediatric syndromes, imaging basics. */
export const Topic = z.object({
  kind: z.literal('topic'),
  id: Id,
  name: z.string().min(2),
  synonyms: z.array(z.string()).default([]),
  category: z.enum(['development', 'physiology', 'neurochemistry', 'electrophysiology', 'approach', 'disease-pattern', 'imaging', 'pediatric', 'infection', 'neoplasm']),
  summary: z.string().min(60).max(1200),
  sections: z.array(z.object({ heading: z.string().min(3).max(120), body: z.string().min(80) })).min(3),
  keyPoints: z.array(z.string().min(10)).min(3),
  /** where in the 3D atlas this topic lives: meshes shown as involved when the topic opens */
  meshIds: z.array(z.string()).default([]),
  imaging: z.object({ normalAppearance: z.string().optional(), pathology: z.array(PathologyImaging).default([]) }).optional(),
  related: z.object({
    structureIds: z.array(z.string()).default([]), pathwayIds: z.array(z.string()).default([]),
    syndromeIds: z.array(z.string()).default([]), topicIds: z.array(z.string()).default([]),
  }).default({ structureIds: [], pathwayIds: [], syndromeIds: [], topicIds: [] }),
  pearls: z.array(z.string()).min(1),
  pitfalls: z.array(z.string()).default([]),
  citations: z.array(Citation).min(1),
  tags: z.array(z.string()).default([]),
  status: Status,
});
export type Topic = z.infer<typeof Topic>;
