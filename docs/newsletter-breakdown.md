# Newsletter breakdown — programmatically recreate Welcome to the Real Breakfast Club

Source: `Kodiak<flapjacks@kodiakcakes.com>` — Welcome to the Real Breakfast Club 👋

## Header
- Preheader: `Can't see this email? View in Your Browser` — 12px `kodiak_sans` gray, centered, link
- Free Shipping bar: `Free Shipping Over $45 to the Contiguous US` — white on Kodiak red `#C1272D` or `brown-texture-2` dark, uppercase, tracking .12em

## Hero
- Logo: circular `KODIAK` bear (100% WHOLE GRAINS, PRIZE, CITY) — `kodiak-primary-logo_optimized.png` centered, 180px
- H1: `welcome to the real breakfast club!` — `NOOMKC-Regular` or `Roar` bold, `Kodiak Red` #C8102E, lowercase as in email, 32px
- Sub: `Get 25% off your next order.` — `kodiak_sans` 16px brown #2c231b
- Code: `use code: BRKFSTCLUB` — `Roar` bold, white on red pill, tracking

## CTAs — 3-up grid (mobile stacks)
- `buy now: maple pecan overnight oats` — image 400×400, button `Buy Now` white on red, `kodiak_sans` 14px
- `buy now: buttermilk power cakes`
- `buy now: double dark chocolate muffin cup`
- Spacing 16px gutter, images `border-radius: 12px` with wheat texture faint

## Textures
- `brown-texture-2.webp` for header/footer brown #2c231b
- `mega-menu_red-bg.webp` for red nav/bars
- Wheat sprigs faint at corners (from logo)

## Footer
- `whole grain greatness` — `Roar` italic, centered
- `Join us on our adventure @kodiakcakes` — social icons, brown
- `Privacy Policy | Manage Preferences` — 12px gray, links
- `No longer want to receive these emails? Unsubscribe` — 11px
- Address: `8163 Gorgoza Pines Rd. Park City, Utah 84098 US` — 11px gray

## Programmatic mapping
- Template: `src/creative_automation/newsletter.py` should render this with Jinja/MJML, swapping product IDs from `data/products/kodiak-full-catalog.json`, hero from `kodiak-primary-logo`, and pulling historically great articles (e.g. `10 Tips to Cook a Flawless Flapjack` https://kodiakcakes.com/blogs/news/10-tips-to-cook-a-flawless-flapjack) as `Read More` blocks below CTAs.
