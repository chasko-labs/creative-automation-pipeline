// pyo3 0.22 #[pyfunction] macro expands to a wrapper that calls .into() on the
// Ok value; clippy flags that generated conversion as useless_conversion even
// though the source has no explicit .into(). scoped allow keeps -D warnings clean.
#![allow(clippy::useless_conversion)]
/// kodiak-local — Rust image helpers mirroring src/creative_automation/enhance.py
///
/// Pillow equivalents:
/// - autocontrast: ImageOps.autocontrast(rgb, cutoff=0.5) — per-channel histogram stretch
/// - vignette: 12 concentric rects outline=(0,0,0,alpha) alpha=i*1.2 inset=i*min(w,h)//90
/// - framing: ImageOps.expand 1px #D9CFC6 then 6px #3B2316 plus 2px #E8530E bottom bar
///
/// Python bindings via PyO3 (`creative_automation._kodiak_local`). All pure functions
/// also compiled as `rlib` for native use / wasm.
use pyo3::prelude::*;

// Bear brand tokens (mirrors enhance.py)
const STONE: [u8; 3] = [0xD9, 0xCF, 0xC6];
const BEAR_BROWN: [u8; 3] = [0x3B, 0x23, 0x16];
const BLAZE_ORANGE: [u8; 3] = [0xE8, 0x53, 0x0E];

/// Per-channel autocontrast.
///
/// `data` is RGBA bytes row-major, length w*h*4. Alpha is preserved.
/// `cutoff` is percent (0.5 matches Pillow default). Computes per-channel
/// histogram 0..255, finds lo/hi where cumulative >= cutoff% and >= (100-cutoff)%,
/// then stretches [lo,hi] -> [0,255] linearly. Flat channels are passed through.
pub fn autocontrast_rgba_inner(data: &mut [u8], w: usize, h: usize, cutoff: f32) {
    if data.len() != w * h * 4 {
        return;
    }
    let total = (w * h) as f32;
    let low_frac = (cutoff / 100.0).clamp(0.0, 0.49);
    let high_frac = 1.0 - low_frac;
    let low_count = (total * low_frac).floor() as usize;
    let high_count = (total * high_frac).ceil() as usize;

    for ch in 0..3 {
        let mut hist = [0usize; 256];
        for px in 0..w * h {
            hist[data[px * 4 + ch] as usize] += 1;
        }
        // find lo
        let mut cum = 0usize;
        let mut lo = 0usize;
        for (i, &c) in hist.iter().enumerate() {
            cum += c;
            if cum > low_count {
                lo = i;
                break;
            }
        }
        // find hi
        cum = 0;
        let mut hi = 255usize;
        for (i, &c) in hist.iter().enumerate() {
            cum += c;
            if cum >= high_count {
                hi = i;
                break;
            }
        }
        if hi <= lo {
            continue;
        }
        let scale = 255.0 / (hi - lo) as f32;
        for px in 0..w * h {
            let v = data[px * 4 + ch] as usize;
            let out = if v <= lo {
                0
            } else if v >= hi {
                255
            } else {
                ((v - lo) as f32 * scale).round() as u8
            };
            data[px * 4 + ch] = out;
        }
    }
}

/// Vignette: darken edges via 12 concentric rect outlines.
/// Mirrors enhance.py: for i in 0..12, alpha=int(i*1.2), inset=i*min(w,h)//90,
/// draw rectangle outline (1px) with RGBA(0,0,0,alpha) alpha-blended over source.
pub fn vignette_rgba_inner(data: &mut [u8], w: usize, h: usize) {
    if data.is_empty() || w == 0 || h == 0 {
        return;
    }
    let min_dim = w.min(h) as i32;
    for i in 0..12i32 {
        let alpha = (i as f32 * 1.2).round() as u8;
        if alpha == 0 {
            continue;
        }
        let inset = (i * min_dim) / 90;
        let x0 = inset;
        let y0 = inset;
        let x1 = w as i32 - 1 - inset;
        let y1 = h as i32 - 1 - inset;
        if x1 <= x0 || y1 <= y0 {
            break;
        }
        // top and bottom edges
        for x in x0..=x1 {
            blend_pixel(data, w, x, y0, alpha);
            blend_pixel(data, w, x, y1, alpha);
        }
        // left and right edges (excluding corners already done)
        for y in (y0 + 1)..y1 {
            blend_pixel(data, w, x0, y, alpha);
            blend_pixel(data, w, x1, y, alpha);
        }
    }
}

