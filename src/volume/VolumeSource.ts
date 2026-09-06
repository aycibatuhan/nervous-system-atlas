import type { VolumeFile } from '../types/manifest.ts';
import { DATA_URL } from '../loader/manifest.ts';

export interface VolumeData { dims: [number, number, number]; data: Uint8Array | Uint16Array }

/** Fetch a volume file; the payload is gzip-compressed (magic 1f 8b) unless the server already decoded it. */
async function fetchGunzip(url: string, onProgress?: (frac: number) => void): Promise<ArrayBuffer> {
  const r = await fetch(url);
  if (!r.ok || !r.body) throw new Error(`${url}: ${r.status}`);
  const total = Number(r.headers.get('content-length') ?? 0);
  let seen = 0;
  const reader = r.body.getReader();
  const chunks: Uint8Array[] = [];
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value); seen += value.byteLength;
    if (total && onProgress) onProgress(seen / total);
  }
  const raw = new Uint8Array(seen); let o = 0; for (const c of chunks) { raw.set(c, o); o += c.byteLength; }
  if (raw[0] !== 0x1f || raw[1] !== 0x8b) return raw.buffer;
  const ds = new DecompressionStream('gzip') as unknown as ReadableWritablePair<Uint8Array, Uint8Array>;
  return new Response(new Blob([raw]).stream().pipeThrough(ds)).arrayBuffer();
}

export async function loadRawVolume(meta: VolumeFile, onProgress?: (frac: number) => void): Promise<VolumeData> {
  const buf = await fetchGunzip(DATA_URL + meta.file, onProgress);
  const expected = meta.shape[0] * meta.shape[1] * meta.shape[2] * (meta.dtype === 'uint16' ? 2 : 1);
  if (buf.byteLength !== expected) throw new Error(`${meta.file}: got ${buf.byteLength} bytes, expected ${expected}`);
  const data = meta.dtype === 'uint16' ? new Uint16Array(buf) : new Uint8Array(buf);
  return { dims: meta.shape, data };
}
