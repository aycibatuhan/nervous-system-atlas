import { h } from './dom.ts';
import type { BibEntry, Citation } from '../types/content.ts';

/** "Authors. Title. Container Year." — the plain-text form of one bibliography entry. */
export function citeText(b: BibEntry | undefined, c: Citation): string {
  if (!b) return c.ref;
  const authors = b.authors.length > 3 ? `${b.authors.slice(0, 3).join(', ')}, et al.` : b.authors.join(', ');
  return `${authors ? authors.replace(/\.$/, '') + '. ' : ''}${b.title}. ${b.container} ${b.year}.`;
}

/** Accession shown after the citation so the source is identifiable offline. */
export function citeId(b: BibEntry | undefined): string {
  if (!b) return '';
  if (b.nbk) return b.nbk;
  if (b.pmcid) return b.pmcid;
  if (b.doi) return `doi:${b.doi}`;
  if (b.pmid) return `PMID ${b.pmid}`;
  return '';
}

/** One rendered citation: a link to the free full text, plus the cited section and the NBK/PMC id. */
export function citeNode(bibliography: Record<string, BibEntry> | undefined, c: Citation): HTMLElement {
  const b = bibliography?.[c.ref];
  const label = citeText(b, c);
  const id = citeId(b);
  return h('span', { class: 'cite' },
    b ? h('a', { href: b.url, target: '_blank', rel: 'noopener noreferrer' }, label) : h('span', {}, label),
    c.section ? h('span', { class: 'cite-section' }, ` ${c.section}.`) : null,
    id ? h('span', { class: 'muted small cite-id' }, ` ${id}`) : null,
    c.note ? h('span', { class: 'muted small' }, ` — ${c.note}`) : null,
  );
}

/** Flat text form (for places that cannot hold markup, e.g. the quiz "Sources:" line). */
export function citeLine(bibliography: Record<string, BibEntry> | undefined, c: Citation): string {
  const b = bibliography?.[c.ref];
  const id = citeId(b);
  return `${citeText(b, c)}${c.section ? ` ${c.section}.` : ''}${id ? ` ${id}` : ''}`;
}
