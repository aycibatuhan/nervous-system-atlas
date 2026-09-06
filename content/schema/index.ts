import { z } from 'zod';
import { Structure, CranialNerve } from './structure.ts';
import { Pathway } from './pathway.ts';
import { Syndrome, GlossaryTerm, QuizItem } from './syndrome.ts';
export * from './common.ts';
export { Structure, CranialNerve, Pathway, Syndrome, GlossaryTerm, QuizItem };
export const Entry = z.discriminatedUnion('kind', [Structure, CranialNerve, Pathway, Syndrome, GlossaryTerm, QuizItem]);
export type Entry = z.infer<typeof Entry>;
export const KIND_DIRS: Record<string, string> = { structure: 'structures', 'cranial-nerve': 'cranial-nerves', pathway: 'pathways', syndrome: 'syndromes', glossary: 'glossary', quiz: 'quiz' };
