#!/usr/bin/env python3
"""
make_pack.py — one pass, deterministic: sheet -> A6 page -> print files + die-cut lines.

Why this order?  The page is assembled by US, so we know exactly where every sticker
and every name chip sits. The cut lines are generated from that same placement data
(alpha masks of the placed stickers), never re-detected from the flattened page.
That removes every "boundary sliced a silhouette" / "ghost cut line" artefact.

Steps per theme
 1. load sheet, drop the header band, split on the widest white gutters, keep 6 stickers
 2. build the A6 page: header (logo + wordmark + QR + pack title), 6 stickers, 3 name chips
 3. cut lines: sticker alpha -> smoothed closed Bezier path; name chip -> rounded-rect path
 4. verify: 9 closed paths, no contact, clear of the trim edge; write SVG/PDF/proofs
"""
import os, json, math
import numpy as np
import cv2
import qrcode
import cairosvg
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from shapely.geometry import Polygon, MultiPolygon

# ---------------------------------------------------------------- config
A6 = (1240, 1748)
DPI = 300
MM = (105.0, 148.0)
HEADER_H = 210
FOOT_H = 236
MARGIN_X = 40
TOP_GAP = 8
STROKE_PT = 0.25
MIN_GAP_PX = 5.0
WHITE_T = 249            # below this = ink
EDGE_MARGIN_PX = 5.0
BLUR_SIGMA = 2.6
RESAMPLE = 5.0
TENSION = 0.85

FONT_XB = 'assets/fonts/Poppins-ExtraBold.ttf'
FONT_SB = 'assets/fonts/Poppins-SemiBold.ttf'
SHOP = 'Ghelghelishop.com'
QR_URL = 'https://ghelghelishop.com'

THEMES = [
    ('01_ugly_cute',      'UGLY CUTE',      ['GOOFY', 'DERP', 'BLOBBY'],   (232, 140, 20)),
    ('02_designer_toys',  'DESIGNER TOYS',  ['MOMO', 'BOBO', 'LUNA'],      (214, 120, 160)),
    ('03_cyber_robots',   'CYBER ROBOTS',   ['BOLT', 'NEON', 'CHIP'],      (0, 140, 200)),
    ('04_greek_gods',     'GREEK GODS',     ['ZEUS', 'POSEIDON', 'HADES'], (166, 120, 40)),
    ('05_kpop_hunters',   'K-POP HUNTERS',  ['RUMI', 'MIRA', 'ZOEY'],      (150, 40, 120)),
]


def name_stickers(strip_path):
    """the three name stickers come from a generated artwork strip, not from type"""
    im = trim(Image.open(strip_path).convert('RGB'), pad=4)
    return [sticker_rgba(c) for c in split_cells(im, 1, 3, strip_top=0)]


# ---------------------------------------------------------------- text / brand
def gradient_text(word, rgb, w, h, font_path=FONT_XB, tracking=0, gloss=True):
    S = 5
    W, H = w * S, h * S
    canvas = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    size = int(H * 0.80)
    while size > 10:
        f = ImageFont.truetype(font_path, size)
        tw = sum(d.textlength(c, font=f) for c in word) + tracking * S * (len(word) - 1)
        if tw < W * 0.90:
            break
        size -= 3
    f = ImageFont.truetype(font_path, size)
    widths = [d.textlength(c, font=f) for c in word]
    tw = sum(widths) + tracking * S * (len(word) - 1)
    asc, desc = f.getmetrics()
    x = (W - tw) / 2
    y = (H - (asc + desc)) / 2

    mask = Image.new('L', (W, H), 0)
    md = ImageDraw.Draw(mask)
    cx = x
    for ch, cw in zip(word, widths):
        md.text((cx, y), ch, font=f, fill=255)
        cx += cw + tracking * S
    # soft drop shadow
    sh = mask.filter(ImageFilter.MaxFilter(11)).filter(ImageFilter.GaussianBlur(3 * S))
    canvas.paste(Image.new('RGBA', (W, H), (25, 20, 45, 70)), (0, 2 * S), sh)
    # contrast outline
    ol = mask.filter(ImageFilter.MaxFilter(5))
    canvas.paste(Image.new('RGBA', (W, H), (18, 16, 30, 255)), (0, 0), ol)
    # gradient fill (light top -> deep bottom)
    light = tuple(min(255, int(c * 0.45 + 140)) for c in rgb)
    dark = tuple(int(c * 0.72) for c in rgb)
    grad = Image.new('RGB', (1, H))
    for i in range(H):
        t = i / max(1, H - 1)
        grad.putpixel((0, i), tuple(int(light[k] + (dark[k] - light[k]) * t) for k in range(3)))
    canvas.paste(grad.resize((W, H)), (0, 0), mask)
    if gloss:
        band = Image.new('L', (W, H), 0)
        ImageDraw.Draw(band).rectangle([0, int(H * 0.10), W, int(H * 0.42)], fill=80)
        band = band.filter(ImageFilter.GaussianBlur(3 * S))
        canvas.paste(Image.new('RGBA', (W, H), (255, 255, 255, 255)), (0, 0),
                     Image.composite(band, Image.new('L', (W, H), 0), mask))
    return canvas.resize((w, h), Image.LANCZOS)


