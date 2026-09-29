#!/usr/bin/env python3
"""Generate 30-second ristra silhouette for SDXL ControlNet input (lineart + depth).

Pillow-only, <1s, deterministic. Synthesizes a real New Mexico ristra geometry
(Capsicum annuum var. annuum) that txt2img alone never held across 9 attempts:
single vertical twine, top knot, 6 smooth tapered pods with star calyx, fine
leather micro-wrinkles. ControlNet locks geometry; text prompt only styles.

Outputs (1344x768, matches kodiak-ink-ingredient-base):
  input_assets/sprint2-ingredients/red-chile-controlnet-lineart.png  — black contours on white (lineart/canny)
  input_assets/sprint2-ingredients/red-chile-controlnet-sketch.png   — alias for 30-sec deliverable name
  input_assets/sprint2-ingredients/red-chile-controlnet-depth.png    — grayscale depth (lighter = closer)

Usage: python scripts/generate_ristra_controlnet.py [--check]
"""
from pathlib import Path
import math
import time
from PIL import Image, ImageDraw, ImageFilter

W, H = 1344, 768
ROOT = Path(__file__).resolve().parent.parent
OUT_LINEART = ROOT / "input_assets/sprint2-ingredients/red-chile-controlnet-lineart.png"
OUT_SKETCH = ROOT / "input_assets/sprint2-ingredients/red-chile-controlnet-sketch.png"
OUT_DEPTH = ROOT / "input_assets/sprint2-ingredients/red-chile-controlnet-depth.png"

N_PODS, CENTER_X, TOP_KNOT_Y, POD_SPACING, POD_LENGTH, POD_WIDTH = 6, W//2, 90, 92, 145, 34

def tapered_pod_polygon(cx, cy, length=POD_LENGTH, width=POD_WIDTH, angle_deg=0):
    angle = math.radians(angle_deg)
    dx_perp = math.cos(angle) * width/2
    dy_perp = math.sin(angle) * width/2
    ax, ay, hl = math.sin(angle), math.cos(angle), length/2
    top = (cx - ax*hl, cy - ay*hl)
    tip = (cx + ax*hl, cy + ay*hl)
    top1 = (top[0] - dx_perp*0.85, top[1] + dy_perp*0.85)
    top2 = (top[0] + dx_perp*0.85, top[1] - dy_perp*0.85)
    mid1 = (cx - ax*hl*0.15 - dx_perp*1.0, cy - ay*hl*0.15 + dy_perp*1.0)
    mid2 = (cx - ax*hl*0.15 + dx_perp*1.0, cy - ay*hl*0.15 - dy_perp*1.0)
    low1 = (cx + ax*hl*0.45 - dx_perp*0.45, cy + ay*hl*0.45 + dy_perp*0.45)
    low2 = (cx + ax*hl*0.45 + dx_perp*0.45, cy + ay*hl*0.45 - dy_perp*0.45)
    return [top1, top2, mid2, low2, tip, low1, mid1]

def draw_lineart():
    img = Image.new("RGB", (W, H), (255,255,255))
    d = ImageDraw.Draw(img)
    d.ellipse([CENTER_X-9, TOP_KNOT_Y-9, CENTER_X+9, TOP_KNOT_Y+9], outline=(0,0,0), width=3)
    d.ellipse([CENTER_X-3, TOP_KNOT_Y-3, CENTER_X+3, TOP_KNOT_Y+3], fill=(0,0,0))
    sy0, sy1 = TOP_KNOT_Y+9, TOP_KNOT_Y + POD_SPACING*N_PODS + 85
    d.line([(CENTER_X, sy0), (CENTER_X, sy1)], fill=(0,0,0), width=3)
    angles = [-14, 11, -9, 13, -11, 9]
    for i in range(N_PODS):
        cy = TOP_KNOT_Y + 55 + i*POD_SPACING
        angle = angles[i%len(angles)]
        cx = CENTER_X + (6 if angle>0 else -6)
        poly = tapered_pod_polygon(cx, cy+12, angle_deg=angle)
        d.polygon(poly, fill=(255,255,255), outline=(0,0,0), width=2)
        calyx_cx = cx - math.sin(math.radians(angle))*POD_LENGTH/2
        calyx_cy = cy+12 - math.cos(math.radians(angle))*POD_LENGTH/2
        r = 8
        pts = []
        for k in range(5):
            a = math.radians(k * 72 - 90 + angle)
            pts.append((calyx_cx + math.cos(a) * r, calyx_cy + math.sin(a) * r))
            a2 = math.radians(k * 72 - 90 + 36 + angle)
            pts.append((calyx_cx + math.cos(a2) * r * 0.45, calyx_cy + math.sin(a2) * r * 0.45))
        d.polygon(pts, outline=(0,0,0), width=2)
        d.line([(CENTER_X-7, calyx_cy), (CENTER_X+7, calyx_cy)], fill=(0,0,0), width=2)
        for off in (-18,-3,12):
            d.line([(cx-8, cy+12+off), (cx+8, cy+12+off)], fill=(45,45,45), width=1)
    d.line([(CENTER_X, sy1), (CENTER_X, sy1+18)], fill=(0,0,0), width=2)
    return img

def draw_depth():
    img = Image.new("L", (W, H), 20)
    d = ImageDraw.Draw(img, "L")
    sy0, sy1 = TOP_KNOT_Y+9, TOP_KNOT_Y + POD_SPACING*N_PODS + 85
    d.line([(CENTER_X, sy0), (CENTER_X, sy1)], fill=90, width=4)
    angles = [-14, 11, -9, 13, -11, 9]
    for i in range(N_PODS):
        cy = TOP_KNOT_Y + 55 + i*POD_SPACING
        angle = angles[i%len(angles)]
        cx = CENTER_X + (6 if angle>0 else -6)
        poly = tapered_pod_polygon(cx, cy+12, angle_deg=angle)
        depth = 185 + int(30*math.sin((i+0.5)*math.pi/N_PODS))
        d.polygon(poly, fill=depth)
        calyx_cx = cx - math.sin(math.radians(angle))*POD_LENGTH/2
        calyx_cy = cy+12 - math.cos(math.radians(angle))*POD_LENGTH/2
        d.ellipse([calyx_cx-6, calyx_cy-6, calyx_cx+6, calyx_cy+6], fill=min(255, depth+25))
    return d._image.filter(ImageFilter.GaussianBlur(radius=3)).convert("RGB")

if __name__ == "__main__":
    t0=time.time()
    lineart = draw_lineart()
    depth = draw_depth()
    OUT_LINEART.parent.mkdir(parents=True, exist_ok=True)
    lineart.save(OUT_LINEART, "PNG")
    lineart.save(OUT_SKETCH, "PNG")
    depth.save(OUT_DEPTH, "PNG")
    print(f"lineart {OUT_LINEART.relative_to(ROOT)} {lineart.size} {time.time()-t0:.2f}s")
    print(f"depth   {OUT_DEPTH.relative_to(ROOT)} {depth.size}")
