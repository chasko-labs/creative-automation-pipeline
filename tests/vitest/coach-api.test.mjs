import { describe, expect, it, vi, beforeEach } from 'vitest';
import { handler } from '../../coach/index.mjs';

const post = (path, body, origin = 'https://kodiak.bryanchasko.com') => ({
  requestContext: { http: { method: 'POST', path } },
  headers: { origin },
  body: JSON.stringify(body),
});

const converseOk = (text) =>
  Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve({ output: { message: { content: [{ text }] } } }),
  });

beforeEach(() => {
  vi.unstubAllGlobals();
  delete process.env.AWS_ACCESS_KEY_ID;
  delete process.env.AWS_SECRET_ACCESS_KEY;
});

describe('coach handler', () => {
  it('insights requires a brief (400, no model call)', async () => {
    const f = vi.fn();
    vi.stubGlobal('fetch', f);
    const r = await handler(post('/insights', { brief: '  ', theme: 'wild-grizzly-bears' }));
    expect(r.statusCode).toBe(400);
    expect(f).not.toHaveBeenCalled();
  });

  it('insights returns parsed bullets', async () => {
    process.env.AWS_ACCESS_KEY_ID = 'x';
    process.env.AWS_SECRET_ACCESS_KEY = 'y';
    vi.stubGlobal('fetch', () => converseOk('["a seed fits", "theme did x", "try costco next"]'));
    const r = await handler(post('/insights', { brief: 'wild mornings', theme: 'wild-grizzly-bears', market: 'us' }));
    expect(r.statusCode).toBe(200);
    expect(JSON.parse(r.body).insights).toHaveLength(3);
  });

  it('ask returns answer plus strict-shape edits only', async () => {
    process.env.AWS_ACCESS_KEY_ID = 'x';
    process.env.AWS_SECRET_ACCESS_KEY = 'y';
    vi.stubGlobal('fetch', () =>
      converseOk('{"answer": "toggle the costco chip", "edits": [{"op": "toggle-chip", "target": "localized-costco", "label": "Costco"}, {"op": "nuke", "target": "x"}, {"op": "append-brief"}]}'));
    const r = await handler(post('/ask', { question: 'how do i get a costco version', pageState: {} }));
    expect(r.statusCode).toBe(200);
    const b = JSON.parse(r.body);
    expect(b.answer).toMatch(/costco/i);
    expect(b.edits).toEqual([{ op: 'toggle-chip', target: 'localized-costco', label: 'Costco' }]);
  });

  it('ask rejects empty questions without calling the model', async () => {
    const f = vi.fn();
    vi.stubGlobal('fetch', f);
    const r = await handler(post('/ask', { question: ' ' }));
    expect(r.statusCode).toBe(400);
    expect(f).not.toHaveBeenCalled();
  });

  it('throttling maps to honest 503, validation to 500', async () => {
    process.env.AWS_ACCESS_KEY_ID = 'x';
    process.env.AWS_SECRET_ACCESS_KEY = 'y';
    vi.stubGlobal('fetch', () => Promise.resolve({ ok: false, status: 429 }));
    const r1 = await handler(post('/ask', { question: 'hi' }));
    expect(r1.statusCode).toBe(503);
    expect(JSON.parse(r1.body).error).toMatch(/busy/);
    vi.stubGlobal('fetch', () => Promise.resolve({ ok: false, status: 400 }));
    const r2 = await handler(post('/ask', { question: 'hi' }));
    expect(r2.statusCode).toBe(500);
  });

  it('unknown path falls through to insights', async () => {
    process.env.AWS_ACCESS_KEY_ID = 'x';
    process.env.AWS_SECRET_ACCESS_KEY = 'y';
    vi.stubGlobal('fetch', () => converseOk('["one"]'));
    const r = await handler(post('/', { brief: 'wild mornings' }));
    expect(r.statusCode).toBe(200);
    expect(JSON.parse(r.body).insights).toEqual(['one']);
  });

  it('disallowed origin still answers with default CORS host', async () => {
    process.env.AWS_ACCESS_KEY_ID = 'x';
    process.env.AWS_SECRET_ACCESS_KEY = 'y';
    vi.stubGlobal('fetch', () => converseOk('["one"]'));
    const r = await handler(post('/insights', { brief: 'b' }, 'https://evil.example'));
    expect(r.statusCode).toBe(200);
    expect(r.headers['access-control-allow-origin']).toBe('https://kodiak.bryanchasko.com');
  });
});
