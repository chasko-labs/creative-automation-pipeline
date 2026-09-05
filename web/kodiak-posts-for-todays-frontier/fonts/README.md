# self-hosted noto webfonts

self-hosted woff2 subsets that back the 7 `@font-face` declarations in
`../index.html` (the translation-surfacing loc-lines: `.loc-line[lang=...]`).

- source: google noto (fonts.google.com / github google/fonts + notofonts/noto-cjk)
- license: SIL open font license 1.1 — see `OFL.txt`. free to bundle + self-host + subset
- each file is subset to only the unicode-range its `@font-face` declares, so a browser
  pulls only the script it actually renders. cjk is subset, never shipped whole

## files, sources, subset ranges

| file                       | family               | source (open, no auth)                                                  | unicode-range (matches index.html)                                                                                                                       |
| -------------------------- | -------------------- | ----------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `NotoSans-Latin.woff2`     | Noto Sans            | google/fonts `ofl/notosans/NotoSans[wdth,wght].ttf`                     | U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD |
| `NotoSans-Cyrillic.woff2`  | Noto Sans            | google/fonts `ofl/notosans/NotoSans[wdth,wght].ttf`                     | U+0301,U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116                                                                                                        |
| `NotoSansArabic.woff2`     | Noto Sans Arabic     | google/fonts `ofl/notosansarabic/NotoSansArabic[wdth,wght].ttf`         | U+0600-06FF,U+0750-077F,U+08A0-08FF,U+FB50-FDFF,U+FE70-FEFF                                                                                              |
| `NotoSansEthiopic.woff2`   | Noto Sans Ethiopic   | google/fonts `ofl/notosansethiopic/NotoSansEthiopic[wdth,wght].ttf`     | U+1200-137F,U+1380-139F,U+2D80-2DDF,U+AB00-AB2F                                                                                                          |
| `NotoSansMyanmar.woff2`    | Noto Sans Myanmar    | google/fonts `ofl/notosansmyanmar/NotoSansMyanmar[wdth,wght].ttf`       | U+1000-109F,U+A9E0-A9FF,U+AA60-AA7F                                                                                                                      |
| `NotoSansDevanagari.woff2` | Noto Sans Devanagari | google/fonts `ofl/notosansdevanagari/NotoSansDevanagari[wdth,wght].ttf` | U+0900-097F,U+1CD0-1CFF,U+20A8,U+A830-A839,U+A8E0-A8FF                                                                                                   |
| `NotoSansCJKjp.woff2`      | Noto Sans CJK        | notofonts/noto-cjk `Sans/SubsetOTF/JP/NotoSansJP-Regular.otf`           | U+3000-303F,U+3040-309F,U+30A0-30FF,U+3100-312F,U+31F0-31FF,U+3200-32FF,U+3400-4DBF,U+4E00-9FFF,U+AC00-D7AF,U+F900-FAFF,U+FF00-FFEF                      |

## notes

- latin + cyrillic are two subsets of the same `NotoSans[wdth,wght].ttf` variable source,
  split by unicode-range so the `'Noto Sans'` family only downloads the script in use
- variable-font axes (wdth,wght) are retained, so the `font-weight:400 700` range in each
  `@font-face` resolves from the file. myanmar/devanagari/etc keep their weight axis too
- cjk uses the japanese cut of pan-cjk (`NotoSansJP-Regular.otf`, 4.5MB source) subset to
  the declared ranges -> 2.3MB woff2. this covers common-use kanji/kana/hangul/cjk-ideographs.
  glyphs unique to korean hanja or traditional-chinese-only cuts outside the JP set are not
  present. if a future loc-line needs full traditional-chinese coverage, source the SC/TC cut
  and add a separate `@font-face`. shipping the full pan-cjk (16.5MB) is not an option for web
- layout features (`*`) are kept so shaping (arabic joining, devanagari/myanmar conjuncts,
  cjk vertical forms) works in-browser

## regenerating

```sh
pip install 'fonttools[woff]' brotli
pyftsubset <source.ttf|otf> \
  --unicodes="<range from table above>" \
  --layout-features='*' --flavor=woff2 \
  --no-hinting --desubroutinize \
  --output-file=<file>.woff2
```
