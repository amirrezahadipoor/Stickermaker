#!/usr/bin/env python3
"""
cutline_white.py — die-cut paths from a WHITE-background sticker sheet
                      (red hairline drawn around each sticker, soft drop shadow).

Why not "every non-white pixel is foreground"?  The sheet has four layers:
    paper white -> soft grey shadow -> white margin -> red hairline -> white -> art
A plain threshold merges the shadow into the sticker. So we do:

1. split the sheet into non-white layers:  paper / shadow / art+line
   art+line = anything saturated or dark  (shadow is neutral grey, paper is white)
2. split the canvas into the sticker cells (rows/cols from the art mask projection),
   so two stickers can never merge into one blob
3. per cell: fill holes -> sticker disc, then grow outward by the measured white
   margin (distance to the first shadow pixel) so the blade runs just outside the
   red hairline, then smooth contour -> closed cubic Bezier
4. verify 9 closed paths, no contact, clear of the canvas edge

Usage: python3 cutline_white.py in.png outdir [--expect=9]
"""
import os, sys, json
import numpy as np
import cv2
from shapely.geometry import Polygon, MultiPolygon

# ---------------------------------------------------------------- tunables
CANVAS_MM = (105.0, 148.0)
DPI = 300
EXPECTED = 9
GROW_PX = 5.0          # cut this far OUTSIDE the outer red hairline (px @ source res) ≈ 0.35 mm
BLUR_SIGMA = 3.0       # smoothing at 2x scale
RESAMPLE_SPACING = 5.0
TENSION = 0.85
MIN_GAP_PX = 4.0
EDGE_MARGIN_PX = 4.0
STROKE_PT = 0.25
MIN_AREA_FRAC = 0.004
SKIP_TOP = 0           # px from the top that must never be treated as sticker art


# ---------------------------------------------------------------- helpers
def fill_holes(mask):
    h, w = mask.shape
    ff = mask.copy()
    f = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(ff, f, (0, 0), 255)
    return cv2.bitwise_or(mask, cv2.bitwise_not(ff))


def layers(img):
    b, g, r = (img[:, :, i].astype(np.int16) for i in range(3))
    mn = img.min(axis=2).astype(np.int16)
    mx = img.max(axis=2).astype(np.int16)
    sat = mx - mn
    paper = ((mn >= 246) & (sat <= 5)).astype(np.uint8) * 255
    shadow = ((paper == 0) & (sat <= 12) & (mn >= 165)).astype(np.uint8) * 255
    art = ((paper == 0) & (shadow == 0)).astype(np.uint8) * 255
    art = cv2.morphologyEx(art, cv2.MORPH_CLOSE,
                           cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    return paper, shadow, art


def kmeans1d(vals, k, iters=60):
    """tiny 1-D k-means -> sorted cluster centres."""
    if k <= 1 or len(vals) <= k:
        return [float(np.mean(vals))] if len(vals) else [0.0]
    v = np.sort(np.asarray(vals, float))
    q = np.linspace(0, len(v) - 1, k).astype(int)
    cent = v[q].copy()
    for _ in range(iters):
        d = np.abs(v[:, None] - cent[None, :])
        lab = d.argmin(1)
        new = np.array([v[lab == i].mean() if (lab == i).any() else cent[i] for i in range(k)])
        if np.allclose(new, cent):
            break
        cent = new
    return sorted(cent.tolist())


def assign_blobs(art, expected, ncol=3):
    """cluster the art blobs into a 3-column grid and return cell rectangles."""
    H, W = art.shape
    core = (cv2.morphologyEx(art, cv2.MORPH_CLOSE,
                             cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))) > 0)
    mn = np.full(art.shape, 255, np.uint8)
    n, lab, st, cen = cv2.connectedComponentsWithStats(art, 8)
    blobs = []
    for i in range(1, n):
        a = st[i, cv2.CC_STAT_AREA]
        if a < 0.0015 * H * W:
            continue
        blobs.append(dict(label=i, area=int(a),
                          x0=int(st[i, cv2.CC_STAT_LEFT]), y0=int(st[i, cv2.CC_STAT_TOP]),
                          x1=int(st[i, cv2.CC_STAT_LEFT] + st[i, cv2.CC_STAT_WIDTH]),
                          y1=int(st[i, cv2.CC_STAT_TOP] + st[i, cv2.CC_STAT_HEIGHT]),
                          cx=float(cen[i][0]), cy=float(cen[i][1])))
    nrow = max(1, int(round(expected / ncol)))
    xc = kmeans1d([b['cx'] for b in blobs], min(ncol, max(1, len(blobs))))
    yc = kmeans1d([b['cy'] for b in blobs], min(nrow, max(1, len(blobs))))
    cellmap = {}
    for b in blobs:
        ci = int(np.argmin([abs(b['cx'] - c) for c in xc]))
        ri = int(np.argmin([abs(b['cy'] - c) for c in yc]))
        cellmap.setdefault((ri, ci), []).append(b['label'])
    return cellmap, len(yc), len(xc), lab


