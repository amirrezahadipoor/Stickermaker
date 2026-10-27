#!/usr/bin/env python3
"""
build_print_pack.py — from each generated sheet:
  1. normalise the artwork to exact A6 @ 300 DPI (1240 x 1748 px, RGB PNG)
  2. build die-cut paths (cutline_white.py): threshold -> fill holes -> components ->
     morphological close -> blur+re-threshold -> Bezier smoothing -> closed paths
  3. emit per sheet: print PNG, cut-line SVG (layer "CutLine", #FF0000, 0.25 pt),
     preview SVG (filled black), vector PDFs, proofs, verification
  4. zip the whole pack
"""
import os, json, subprocess, glob
import numpy as np
import cv2
import cairosvg
from PIL import Image

A6 = (1240, 1748)                      # 105 x 148 mm @ 300 DPI
SHEETS = [
    ('01_anime_legends',    'ANIME LEGENDS',  'انیمه — نیم‌تنه، پوزهای متفاوت',
     ['LUFFY', 'NARUTO', 'GOJO']),
    ('02_football_stars',   'FOOTBALL STARS', 'فوتبال — نیم‌تنه با چهره‌های واضح',
     ['MESSI', 'RONALDO', 'MBAPPE']),
    ('03_dota2_heroes',     'DOTA 2 HEROES',  'دوتا ۲ — هیروهای پرطرفدار',
     ['PUDGE', 'INVOKER', 'AXE']),
    ('04_cute_pets',        'CUTE PETS',      'حیوانات بامزه — پوزهای متنوع',
     ['CAT', 'DOG', 'PUPPY']),
    ('05_anime_cool',       'ANIME COOL',     'انیمه پک ۲ — خفن‌ترین کاراکترها',
     ['SUKUNA', 'ZORO', 'TOJI']),
]
EXPECTED = 9


