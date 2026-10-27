import json
from PIL import Image, ImageDraw, ImageFont

reps = json.load(open('pack/summary.json'))
F = 'assets/fonts/Poppins-SemiBold.ttf'

SHEET_README = """{folder} — A6 sticker sheet / برگه استیکر A6
==========================================================
Title / عنوان:        {title}
Name stickers / استیکر اسم: {words}
Shapes per sheet:     {n}  (6 character stickers + 3 name stickers)

FILES
  {folder}_A6_300dpi.png     print artwork, A6 105x148 mm, 300 DPI (1240x1748 px), pure white
  sticker_cutline_A6.svg     die-cut line only — #FF0000, 0.25 pt, fill:none, layer id "CutLine"
  sticker_cutline_A6.pdf     same, vector PDF, A6
  sticker_cutline_preview.svg / .pdf    all paths filled black (shape check)
  proof_overlay.png          artwork + cut line in register (what the blade will follow)
  proof_cutline_600dpi.png   cut line rendered at 600 DPI
  verification.json          automatic geometry report
  README.txt                 this file

PRINT NOTES / نکات چاپ
  * White self-adhesive paper, kiss-cut or through-cut; no bleed needed.
  * Minimum distance between two cut lines: {gap} mm — safe for a plotter blade.
  * Smallest margin from any cut line to the trim edge: {edge} mm.
  * Keep the cut line as a spot colour named "CutContour" in the RIP, or tell the
    operator that #FF0000 is the cut layer and must not print as ink.
  * Artwork is RGB; let the printer convert with its own CMYK profile. For a deep
    black ask for rich black C45 M35 Y30 K100.
  * The header QR points to https://ghelghelishop.com — decoded successfully from
    the 300 DPI page.

Geometry check: {paths} closed paths, {selfint} self-intersections, min gap {gap} mm,
min edge margin {edge} mm — {verdict}.

Artwork note: the six characters are generated artwork; the three name stickers are
generated glossy sticker lettering (not typeset), so their cut line follows the
lettering silhouette. Photo-style sheets keep a soft studio shadow inside the cut.
"""

for r in reps:
    d = f"pack/{r['sheet']}"
    open(f'{d}/README.txt', 'w').write(SHEET_README.format(
        folder=r['sheet'], title=r['title'], words=' / '.join(r['words']), n=r['path_count'],
        edge=r['min_edge_margin_mm'], gap=r['min_gap_mm'], paths=r['path_count'],
        selfint=r['self_intersections'], verdict='PASS' if r['PASS'] else 'FAIL'))

thumbs = []
for r in reps:
    im = Image.open(f"pack/{r['sheet']}/{r['sheet']}_A6_300dpi.png").convert('RGB')
    im.thumbnail((520, 740), Image.LANCZOS)
    thumbs.append(im.copy())

W, H = 520 * 3 + 60 * 4, 740 * 2 + 90 * 3 + 70
ov = Image.new('RGB', (W, H), (245, 246, 248))
d = ImageDraw.Draw(ov)
f = ImageFont.truetype(F, 22)
d.text((60, 18), f'Ghelghelishop.com — {len(reps)} sheets · A6 105×148 mm · 300 DPI · 9 die-cut shapes each',
       font=f, fill=(30, 30, 40))
for i, im in enumerate(thumbs):
    r, c = divmod(i, 3)
    x = 60 + c * (520 + 60) + (520 - im.width) // 2
    y = 70 + r * (740 + 60) + (740 - im.height) // 2
    ov.paste(im, (x, y))
ov.save('pack/all_sheets_overview.png', optimize=True)
print('ok', ov.size)
