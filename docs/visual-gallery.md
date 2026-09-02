# Visual Examples Gallery — Kodiak Cakes

> Every Kodiak campaign, side by side. One brand — Bear Brown #3B2316, Blaze Orange #E8530E, Frontier Green #1A3C34, bear at 24,24 — many local frontiers. Open any preview to see the real ads.

How this system works in one sentence: **You write a one-page brief, the pipeline builds three finished sizes for every product, checks the bear and the colors, and saves a click-ready preview.**

**How to use this gallery:**

1. Pick the story that sounds closest to your store or audience below.
2. Click **Open preview** to see all 9 creatives (square, tall, wide) with green PASS badges.
3. Copy the image paths for your ad manager, or run `uv run python -m creative_automation.cli --brief briefs/<name>.yaml --assets input_assets --out /tmp/<name>` to rebuild in 10 seconds.

Preview pages are full HTML boards (`preview.html`) — dark header, 9 cards in a grid, each card shows the headline over a soft dark band, the bear logo, and the 8px Blaze Orange bar at the bottom. They work in any browser, no credentials needed.

---

## All nine campaigns at a glance

| # | Brief | Campaign | Output preview | Region | Audience shorthand |
|---|-------|----------|---------------|--------|-------------------|
| 1 | `briefs/kodiak.yaml` | Keep It Wild — Frontier Breakfast | [Open preview](assets/previews/kodiak/preview.html) | US-MW | Active families, outdoor, protein-forward |
| 2 | `briefs/kodiak-publix.yaml` | Frontier Breakfast — Publix Southeast Family | [Open preview](assets/previews/kodiak-publix/preview.html) | US-SE-PUBLIX | Southeast families, porch breakfast, cubs |
| 3 | `briefs/kodiak-target.yaml` | Frontier Breakfast — Target Midwest Gen Z | [Open preview](assets/previews/kodiak-target/preview.html) | US-MW-TARGET | Gen Z + millennial, clean label, active |
| 4 | `briefs/kodiak-costco.yaml` | Frontier Breakfast — Costco Bulk Family | [Open preview](assets/previews/kodiak-costco/preview.html) | US-W-COSTCO | Bulk families, value + protein, weekend stack |
| 5 | `briefs/kodiak-on-the-go.yaml` | Kodiak — On the Go Frontier | [Open preview](assets/previews/kodiak-on-the-go/preview.html) | US-NATIONAL-ON-THE-GO | Students, commuters, trail families 18-34 |
| 6 | `briefs/kodiak-trail.yaml` | Kodiak — Trail Season Oatmeal | [Open preview](assets/previews/kodiak-trail/preview.html) | US-W | Trail hikers, Wasatch, on-the-go protein |
| 7 | `briefs/kodiak-holiday.yaml` | Kodiak — Holiday Frontier Cast-Iron | [Open preview](assets/previews/kodiak-holiday/preview.html) | US | Holiday hosts, cabin gatherers 28-50 |
| 8 | `briefs/kodiak-diner.yaml` | Kodiak — Diner Flip | [Open preview](assets/previews/kodiak-diner/preview.html) | US-SW-DINER | Diner regulars, Las Cruces & Alamogordo brunch |
| 9 | `briefs/kodiak-subscription.yaml` | Kodiak — Subscribe and Save Home Delivery | [Open preview](assets/previews/kodiak-subscription/preview.html) | US-NATIONAL-DTC | Home pantry, subscribe & save 25-50 |

All nine render **9 creatives each** (3 products × 3 ratios: 1x1 square 1080×1080, 9x16 story 1080×1920, 16x9 wide 1920×1080). Every creative in the current outputs passes brand checks (logo present, palette probe, legal gate) — look for the green `PASS` badge in the preview.

---

## 1. Keep It Wild — Frontier Breakfast

**Brief:** [`briefs/kodiak.yaml`](../briefs/kodiak.yaml) · **Preview:** [Open full board →](assets/previews/kodiak/preview.html) · **Output folder:** `output_kodiak/`

This is the master brand campaign — the always-on Kodiak story. Born from the red wagon in Park City in 1982, now in 26,000 doors, still saying *Nourishment for Today's Frontier* and *Keep It Wild*. It's the template every other campaign copies: Wasatch dawn, protein you can feel, bear that means something.

