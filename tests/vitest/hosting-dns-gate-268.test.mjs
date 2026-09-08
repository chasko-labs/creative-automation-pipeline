import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const stack = readFileSync(
  resolve(root, 'infra-cdk/lib/hosting-stack.ts'), 'utf8');

// #268: the Route53 alias lives in the website account (aerospaceug-admin),
// unreachable from the deploy role, and the live record is correct. The
// record must be opt-in so a bare `cdk deploy` never attempts the
// cross-account CREATE (it fails, and during import it rolled back the
// whole adoption).
describe('hosting DNS alias gate (#268)', () => {
  it('the alias record is opt-in, default OFF', () => {
    expect(stack).toMatch(/includeDnsRecord\s*=\s*dnsFlag\s*===\s*true\s*\|\|\s*dnsFlag\s*===\s*['"]true['"]/);
  });

  it('the hand-managed decision is recorded at the gate', () => {
    expect(stack).toMatch(/HAND-MANAGED/);
    expect(stack).toMatch(/hostingIncludeDnsRecord=true/);
  });
});
