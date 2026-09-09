import type { LabelsJson, Manifest } from '../types/manifest.ts';

export const DATA_URL = 'data/';

/**
 * The atlas data is not in the repository — it is built by the pipeline or fetched from a release — so a
 * fresh clone reaches the app with public/data/ empty. That is a setup step the reader has not done yet,
 * not a bug, and it gets its own message; every other failure keeps the generic one.
 */
export class MissingDataError extends Error {
  constructor(readonly detail: string) {
    super(`no atlas data (${detail})`);
    this.name = 'MissingDataError';
  }
}

/** True for a response that is really the dev server's SPA fallback page rather than the file we asked for. */
function isFallbackHtml(res: Response, body: string): boolean {
  return (res.headers.get('content-type') ?? '').includes('text/html') || /^\s*<(?:!doctype|html)/i.test(body);
}

export async function loadManifest(): Promise<Manifest> {
  const url = DATA_URL + 'manifest.json';
  const r = await fetch(url);
  // Two different shapes mean the same thing. A built site (or `vite preview`) 404s a file it does not have,
  // but `vite dev` answers any unknown path with index.html — so on a fresh clone this request succeeds with
  // 200 and a page of HTML, and the old code died on `JSON.parse` with "Unexpected token '<'".
  if (r.status === 404) throw new MissingDataError(`${url} → 404`);
  if (!r.ok) throw new Error(`manifest.json: ${r.status}`);
  const body = await r.text();
  if (isFallbackHtml(r, body)) throw new MissingDataError(`${url} → HTML instead of JSON`);
  let m: Manifest;
  try {
    m = JSON.parse(body) as Manifest;
  } catch {
    throw new Error('manifest.json: not valid JSON');
  }
  if (m.schema !== 1 || !Array.isArray(m.meshes)) throw new Error('manifest.json: unexpected schema');
  return m;
}

export async function loadLabels(): Promise<LabelsJson> {
  const r = await fetch(DATA_URL + 'volumes/labels.json');
  if (!r.ok) throw new Error(`labels.json: ${r.status}`);
  return (await r.json()) as LabelsJson;
}