def split_page(art, expected, ncol=3, top_skip=0):
    """cut the page into a rows x cols grid at the widest white gutters.
    Boundaries are searched inside equal bands, so they always land in paper white
    instead of slicing a silhouette (a rectangle edge through art = straight cut)."""
    H, W = art.shape
    nrow = max(1, int(round(expected / ncol)))
    prof_x = (art > 0).sum(axis=0).astype(np.float64)
    prof_y = (art > 0).sum(axis=1).astype(np.float64)
    k = np.ones(15) / 15.0
    prof_x = np.convolve(prof_x, k, mode='same')
    prof_y = np.convolve(prof_y, k, mode='same')
    prof_y[:top_skip] = 0

    def bounds(prof, n, size, start=0):
        """greedy: each next boundary is the whitest spot between +12% and +55% ahead."""
        e = [start]
        pos = start
        for i in range(1, n):
            lo = int(pos + max(0.10 * size, 0.55 * (size - start) / n))
            hi = int(pos + 1.60 * (size - start) / n)
            lo, hi = max(start + 2, lo), min(size - 3, hi)
            nxt = lo + int(np.argmin(prof[lo:hi])) if hi > lo else int(pos + (size - start) / n)
            e.append(nxt)
            pos = nxt
        e.append(size)
        return e

    xe = bounds(prof_x, ncol, W)
    ye = bounds(prof_y, nrow, H, start=top_skip)
    out = []
    for r in range(len(ye) - 1):
        for c in range(len(xe) - 1):
            out.append((r, c, xe[c], ye[r], xe[c + 1], ye[r + 1]))
    return out


def sticker_disc(blob_labels, art, grow_px):
    """union of all art blobs that belong to one sticker -> filled disc, grown outward."""
    m = np.zeros(art.shape, np.uint8)
    for l in blob_labels:
        m[art_label == l] = 255
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE,
                         cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    # bridge narrow concave channels (hair strands, scarf tails) so the blade
    # never has to run into a thin slot
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE,
                         cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13)))
    m = fill_holes(m)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    if n > 1:
        big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        m = ((lab == big) * 255).astype(np.uint8)
    if grow_px > 0:
        k = int(round(grow_px)) * 2 + 1
        m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    # drop slivers/pinches that would create self-intersections after smoothing
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN,
                         cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE,
                         cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    return fill_holes(m)