- **Campaign:** Keep It Wild — Frontier Breakfast
- **Audience:** Active families and outdoor enthusiasts, 25–45, Midwest + Mountain West,蛋白-forward breakfast seekers — the people who choose whole grains because they hike before work.
- **Message:** *"Protein-packed whole grains for today's frontier."* — the one approved, class-action-safe headline.
- **Market / Region:** US-MW
- **Products:** Buttermilk Power Cakes (14g protein, real DAM photo reused), Bear Bites Graham Crackers (cubs, cinnamon & honey), Protein Oatmeal Cup (maple & brown sugar).

**What you'll see:** A warm, rugged stack against a blurred Wasatch cover with scrim. The real hero photo for Power Cakes grounds it; Bear Bites and oatmeal are generated in the frontier palette so the whole board still feels like Kodiak.

**Embedded preview (square):**

| Power Cakes (DAM hero) | Bear Bites (generated) | Oatmeal Cup (generated) |
|---|---|---|
| ![Kodiak Frontier — Power Cakes 1x1](assets/previews/kodiak/power-cakes/1x1/power-cakes_1x1.png) | ![Kodiak Frontier — Bear Bites 1x1](assets/previews/kodiak/bear-bites/1x1/bear-bites_1x1.png) | ![Kodiak Frontier — Oatmeal 1x1](assets/previews/kodiak/oatmeal-cup/1x1/oatmeal-cup_1x1.png) |
| `power-cakes/1x1` · 1080×1080 | `bear-bites/1x1` | `oatmeal-cup/1x1` |

> Also in [9x16 stories](assets/previews/kodiak/power-cakes/9x16/power-cakes_9x16.png) and [16x9 wide](assets/previews/kodiak/power-cakes/16x9/power-cakes_16x9.png) — same headline, different crop. Full board: [preview.html](assets/previews/kodiak/preview.html)

---

## 2. Frontier Breakfast — Publix Southeast Family

**Brief:** [`briefs/kodiak-publix.yaml`](../briefs/kodiak-publix.yaml) · **Preview:** [Open full board →](assets/previews/kodiak-publix/preview.html) · **Output folder:** `output_kodiak-publix/`

Same frontier promise, tuned for the porch. This is how the same Power Cakes feel different in Savannah than in Salt Lake — warm humidity-green light, family breakfast, cubs with lunchboxes.

- **Campaign:** Frontier Breakfast — Publix Southeast Family
- **Audience:** Southeast families 28–45, Publix shoppers — porch-breakfast, kids + cubs, warm family.
- **Message:** *"Protein-packed whole grains for your family's frontier."* — the frontier comes home.
- **Market / Region:** US-SE-PUBLIX
- **Products:** Power Cakes (heirloom whole grain), Bear Bites (lunchbox-ready), Oatmeal Cup (trail to table).

**Embedded preview:**

| Power Cakes | Bear Bites | Oatmeal Cup |
|---|---|---|
| ![Publix — Power Cakes 1x1](assets/previews/kodiak-publix/power-cakes/1x1/power-cakes_1x1.png) | ![Publix — Bear Bites 1x1](assets/previews/kodiak-publix/bear-bites/1x1/bear-bites_1x1.png) | ![Publix — Oatmeal 1x1](assets/previews/kodiak-publix/oatmeal-cup/1x1/oatmeal-cup_1x1.png) |

> See all three ratios in the [preview board](assets/previews/kodiak-publix/preview.html). Ideal if you're briefing Publix or any southeast porch-family placement.

---

## 3. Frontier Breakfast — Target Midwest Gen Z

**Brief:** [`briefs/kodiak-target.yaml`](../briefs/kodiak-target.yaml) · **Preview:** [Open full board →](assets/previews/kodiak-target/preview.html) · **Output folder:** `output_kodiak-target/`

Clean light, clean label. For the shopper who reads the ingredient list at Target before she puts it in the cart.

- **Campaign:** Frontier Breakfast — Target Midwest Gen Z
- **Audience:** Gen Z and millennial health seekers 22–34, Target shoppers — active, ingredient-aware.
- **Message:** *"Fuel your frontier — 14g protein, 100% whole grains."* — short, verb-forward.
- **Market / Region:** US-MW-TARGET
- **Products:** Power Cakes, Bear Bites, Oatmeal Cup — all high-protein, whole-grain, no fluff.

