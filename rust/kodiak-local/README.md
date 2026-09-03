# kodiak-local

Rust accelerators for `creative_automation` — mirrors `src/creative_automation/enhance.py` and `compose.py` hotspots.

## Functions (also exposed via PyO3 as `creative_automation._kodiak_local`)

- `autocontrast_rgba(data, w, h, cutoff)` — per-channel histogram stretch, `cutoff=0.5` matches `ImageOps.autocontrast(..., cutoff=0.5)`.
- `apply_vignette_rgba(data, w, h)` — 12 concentric rects outline alpha `i*1.2`, inset `i * min(w,h)//90` (6% radial darken).
- `apply_framing_rgba(data, w, h)` — expand 1px stone `#D9CFC6`, 6px bear-brown `#3B2316`, 2px blaze-orange `#E8530E` hairline bottom.
- `enhance_hero_file(in_path, out_path)` — convenience wrapper that loads/saves PNG (used by `enhance.py` fallback).

### Build (optional, pure-Python fallback is default)

```bash
# dev
maturin develop --manifest-path rust/kodiak-local/Cargo.toml
# or
pip install -e .  # after maturin build
```

Python falls back to Pillow if the extension is absent:

```python
try:
    import creative_automation._kodiak_local as rust
except ImportError:
    rust = None
```

Hatchling remains the default sdist build backend; `tool.maturin` in the workspace `pyproject.toml` points at this crate.
