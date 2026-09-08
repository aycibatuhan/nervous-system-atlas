import type { App } from '../app.ts';
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

/** Display name of a mesh: its content entry if it has one, otherwise the manifest label. */
export function meshLabel(app: App, meshId: string): DisplayName {
  const mesh = app.registry?.byId.get(meshId) ?? app.manifest.meshes.find((m) => m.id === meshId);
  const sid = app.content?.meshToStructure[meshId] ?? mesh?.structureId ?? null;
  const entry = sid ? (app.content?.structures[sid] as NamedEntry | undefined) : undefined;
  return entryName(entry, mesh?.name ?? meshId);
}