**Embedded preview:**

| Power Cakes | Bear Bites | Oatmeal Cup |
|---|---|---|
| ![Target — Power Cakes 1x1](assets/previews/kodiak-target/power-cakes/1x1/power-cakes_1x1.png) | ![Target — Bear Bites 1x1](assets/previews/kodiak-target/bear-bites/1x1/bear-bites_1x1.png) | ![Target — Oatmeal 1x1](assets/previews/kodiak-target/oatmeal-cup/1x1/oatmeal-cup_1x1.png) |

> Best for Target, clean-label retail, or any young active feed. Full grid: [preview.html](assets/previews/kodiak-target/preview.html)

---

## 4. Frontier Breakfast — Costco Bulk Family

**Brief:** [`briefs/kodiak-costco.yaml`](../briefs/kodiak-costco.yaml) · **Preview:** [Open full board →](assets/previews/kodiak-costco/preview.html) · **Output folder:** `output_kodiak-costco/`

The weekend stack, family-size. Value without losing the wild.

- **Campaign:** Frontier Breakfast — Costco Bulk Family
- **Audience:** Bulk family shoppers 30–50, Costco members — value + protein, weekend stack for a full table.
- **Message:** *"Stock the frontier — protein-packed whole grains for every morning."* — pantry-staple language.
- **Market / Region:** US-W-COSTCO
- **Products:** Family-size Power Cakes, shareable Bear Bites, 12-pack Oatmeal Cup.

**Embedded preview:**

| Power Cakes | Bear Bites | Oatmeal Cup |
|---|---|---|
| ![Costco — Power Cakes 1x1](assets/previews/kodiak-costco/power-cakes/1x1/power-cakes_1x1.png) | ![Costco — Bear Bites 1x1](assets/previews/kodiak-costco/bear-bites/1x1/bear-bites_1x1.png) | ![Costco — Oatmeal 1x1](assets/previews/kodiak-costco/oatmeal-cup/1x1/oatmeal-cup_1x1.png) |

> Show this when you need "stock the pantry" energy. [All 9 creatives →](assets/previews/kodiak-costco/preview.html)

---

## 5. On the Go Frontier

**Brief:** [`briefs/kodiak-on-the-go.yaml`](../briefs/kodiak-on-the-go.yaml) · **Preview:** [Open full board →](assets/previews/kodiak-on-the-go/preview.html) · **Output folder:** `output_kodiak-on-the-go/`

For the bus, the trailhead, the dorm — protein that travels. This replaced the old back-to-school idea because students and commuters need fuel year-round, not just in August.

- **Campaign:** Kodiak — On the Go Frontier
- **Audience:** Busy students, commuters, and trail families 18–34 — need quick protein that travels.
- **Message:** *"On the go never tasted so good — 5 grams of protein for busy mornings."* — approachable, snackable.
- **Market / Region:** US-NATIONAL-ON-THE-GO
- **Products (reordered for the story):** Oatmeal Cup (just add water, 5 minutes), Bear Bites (100-calorie anytime fuel), Power Cakes (make ahead, reheat, go).

**Embedded preview:**

| Oatmeal Cup | Bear Bites | Power Cakes |
|---|---|---|
| ![On the Go — Oatmeal 1x1](assets/previews/kodiak-on-the-go/oatmeal-cup/1x1/oatmeal-cup_1x1.png) | ![On the Go — Bear Bites 1x1](assets/previews/kodiak-on-the-go/bear-bites/1x1/bear-bites_1x1.png) | ![On the Go — Power Cakes 1x1](assets/previews/kodiak-on-the-go/power-cakes/1x1/power-cakes_1x1.png) |

> Tall 9x16 is the hero here — think bus-stop story. [Full preview →](assets/previews/kodiak-on-the-go/preview.html)

---

## 6. Trail Season Oatmeal

**Brief:** [`briefs/kodiak-trail.yaml`](../briefs/kodiak-trail.yaml) · **Preview:** [Open full board →](assets/previews/kodiak-trail/preview.html) · **Output folder:** `output_kodiak-trail/`

