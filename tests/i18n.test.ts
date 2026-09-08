import { describe, expect, it } from 'vitest';
import { en } from '../src/i18n/en.ts';
import { tr } from '../src/i18n/tr.ts';
import { entryName, getLocale, t } from '../src/i18n/index.ts';

describe('interface strings', () => {
  it('has a Turkish string for every English key, and no empty ones beyond the deliberate joins', () => {
    const enKeys = Object.keys(en).sort();
    expect(Object.keys(tr).sort()).toEqual(enKeys);
    const joins = new Set(['about.dataNote.c', 'content.noContent.before']);
    for (const k of enKeys) if (!joins.has(k)) expect((tr as Record<string, string>)[k], k).not.toBe('');
  });
  it('keeps the {placeholders} of each English string in the Turkish one', () => {
    const vars = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
    for (const [k, v] of Object.entries(en)) expect(vars((tr as Record<string, string>)[k]!), k).toEqual(vars(v));
  });
  it('interpolates and falls back to English', () => {
    expect(getLocale()).toBe('en');                       // no hash, no storage, no tr navigator in vitest
    expect(t('status.structures', { n: 662 })).toBe('662 structures');
    expect(t('quiz.title', { n: 1, total: 60 })).toBe('Clinical vignette 1 of 60');
  });
});

describe('entryName', () => {
  const brainstem = { name: 'Brainstem', latin: 'Truncus encephali', names: { tr: 'Truncus encephali' } };
  it('leaves English alone', () => {
    expect(entryName(brainstem, '', 'en')).toEqual({ primary: 'Brainstem', secondary: null });
  });
  it('puts the Latin term first in Turkish, English underneath', () => {
    expect(entryName(brainstem, '', 'tr')).toEqual({ primary: 'Truncus encephali', secondary: 'Brainstem' });
    expect(entryName({ name: 'Insula', latin: 'Insula' }, '', 'tr')).toEqual({ primary: 'Insula', secondary: null });
    expect(entryName({ name: 'Wallenberg syndrome' }, '', 'tr')).toEqual({ primary: 'Wallenberg syndrome', secondary: null });
    expect(entryName(undefined, 'amygdala-l', 'tr')).toEqual({ primary: 'amygdala-l', secondary: null });
  });
});
