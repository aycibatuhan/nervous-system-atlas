import { z } from 'zod';

export const Book = z.enum(['snell', 'berkowitz']);
export const Citation = z.object({
  book: Book,
  chapter: z.number().int().min(1).max(31),
  pages: z.tuple([z.number().int().min(1), z.number().int().min(1)]),   // printed pages, inclusive
  section: z.string().max(120).optional(),
  note: z.string().max(240).optional(),
});
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