Wasatch at sunrise. Rocky overlook, steaming cup, cubs on a trail bench. The most outdoorsy board we have.

- **Campaign:** Kodiak — Trail Season Oatmeal
- **Audience:** Active families and trail hikers 25–45, Mountain West + Wasatch — on-the-go protein seekers who actually eat on the trail.
- **Message:** *"Fuel your trail — protein oatmeal for today's frontier."*
- **Market / Region:** US-W
- **Products:** Oatmeal Cup (rocky-overlook ready, steam rising), Bear Bites (trail bench snack for cubs), Power Cakes (basecamp breakfast before the climb).

**Embedded preview:**

| Oatmeal Cup | Bear Bites | Power Cakes |
|---|---|---|
| ![Trail — Oatmeal 1x1](assets/previews/kodiak-trail/oatmeal-cup/1x1/oatmeal-cup_1x1.png) | ![Trail — Bear Bites 1x1](assets/previews/kodiak-trail/bear-bites/1x1/bear-bites_1x1.png) | ![Trail — Power Cakes 1x1](assets/previews/kodiak-trail/power-cakes/1x1/power-cakes_1x1.png) |

> If your buyer loves the Keep It Wild photography direction, start here. [All 9 →](assets/previews/kodiak-trail/preview.html)

---

## 7. Holiday Frontier Cast-Iron

**Brief:** [`briefs/kodiak-holiday.yaml`](../briefs/kodiak-holiday.yaml) · **Preview:** [Open full board →](assets/previews/kodiak-holiday/preview.html) · **Output folder:** `output_kodiak-holiday/`

Cozy cabin, cast iron, steam on rustic wood. The holiday table where the stack is the centerpiece.

- **Campaign:** Kodiak — Holiday Frontier Cast-Iron
- **Audience:** Families 28–50, holiday hosts and cozy cabin gatherers — the cast-iron breakfast ritual.
- **Message:** *"Gather 'round the frontier — cast-iron Power Cakes for holiday mornings."*
- **Market / Region:** US (national holiday)
- **Products:** Power Cakes (holiday cast-iron stack hero), Bear Bites (table shareable), Oatmeal Cup (warm option for guests).

**Embedded preview:**

| Power Cakes | Bear Bites | Oatmeal Cup |
|---|---|---|
| ![Holiday — Power Cakes 1x1](assets/previews/kodiak-holiday/power-cakes/1x1/power-cakes_1x1.png) | ![Holiday — Bear Bites 1x1](assets/previews/kodiak-holiday/bear-bites/1x1/bear-bites_1x1.png) | ![Holiday — Oatmeal 1x1](assets/previews/kodiak-holiday/oatmeal-cup/1x1/oatmeal-cup_1x1.png) |

> Square 1x1 shines for the holiday feed. [Full holiday board →](assets/previews/kodiak-holiday/preview.html)

---

## 8. Diner Flip

**Brief:** [`briefs/kodiak-diner.yaml`](../briefs/kodiak-diner.yaml) · **Preview:** [Open full board →](assets/previews/kodiak-diner/preview.html) · **Output folder:** `output_kodiak-diner/`

The smallest footprint, the closest to the customer — the diner griddle in Las Cruces and Alamogordo that now flips Kodiak cakes on Saturday morning. Same template, now a printable table tent and menu board (square for the table, wide for the board).

- **Campaign:** Kodiak — Diner Flip
- **Audience:** Diner regulars and families near Las Cruces and Alamogordo — weekend brunch, no pretense.
- **Message:** *"Now flipping Kodiak Cakes at your diner — protein-packed whole grains for your frontier."*
- **Market / Region:** US-SW-DINER
- **Products:** Power Cakes on the griddle (14g), Bear Bites kids side.

**Embedded preview:**

| Power Cakes | Bear Bites |
|---|---|
| ![Diner — Power Cakes 1x1](assets/previews/kodiak-diner/power-cakes/1x1/power-cakes_1x1.png) | ![Diner — Bear Bites 1x1](assets/previews/kodiak-diner/bear-bites/1x1/bear-bites_1x1.png) |

> Only two products here — that's intentional (it's a diner menu, not a grocery aisle). [See both ratios →](assets/previews/kodiak-diner/preview.html) — 16x9 is the menu board.

---

