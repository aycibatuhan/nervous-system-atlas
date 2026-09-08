import { describe, expect, it } from 'vitest';
import { parseHash, serialize } from '../src/router/hashRouter.ts';

describe('hash router', () => {
  it('parses structure routes with slice params', () => {
    const { route, params } = parseHash('#/structure/putamen-l?ax=2&cor=4&sag=-24&c=t2w');
    expect(route).toEqual({ kind: 'structure', id: 'putamen-l' });
    expect(params).toEqual({ ax: 2, cor: 4, sag: -24, c: 't2w' });
  });
  it('parses syndrome step and tolerates junk', () => {
    expect(parseHash('#/syndrome/syn-wallenberg-lateral-medullary?step=2&ax=abc').route).toEqual({ kind: 'syndrome', id: 'syn-wallenberg-lateral-medullary', step: 2 });
    expect(parseHash('').route).toEqual({ kind: 'home' });
    expect(parseHash('#/nonsense/x').route).toEqual({ kind: 'home' });
  });
  it('carries the interface language in the hash', () => {
    const { route, params } = parseHash('#/structure/brainstem?lang=tr');
    expect(route).toEqual({ kind: 'structure', id: 'brainstem' });
    expect(params.lang).toBe('tr');
    expect(parseHash('#/structure/brainstem?lang=de').params.lang).toBeUndefined();
    expect(parseHash('#/structure/brainstem').params.lang).toBeUndefined();
    const h = serialize({ kind: 'structure', id: 'brainstem' }, { lang: 'tr' });
    expect(h).toBe('#/structure/brainstem?lang=tr');
    expect(parseHash(h).params.lang).toBe('tr');
    // it survives next to the slice params, and English (the default) leaves no trace
    const both = serialize({ kind: 'syndrome', id: 'syn-x', step: 2 }, { ax: 10, c: 't2w', side: 'l', lang: 'tr' });
    expect(parseHash(both)).toEqual({ route: { kind: 'syndrome', id: 'syn-x', step: 2 }, params: { ax: 10, c: 't2w', side: 'l', lang: 'tr' } });
    expect(serialize({ kind: 'slice' }, {})).toBe('#/slice');
  });
  it('round-trips', () => {
    const h = serialize({ kind: 'structure', id: 'thalamus-r' }, { ax: 10, cor: -18, sag: 12 });
    expect(h).toBe('#/structure/thalamus-r?ax=10&cor=-18&sag=12');
    expect(parseHash(h).route).toEqual({ kind: 'structure', id: 'thalamus-r' });
  });
});
