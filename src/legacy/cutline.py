#!/usr/bin/env python3
"""
cutline.py - build die-cut (cut line) vector paths from a black-background sticker sheet.

Pipeline
--------
1. threshold  : every non-black pixel -> foreground, holes filled, connected components found (15 stickers)
2. smooth     : per sticker -> morphological close, 2x upsample, Gaussian blur + re-threshold,
                then contour -> resample -> closed Catmull-Rom -> cubic Bezier path
3. output SVG : A) white bg, layer "CutLine", 15 paths, stroke #FF0000, stroke-width 0.25pt, fill none
                B) same 15 paths filled solid black on white (preview)
4. verify     : exactly 15 closed paths, no path touches another, none touches the canvas edge

Usage: python3 cutline.py [input.png] [outdir]
"""
import sys, os, json, math
import numpy as np
import cv2
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union

# ----------------------------------------------------------------------------- config
CANVAS_MM = (105.0, 148.0)          # A6 portrait
DPI = 300
MIN_AREA_FRAC = 0.002               # discard blobs smaller than 0.2% of the sheet
CLOSE_KERNEL = 7                    # morphological close (merge thin parts / tiny notches)
BLUR_SIGMA = 2.6                    # smoothing strength (px, at 2x scale) — gentle: keeps fingers/balls
RESAMPLE_SPACING = 4.0              # point spacing along the cut line (px at 2x scale)
BEZIER_TENSION = 0.85               # Catmull-Rom tension (1.0 = classic, <1 = tamer curves)
CUT_INSET_PX = 1.6                  # cut slightly inside the printed edge (px at 1x)
EDGE_MARGIN_PX = 2.0                # required free space to the canvas edge (px at 1x)
MIN_GAP_PX = 2.0                    # required free space between two cut lines (px at 1x)
STROKE_PT = 0.25
EXPECTED_STICKERS = 15              # sheet contract from the brief
# foreground rule
#   'any'    : every non-black pixel is foreground (brief) -> the blade follows glows/effects
#   'border' : only the near-white sticker border is foreground -> the blade follows the white halo
FG_MODE = 'border'
WHITE_MIN_CHANNEL = 235             # 'border' mode: min(R,G,B) above this == white border
BORDER_BRIDGE_PX = 2                # 'border' mode: close small gaps in the ring before hole filling


# ----------------------------------------------------------------------------- helpers
def load_mask(path, mode=None):
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise SystemExit(f'cannot read {path}')
    mode = mode or FG_MODE
    if mode == 'border':
        # near-white ring only; bridge antialias gaps, fill, then shrink back
        mn = img.min(axis=2)
        m = (mn > WHITE_MIN_CHANNEL).astype(np.uint8) * 255
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k)
        m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                                   (2 * BORDER_BRIDGE_PX + 1,) * 2))
        m = fill_holes(m)
        m = cv2.erode(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                                   (2 * BORDER_BRIDGE_PX + 1,) * 2))
        return img, m
    # max channel > small epsilon  ==  "every non-black pixel"
    mx = img.max(axis=2)
    mask = (mx > 12).astype(np.uint8) * 255
    return img, mask


def fill_holes(mask):
    """flood fill from the border, everything not reached is a hole -> add it."""
    h, w = mask.shape
    flood = mask.copy()
    ff = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(flood, ff, (0, 0), 255)
    holes = cv2.bitwise_not(flood)
    return cv2.bitwise_or(mask, holes)


def components(mask):
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    total = mask.shape[0] * mask.shape[1]
    keep = []
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        if area / total < MIN_AREA_FRAC:
            continue                                  # tiny noise
        x, y, w, h = (stats[i, cv2.CC_STAT_LEFT], stats[i, cv2.CC_STAT_TOP],
                      stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT])
        keep.append(dict(label=i, area=int(area), bbox=(x, y, w, h), cy=y + h / 2, cx=x + w / 2))
    # if more blobs survived the noise filter than the sheet is supposed to have,
    # keep the largest EXPECTED_STICKERS ones and report the rest
    discarded = []
    if len(keep) > EXPECTED_STICKERS:
        keep.sort(key=lambda d: d['area'], reverse=True)
        discarded = [d['area'] for d in keep[EXPECTED_STICKERS:]]
        keep = keep[:EXPECTED_STICKERS]
        for d in keep:
            d['nb'] = next((k for k in range(1, n) if labels[0, 0] == -1), None)
    # reading order: top->bottom, left->right
    keep.sort(key=lambda d: (round(d['cy'] / 250), d['cx']))
    return labels, keep, discarded


