import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const coach = readFileSync(resolve(root, 'coach/index.mjs'), 'utf8');

// SigV4 canonical URI must double-encode the % from encodeURIComponent
// (botocore/AWS server behavior); the wire URL stays single-encoded.
// Without this every Bedrock call fails SignatureDoesNotMatch (HTTP 403),
// surfacing as "coach is unavailable right now". Proven 2026-09-08: verbatim
// signer + role creds -> 403; with double-encode -> 200.
describe('coach SigV4 canonical path', () => {
  it('builds a double-encoded canonical path from the wire path', () => {
    expect(coach).toMatch(/const canonicalPath = path\.replace\(\/%\/g, "%25"\)/);
    expect(coach).toMatch(/`POST\\n\$\{canonicalPath\}\\n\\n`/);
  });

  it('sends the single-encoded URL on the wire', () => {
    expect(coach).toMatch(/fetch\(`https:\/\/\$\{host\}\$\{path\}`/);
  });

  it('logs only the error name, never message/body (PII)', () => {
    expect(coach).toMatch(/coach_error.*detail/);
    expect(coach).not.toMatch(/console\.error\(err\)/);
  });
});