def smooth_polygon(mask, ox, oy, scale=2.0):
    up = cv2.resize(mask, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
    up = cv2.GaussianBlur(up, (0, 0), BLUR_SIGMA)
    up = (up > 127).astype(np.uint8) * 255
    up = fill_holes(up)
    cnts, _ = cv2.findContours(up, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return None
    c = max(cnts, key=cv2.contourArea)[:, 0, :].astype(np.float64) / scale + np.array([ox, oy])
    poly = Polygon(c).buffer(0)
    if isinstance(poly, MultiPolygon):
        poly = max(poly.geoms, key=lambda g: g.area)
    if not poly.is_valid or poly.area <= 0:
        poly = Polygon(c)
    return poly


def resample(poly, spacing):
    ring = poly.exterior
    per = ring.length
    n = max(24, int(round(per / spacing)))
    return np.array([[p.x, p.y] for p in (ring.interpolate(i * per / n) for i in range(n))])


def bezier_path(pts, nd=2, tension=TENSION):
    n = len(pts)
    out = [f'M {pts[0][0]:.{nd}f} {pts[0][1]:.{nd}f}']
    for i in range(n):
        p0, p1, p2, p3 = pts[(i - 1) % n], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        c1 = p1 + (p2 - p0) * (tension / 6.0)
        c2 = p2 - (p3 - p1) * (tension / 6.0)
        out.append(f'C {c1[0]:.{nd}f} {c1[1]:.{nd}f} {c2[0]:.{nd}f} {c2[1]:.{nd}f} '
                   f'{p2[0]:.{nd}f} {p2[1]:.{nd}f}')
    out.append('Z')
    return ' '.join(out)


def repair(pts):
    """resampled rings can self-touch at pinch points -> make a clean single polygon."""
    p = Polygon(pts).buffer(0)
    if isinstance(p, MultiPolygon):
        p = max(p.geoms, key=lambda g: g.area)
    p = p.buffer(0)
    if isinstance(p, MultiPolygon):
        p = max(p.geoms, key=lambda g: g.area)
    if p.is_valid and p.area > 0:
        return resample(p, RESAMPLE_SPACING)
    return pts


def sample_path(pts, steps=10, tension=TENSION):
    n = len(pts)
    s = np.linspace(0, 1, steps, endpoint=False)[:, None]
    out = []
    for i in range(n):
        p0, p1, p2, p3 = pts[(i - 1) % n], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        c1 = p1 + (p2 - p0) * (tension / 6.0)
        c2 = p2 - (p3 - p1) * (tension / 6.0)
        out.append(((1 - s) ** 3) * p1 + 3 * ((1 - s) ** 2) * s * c1 + 3 * (1 - s) * s ** 2 * c2 + s ** 3 * p2)
    return np.vstack(out)


# ---------------------------------------------------------------- main
def main(inp, outdir, expected=EXPECTED):
    os.makedirs(outdir, exist_ok=True)
    img = cv2.imread(inp, cv2.IMREAD_COLOR)
    if img is None:
        raise SystemExit(f'cannot read {inp}')
    H, W = img.shape[:2]
    mm_per_px = CANVAS_MM[0] / W

    paper, shadow, art = layers(img)
    if SKIP_TOP:
        art[:SKIP_TOP, :] = 0            # header strip (logo / address / barcode) is never cut
    rects = split_page(art, expected, top_skip=SKIP_TOP)
    print(f'grid: {len({r[0] for r in rects})} rows x {len({r[1] for r in rects})} cols, {len(rects)} cells')

    def disc_of_cell(x0, y0, x1, y1, grow=GROW_PX):
        cell = np.zeros((H, W), np.uint8)
        cell[y0:y1, x0:x1] = art[y0:y1, x0:x1]
        if (cell > 0).sum() < MIN_AREA_FRAC * H * W * 0.2:
            return None
        m = cv2.morphologyEx(cell, cv2.MORPH_CLOSE,
                             cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE,
                             cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13)))
        m = fill_holes(m)
        nn, ll, ss, _ = cv2.connectedComponentsWithStats(m, 8)
        if nn > 1:
            big = 1 + int(np.argmax(ss[1:, cv2.CC_STAT_AREA]))
            m = ((ll == big) * 255).astype(np.uint8)
        if grow > 0:
            k = int(round(grow)) * 2 + 1
            m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN,
                             cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE,
                             cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
        return fill_holes(m)

    shapes = []
    for (ri, ci, x0, y0, x1, y1) in rects:
        m = disc_of_cell(x0, y0, x1, y1)
        if m is None:
            continue
        if (m > 0).sum() < MIN_AREA_FRAC * H * W * 0.3:
            continue
        poly = smooth_polygon(m, 0, 0)
        if poly is None or poly.area < MIN_AREA_FRAC * H * W * 0.25:
            continue
        shapes.append(dict(id=len(shapes) + 1, pts=repair(resample(poly, RESAMPLE_SPACING)),
                           grow=GROW_PX, row=ri, col=ci))
    print(f'sticker shapes: {len(shapes)}')

    # ---- guarantee clearance: where two stickers bleed into each other, the
    #      cut line is split down the middle (this is what a die maker does).
    def to_poly(sh):
        return Polygon(sh['pts']).buffer(0)

    shapes = [dict(s_, pts=repair(s_['pts'])) for s_ in shapes]
    for it in range(12):
        pl = [to_poly(sh) for sh in shapes]
        pair = None
        for i in range(len(pl)):
            for j in range(i + 1, len(pl)):
                if pl[i].distance(pl[j]) < MIN_GAP_PX:
                    pair = (i, j)
                    break
            if pair:
                break
        edge_i = next((i for i, p in enumerate(pl)
                       if min(p.bounds[0], p.bounds[1], W - p.bounds[2], H - p.bounds[3]) < EDGE_MARGIN_PX), None)
        if pair is None and edge_i is None:
            break
        if pair:
            i, j = pair
            half = MIN_GAP_PX / 2.0 + 0.5
            a = pl[i].difference(pl[j].buffer(half, join_style=1, quad_segs=16))
            b = pl[j].difference(pl[i].buffer(half, join_style=1, quad_segs=16))
            for k, q in ((i, a), (j, b)):
                if isinstance(q, MultiPolygon):
                    q = max(q.geoms, key=lambda g: g.area)
                if q.is_valid and q.area > MIN_AREA_FRAC * H * W * 0.1:
                    shapes[k] = dict(shapes[k], pts=repair(resample(q, RESAMPLE_SPACING)))
        if edge_i is not None:
            q = pl[edge_i].buffer(-(EDGE_MARGIN_PX + 1.5), join_style=1, quad_segs=16)
            if isinstance(q, MultiPolygon):
                q = max(q.geoms, key=lambda g: g.area)
            if q.is_valid and q.area > MIN_AREA_FRAC * H * W * 0.1:
                shapes[edge_i] = dict(shapes[edge_i], pts=repair(resample(q, RESAMPLE_SPACING)))
    if it:
        print(f'[fix] clearance pass ran {it} iteration(s)')

    # ---- fallback: if clipping did not converge (deeply overlapping artwork),
    #      shrink the offending shapes uniformly until the lines are clear.
    for attempt in range(30):
        pl = [to_poly(sh) for sh in shapes]
        bad = [(i, j) for i in range(len(pl)) for j in range(i + 1, len(pl))
               if pl[i].distance(pl[j]) < MIN_GAP_PX]
        edges = [i for i, p in enumerate(pl)
                 if min(p.bounds[0], p.bounds[1], W - p.bounds[2], H - p.bounds[3]) < EDGE_MARGIN_PX]
        if not bad and not edges:
            break
        idx = sorted({k for pair in bad for k in pair} | set(edges))
        for k in idx:
            pts = shapes[k]['pts']
            c = pts.mean(axis=0)
            shrunk = repair((pts - c) * 0.965 + c)
            if Polygon(shrunk).area > MIN_AREA_FRAC * H * W * 0.1:
                shapes[k] = dict(shapes[k], pts=shrunk)
    if attempt:
        print(f'[fix] uniform scale-down used ({attempt} step(s))')

    # ---- SVG 1: cut line
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1"\n'
            f'     width="{CANVAS_MM[0]}mm" height="{CANVAS_MM[1]}mm"\n'
            f'     viewBox="0 0 {W} {H}">\n'
            f'  <title>{os.path.basename(os.path.dirname(inp))} - DIE CUT LINE - A6 '
            f'{CANVAS_MM[0]:.0f}x{CANVAS_MM[1]:.0f} mm / {DPI} DPI</title>\n'
            f'  <!-- 1 user unit = {mm_per_px:.5f} mm ; stroke 0.25pt is resolution independent -->\n'
            f'  <rect x="0" y="0" width="{W}" height="{H}" fill="#FFFFFF"/>\n'
            f'  <g id="CutLine" inkscape:groupmode="layer" inkscape:label="CutLine"\n'
            f'     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"\n'
            f'     fill="none" stroke="#FF0000" stroke-width="{STROKE_PT}pt"\n'
            f'     stroke-linejoin="round" stroke-linecap="round">\n')
    body = ''.join(f'    <path id="cut-{s["id"]:02d}" fill="none" stroke="#FF0000" '
                   f'stroke-width="{STROKE_PT}pt" stroke-linejoin="round" stroke-linecap="round" '
                   f'd="{bezier_path(s["pts"])}"/>\n' for s in shapes)
    svg_cut = head + body + '  </g>\n</svg>\n'
    p_cut = os.path.join(outdir, 'sticker_cutline_A6.svg')
    open(p_cut, 'w').write(svg_cut)

    # ---- SVG 2: preview (filled black on white)
    head_b = (f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1"\n'
              f'     width="{CANVAS_MM[0]}mm" height="{CANVAS_MM[1]}mm"\n'
              f'     viewBox="0 0 {W} {H}">\n  <title>cut line preview</title>\n'
              f'  <rect x="0" y="0" width="{W}" height="{H}" fill="#FFFFFF"/>\n'
              f'  <g id="CutLinePreview" fill="#000000" stroke="none">\n')
    body_b = ''.join(
        f'    <path id="shape-{s["id"]:02d}" d="{bezier_path(s["pts"])}"/>\n' for s in shapes)
    svg_prev = head_b + body_b + '  </g>\n</svg>\n'
    p_prev = os.path.join(outdir, 'sticker_cutline_preview.svg')
    open(p_prev, 'w').write(svg_prev)

    # ---- verification
    pl = [Polygon(sample_path(s['pts'])) for s in shapes]
    valid = all(p.is_valid and p.area > 0 for p in pl)
    gaps = [(round(pl[i].distance(pl[j]), 2), shapes[i]['id'], shapes[j]['id'])
            for i in range(len(pl)) for j in range(i + 1, len(pl))]
    min_gap = min(gaps)[0] if gaps else None
    edges = [min(p.bounds[0], p.bounds[1], W - p.bounds[2], H - p.bounds[3]) for p in pl]
    min_edge = round(min(edges), 2) if edges else None
    report = dict(
        source=inp, canvas_px=[W, H], canvas_mm=list(CANVAS_MM), dpi=DPI,
        expected_paths=expected, path_count=len(shapes),
        count_ok=len(shapes) == expected,
        closed_single_contour=valid,
        self_intersections=sum(0 if p.is_valid else 1 for p in pl),
        min_gap_px=min_gap, min_gap_mm=round(min_gap * mm_per_px, 3) if min_gap else None,
        min_edge_margin_px=min_edge, min_edge_margin_mm=round(min_edge * mm_per_px, 3) if min_edge else None,
        touching_pairs=[g for g in gaps if g[0] < MIN_GAP_PX],
        touching_edge=[i + 1 for i, e in enumerate(edges) if e < EDGE_MARGIN_PX],
        growth_px=[s['grow'] for s in shapes],
        total_area_mm2=round(sum(p.area for p in pl) * mm_per_px ** 2, 1),
        per_sticker=[dict(id=s['id'], row=s['row'], col=s['col'],
                          w_mm=round((pl[i].bounds[2] - pl[i].bounds[0]) * mm_per_px, 1),
                          h_mm=round((pl[i].bounds[3] - pl[i].bounds[1]) * mm_per_px, 1))
                     for i, s in enumerate(shapes)],
    )
    report['geometry_pass'] = (valid and not report['touching_pairs']
                               and not report['touching_edge'] and report['self_intersections'] == 0)
    report['PASS'] = report['count_ok'] and report['geometry_pass']
    json.dump(report, open(os.path.join(outdir, 'verification.json'), 'w'), indent=2)
    print(json.dumps({k: report[k] for k in
                      ['path_count', 'count_ok', 'closed_single_contour', 'min_gap_mm',
                       'min_edge_margin_mm', 'touching_pairs', 'touching_edge', 'PASS']}, indent=2))
    return report


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    exp = next((int(a.split('=')[1]) for a in sys.argv if a.startswith('--expect=')), EXPECTED)
    SKIP_TOP = next((int(a.split('=')[1]) for a in sys.argv if a.startswith('--skip-top=')), 0)
    main(args[0], args[1], exp)