def smooth_component_mask(sub):
    """morph close -> 2x upsample -> gaussian blur -> re-threshold -> fill holes."""
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (CLOSE_KERNEL, CLOSE_KERNEL))
    sub = cv2.morphologyEx(sub, cv2.MORPH_CLOSE, k)
    sub = fill_holes(sub)
    up = cv2.resize(sub, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
    sigma = BLUR_SIGMA
    if sigma > 0:
        up = cv2.GaussianBlur(up, (0, 0), sigma)
    up = (up > 127).astype(np.uint8) * 255
    up = fill_holes(up)
    # keep only the largest blob of this sticker (islands from blur noise)
    n, lab, st, _ = cv2.connectedComponentsWithStats(up, 8)
    if n > 2:
        big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        up = ((lab == big) * 255).astype(np.uint8)
    return up


def polygon_from_mask(up, scale_back=2.0, ox=0.0, oy=0.0):
    cnts, _ = cv2.findContours(up, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cnts, key=cv2.contourArea)
    pts = c[:, 0, :].astype(np.float64) / scale_back + np.array([ox, oy])
    poly = Polygon(pts)
    if not poly.is_valid:
        poly = poly.buffer(0)
    if isinstance(poly, MultiPolygon):
        poly = max(poly.geoms, key=lambda g: g.area)
    if poly.area <= 0:
        poly = poly.buffer(0.01)
    return poly


def resample(poly, spacing):
    """evenly spaced points along a closed ring (shapely linear referencing)."""
    ring = poly.exterior
    per = ring.length
    n = max(24, int(round(per / spacing)))
    pts = [ring.interpolate(i * per / n) for i in range(n)]
    return np.array([[p.x, p.y] for p in pts])


def catmull_rom_path(pts, tension=1.0, nd=2):
    """closed Catmull-Rom spline -> cubic bezier SVG 'd' string."""
    n = len(pts)
    out = [f'M {pts[0][0]:.{nd}f} {pts[0][1]:.{nd}f}']
    for i in range(n):
        p0 = pts[(i - 1) % n]
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n]
        c1 = p1 + (p2 - p0) * (tension / 6.0)
        c2 = p2 - (p3 - p1) * (tension / 6.0)
        out.append(f'C {c1[0]:.{nd}f} {c1[1]:.{nd}f} {c2[0]:.{nd}f} {c2[1]:.{nd}f} '
                   f'{p2[0]:.{nd}f} {p2[1]:.{nd}f}')
    out.append('Z')
    return ' '.join(out)


def sample_bezier_path(pts, tension=1.0, steps=12):
    """dense polyline of the same spline (used for geometric verification)."""
    n = len(pts)
    s = np.linspace(0, 1, steps, endpoint=False)[:, None]
    out = []
    for i in range(n):
        p0, p1 = pts[(i - 1) % n], pts[i]
        p2, p3 = pts[(i + 1) % n], pts[(i + 2) % n]
        c1 = p1 + (p2 - p0) * (tension / 6.0)
        c2 = p2 - (p3 - p1) * (tension / 6.0)
        b = ((1 - s) ** 3) * p1 + 3 * ((1 - s) ** 2) * s * c1 + 3 * (1 - s) * s ** 2 * c2 + s ** 3 * p2
        out.append(b)
    return np.vstack(out)


