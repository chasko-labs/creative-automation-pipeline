# recipe video test case 1 — PXL_20260930_223402275

source: pixel9 pro, 1920x1080 hevc, 382 s, handheld over brown paper.
input lives on mac-mini only (too big for local disk); this note plus
`frame_scores.csv` plus best frames are the committed record.

## what bryan actually did (assume this every time)
- laminated bag cutout first (scottish buttermilk oat scones): wiggled it,
  full text never visible in one frame, best view near end of dwell
- zoom hunts before landing on several recipes
- lost count; dwells fragment (42 raw motion dwells for ~6 items)

## confirmed readable at 1080p 1 fps extraction
- f_0037: scottish buttermilk oat scones (laminated, glare 0.0018, sharp 5523)
- f_0148: amish sugar cookies + french dressing (typed page)
- f_0227: bacon and onion rolls (spiral cookbook)
- f_0368: foodnetwork printed sheet, 8 hour + 6 hour tri-tip marinade

## segmentation findings (motion median 2.8 cv2 probe, 2.1 pillow port)
- motion spikes mark hand-enter page turns; stable runs mark readable dwells
- best frame per dwell is usually late in the dwell, matching the report
- long low-sharpness dwells are gaps (f_0326: empty brown paper)
- 42 raw dwells (cv2 probe; pillow port finds 41, same boundaries except
  the final two merged) need similarity merging: same card shot at several
  angles/zooms splits into multiple dwells
- per-dwell best picks all carry near zero glare, but the global variance
  max lands on a washed transitional frame (f_0363), so the reader stage
  must confirm text presence and fall back to neighbor frames on failure

## family vs favorite split
- printed sheets carry a header (`foodnetwork.com recipe cards`) and a
  footer address line; match that text after reading, no similarity
  model needed for the split
- similarity model still earns its place grouping multiple views of the
  same card and powering search over the finished records

## tool verdict
- change points: frame differencing (this module), not embeddings
- grouping + search: nova multimodal embeddings, one invoke per kept frame
- reading: multimodal vision reader over dwell-best frames, stitch text
  across views of the same card until covered
- bulk runs: batch inference pricing for the embedding + reading passes
