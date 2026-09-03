#!/usr/bin/env python3
"""backward-compatible normalize: add translate_code (from lang_code) and pct_home (from pct)
to every markets[].top_languages entry, in place, without removing existing fields."""
import json


FILES = [
    "web/kodiak-posts-for-todays-frontier/data/localization/market-languages.json",
    "data/localization/market-languages.json",
]

for path in FILES:
    with open(path) as fh:
        d = json.load(fh)
    added = 0
    for m in d["markets"]:
        for t in m["top_languages"]:
            if "translate_code" not in t:
                t["translate_code"] = t["lang_code"]
                added += 1
            if "pct_home" not in t:
                t["pct_home"] = t["pct"]
    with open(path, "w") as fh:
        json.dump(d, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"{path}: added translate_code to {added} entries")
