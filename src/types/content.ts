// Compiled content bundle (public/data/content.json) — produced by scripts/content/build.ts
export interface Citation { book: 'snell' | 'berkowitz'; chapter: number; pages: [number, number]; section?: string; note?: string }
export interface ContentEntryBase { kind: string; id: string; name: string; synonyms?: string[]; summary?: string; citations: Citation[]; status?: string; html?: Record<string, string> }
export interface ContentBundle {
  generated: string;
  sources: Record<string, { cite: string; title: string }>;
  structures: Record<string, ContentEntryBase & Record<string, unknown>>;
  pathways: Record<string, ContentEntryBase & Record<string, unknown>>;
  syndromes: Record<string, ContentEntryBase & Record<string, unknown>>;
  glossary: Record<string, ContentEntryBase & Record<string, unknown>>;
  quiz: Record<string, ContentEntryBase & Record<string, unknown>>;
  topics: Record<string, ContentEntryBase & Record<string, unknown>>;
  meshToStructure: Record<string, string>;
}
