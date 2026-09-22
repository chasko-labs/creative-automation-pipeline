import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const web = resolve(root, 'web/kodiak-posts-for-todays-frontier');
const index = readFileSync(resolve(web, 'index.html'), 'utf8');
const css = readFileSync(resolve(web, 'design/components.css'), 'utf8');
const ember = readFileSync(resolve(root, 'src/kodiak-ember.js'), 'utf8');

// Frontier marquee sign: static headline plate is the default visual; the
// vendored Babylon bundle progressively enhances it to a bulb-chase marquee
// with live status plates. The page must stay complete with 3D absent.
describe('frontier marquee sign', () => {
  it('hosts the sign on the headline plate with the static headline intact', () => {
    expect(index).toMatch(/id="frontierSign"/);
    expect(index).toMatch(/class="kodiak-headline-static">Kodiak Cakes Creative Automation Pipeline</);
  });

  it('loads the vendored entry same-origin with a guarded boot call', () => {
    expect(index).toMatch(/<script type="module" src="vendor\/kodiak-ember\.esm\.js\?v=[^"]+"><\/script>/);
    expect(index).toMatch(/window\.KodiakEmber[\s\S]{0,400}mountFrontierSign\('#frontierSign'\)/);
  });

  it('retires the static plate only after the 3D scene constructs', () => {
    expect(ember).toMatch(/host\.classList\.add\("is-live"\)/);
    expect(css).toMatch(/#frontierSign\.is-live \.kodiak-headline-static\{[^}]*clip:rect\(0,0,0,0\)/);
  });

  it('builds the Vegas wash from warm light + emissive bulbs + glow', () => {
    // RectAreaLight cannot be aimed (lights are Nodes, not TransformNodes), so
    // the wash is a warm point light — asserted present, area light absent.
    expect(ember).toMatch(/new PointLight\("signWash"/);
    expect(ember).not.toMatch(/new RectAreaLight\(/);
    expect(ember).toMatch(/new GlowLayer\("signGlow"/);
    expect(ember).toMatch(/emissiveColor = AMBER/);
  });

  it('mirrors live page state on four status plates', () => {
    for (const label of ['MARKET', 'SEASON', 'PREVIEW', 'PACK']) {
      expect(ember).toContain(`"${label}"`);
    }
    expect(ember).toMatch(/\["locationSectionLabel", "seasonSectionLabel"\]/);
    expect(ember).toMatch(/getElementById\(id\)/);
    expect(ember).toMatch(/li\[data-node="\$\{node\}"\]/);
    expect(ember).toMatch(/new MutationObserver\(\(\) => this\.refreshPlates\(\)\)/);
  });

  it('adapts to light/dark and holds still under reduced motion', () => {
    expect(ember).toMatch(/matchMedia\("\(prefers-color-scheme: dark\)"\)/);
    expect(ember).toMatch(/addEventListener\("change", this\._onScheme\)/);
    expect(ember).toMatch(/if \(this\._reduceMotion\) return; \/\/ static alternating bulbs/);
  });

  it('fits the camera to the host aspect on mount and resize', () => {
    expect(ember).toMatch(/fitCamera\(\) \{[\s\S]{0,600}getDeltaTime|clientWidth/);
    expect(ember).toMatch(/window\.addEventListener\("resize", this\._onResize\)/);
    expect(ember).toMatch(/window\.removeEventListener\("resize", this\._onResize\)/);
    // cabinet holds a fixed clamp height at every breakpoint incl. mobile
    expect(css).toMatch(/#frontierSign\.is-live\{[^}]*height:clamp\(150px,22vw,220px\)/);
    expect(css).toMatch(/@media\(max-width:640px\)\{#frontierSign\.is-live\{height:150px\}\}/);
  });

  it('leaves face and plates unrotated (a half-turn hides them)', () => {
    // hardware-verified: CreatePlane already faces the -Z camera; rotating
    // the textured side away renders the board as a dark void.
    expect(ember).not.toMatch(/(face|plate)\.rotation\.y/);
  });

  it('shares the engine harness and exports the mount', () => {
    expect(ember).toMatch(/mountFrontierSign,/);
    expect(ember).toMatch(/gateReason\(host\)/);
    expect(ember).toMatch(/registerSceneView\(canvas, this\.camera/);
    expect(ember).toMatch(/_version: "0\.6\.0"/);
  });
});