## 9. Subscribe and Save Home Delivery

**Brief:** [`briefs/kodiak-subscription.yaml`](../briefs/kodiak-subscription.yaml) · **Preview:** [Open full board →](assets/previews/kodiak-subscription/preview.html) · **Output folder:** `output_kodiak-subscription/`

Direct to the front door. No retailer, no aisle — just the pantry refilling itself every month. The clearest value prop we have.

- **Campaign:** Kodiak — Subscribe and Save Home Delivery
- **Audience:** Home pantry shoppers 25–50, subscribe and save — free shipping over $45.
- **Message:** *"Subscribe and save — 15 percent off plus free shipping over 45 dollars, real food for real adventures."*
- **Market / Region:** US-NATIONAL-DTC
- **Products:** Power Cakes (front door every month), Oatmeal Cups (start and stop anytime).

**Embedded preview:**

| Power Cakes | Oatmeal Cup |
|---|---|
| ![Subscription — Power Cakes 1x1](assets/previews/kodiak-subscription/power-cakes/1x1/power-cakes_1x1.png) | ![Subscription — Oatmeal 1x1](assets/previews/kodiak-subscription/oatmeal-cup/1x1/oatmeal-cup_1x1.png) |

> Two-product DTC board — the simplest to launch. [Full preview →](assets/previews/kodiak-subscription/preview.html)

---

## Which examples work hardest for each persona?

Maya, Diego, and Priya don't think in SKUs — they think in people. Here's how the nine boards map to the three personas we actually design for (see [`docs/ux-persona-kodiak.md`](./ux-persona-kodiak.md)).

### At a glance — table

| Persona | Who they are | Strongest examples (use these first) | Good next | Why it works |
|---------|-------------|--------------------------------------|-----------|--------------|
| **Frontier** — the Wasatch explorer | 25–45, active, outdoor, keeps Vital Ground in mind, wants rugged nourishment | **Keep It Wild** (`kodiak.yaml`), **Trail Season** (`kodiak-trail.yaml`) | **Holiday Cast-Iron** (`kodiak-holiday.yaml`) | Dawn light + bear-safe wild + trail steam = "this is my frontier." Frontier Green #1A3C34 and Bear Brown #3B2316 dominate. |
| **Family** — the porch and pantry host | 28–50, feeds cubs, shops Publix/Costco, hosts holidays, values protein + sharing | **Publix Family** (`kodiak-publix.yaml`), **Costco Bulk** (`kodiak-costco.yaml`), **Holiday Cast-Iron** (`kodiak-holiday.yaml`) | **Diner Flip** (`kodiak-diner.yaml`), **Subscription** (`kodiak-subscription.yaml`) | Warm light, cubs, lunchbox / bulk / cabin language. Bear Bites shine here. |
| **On-the-Go** — the busy mover | 18–34, student/commuter/trail family, needs 5-minute protein that travels | **On the Go** (`kodiak-on-the-go.yaml`), **Trail Season** (`kodiak-trail.yaml`) | **Target Gen Z** (`kodiak-target.yaml`), **Subscription** (`kodiak-subscription.yaml`) | Oatmeal Cup hero, 5g / 5-minute promise, 9x16 story-first. Fast, light, no cast iron. |

> **Reading the table:** If you're briefing for Publix, Costco, or a holiday table — start in the Family row. If you're briefing for Wasatch trailheads or Keep It Wild conservation — start in Frontier. If you're briefing for students, commuters, or the Las Cruces green-chile commuter test — start On-the-Go.

### Visual map — mermaid

