import type { Store } from '../state/store.ts';
import type { AppState, Axis } from '../types/state.ts';

export type Route =
  | { kind: 'home' }
  | { kind: 'structure'; id: string }
  | { kind: 'syndrome'; id: string; step?: number }
  | { kind: 'pathway'; id: string }
  | { kind: 'slice' };

export interface RouteParams { ax?: number; cor?: number; sag?: number; c?: 't1w' | 't2w'; side?: 'l' | 'r' }

export function parseHash(hash: string): { route: Route; params: RouteParams } {
  const h = hash.replace(/^#\/?/, '');
  const [path, query = ''] = h.split('?');
  const q = new URLSearchParams(query);
  const num = (k: string): number | undefined => { const v = q.get(k); if (v === null) return undefined; const n = Number(v); return Number.isFinite(n) ? n : undefined; };
  const params: RouteParams = { ax: num('ax'), cor: num('cor'), sag: num('sag') };
  const c = q.get('c'); if (c === 't1w' || c === 't2w') params.c = c;
  const side = q.get('side'); if (side === 'l' || side === 'r') params.side = side;
  const seg = (path ?? '').split('/').filter(Boolean);
  let route: Route = { kind: 'home' };
  if (seg[0] === 'structure' && seg[1]) route = { kind: 'structure', id: seg[1] };
  else if (seg[0] === 'syndrome' && seg[1]) route = { kind: 'syndrome', id: seg[1], step: num('step') };
  else if (seg[0] === 'pathway' && seg[1]) route = { kind: 'pathway', id: seg[1] };
  else if (seg[0] === 'slice') route = { kind: 'slice' };
  return { route, params };
}

export function serialize(route: Route, params: RouteParams): string {
  let path = '';
  if (route.kind === 'structure') path = `structure/${route.id}`;
  else if (route.kind === 'syndrome') path = `syndrome/${route.id}`;
  else if (route.kind === 'pathway') path = `pathway/${route.id}`;
  else if (route.kind === 'slice') path = 'slice';
  const q = new URLSearchParams();
  if (route.kind === 'syndrome' && route.step !== undefined) q.set('step', String(route.step));
  if (params.ax !== undefined) q.set('ax', String(params.ax));
  if (params.cor !== undefined) q.set('cor', String(params.cor));
  if (params.sag !== undefined) q.set('sag', String(params.sag));
  if (params.c) q.set('c', params.c);
  if (params.side) q.set('side', params.side);
  const qs = q.toString();
  return `#/${path}${qs ? '?' + qs : ''}`;
}

/** Two-way binding: hashchange → handlers; store → location.hash (debounced, replaceState). */
export function bindRouter(store: Store<AppState>, handlers: { onRoute(route: Route, params: RouteParams): void }): () => void {
  let applying = false;
  const apply = () => { applying = true; try { const { route, params } = parseHash(location.hash); handlers.onRoute(route, params); } finally { applying = false; } };
  window.addEventListener('hashchange', apply);
  let timer = 0;
  const unsub = store.subscribe((s) => [s.selectedId, s.syndrome?.id ?? null, s.syndrome?.step ?? -1, s.slices.axial, s.slices.coronal, s.slices.sagittal, s.contrast, s.syndrome ? s.lesionSide : null] as const, (v) => {
    if (applying) return;
    clearTimeout(timer);
    timer = window.setTimeout(() => {
      const [sel, syn, step, ax, cor, sag, c, side] = v;
      const route: Route = syn ? { kind: 'syndrome', id: syn, step: step >= 0 ? step : undefined } : sel ? { kind: 'structure', id: sel } : { kind: 'slice' };
      const hash = serialize(route, { ax, cor, sag, c: c === 't2w' ? 't2w' : undefined, side: syn && side ? side : undefined });
      if (location.hash !== hash) history.replaceState(null, '', hash);
    }, 150);
  }, (a, b) => a.every((x, i) => x === b[i]));
  apply();
  return () => { window.removeEventListener('hashchange', apply); unsub(); };
}
