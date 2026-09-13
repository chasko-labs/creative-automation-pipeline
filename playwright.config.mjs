// Playwright config — LOCAL / OPT-IN render suite for the kodiak-ember harness.
// NOT wired into scripts/hooks/full-check.sh (the fast push gate is Python-only
// and never runs Babylon/browser checks). Run explicitly: npm run test:render.
//
// Headless Chromium has no hardware GPU on the build host, so WebGL is backed by
// SwiftShader (software). The launch flags below force a usable software WebGL
// context so the harness can be exercised at all. This is deliberate: the device
// gate MUST classify SwiftShader/llvmpipe as software and refuse to mount, so the
// "software renderer refused" test asserts exactly that relationship.
// import from the 'playwright' package's test subpath — the repo pins
// `playwright` (not the separate `@playwright/test` package) in devDependencies,
// and 1.63.0 ships the test runner at playwright/test.
import { defineConfig } from 'playwright/test';

export default defineConfig({
  testDir: './tests/playwright',
  testMatch: '**/*.spec.mjs',
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    // fixtures load via file:// — the runbook's offline requirement. no server.
    launchOptions: {
      args: [
        '--use-gl=angle',
        '--use-angle=swiftshader',
        '--enable-unsafe-swiftshader',
        '--ignore-gpu-blocklist',
        '--allow-file-access-from-files',
      ],
    },
  },
});
