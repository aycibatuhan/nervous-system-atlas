import { z } from 'zod';

/** Open-access citation: `ref` is a file name in content/bibliography/<ref>.json (StatPearls chapter, open-access review, open textbook). */
export const RefCitation = z.object({
  ref: z.string().regex(/^[a-z0-9]+(-[a-z0-9]+)*$/, 'kebab-case bibliography id'),
  section: z.string().max(160).optional(),   // section of the cited work, e.g. "Structure and Function"
  note: z.string().max(240).optional(),
}).strict();
export const Citation = RefCitation;
export type Citation = z.infer<typeof Citation>;

export const Side = z.enum(['left', 'right', 'bilateral', 'ipsilateral', 'contralateral', 'midline', 'n/a']);
export const Mni = z.object({ x: z.number(), y: z.number(), z: z.number() });
export const MniRef = z.union([Mni, z.object({ meshId: z.string(), offset: Mni.optional() })]);
export const Plane = z.enum(['axial', 'coronal', 'sagittal']);
export const Modality = z.enum(['CT', 'CTA', 'CTV', 'CT perfusion', 'MRI', 'MRA', 'MRV', 'DSA', 'PET', 'SPECT', 'US', 'EMG/NCS', 'EEG', 'LP/CSF']);
export const Sequence = z.enum(['T1', 'T2', 'FLAIR', 'DWI', 'ADC', 'SWI', 'GRE', 'T1+Gd', 'STIR', 'T2*', 'CT non-contrast', 'CT contrast', 'TOF', 'n/a']);

export const ImagingHint = z.object({ plane: Plane, mni: MniRef, label: z.string().max(140) });
export const PathologyImaging = z.object({
  pathology: z.string().max(120),
  modality: Modality,
  sequence: Sequence.optional(),
  finding: z.string().min(40),
  timing: z.string().max(240).optional(),
  pitfalls: z.string().max(400).optional(),
});
export const ImagingBlock = z.object({
  bestView: z.array(ImagingHint).min(1).max(4),
  normalAppearance: z.string().min(60),
  pathology: z.array(PathologyImaging).min(1),
  sequenceOfChoice: z.string().max(300).optional(),
});
export const Status = z.enum(['draft', 'reviewed']);
export const Id = z.string().regex(/^[a-z0-9]+(-[a-z0-9]+)*$/, 'kebab-case id');

export const SystemId = z.enum(['cerebrum', 'basal-ganglia', 'diencephalon', 'brainstem', 'cerebellum', 'cranial-nerves', 'spinal-cord',
  'peripheral', 'autonomic', 'ventricles-csf', 'meninges', 'arteries', 'arterial-territories', 'venous', 'tracts', 'envelope']);
export const BrainstemLevel = z.enum(['medulla-pyramidal-decussation', 'medulla-sensory-decussation', 'medulla-olive', 'medulla-rostral',
  'pons-caudal', 'pons-rostral', 'midbrain-inferior-colliculus', 'midbrain-superior-colliculus']);
