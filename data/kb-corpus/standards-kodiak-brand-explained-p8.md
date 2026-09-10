### 3. Retailer and seasonal sprints — the hundreds-per-month engine
*Next up:* Back-to-school (Bear Bites in lunchboxes, 9:16 Stories), trail season (oatmeal cup on a rocky overlook, 16:9), holiday baking (Power Cakes cast-iron stack, 1:1). Each is the same six-piece template with a swapped hero prompt (`kodiak-04` for cubs on a trail bench, `kodiak-05` for oatmeal at sunrise) and a swapped accent — orange for protein, green for evergreen.

All three campaign types share the same brand check: logo present, blaze orange 8px bar at the bottom, palette probe for #3B2316/#E8530E/#1A3C34, and legal gate for protein claims. That check is our interim style guide until Kodiak publishes a formal one per retailer.

---

## How we'll produce the assets — the loop you can watch

You don't need AWS credentials to see it work, but the path is the same with or without S3.

1. **Brief in.** A YAML or JSON file names the campaign, the three products, the target market (e.g., US-MW vs US-SE), the audience, and one headline. `briefs/kodiak.yaml` is the source you can edit.