def qr_image(px):
    q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=12, border=1)
    q.add_data(QR_URL)
    q.make(fit=True)
    return q.make_image(fill_color=(20, 20, 26), back_color='white').convert('RGB').resize((px, px), Image.LANCZOS)


def header(width, logo, qr, title, rgb):
    h = HEADER_H
    out = Image.new('RGBA', (width, h), (255, 255, 255, 0))
    lg_h = 128
    lg = logo.resize((int(logo.width * lg_h / logo.height), lg_h), Image.LANCZOS)
    out.alpha_composite(lg, (34, (h - lg_h) // 2 - 6))
    wm = gradient_text(SHOP, rgb, 452, 76)
    out.alpha_composite(wm, (lg.width + 64, 48))
    sub = gradient_text(title, tuple(int(c * 0.72) for c in rgb), 300, 34, FONT_SB, tracking=3)
    out.alpha_composite(sub, (lg.width + 68, 128))
    qp = 116
    qr_i = qr.resize((qp, qp), Image.LANCZOS).convert('RGBA')
    qx = width - 34 - qp
    out.alpha_composite(qr_i, (qx, (h - qp) // 2 - 10))
    d = ImageDraw.Draw(out)
    f = ImageFont.truetype(FONT_SB, 17)
    cap = 'SCAN TO SHOP'
    d.text((qx + (qp - d.textlength(cap, font=f)) / 2, (h - qp) // 2 + qp - 8), cap,
           font=f, fill=(60, 60, 68, 255))
    d.line([(28, h - 3), (width - 28, h - 3)], fill=(230, 230, 234, 255), width=2)
    return out


def name_chip(word, rgb, w, h):
    S = 4
    W, H = w * S, h * S
    chip = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(chip)
    pad = int(H * 0.09)
    d.rounded_rectangle([pad, pad, W - pad, H - pad], radius=int(H * 0.28),
                        fill=(255, 255, 255, 255), outline=(228, 46, 46, 255), width=3 * S)
    txt = gradient_text(word, rgb, W - 2 * pad - 10 * S, H - 2 * pad - 10 * S)
    chip.alpha_composite(txt, (pad + 5 * S, pad + 5 * S))
    return chip.resize((w, h), Image.LANCZOS)


# ---------------------------------------------------------------- sheet splitting
def trim(im, pad=4, thresh=249):
    a = np.array(im.convert('RGB'))
    ys, xs = np.where(a.min(axis=2) < thresh)
    if not len(ys):
        return im
    return im.crop((max(0, xs.min() - pad), max(0, ys.min() - pad),
                    min(a.shape[1], xs.max() + pad), min(a.shape[0], ys.max() + pad)))


def split_cells(img, rows=2, cols=3, strip_top=0):
    a = np.array(img.convert('RGB'))
    solid = (a.min(axis=2) < 249).astype(np.uint8)
    if strip_top:
        solid[:strip_top, :] = 0
    py = np.convolve(solid.sum(axis=1), np.ones(15) / 15, mode='same')
    px = np.convolve(solid.sum(axis=0), np.ones(15) / 15, mode='same')
    H, W = solid.shape

    def bounds(prof, n, size):
        """split on real white gutters: every candidate is the middle of a run of
        empty columns/rows, and each ideal boundary takes the closest free gutter."""
        thr = max(1.0, prof.max() * 0.05)
        white, runs, i = prof < thr, [], 0
        while i < size:
            if white[i]:
                j = i
                while j < size and white[j]:
                    j += 1
                if j - i >= 5:
                    runs.append((i + j) / 2.0)
                i = j
            else:
                i += 1
        e = [0]
        for k in range(1, n):
            ideal = size * k / n
            if runs:
                c = min(runs, key=lambda x: abs(x - ideal))
                runs.remove(c)
                e.append(int(c))
            else:
                e.append(int(ideal))
        e.append(size)
        return sorted(e)

    ye, xe = bounds(py, rows, H), bounds(px, cols, W)
    PAD = 16                                   # let each cell breathe into the white gutter
    def pad(v, n):
        return max(0, int(v) - PAD), min(n, int(v) + PAD)
    cells = []
    for r in range(rows):
        for c in range(cols):
            x0, x1 = pad(xe[c], W)[0], pad(xe[c + 1], W)[1]
            y0, y1 = pad(ye[r], H)[0], pad(ye[r + 1], H)[1]
            cells.append(img.crop((x0, y0, x1, y1)))
    return cells


def sticker_rgba(cell):
    """white -> transparent, keep only the biggest silhouette (kills neighbour slivers)."""
    im = trim(cell, pad=3)
    a = np.array(im.convert('RGB'))
    mask = (a.min(axis=2) < WHITE_T).astype(np.uint8)
    # a thin closed outline drawn by the generator would otherwise be filled into a
    # rectangle by fill_holes -> open first to delete hairlines thinner than ~7 px
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    n, lab, st, _ = cv2.connectedComponentsWithStats(mask, 8)
    if n > 1:
        big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        keep = cv2.dilate((lab == big).astype(np.uint8),
                          cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13)))
    else:
        keep = np.ones_like(mask)
    ys, xs = np.where(keep > 0)
    y0, y1 = max(0, ys.min() - 2), min(a.shape[0], ys.max() + 3)
    x0, x1 = max(0, xs.min() - 2), min(a.shape[1], xs.max() + 3)
    keep, a = keep[y0:y1, x0:x1], a[y0:y1, x0:x1]
    alpha = (keep > 0).astype(np.uint8) * 255
    # erase faint leftovers outside the kept silhouette
    rgb = a.copy()
    rgb[(keep == 0) | (a.min(axis=2) >= WHITE_T)] = (255, 255, 255)
    rgba = np.dstack([rgb, alpha])
    return Image.fromarray(rgba, 'RGBA')


# ---------------------------------------------------------------- paths
def fill_holes(m):
    # pad first: without a margin, a shape that touches the border splits the canvas
    # and the bottom empty band gets mistaken for a hole and filled
    p = cv2.copyMakeBorder(m, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=0)
    h, w = p.shape
    ff = p.copy()
    f = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(ff, f, (0, 0), 255)
    out = cv2.bitwise_or(p, cv2.bitwise_not(ff))
    return out[2:-2, 2:-2]


def smooth_path(alpha, ox, oy, grow=4):
    m = ((alpha > 40).astype(np.uint8)) * 255
    k = int(max(5, min(m.shape) * 0.035)) | 1          # prune thin spikes / hair lines
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN,
                         cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    m = fill_holes(m)
    if grow:
        m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * grow + 1,) * 2))
    up = cv2.resize(m, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
    up = cv2.GaussianBlur(up, (0, 0), BLUR_SIGMA)
    up = (up > 127).astype(np.uint8) * 255
    up = fill_holes(up)
    cnts, _ = cv2.findContours(up, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cnts, key=cv2.contourArea)[:, 0, :].astype(np.float64) / 2.0
    pts = Polygon(c).buffer(0)
    if isinstance(pts, MultiPolygon):
        pts = max(pts.geoms, key=lambda g: g.area)
    ring = pts.exterior
    per = ring.length
    n = max(30, int(per / RESAMPLE))
    arr = np.array([[p.x + ox, p.y + oy] for p in (ring.interpolate(i * per / n) for i in range(n))])
    return arr


def rounded_rect_path(x0, y0, x1, y1, r, seg=12):
    """closed polyline of a rounded rectangle."""
    pts = []
    cor = [(x1 - r, y0 + r, -90, 0), (x1 - r, y1 - r, 0, 90),
           (x0 + r, y1 - r, 90, 180), (x0 + r, y0 + r, 180, 270)]
    for cx, cy, a0, a1 in cor:
        for t in np.linspace(math.radians(a0), math.radians(a1), seg):
            pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    return np.array(pts)


def bezier(pts, nd=2):
    n = len(pts)
    out = [f'M {pts[0][0]:.{nd}f} {pts[0][1]:.{nd}f}']
    for i in range(n):
        p0, p1, p2, p3 = pts[(i - 1) % n], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        c1 = p1 + (p2 - p0) * (TENSION / 6.0)
        c2 = p2 - (p3 - p1) * (TENSION / 6.0)
        out.append(f'C {c1[0]:.{nd}f} {c1[1]:.{nd}f} {c2[0]:.{nd}f} {c2[1]:.{nd}f} '
                   f'{p2[0]:.{nd}f} {p2[1]:.{nd}f}')
    out.append('Z')
    return ' '.join(out)


def resample_ring(arr, spacing=RESAMPLE):
    ring = Polygon(arr)
    if not ring.is_valid:
        ring = ring.buffer(0)
    if isinstance(ring, MultiPolygon):
        ring = max(ring.geoms, key=lambda g: g.area)
    e = ring.exterior
    n = max(24, int(e.length / spacing))
    return np.array([[p.x, p.y] for p in (e.interpolate(i * e.length / n) for i in range(n))])


# ---------------------------------------------------------------- per sheet
def build(folder, title, words, rgb, logo, qr, expected=9):
    src = f'sheets/{folder}/raw.png'
    sheet = trim(Image.open(src).convert('RGB'), pad=6)
    cells = split_cells(sheet, 2, 3, strip_top=0)
    stickers = [sticker_rgba(c) for c in cells]

    page = Image.new('RGB', A6, (255, 255, 255))
    hdr = header(A6[0], logo, qr, title, rgb)
    page.paste(hdr, (0, 0), hdr)

    body_top = HEADER_H + TOP_GAP
    body_bottom = A6[1] - FOOT_H
    cell_w = (A6[0] - 2 * MARGIN_X) // 3
    cell_h = (body_bottom - body_top) // 2

    # scale every sticker to its cell, then centre the two rows as one block so the
    # page never gets a dead white band between rows
    box_w, box_h = cell_w - 14, cell_h - 12
    sized = []
    for st in stickers:
        sc = min(box_w / st.width, box_h / st.height)
        nw, nh = int(st.width * sc), int(st.height * sc)
        sized.append(st.resize((nw, nh), Image.LANCZOS))
    row_h = [max(s.height for s in sized[r * 3:r * 3 + 3]) for r in (0, 1)]
    block_h = sum(row_h) + 34
    top = body_top + max(0, (cell_h * 2 - block_h) // 2)
    row_y = [top, top + row_h[0] + 34]

    paths = []
    for i, st_r in enumerate(sized):
        r, c = divmod(i, 3)
        x = MARGIN_X + c * cell_w + (cell_w - st_r.width) // 2
        y = row_y[r] + (row_h[r] - st_r.height) // 2
        page.paste(st_r, (x, y), st_r)
        alpha = np.array(st_r.split()[-1])
        paths.append(('sticker', smooth_path(alpha, x, y), dict(row=r, col=c)))

    chip_box_w = (A6[0] - 2 * MARGIN_X) // 3 - 16
    chip_box_h = FOOT_H - 110
    for i, (w, art) in enumerate(zip(words, name_stickers(f'assets/names/{folder[:2]}.png'))):
        sc = min(chip_box_w / art.width, chip_box_h / art.height)
        nw, nh = int(art.width * sc), int(art.height * sc)
        chip = art.resize((nw, nh), Image.LANCZOS)
        cx = MARGIN_X + i * (chip_box_w + 16)
        x = cx + (chip_box_w - nw) // 2
        y = body_bottom + 52 + (chip_box_h - nh) // 2
        page.paste(chip, (x, y), chip)
        alpha = np.array(chip.split()[-1])
        paths.append(('chip', smooth_path(alpha, x, y, grow=2), dict(word=w)))

    # ---------- clearance fixer (should not trigger, kept as a guard) ----------
    def polys():
        return [resample_ring(p[1]) for p in paths]

    for _ in range(8):
        pl = [Polygon(a) for a in polys()]
        bad = False
        for i in range(len(pl)):
            for j in range(i + 1, len(pl)):
                if pl[i].distance(pl[j]) < MIN_GAP_PX:
                    bad = True
        if not bad:
            break
        for k, (kind, arr, meta) in enumerate(paths):
            c0 = arr.mean(axis=0)
            paths[k] = (kind, resample_ring((arr - c0) * 0.985 + c0), meta)

    # ---------- write files ----------
    out = f'pack/{folder}'
    os.makedirs(out, exist_ok=True)
    page.save(f'{out}/{folder}_A6_300dpi.png', 'PNG', optimize=True, dpi=(DPI, DPI))

    W, H = A6
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{MM[0]}mm" height="{MM[1]}mm"'
            f' viewBox="0 0 {W} {H}">\n'
            f'  <title>{folder} — die cut line — A6 105x148 mm @ {DPI} DPI</title>\n'
            f'  <rect x="0" y="0" width="{W}" height="{H}" fill="#FFFFFF"/>\n'
            f'  <g id="CutLine" inkscape:groupmode="layer" inkscape:label="CutLine"\n'
            f'     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"\n'
            f'     fill="none" stroke="#FF0000" stroke-width="{STROKE_PT}pt"\n'
            f'     stroke-linejoin="round" stroke-linecap="round">\n')
    body = ''.join(
        f'    <path id="cut-{i + 1:02d}" fill="none" stroke="#FF0000" stroke-width="{STROKE_PT}pt" '
        f'stroke-linejoin="round" stroke-linecap="round" d="{bezier(resample_ring(p[1]))}"/>\n'
        for i, p in enumerate(paths))
    open(f'{out}/sticker_cutline_A6.svg', 'w').write(head + body + '  </g>\n</svg>\n')

    head2 = (f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{MM[0]}mm" height="{MM[1]}mm"'
             f' viewBox="0 0 {W} {H}">\n  <title>cut line preview</title>\n'
             f'  <rect x="0" y="0" width="{W}" height="{H}" fill="#FFFFFF"/>\n'
             f'  <g id="CutLinePreview" fill="#000000" stroke="none">\n')
    body2 = ''.join(f'    <path id="shape-{i + 1:02d}" d="{bezier(resample_ring(p[1]))}"/>\n'
                    for i, p in enumerate(paths))
    open(f'{out}/sticker_cutline_preview.svg', 'w').write(head2 + body2 + '  </g>\n</svg>\n')

    # proofs + pdfs
    cairosvg.svg2pdf(url=f'{out}/sticker_cutline_A6.svg', write_to=f'{out}/sticker_cutline_A6.pdf')
    cairosvg.svg2pdf(url=f'{out}/sticker_cutline_preview.svg', write_to=f'{out}/sticker_cutline_preview.pdf')
    cairosvg.svg2png(url=f'{out}/sticker_cutline_preview.svg', write_to=f'{out}/proof_preview_black.png',
                     output_width=620, background_color='white')
    cairosvg.svg2png(url=f'{out}/sticker_cutline_A6.svg', write_to=f'{out}/proof_cutline_600dpi.png',
                     output_width=2480, output_height=3496, background_color='white')
    svg_vis = open(f'{out}/sticker_cutline_A6.svg').read().replace(f'stroke-width="{STROKE_PT}pt"',
                                                                  'stroke-width="1.5pt"')
    open('/tmp/_vis.svg', 'w').write(svg_vis)
    cairosvg.svg2png(url='/tmp/_vis.svg', write_to=f'{out}/proof_cutline_visible.png',
                     output_width=620, background_color='white')
    cairosvg.svg2png(url='/tmp/_vis.svg', write_to='/tmp/_ov.png',
                     output_width=A6[0], output_height=A6[1], background_color='white')
    ov = np.array(Image.open('/tmp/_ov.png').convert('RGB')).astype(np.int16)
    red = (ov[:, :, 0] - ov[:, :, 1] > 60) & (ov[:, :, 0] - ov[:, :, 2] > 60)
    base = np.array(page).copy()
    base[red] = [230, 30, 30]
    Image.fromarray(base).resize((640, 902), Image.LANCZOS).save(f'{out}/proof_overlay.png')

    # verification
    pl = [Polygon(resample_ring(p[1])) for p in paths]
    gaps = [(pl[i].distance(pl[j]), i + 1, j + 1) for i in range(len(pl)) for j in range(i + 1, len(pl))]
    mingu = min(g[0] for g in gaps) if gaps else None
    edges = [min(p.bounds[0], p.bounds[1], W - p.bounds[2], H - p.bounds[3]) for p in pl]
    mm_px = MM[0] / W
    rep = dict(sheet=folder, title=title, words=words, canvas_px=list(A6), canvas_mm=list(MM), dpi=DPI,
               path_count=len(paths), expected=expected, count_ok=len(paths) == expected,
               closed_single_contour=all(p.is_valid and p.area > 0 for p in pl),
               self_intersections=sum(0 if p.is_valid else 1 for p in pl),
               min_gap_px=round(mingu, 2), min_gap_mm=round(mingu * mm_px, 3),
               min_edge_margin_px=round(min(edges), 2), min_edge_margin_mm=round(min(edges) * mm_px, 3),
               touching_pairs=[[round(g[0], 2), g[1], g[2]] for g in gaps if g[0] < MIN_GAP_PX],
               touching_edge=[i + 1 for i, e in enumerate(edges) if e < EDGE_MARGIN_PX],
               types=[p[0] for p in paths])
    rep['PASS'] = (rep['count_ok'] and rep['closed_single_contour']
                   and not rep['touching_pairs'] and not rep['touching_edge'])
    json.dump(rep, open(f'{out}/verification.json', 'w'), ensure_ascii=False, indent=2)
    print(f'{folder}: paths={rep["path_count"]} gap={rep["min_gap_mm"]}mm '
          f'edge={rep["min_edge_margin_mm"]}mm PASS={rep["PASS"]}')
    return rep


def main():
    logo_path = next(p for p in ('assets/brand/logo.png',
                                 'uploads/logo-fixed-transparent.png') if os.path.exists(p))
    logo = Image.open(logo_path).convert('RGBA')
    qr = qr_image(360)
    todo = [th for th in THEMES if os.path.exists(f'assets/names/{th[0][:2]}.png')]
    missing = [th[0] for th in THEMES if th not in todo]
    if missing:
        print('SKIP (no generated name strip yet):', ', '.join(missing))
    reps = [build(f, t, w, c, logo, qr) for f, t, w, c in todo]
    json.dump(reps, open('pack/summary.json', 'w'), ensure_ascii=False, indent=2)
    print('\n===== SUMMARY =====')
    for r in reps:
        print(f'{r["sheet"]:20} paths {r["path_count"]:>2} gap {r["min_gap_mm"]:>6} mm '
              f'edge {r["min_edge_margin_mm"]:>6} mm  self {r["self_intersections"]}  '
              f'{"PASS" if r["PASS"] else "FAIL"}')


if __name__ == '__main__':
    main()
