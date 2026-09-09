import type { App } from '../app.ts';
import type { ContentBundle, ContentEntryBase } from '../types/content.ts';
import { en } from './en.ts';
import { tr } from './tr.ts';

export type Locale = 'en' | 'tr';
export const LOCALES: Locale[] = ['en', 'tr'];
/** Every interface string key; `tr.ts` is typed against it, so a missing translation fails typecheck. */
export type Key = keyof typeof en;

const TABLES: Record<Locale, Record<string, string>> = { en, tr };
export const LOCALE_KEY = 'atlas.locale';

function isLocale(v: unknown): v is Locale { return v === 'en' || v === 'tr'; }

/** hash `lang` > localStorage > browser language > English. */
function resolve(): Locale {
  try {
    const q = (location.hash.split('?')[1] ?? '');
    const fromHash = new URLSearchParams(q).get('lang');
    if (isLocale(fromHash)) return fromHash;
  } catch { /* no location (unit tests) */ }
  try { const s = localStorage.getItem(LOCALE_KEY); if (isLocale(s)) return s; } catch { /* private mode */ }
  try { if (navigator.language.toLowerCase().startsWith('tr')) return 'tr'; } catch { /* no navigator */ }
  return 'en';
}

let current: Locale = resolve();
try { document.documentElement.lang = current; } catch { /* no document */ }

const listeners = new Set<(l: Locale) => void>();

export function getLocale(): Locale { return current; }

/** Keep `lang` in the hash without disturbing the route or the other params. */
function writeHashLang(l: Locale): void {
  try {
    const raw = location.hash || '#/';
    const [path, query = ''] = raw.replace(/^#/, '').split('?');
    const q = new URLSearchParams(query);
    if (l === 'en') q.delete('lang'); else q.set('lang', l);
    const qs = q.toString();
    const next = `#${path || '/'}${qs ? '?' + qs : ''}`;
    if (location.hash !== next) history.replaceState(null, '', next);
  } catch { /* no location */ }
}

/**
 * Switch the interface language. Writes the hash and localStorage, moves `<html lang>` and tells
 * every listener; main.ts turns that into `AppState.locale`, which is what the panels re-render from.
 */
export function setLocale(l: Locale): void {
  if (!isLocale(l)) return;
  const changed = l !== current;
  current = l;
  try { localStorage.setItem(LOCALE_KEY, l); } catch { /* private mode */ }
  try { document.documentElement.lang = l; } catch { /* no document */ }
  writeHashLang(l);
  if (changed) for (const cb of Array.from(listeners)) cb(l);
}

export function onLocaleChange(cb: (l: Locale) => void): () => void {
  listeners.add(cb);
  return () => { listeners.delete(cb); };
}

/** One interface string, with `{name}` placeholders filled in. Falls back to English, then to the key. */
export function t(key: Key, vars?: Record<string, string | number>): string {
  const s = TABLES[current][key] ?? (en as Record<string, string>)[key] ?? key;
  return vars ? s.replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? String(vars[k]) : m)) : s;
}

/** The other locale — what the toolbar switch offers. */
export function otherLocale(l: Locale = current): Locale { return l === 'en' ? 'tr' : 'en'; }

export interface DisplayName {
  /** what to print as the name */
  primary: string;
  /** the English name, when the primary is not it (Turkish mode only); null otherwise */
  secondary: string | null;
}

export interface NamedEntry { name: string; latin?: string; names?: { tr?: string } }

/**
 * Display name of a content entry. Turkish medical teaching names structures in Latin, so in `tr`
 * the primary line is `names.tr ?? latin ?? name` and the English name goes underneath; in `en`
 * nothing changes (the panels keep showing `latin` in the crumbs).
 */
export function entryName(e: NamedEntry | undefined | null, fallback = '', locale: Locale = current): DisplayName {
  const name = (e?.name ?? '') || fallback;
  if (locale !== 'tr') return { primary: name, secondary: null };
  const primary = e?.names?.tr ?? e?.latin ?? name;
  return { primary, secondary: name && name !== primary ? name : null };
}

export type EntryKind = 'structures' | 'pathways' | 'syndromes' | 'glossary' | 'quiz' | 'topics';
export type Rec = ContentEntryBase & Record<string, unknown>;

/** One content entry in the current language: the translated copy when the locale is Turkish and content.tr.json has it, else the English one. */
export function entryOf(app: App, kind: EntryKind, id: string): Rec | undefined {
  if (current === 'tr') { const tr = (app.contentTr?.[kind] as Record<string, Rec> | undefined)?.[id]; if (tr) return tr; }
  return (app.content?.[kind] as Record<string, Rec> | undefined)?.[id];
}

/** Every entry of a kind in the current language (English entries stand in for the untranslated ones). */
export function entriesOf(app: App, kind: EntryKind): Record<string, Rec> {
  const base = (app.content?.[kind] as Record<string, Rec> | undefined) ?? {};
  if (current !== 'tr' || !app.contentTr) return base;
  const tr = (app.contentTr[kind] as Record<string, Rec> | undefined) ?? {};
  const out: Record<string, Rec> = {};
  for (const [id, e] of Object.entries(base)) out[id] = tr[id] ?? e;
  return out;
}

/** True when this entry's prose is in the interface language (English mode, or a translated entry). */
export function isTranslated(e: { lang?: string } | undefined | null): boolean { return current !== 'tr' || e?.lang === 'tr'; }
export type { ContentBundle };

/**
 * A trailing side marker as the manifest writes it: `(L)`, `(R)`, or `(L, AAN atlas)` where the parenthesis
 * carries something else too. Matched so it can be stripped and re-added in the interface language.
 */
const SIDE_TAIL = /\s*\((?:L|R)(?:,\s*([^)]*))?\)\s*$/i;

/**
 * Put the side into a display name.
 *
 * The two members of a pair share one content entry -- `caudate-nucleus-l` and `-r` both resolve to
 * `caudate-nucleus` -- so a name taken from the entry has no side in it and the tree printed "Caudate nucleus"
 * twice. The mesh record always knows: `side` is "left" or "right". The manifest's own name carries a marker
 * too, but only in English, so any existing one is stripped and rewritten in the current language.
 */
function withSide(n: DisplayName, side: string | undefined): DisplayName {
  if (side !== 'left' && side !== 'right') return n;
  const put = (s: string, mark: string): string => {
    const rest = SIDE_TAIL.exec(s)?.[1];
    const base = s.replace(SIDE_TAIL, '').trim();
    return rest ? `${base} (${mark}, ${rest})` : `${base} (${mark})`;
  };
  const key = side === 'left' ? 'side.l' : 'side.r';
  // the secondary line is the English name, so it keeps the English marker
  return { primary: put(n.primary, t(key)), secondary: n.secondary ? put(n.secondary, en[key]) : null };
}

/** Display name of a mesh: its content entry if it has one, otherwise the manifest label, plus its side. */
export function meshLabel(app: App, meshId: string): DisplayName {
  const mesh = app.registry?.byId.get(meshId) ?? app.manifest.meshes.find((m) => m.id === meshId);
  const sid = app.content?.meshToStructure[meshId] ?? mesh?.structureId ?? null;
  const entry = sid ? (app.content?.structures[sid] as NamedEntry | undefined) : undefined;
  return withSide(entryName(entry, mesh?.name ?? meshId), mesh?.side);
}
