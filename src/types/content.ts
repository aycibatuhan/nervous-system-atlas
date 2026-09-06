// Compiled content bundle (public/data/content.json) — produced by scripts/content/build.ts
/** A citation points at a bibliography entry (content/bibliography/<ref>.json), never at a printed book. */
export interface Citation { ref: string; section?: string; note?: string }
export interface BibEntry {
  id: string; type: 'statpearls' | 'journal' | 'book' | 'web'; title: string; authors: string[]; year: number;
  container: string; publisher?: string; url: string; nbk?: string; doi?: string; pmid?: string; pmcid?: string;
  license?: string; accessed: string; verified: true; tags: string[];
}
export interface ContentEntryBase { kind: string; id: string; name: string; synonyms?: string[]; summary?: string; citations: Citation[]; status?: string; html?: Record<string, string> }
export interface ContentBundle {
  generated: string;
  bibliography: Record<string, BibEntry>;
  structures: Record<string, ContentEntryBase & Record<string, unknown>>;
  pathways: Record<string, ContentEntryBase & Record<string, unknown>>;
  syndromes: Record<string, ContentEntryBase & Record<string, unknown>>;
  glossary: Record<string, ContentEntryBase & Record<string, unknown>>;
  quiz: Record<string, ContentEntryBase & Record<string, unknown>>;
  topics: Record<string, ContentEntryBase & Record<string, unknown>>;
  meshToStructure: Record<string, string>;
}
