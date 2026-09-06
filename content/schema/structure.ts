import { z } from 'zod';
import { BrainstemLevel, Citation, Id, ImagingBlock, Side, Status, SystemId } from './common.ts';

export const Structure = z.object({
  kind: z.literal('structure'),
  id: Id,
  name: z.string().min(2),
  synonyms: z.array(z.string()).default([]),
  latin: z.string().optional(),
  system: SystemId,
  subsystem: z.string().optional(),
  parent: Id.optional(),
  meshIds: z.array(z.string()).default([]),          // manifest mesh ids (may be empty for virtual structures)
  level: z.object({
    region: z.enum(['medulla', 'pons', 'midbrain', 'spinal', 'supratentorial', 'infratentorial', 'peripheral']),
    sub: z.union([BrainstemLevel, z.string()]).optional(),
  }).optional(),
  summary: z.string().min(60).max(1200),
  anatomy: z.object({
    location: z.string().min(40),
    boundaries: z.string().optional(),
    subdivisions: z.array(z.object({ name: z.string(), note: z.string() })).default([]),
    relations: z.object({ anterior: z.string(), posterior: z.string(), medial: z.string(), lateral: z.string(), superior: z.string(), inferior: z.string() }).partial().optional(),
  }),
  connections: z.object({
    afferents: z.array(z.object({ from: z.string(), via: z.string().optional(), note: z.string().optional() })).default([]),
    efferents: z.array(z.object({ to: z.string(), via: z.string().optional(), note: z.string().optional() })).default([]),
    pathways: z.array(Id).default([]),
  }).default({ afferents: [], efferents: [], pathways: [] }),
  function: z.string().min(40),
  bloodSupply: z.object({
    arteries: z.array(z.string()).min(1),          // artery structure ids (authored later) or plain names
    territories: z.array(z.string()).default([]),  // territory mesh/structure ids
    venous: z.string().optional(),
    note: z.string().optional(),
  }),
  imaging: ImagingBlock,
  clinical: z.object({
    lesionEffects: z.array(z.object({ deficit: z.string(), side: Side, mechanism: z.string() })).min(1),
    examination: z.array(z.string()).min(1),
    syndromes: z.array(Id).default([]),
    pearls: z.array(z.string()).min(1),
  }),
  pitfalls: z.array(z.string()).default([]),
  citations: z.array(Citation).min(1),
  tags: z.array(z.string()).default([]),
  status: Status,
});
export type Structure = z.infer<typeof Structure>;

export const CranialNerve = Structure.extend({
  kind: z.literal('cranial-nerve'),
  cranial: z.object({
    number: z.number().int().min(1).max(12),
    roman: z.string(),
    components: z.array(z.enum(['GSE', 'GVE', 'SVE', 'GSA', 'GVA', 'SVA', 'SSA'])).min(1),
    nuclei: z.array(z.object({ structureId: z.string(), component: z.string(), level: z.string() })).min(1),
    ganglia: z.array(z.object({ name: z.string(), type: z.enum(['sensory', 'parasympathetic', 'sympathetic']), structureId: z.string().optional() })).default([]),
    exit: z.object({ brainstemExit: z.string(), cisternalCourse: z.string(), foramen: z.string(), extracranialCourse: z.string() }),
    branches: z.array(z.object({ name: z.string(), supplies: z.string() })).default([]),
    reflexes: z.array(z.object({ name: z.string(), afferent: z.string(), center: z.string(), efferent: z.string() })).default([]),
    tests: z.array(z.object({ name: z.string(), how: z.string(), normal: z.string(), abnormal: z.string() })).min(1),
    lesionSigns: z.array(z.object({ sign: z.string(), localisingValue: z.string() })).min(2),
    nuclearVsPeripheral: z.string().optional(),
    supranuclear: z.string().optional(),
  }),
});
export type CranialNerve = z.infer<typeof CranialNerve>;
