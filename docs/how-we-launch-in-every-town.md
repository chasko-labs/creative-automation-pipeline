# How we launch in every town — plain language for marketing teams

You don't need to learn ad tech. This is how one person's idea becomes a local ad in Las Cruces or a diner menu board in Alamogordo without extra work.

## Step one: tell the system where your stores are

Think of this as giving the ad platform a phone book it can trust.

1. Open your business settings and find Business Locations. This is where the master store list lives. It used to be called Store Locations — same thing, new name.
2. Download the simple sheet the platform gives you. It's a table with one row per place that carries Kodiak — street address, city, zip code, phone number, and a unique store number you make up (for example, ALAMO-WALMART-01). Do this for every Walmart, every Albertsons, every Target, every small independent on Main Street that said yes, and every diner that agreed to flip Kodiak cakes.
3. Upload that sheet. Now organize your stores into groups so you can talk to them the way you think: one group for the big southern supermarkets, one for the style-forward national chain, one for the big membership stores, and extra groups for city clusters like "Las Cruces and Alamogordo" or "Chicago Retailers." Priya calls these groups "Store Sets." You will never type a city name again — you just pick the right store group.

**What that gives you:** A single place that remembers Alamogordo Walmart at 3500 E Highway 70, the Albertsons at 1010 N White Sands Blvd, the Las Cruces Target, and the little diner on US-70. If a shopper is within about 5 to 10 miles of any of those, your ad can find them. This same list also feeds our own store tables — the retail network table and the localization memory — so Kodiak's own system remembers per town what worked.

## Step two: set up one campaign that stays under your control

You build the structure once, then it repeats for every town.

- **Campaign:** Start a new campaign and choose Awareness or Sales. One important choice: leave the setting called Advantage Campaign Budget turned off. That keeps you in control — so ten dollars for Las Cruces actually stays in Las Cruces, and Chicago has its own ten dollars. No hidden re-budgeting.
- **One local bucket per place:** For each city or retailer group, make one local bucket. Inside each, in the locations section, don't type the city name — pick "Choose Store Set" and pick the group you made in step one. Set its local budget. Now that bucket will only show ads to people near those exact storefronts.
- **One beautiful ad, used everywhere:** Make your ad once — a high-quality photo of the stack, the Bear Bites bowl, or the oatmeal cup, with your line like "Green chile meets grizzly" — under the first local bucket. Publish it once and copy its post number. For every other local bucket, don't make a new ad — choose "Use Existing Post" and paste that same number. You now have one creative, many local doors. If you fix a typo, it fixes everywhere.

## Step three: the local magic that makes one post feel custom

This is where the same post looks like you wrote it just for Las Cruces.

- **Dynamic text:** In the main text box, instead of writing "Available at stores everywhere," write "Find us today at your nearest town — {{store.city}}!" The platform will automatically swap in Las Cruces for a viewer in Las Cruces, Chicago for a viewer in Chicago, and Alamogordo for a viewer in Alamogordo. No extra versions. Same for street and phone if you want it.
- **The map card:** Turn on the Store Locator Map add-on in the ad settings. Now your ad carries a tiny map.
- **The button:** Set the button to "Get Directions." A person in Las Cruces who taps it gets walking directions to the Las Cruces Target or the Alamogordo Walmart that is closest to them. A person in Miami who saw the exact same ad gets Miami. No extra creative.

**Why this matters for Kodiak's smaller stores and diners:**

The map card doesn't care if it's a big chain or a small grocer or a diner. If the address is in the store list you uploaded in step one, it can be the destination. That is how the small independents stay involved — they are just another row in the same phone book. For a diner, you also get a free printed table tent (square for the table, wide for the menu board) from the same template the pipeline used for the social ads — same bear, same colors, same line, just printed. The store locator on https://kodiakcakes.com/pages/store-locator already shows Alamogordo has Walmart and Albertsons; the same list, when you expand it, already has the independents around it. You just keep adding rows.

## How this ties to the style library and the training data you asked for

Every ad we make through the pipeline — whether it was for a Publix porch in Savannah, a Target in Minneapolis, or a diner in Alamogordo — saves one row to the growing table: place (market like US-SW-LASCRUCES, city Las Cruces, zip 88001), store group (Las Cruces Target vs Alamogordo Walmart vs small grocer), audience (28-45 green chile families), message ("Green chile meets grizzly — protein for your Las Cruces frontier"), and photo cue (roasted Hatch on an Organ Mountains bench, prompt kodiak-04). That row lives in two places that marketing can query without knowing which is which:

- **A simple lookup table** you can open like a spreadsheet: ask for market US-SW-LASCRUCES and you get back the last winning audience and line for Las Cruces.
- **A searchable knowledge** where you can type "What worked for green chile families?" or "What photo worked for porch breakfasts?" and it returns the closest past wins by meaning, not just exact words.

Both are fed from the same cloud storage bucket at `s3://chasko-creative-dam-946179428633-us-east-1/brands/kodiak/` and described together in the single cloud setup file at `infra/template.yaml`. That file also keeps the nightly logs.

## What to do next week — without a research sprint

Pick a place from `docs/regional-cultural-database.md` — start with Las Cruces. Pick the store group (Las Cruces Target + Alamogordo Walmart + Albertsons + one independent + one diner), pick the on-the-go product (oatmeal cup, Bear Bites, Power Cakes make-ahead), and run the brief `briefs/kodiak-on-the-go.yaml` with `target_market: US-SW-LASCRUCES` and the green chile message. The pipeline will make the three sizes with the frontier palette, the report will say which product's photo got reused versus generated, and the store map will already be right. That first run becomes the training row the next Las Cruces run suggests first.