```mermaid
flowchart LR
    subgraph Frontier["Frontier — Wasatch & Wild"]
        A[Keep It Wild<br/>kodiak.yaml<br/>★★★]
        B[Trail Season<br/>kodiak-trail.yaml<br/>★★★]
        C[Holiday Cast-Iron<br/>kodiak-holiday.yaml<br/>★★]
    end
    subgraph Family["Family — Porch, Pantry & Table"]
        D[Publix Family<br/>kodiak-publix.yaml<br/>★★★]
        E[Costco Bulk<br/>kodiak-costco.yaml<br/>★★★]
        F[Holiday Cast-Iron<br/>kodiak-holiday.yaml<br/>★★★]
        G[Diner Flip<br/>kodiak-diner.yaml<br/>★★]
        H[Subscribe & Save<br/>kodiak-subscription.yaml<br/>★★]
    end
    subgraph OnTheGo["On-the-Go — Bus, Trail & Desk"]
        I[On the Go<br/>kodiak-on-the-go.yaml<br/>★★★]
        J[Trail Season<br/>kodiak-trail.yaml<br/>★★★]
        K[Target Gen Z<br/>kodiak-target.yaml<br/>★★]
        L[Subscribe & Save<br/>kodiak-subscription.yaml<br/>★★]
    end

    A --- B
    D --- E --- F
    I --- J

    B -. shared hero .-> J
    F -. warm hosting .-> G
    C -. cozy overlap .-> F

    classDef frontier fill:#1A3C34,stroke:#3B2316,color:#FFF8F0
    classDef family fill:#E8530E,stroke:#3B2316,color:#FFF
    classDef go fill:#3B2316,stroke:#E8530E,color:#FFF8F0
    class A,B,C frontier
    class D,E,F,G,H family
    class I,J,K,L go
```

**How to read the diagram:** Each subgraph is a persona. ★★★ = strongest fit — use first in a pitch. ★★ = strong supporting — good for a second test. Dashed lines show boards that bridge personas: Trail works for both Frontier and On-the-Go, Holiday bridges Frontier and Family, Subscription bridges Family and On-the-Go because "pantry that refills itself" helps both.

### Quick picker — if you only have time for one example per persona

- **Frontier?** Open [Keep It Wild →](assets/previews/kodiak/preview.html) — Wasatch dawn, 14g, Vital Ground co-badge in the footer.
- **Family?** Open [Publix Family →](assets/previews/kodiak-publix/preview.html) — warm, cub-forward, "for your family's frontier."
- **On-the-Go?** Open [On the Go →](assets/previews/kodiak-on-the-go/preview.html) — 9x16-first, oatmeal cup, 5 grams that travels.

---

## Design rules every preview follows

These aren't opinions — they're tokens from [`design/tokens/kodiak.json`](../design/tokens/kodiak.json) and [`references/templates/social-3ratio.json`](../references/templates/social-3ratio.json), applied by code in `src/creative_automation/compose.py`.

- **Six-piece template:** Blurred Wasatch cover + 0.18 scrim (#1A1110CC), hero contained at min(W×0.82/hw, H×0.58/hh) centered 8% down, 48px outer pad / 24px logo offset / 8px Blaze Orange bar, message bar at 68% down, logo 140px at 24,24, footer "KODIAK • kodiakcakes.com • Keep It Wild".
- **Type:** Headline slab (56px at 1x1, 64px at 9x16, 72px at 16x9, max 3 lines, stroke 2), footer Inter 500 uppercase 22/24px, 0.06em tracking.
- **Checks:** Every PNG is probed for logo presence, palette presence (Bear Brown / Blaze Orange / Frontier Green), and prohibited legal terms. Green PASS in the preview = ready to ship. The report that proves it lives next to the preview: `report.json` + `report.jsonl` (one line per creative).
- **Heros:** DAM first (`input_assets/power-cakes/hero.png` reused), then S3 `brands/kodiak/` if `DAM_S3_BUCKET` is set, then generated (mock Pillow locally, Nova Canvas `amazon.nova-canvas-v1:0` with creds). No blank heroes.

**Rebuild any board yourself:**

```bash
uv run python -m creative_automation.cli --brief briefs/kodiak.yaml --assets input_assets --out /tmp/kodiak-verify
open /tmp/kodiak-verify/preview.html

# Another town
uv run python -m creative_automation.cli --brief briefs/kodiak-trail.yaml --assets input_assets --out /tmp/kodiak-trail
open /tmp/kodiak-trail/preview.html
```

More context: [Brand story in plain language](./kodiak-brand-explained.md) · [Style guide (7 parts)](./kodiak-style-guide.md) · [Who runs this — Maya, Diego, Priya](./ux-persona-kodiak.md) · [How we launch in every town](./how-we-launch-in-every-town.md) · [Brand view (visual)](./kodiak-brand-view.html)

---

*Generated for the creative-automation-pipeline visual gallery. Nine briefs, 81 creatives, three sizes, one bear.*