#[inline]
fn blend_pixel(data: &mut [u8], w: usize, x: i32, y: i32, alpha: u8) {
    let idx = (y as usize * w + x as usize) * 4;
    if idx + 2 >= data.len() {
        return;
    }
    let a = alpha as f32 / 255.0;
    // darken towards black: out = src * (1 - a)
    for ch in 0..3 {
        let v = data[idx + ch] as f32 * (1.0 - a);
        data[idx + ch] = v.round().clamp(0.0, 255.0) as u8;
    }
}

/// Framing: expand 1px stone, 6px bear-brown, 2px blaze hairline bottom.
/// Returns a new buffer and new dimensions. Input is RGBA w*h*4.
pub fn framing_rgba_inner(data: &[u8], w: usize, h: usize) -> (Vec<u8>, usize, usize) {
    let w1 = w + 2; // +1 each side stone
    let h1 = h + 2;
    let w2 = w1 + 12; // +6 each side bear
    let h2 = h1 + 12;
    let mut out = vec![0u8; w2 * h2 * 4];
    // fill outer bear brown
    for px in 0..w2 * h2 {
        out[px * 4] = BEAR_BROWN[0];
        out[px * 4 + 1] = BEAR_BROWN[1];
        out[px * 4 + 2] = BEAR_BROWN[2];
        out[px * 4 + 3] = 255;
    }
    // fill inner stone ring thickness 1 around original (at offset 6)
    // Easier: composite layers: outer already bear, now blit stone-bordered inner,
    // then blit source centered at (7,7)
    // Draw stone border: area [6,6)..[6+w1,6+h1) where border==0 or w1-1 or h1-1
    for y in 0..h1 {
        for x in 0..w1 {
            let is_border = x == 0 || x == w1 - 1 || y == 0 || y == h1 - 1;
            let ox = 6 + x;
            let oy = 6 + y;
            let oidx = (oy * w2 + ox) * 4;
            if is_border {
                out[oidx] = STONE[0];
                out[oidx + 1] = STONE[1];
                out[oidx + 2] = STONE[2];
                out[oidx + 3] = 255;
            } else {
                // interior: will be overwritten by source; fill placeholder
                out[oidx] = 255;
                out[oidx + 1] = 255;
                out[oidx + 2] = 255;
                out[oidx + 3] = 255;
            }
        }
    }
    // blit source at (7,7)
    for y in 0..h {
        for x in 0..w {
            let sidx = (y * w + x) * 4;
            let didx = ((y + 7) * w2 + (x + 7)) * 4;
            out[didx] = data[sidx];
            out[didx + 1] = data[sidx + 1];
            out[didx + 2] = data[sidx + 2];
            out[didx + 3] = data[sidx + 3];
        }
    }
    // blaze hairline bottom 2px: rows h2-2..h2
    for y in (h2 - 2)..h2 {
        for x in 0..w2 {
            let idx = (y * w2 + x) * 4;
            out[idx] = BLAZE_ORANGE[0];
            out[idx + 1] = BLAZE_ORANGE[1];
            out[idx + 2] = BLAZE_ORANGE[2];
            out[idx + 3] = 255;
        }
    }
    (out, w2, h2)
}

// ---------------------------------------------------------------------------
// PyO3 bindings
// ---------------------------------------------------------------------------

/// autocontrast(data: bytes, width: int, height: int, cutoff: float = 0.5) -> bytes
#[pyfunction]
#[pyo3(signature = (data, width, height, cutoff=0.5))]
fn autocontrast(data: Vec<u8>, width: usize, height: usize, cutoff: f32) -> PyResult<Vec<u8>> {
    if data.len() != width * height * 4 {
        return Err(pyo3::exceptions::PyValueError::new_err(format!(
            "expected {} bytes for {}x{} RGBA, got {}",
            width * height * 4,
            width,
            height,
            data.len()
        )));
    }
    let mut buf = data;
    autocontrast_rgba_inner(&mut buf, width, height, cutoff);
    Ok(buf)
}

