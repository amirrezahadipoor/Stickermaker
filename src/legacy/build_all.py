#!/usr/bin/env python3
"""
build_all.py - run the full die-cut line pipeline for every sticker sheet and
              write the shared deliverables (SVG cut, SVG preview, PDFs, proofs, README).

    python3 build_all.py
"""
import os, json, subprocess, sys
import numpy as np
from PIL import Image
import cairosvg

SHEETS = [
    # input file,          folder,  expected stickers, note
    ('uploads/soccer.png', 'soccer', 15, 'football players (15 stickers)'),
    ('uploads/dota2.jpeg', 'dota2', 15, 'game / pop-culture characters (15 stickers)'),
    ('uploads/gen z.png',  'genz',   15, 'y2k / gen-z objects (15 stickers)'),
    ('uploads/anime.png',  'anime',  14, 'anime characters - the artwork itself has 14 stickers'),
]
ROOT = 'cutlines'


def run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if r.returncode:
        print(r.stdout, r.stderr)
        raise SystemExit(f'FAILED: {cmd}')
    return r.stdout


def overlay(src, svg, out_png, mm_w=105.0):
    """render the cut line 9x thicker over the original artwork, at 2x artwork size."""
    W, H = Image.open(src).size
    W, H = W * 2, H * 2
    svg_text = open(svg).read().replace('stroke-width="0.25pt"', 'stroke-width="2.2pt"')
    tmp = '/tmp/_thick.svg'
    open(tmp, 'w').write(svg_text)
    cairosvg.svg2png(url=tmp, write_to='/tmp/_thick.png', output_width=W, output_height=H,
                     background_color='white')
    a = np.array(Image.open('/tmp/_thick.png').convert('RGB')).astype(np.int16)
    red = (a[:, :, 0] - a[:, :, 1] > 40) & (a[:, :, 0] > 140)
    base = np.array(Image.open(src).convert('RGB').resize((W, H), Image.LANCZOS)).astype(np.int16)
    base[red] = [255, 20, 20]
    im = Image.fromarray(base.astype(np.uint8))
    im.resize((700, int(700 * H / W)), Image.LANCZOS).save(out_png)
    return int(red.sum())


def main():
    summary = []
    for src, name, expected, note in SHEETS:
        d = os.path.join(ROOT, name)
        print(f'\n=== {name} ({note}) ===')
        run(f'python3 cutline.py "{src}" "{d}" --border --expect={expected}')
        cut = os.path.join(d, 'sticker_cutline_A6.svg')
        prev = os.path.join(d, 'sticker_cutline_preview.svg')

        ver = run(f'python3 verify.py "{cut}" {expected}')
        open(os.path.join(d, 'verification.txt'), 'w').write(ver)

        cairosvg.svg2pdf(url=cut, write_to=os.path.join(d, 'sticker_cutline_A6.pdf'))
        cairosvg.svg2pdf(url=prev, write_to=os.path.join(d, 'sticker_cutline_preview.pdf'))
        cairosvg.svg2png(url=cut, write_to=os.path.join(d, 'check_cutline_600dpi.png'),
                         output_width=2480, output_height=3496, background_color='white')
        # thin line is invisible when scaled down -> make a 3x thicker proof for humans
        p3 = open(cut).read().replace('stroke-width="0.25pt"', 'stroke-width="0.75pt"')
        open('/tmp/_p3.svg', 'w').write(p3)
        cairosvg.svg2png(url='/tmp/_p3.svg', write_to=os.path.join(d, 'check_cutline_visible.png'),
                         output_width=700, background_color='white')
        px = overlay(src, cut, os.path.join(d, 'check_overlay.png'))

        js = json.load(open(os.path.join(d, 'verification.json')))
        summary.append(dict(sheet=name, art=os.path.basename(src), note=note,
                            expected=expected, paths=js['path_count'], count_ok=js['count_ok'],
                            closed=js['paths_valid_closed'], min_gap_mm=js['min_gap_mm'],
                            min_edge_mm=js['min_edge_margin_mm'],
                            touching=len(js['touching_pairs']),
                            edge_hits=len(js['paths_touching_edge']),
                            self_int=js['self_intersecting_paths'],
                            verdict=js['PASS'], overlay_red_px=px))

    print('\n===== SUMMARY =====')
    hdr = f'{"sheet":8} {"paths":>5} {"exp":>4} {"gap mm":>7} {"edge mm":>8} {"self":>5} {"touch":>5} {"verdict":>8}'
    print(hdr)
    for s in summary:
        print(f'{s["sheet"]:8} {s["paths"]:>5} {s["expected"]:>4} {s["min_gap_mm"]:>7} '
              f'{s["min_edge_mm"]:>8} {s["self_int"]:>5} {s["touching"]:>5} '
              f'{"PASS" if s["verdict"] else "FAIL":>8}')
    json.dump(summary, open(os.path.join(ROOT, 'summary.json'), 'w'), indent=2)


if __name__ == '__main__':
    main()
