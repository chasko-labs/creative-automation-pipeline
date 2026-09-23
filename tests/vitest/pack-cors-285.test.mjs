import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const dataStack = readFileSync(
  resolve(root, 'infra-cdk/lib/data-stack.ts'), 'utf8');
const genStack = readFileSync(
  resolve(root, 'infra-cdk/lib/generate-stack.ts'), 'utf8');

// #285 — presigned asset store GETs failed CORS (no bucket config) and POST
// /assets/pack 500'd (lambda role lacked brands/kodiak/packs/*).
describe('pack cors + grant (#285)', () => {
  it('asset store bucket allows cross-origin GET/HEAD from the site origins only', () => {
    expect(dataStack).toMatch(/corsConfiguration/);
    expect(dataStack).toMatch(/allowedMethods: \["GET", "HEAD"\]/);
    expect(dataStack).toMatch(/FRONTIER_ALIASES/);
    expect(dataStack).toMatch(/FRONTIER_DOMAIN_NAME/);
    expect(dataStack).not.toMatch(/allowedOrigins: \["\*"\]/);
  });

  it('generate role can persist + serve pack zips under packs/*', () => {
    expect(genStack).toMatch(/DamPacksReadWrite/);
    expect(genStack).toMatch(/brands\/kodiak\/packs\/\*/);
    expect(genStack).toMatch(/\["s3:PutObject", "s3:GetObject"\]/);
  });
});
