import { getLocale, t, type DisplayName } from '../i18n/index.ts';

type Child = Node | string | null | undefined | false;
export function h<K extends keyof HTMLElementTagNameMap>(tag: K, attrs: Record<string, unknown> = {}, ...children: Child[]): HTMLElementTagNameMap[K] {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === undefined || v === null || v === false) continue;
    if (k === 'class') el.className = String(v);
    else if (k === 'style') el.setAttribute('style', String(v));
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2).toLowerCase(), v as EventListener);
    else if (k === 'dataset') Object.assign(el.dataset, v as Record<string, string>);
    else if (k in el && typeof v !== 'string') (el as unknown as Record<string, unknown>)[k] = v;
    else el.setAttribute(k, String(v));
  }
  for (const c of children) if (c !== null && c !== undefined && c !== false) el.append(c instanceof Node ? c : document.createTextNode(c));
  return el;
}
export function clear(el: Element): void { while (el.firstChild) el.removeChild(el.firstChild); }

/** In Turkish mode, the pill that marks a prose block still shown in English. Null in English mode. */
export function enTag(): HTMLElement | null {
  return getLocale() === 'tr' ? h('span', { class: 'tag lang-en', title: t('tag.langEn.title') }, t('tag.langEn')) : null;
}

/** The muted English name printed under a Latin/Turkish primary name (null when there is nothing to add). */
export function secondaryName(n: DisplayName): HTMLElement | null {
  return n.secondary ? h('span', { class: 'name-secondary' }, n.secondary) : null;
}