/// vignette(data: bytes, width: int, height: int) -> bytes
#[pyfunction]
fn vignette(data: Vec<u8>, width: usize, height: usize) -> PyResult<Vec<u8>> {
    if data.len() != width * height * 4 {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "invalid RGBA length",
        ));
    }
    let mut buf = data;
    vignette_rgba_inner(&mut buf, width, height);
    Ok(buf)
}

/// framing(data: bytes, width: int, height: int) -> tuple[bytes, int, int]
#[pyfunction]
fn framing(data: Vec<u8>, width: usize, height: usize) -> PyResult<(Vec<u8>, usize, usize)> {
    if data.len() != width * height * 4 {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "invalid RGBA length",
        ));
    }
    Ok(framing_rgba_inner(&data, width, height))
}

/// enhance_hero_file(in_path: str, out_path: str, cutoff: float=0.5, with_vignette: bool=true, with_framing: bool=true) -> str
/// Convenience: loads PNG/JPEG, applies autocontrast+vignette+framing, saves PNG.
#[pyfunction]
#[pyo3(signature = (in_path, out_path, cutoff=0.5, with_vignette=true, with_framing=true))]
fn enhance_hero_file(
    in_path: String,
    out_path: String,
    cutoff: f32,
    with_vignette: bool,
    with_framing: bool,
) -> PyResult<String> {
    let img =
        image::open(&in_path).map_err(|e| pyo3::exceptions::PyIOError::new_err(format!("{e}")))?;
    let rgba = img.to_rgba8();
    let (w, h) = (rgba.width() as usize, rgba.height() as usize);
    let mut buf = rgba.into_raw();
    autocontrast_rgba_inner(&mut buf, w, h, cutoff);
    if with_vignette {
        vignette_rgba_inner(&mut buf, w, h);
    }
    let (final_buf, fw, fh) = if with_framing {
        framing_rgba_inner(&buf, w, h)
    } else {
        (buf, w, h)
    };
    let out_img = image::RgbaImage::from_raw(fw as u32, fh as u32, final_buf)
        .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("failed to create image"))?;
    out_img
        .save(&out_path)
        .map_err(|e| pyo3::exceptions::PyIOError::new_err(format!("{e}")))?;
    Ok(out_path)
}

#[pymodule]
fn _kodiak_local(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(autocontrast, m)?)?;
    m.add_function(wrap_pyfunction!(vignette, m)?)?;
    m.add_function(wrap_pyfunction!(framing, m)?)?;
    m.add_function(wrap_pyfunction!(enhance_hero_file, m)?)?;
    m.add(
        "__doc__",
        "Kodiak local Rust accelerators: autocontrast, vignette, framing",
    )?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn autocontrast_stretches() {
        // gradient 0..255 across R channel
        let w = 256;
        let h = 1;
        let mut data = vec![0u8; w * h * 4];
        for x in 0..w {
            data[x * 4] = x as u8;
            data[x * 4 + 1] = 128;
            data[x * 4 + 2] = 128;
            data[x * 4 + 3] = 255;
        }
        autocontrast_rgba_inner(&mut data, w, h, 0.5);
        // lo/hi trimming small; output should still be ~0..255
        assert_eq!(data[0], 0);
        assert_eq!(data[(w - 1) * 4], 255);
    }
    #[test]
    fn vignette_darkens_edge() {
        let w = 100;
        let h = 100;
        let mut data = vec![255u8; w * h * 4];
        vignette_rgba_inner(&mut data, w, h);
        // the i=0 ring has alpha 0 (skipped) so the absolute corner (0,0) is
        // untouched; the first darkened ring is inset 1px. assert the edge pixel
        // that actually lies on a ring is darkened.
        let edge = (1 * w + 1) * 4;
        assert!(data[edge] < 255);
        // center unchanged
        let mid = (50 * w + 50) * 4;
        assert_eq!(data[mid], 255);
    }
    #[test]
    fn framing_expands() {
        let w = 10;
        let h = 10;
        let data = vec![255u8; w * h * 4];
        let (out, fw, fh) = framing_rgba_inner(&data, w, h);
        assert_eq!(fw, w + 14);
        assert_eq!(fh, h + 14);
        assert_eq!(out.len(), fw * fh * 4);
        // bottom row blaze
        let idx = ((fh - 1) * fw) * 4;
        assert_eq!([out[idx], out[idx + 1], out[idx + 2]], BLAZE_ORANGE);
    }
}
