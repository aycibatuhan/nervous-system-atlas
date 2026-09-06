import { z } from 'zod';
/** One open-access source, stored as content/bibliography/<id>.json. Every entry must be freely readable online. */
export const BibEntry = z.object({
  id: z.string().regex(/^[a-z0-9]+(-[a-z0-9]+)*$/),
  type: z.enum(['statpearls', 'journal', 'book', 'web']),
  title: z.string().min(3),
  authors: z.array(z.string()).min(1),              // "Ghandili M", "Munakomi S"
  year: z.number().int().min(1990).max(2030),
  container: z.string().min(2),                      // journal or book, e.g. "StatPearls [Internet]"
  publisher: z.string().optional(),                  // e.g. "StatPearls Publishing, Treasure Island (FL)"
  url: z.string().url(),                             // canonical free full-text URL
  nbk: z.string().regex(/^NBK\d+$/).optional(),     // NCBI Bookshelf accession for StatPearls
  doi: z.string().optional(),
  pmid: z.string().regex(/^\d+$/).optional(),
  pmcid: z.string().regex(/^PMC\d+$/).optional(),
  license: z.string().optional(),                    // e.g. "CC BY-NC-ND 4.0"
  accessed: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  verified: z.literal(true),                         // set only after the title was confirmed against the live record (NCBI API / DOI)
  tags: z.array(z.string()).default([]),
});
export type BibEntry = z.infer<typeof BibEntry>;