def sh(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if r.returncode:
        print(r.stdout, r.stderr)
        raise SystemExit(f'failed: {cmd}')
    return r.stdout


def normalise(src, dst):
    im = Image.open(src).convert('RGB')
    r = min(A6[0] / im.width, A6[1] / im.height)
    new = (round(im.width * r), round(im.height * r))
    im = im.resize(new, Image.LANCZOS)
    canvas = Image.new('RGB', A6, (255, 255, 255))       # white paper
    canvas.paste(im, ((A6[0] - new[0]) // 2, (A6[1] - new[1]) // 2))
    canvas.save(dst, 'PNG', optimize=True, dpi=(300, 300))


def overlay_proof(print_png, cut_svg, out_png):
    svg = open(cut_svg).read().replace('stroke-width="0.25pt"', 'stroke-width="2.0pt"')
    open('/tmp/_thick.svg', 'w').write(svg)
    cairosvg.svg2png(url='/tmp/_thick.svg', write_to='/tmp/_thick.png',
                     output_width=A6[0], output_height=A6[1], background_color='white')
    a = cv2.imread('/tmp/_thick.png')
    b, g, r = a[:, :, 0].astype(int), a[:, :, 1].astype(int), a[:, :, 2].astype(int)
    red = (r - g > 60) & (r - b > 60)
    out = cv2.imread(print_png)
    out[red] = (0, 0, 255)
    cv2.imwrite(out_png, out)


def main():
    summary = []
    for folder, title, fa, tags in SHEETS:
        src = f'sheets/{folder}/raw.png'
        out = f'pack/{folder}'
        os.makedirs(out, exist_ok=True)
        print(f'\n=== {folder} — {title} ===')

        print_png = f'{out}/{folder}_A6_300dpi.png'
        comp = f'working/{folder}/print_A6.png'
        if os.path.exists(comp):
            sh(f'cp "{comp}" "{print_png}"')
        else:
            normalise(src, print_png)

        # die-cut paths
        print(sh(f'python3 cutline_white.py "{print_png}" "{out}" --expect={EXPECTED} --skip-top=244').strip())

        cut = f'{out}/sticker_cutline_A6.svg'
        prev = f'{out}/sticker_cutline_preview.svg'
        cairosvg.svg2pdf(url=cut, write_to=f'{out}/sticker_cutline_A6.pdf')
        cairosvg.svg2pdf(url=prev, write_to=f'{out}/sticker_cutline_preview.pdf')
        cairosvg.svg2png(url=cut, write_to=f'{out}/proof_cutline_600dpi.png',
                         output_width=2480, output_height=3496, background_color='white')
        svg_vis = open(cut).read().replace('stroke-width="0.25pt"', 'stroke-width="0.75pt"')
        open('/tmp/_vis.svg', 'w').write(svg_vis)
        cairosvg.svg2png(url='/tmp/_vis.svg', write_to=f'{out}/proof_cutline_visible.png',
                         output_width=700, background_color='white')
        cairosvg.svg2png(url=prev, write_to=f'{out}/proof_preview_black.png',
                         output_width=700, background_color='white')
        overlay_proof(print_png, cut, f'{out}/proof_overlay.png')

        js = json.load(open(f'{out}/verification.json'))
        txt = '\n'.join([
            f'{folder} — {title}',
            f'fa: {fa}',
            f'name stickers: {", ".join(tags)}',
            '=' * 62,
            'paper      : A6 105 x 148 mm @ 300 DPI (1240 x 1748 px), white background',
            'stickers   : 6 hero stickers + 3 name stickers = 9 die-cut paths',
            '',
            'files',
            f'  {os.path.basename(print_png)}       print artwork, RGB PNG 300 DPI',
            '  sticker_cutline_A6.svg          cut line: layer "CutLine",',
            '                                  9 closed paths, fill none, stroke #FF0000, 0.25 pt',
            '  sticker_cutline_preview.svg     same paths filled solid black on white',
            '  sticker_cutline_A6.pdf          vector PDF of the cut line (105 x 148 mm)',
            '  sticker_cutline_preview.pdf     vector PDF of the black preview',
            '  proof_cutline_600dpi.png        raster proof of the cut line at print size',
            '  proof_cutline_visible.png       cut line drawn 3x thicker (screen check)',
            '  proof_preview_black.png         black silhouettes = what the blade cuts',
            '  proof_overlay.png               cut line (thickened) over the print artwork',
            '  verification.json               machine-readable checks',
            '',
            'verification',
            f'  paths                    {js["path_count"]} (expected {js["expected_paths"]})  count_ok={js["count_ok"]}',
            f'  closed single contour    {js["closed_single_contour"]}',
            f'  self intersections       {js["self_intersections"]}',
            f'  min clearance path-path  {js["min_gap_mm"]} mm',
            f'  min clearance to edge    {js["min_edge_margin_mm"]} mm',
            f'  touching pairs / edge    {len(js["touching_pairs"])} / {len(js["touching_edge"])}',
            f'  VERDICT                  {"PASS" if js["PASS"] else "FAIL"}',
            '',
            'regenerate',
            f'  python3 cutline_white.py "{print_png}" out --expect=9',
        ]) + '\n'
        open(f'{out}/README.txt', 'w').write(txt)
        summary.append(dict(folder=folder, title=title, fa=fa, tags=tags,
                            paths=js['path_count'], count_ok=js['count_ok'],
                            gap_mm=js['min_gap_mm'], edge_mm=js['min_edge_margin_mm'],
                            self_int=js['self_intersections'],
                            touching=len(js['touching_pairs']) + len(js['touching_edge']),
                            verdict=js['PASS']))

    json.dump(summary, open('pack/summary.json', 'w'), ensure_ascii=False, indent=2)
    print('\n================ SUMMARY ================')
    print(f'{"sheet":20} {"paths":>5} {"gap mm":>7} {"edge mm":>8} {"self":>5} {"touch":>6} {"verdict":>8}')
    for s in summary:
        print(f'{s["folder"]:20} {s["paths"]:>5} {s["gap_mm"]:>7} {s["edge_mm"]:>8} '
              f'{s["self_int"]:>5} {s["touching"]:>6} {"PASS" if s["verdict"] else "FAIL":>8}')


if __name__ == '__main__':
    main()