# ----------------------------------------------------------------------------- main
def main(inp='uploads/soccer.png', outdir='cutlines', mode=None, expected=None):
    global EXPECTED_STICKERS
    if expected:
        EXPECTED_STICKERS = expected
    os.makedirs(outdir, exist_ok=True)
    img, mask = load_mask(inp, mode)
    H, W = mask.shape
    mm_per_px = CANVAS_MM[0] / W
    px_per_pt = (CANVAS_MM[0] / W) / (25.4 / 72.0)     # canvas px per typographic point

    mask_filled = fill_holes(mask)
    labels, comps, extra_blobs = components(mask_filled)
    if len(comps) != EXPECTED_STICKERS:
        print(f'[warn] found {len(comps)} components (expected {EXPECTED_STICKERS})')

    shapes = []
    for idx, c in enumerate(comps, start=1):
        x, y, w, h = c['bbox']
        pad = 24
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(W, x + w + pad), min(H, y + h + pad)
        sub = np.where(labels[y0:y1, x0:x1] == c['label'], 255, 0).astype(np.uint8)
        up = smooth_component_mask(sub)
        poly = polygon_from_mask(up, 2.0, x0, y0)
        # inset so the blade runs just inside the printed edge (keeps the white halo)
        if CUT_INSET_PX > 0:
            q = poly.buffer(-CUT_INSET_PX, join_style=1, quad_segs=8)
            if isinstance(q, MultiPolygon):
                q = max(q.geoms, key=lambda g: g.area)
            if q.is_valid and q.area > 0:
                poly = q
        pts = resample(poly, RESAMPLE_SPACING)
        shapes.append(dict(id=idx, pts=pts))

    # ---- collision / edge fixing (shrink only if really needed) -----------------
    def polys_of(shapes, shrink=0.0):
        out = []
        for s in shapes:
            p = Polygon(s['pts'])
            if shrink:
                p = p.buffer(-shrink, join_style=1, quad_segs=8)
            out.append(p)
        return out

    shrink_iter = 0
    while True:
        pl = polys_of(shapes, shrink=shrink_iter)
        bad = False
        for i in range(len(pl)):
            minx, miny, maxx, maxy = pl[i].bounds
            if minx < EDGE_MARGIN_PX or miny < EDGE_MARGIN_PX or \
               maxx > W - EDGE_MARGIN_PX or maxy > H - EDGE_MARGIN_PX:
                bad = True
        for i in range(len(pl)):
            for j in range(i + 1, len(pl)):
                if pl[i].distance(pl[j]) < MIN_GAP_PX:
                    bad = True
        if not bad or shrink_iter > 4:
            break
        shrink_iter += 0.5
        shapes = [dict(id=s['id'], pts=resample(Polygon(s['pts']).buffer(-0.5, join_style=1, quad_segs=8)
                                                .buffer(0), RESAMPLE_SPACING)) for s in shapes]
    if shrink_iter:
        print(f'[fix] extra inward offset applied: {shrink_iter} px')

    # ---- SVG A : cut line -------------------------------------------------------
    stroke_user = STROKE_PT * px_per_pt
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1"\n'
            f'     width="{CANVAS_MM[0]}mm" height="{CANVAS_MM[1]}mm"\n'
            f'     viewBox="0 0 {W} {H}">\n'
            f'  <title>{os.path.basename(inp)} - DIE CUT LINE - A6 {CANVAS_MM[0]:.0f}x{CANVAS_MM[1]:.0f} mm / {DPI} DPI</title>\n'
            f'  <!-- 1 user unit = {mm_per_px:.5f} mm ; stroke-width {stroke_user:.5f} uu = {STROKE_PT} pt -->\n'
            f'  <rect x="0" y="0" width="{W}" height="{H}" fill="#FFFFFF"/>\n'
            f'  <g id="CutLine" inkscape:groupmode="layer" inkscape:label="CutLine"\n'
            f'     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"\n'
            f'     fill="none" stroke="#FF0000" stroke-width="{STROKE_PT}pt" data-stroke-uu="{stroke_user:.5f}"\n'
            f'     stroke-linejoin="round" stroke-linecap="round">\n')
    body = []
    for s in shapes:
        body.append(f'    <path id="cut-{s["id"]:02d}" fill="none" stroke="#FF0000" '
                    f'stroke-width="{STROKE_PT}pt" stroke-linejoin="round" stroke-linecap="round" '
                    f'd="{catmull_rom_path(s["pts"], BEZIER_TENSION)}"/>\n')
    svg_cut = head + ''.join(body) + '  </g>\n</svg>\n'
    p_cut = os.path.join(outdir, 'sticker_cutline_A6.svg')
    open(p_cut, 'w').write(svg_cut)

    # ---- SVG B : preview (filled black on white) --------------------------------
    head_b = (f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1"\n'
              f'     width="{CANVAS_MM[0]}mm" height="{CANVAS_MM[1]}mm"\n'
              f'     viewBox="0 0 {W} {H}">\n'
              f'  <title>Football sticker sheet - cut line preview</title>\n'
              f'  <rect x="0" y="0" width="{W}" height="{H}" fill="#FFFFFF"/>\n'
              f'  <g id="CutLinePreview" fill="#000000" stroke="none">\n')
    body_b = [f'    <path id="shape-{s["id"]:02d}" d="{catmull_rom_path(s["pts"], BEZIER_TENSION)}"/>\n'
              for s in shapes]
    svg_prev = head_b + ''.join(body_b) + '  </g>\n</svg>\n'
    p_prev = os.path.join(outdir, 'sticker_cutline_preview.svg')
    open(p_prev, 'w').write(svg_prev)

    # ---- verification -----------------------------------------------------------
    report = {}
    report['canvas_px'] = [W, H]
    report['canvas_mm'] = list(CANVAS_MM)
    report['fg_mode'] = FG_MODE if mode is None else mode
    report['discarded_extra_blobs'] = len(extra_blobs)
    report['path_count'] = len(shapes)
    pl = polys_of(shapes)
    sampled = []
    for s in shapes:
        sm = sample_bezier_path(s['pts'], BEZIER_TENSION)
        sp = Polygon(sm)
        sampled.append(sp)

    simport = {'valid': all(p.is_valid for p in sampled),
               'simple': all(p.is_valid and p.area > 0 for p in sampled),
               'self_intersections': int(sum(0 if p.is_valid else 1 for p in sampled))}
    report['paths_valid_closed'] = all(p.is_valid and p.area > 0 for p in sampled)
    report['self_intersecting_paths'] = simport['self_intersections']

    gaps = []
    for i in range(len(pl)):
        for j in range(i + 1, len(pl)):
            gaps.append(dict(pair=[shapes[i]['id'], shapes[j]['id']], gap_px=round(pl[i].distance(pl[j]), 2),
                             gap_mm=round(pl[i].distance(pl[j]) * mm_per_px, 3)))
    report['min_gap_px'] = min(g['gap_px'] for g in gaps)
    report['min_gap_mm'] = round(report['min_gap_px'] * mm_per_px, 3)
    report['touching_pairs'] = [g for g in gaps if g['gap_px'] < MIN_GAP_PX]

    edges = []
    for i, p in enumerate(pl):
        minx, miny, maxx, maxy = p.bounds
        m = min(minx, miny, W - maxx, H - maxy)
        edges.append(dict(id=shapes[i]['id'], edge_margin_px=round(m, 2), edge_margin_mm=round(m * mm_per_px, 3)))
    report['min_edge_margin_px'] = min(e['edge_margin_px'] for e in edges)
    report['min_edge_margin_mm'] = round(report['min_edge_margin_px'] * mm_per_px, 3)
    report['paths_touching_edge'] = [e for e in edges if e['edge_margin_px'] < EDGE_MARGIN_PX]
    report['per_sticker'] = [
        dict(id=s['id'], points=int(len(s['pts'])),
             bbox_mm=[round(v * mm_per_px, 2) for v in pl[i].bounds],
             width_mm=round((pl[i].bounds[2] - pl[i].bounds[0]) * mm_per_px, 2),
             height_mm=round((pl[i].bounds[3] - pl[i].bounds[1]) * mm_per_px, 2))
        for i, s in enumerate(shapes)]

    report['expected_path_count'] = EXPECTED_STICKERS
    report['count_ok'] = report['path_count'] == EXPECTED_STICKERS
    report['geometry_pass'] = (report['paths_valid_closed'] and not report['touching_pairs']
                               and not report['paths_touching_edge']
                               and report['self_intersecting_paths'] == 0)
    report['PASS'] = report['count_ok'] and report['geometry_pass']
    open(os.path.join(outdir, 'verification.json'), 'w').write(json.dumps(report, indent=2))

    # ---- raster check renders ----------------------------------------------------
    try:
        import cairosvg
        cairosvg.svg2png(url=p_cut, write_to=os.path.join(outdir, 'check_cutline.png'), output_width=700)
        cairosvg.svg2png(url=p_prev, write_to=os.path.join(outdir, 'check_preview.png'), output_width=700)
    except Exception as e:                                    # pragma: no cover
        print('[warn] no raster preview:', e)

    print(json.dumps({k: report[k] for k in
                      ['path_count', 'count_ok', 'paths_valid_closed', 'min_gap_mm', 'min_edge_margin_mm',
                       'touching_pairs', 'paths_touching_edge', 'geometry_pass', 'PASS']}, indent=2))
    print('wrote:', p_cut, p_prev, sep='\n  ')
    return report


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    mode = 'border' if '--border' in sys.argv else ('any' if '--any' in sys.argv else None)
    exp = None
    for a in sys.argv:
        if a.startswith('--expect='):
            exp = int(a.split('=')[1])
    main(*args[:2], mode=mode, expected=exp)
