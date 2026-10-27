# Stickermaker — A6 die-cut sticker sheets for Ghelghelishop.com

Production pipeline that turns generated character art into **print-ready A6 sticker sheets**
(105 × 148 mm @ 300 DPI, pure white) with a **vector die-cut line** for every sticker.

Every sheet = 6 character stickers + 3 glossy name stickers, plus a branded header with the
shop logo, the `Ghelghelishop.com` wordmark and a QR code to the shop.

![workflow](https://img.shields.io/badge/output-A6%20105%C3%97148%20mm%20%C2%B7%20300%20DPI-e42e2e)

## What is in the box

```
src/make_pack.py        <- the whole pipeline: compose + cut line + proofs + verification
src/pack_extra.py       <- per-sheet README + all_sheets_overview.png contact sheet
src/legacy/             <- older engines (cutline_white, build_*, verify, rgb2cmyk, ...)
memory.md               <- the build bible: prompts, constants, bugs, checklist
assets/brand/logo.png               shop logo (RGBA)
assets/brand/qr-ghelghelishop.png   QR to https://ghelghelishop.com
assets/fonts/           Poppins ExtraBold + SemiBold (OFL)
docs/                   long-form HOWTOs for the cut-line and vector print engine
```

## Quick start

```bash
git clone https://github.com/amirrezahadipoor/Stickermaker.git
cd Stickermaker
pip install -r requirements.txt

# 1. put generated art here:   sheets/<folder>/raw.png   (3 x 2 grid, flat white, no frames)
# 2. put generated names here: assets/names/<NN>.png     (three name stickers in one row)
python3 src/make_pack.py        # -> pack/<folder>/...
python3 src/pack_extra.py       # -> READMEs + pack/all_sheets_overview.png
zip -9 -r sticker_pack_print_cut.zip pack
```

Themes live in the `THEMES` list inside `src/make_pack.py`:

```python
THEMES = [
    ('01_ugly_cute', 'UGLY CUTE', ['GOOFY', 'DERP', 'BLOBBY'], (232, 140, 20)),
    ...
]
```

Themes without a matching `assets/names/<NN>.png` are skipped automatically.

## Output per sheet

| file | what it is |
|---|---|
| `<sheet>_A6_300dpi.png` | flattened artwork, exactly 1240 × 1748 px |
| `sticker_cutline_A6.svg` | cut line only — `#FF0000`, `0.25 pt`, `fill:none`, layer `CutLine` |
| `sticker_cutline_A6.pdf` | same, vector PDF at A6 |
| `sticker_cutline_preview.svg/.pdf` | all paths filled black (shape check) |
| `proof_overlay.png` | artwork + cut line in register |
| `proof_cutline_600dpi.png` | cut line rendered at 600 DPI |
| `verification.json` | 9 closed paths, no self-intersections, min gap, min edge margin |
| `README.txt` | print notes for the operator |

## Rules that must not be broken

- Flat white background, characters **complete and uncropped**, no frames/outlines drawn by the
  image model (a closed outline becomes a rectangle after hole filling).
- Name stickers are **generated artwork**, never typeset text.
- Cut line: 9 closed Bézier paths, `#FF0000`, `0.25 pt`, `fill:none`, layer `CutLine`,
  ≥ 0.8 mm between paths, ≥ 2.5 mm from the trim edge.
- Real people's likenesses get `moderation_blocked` — use "photorealistic faces, ultra-realistic
  3D characters" without names.

See **`memory.md`** for the full prompt library, constants, known bugs and the delivery checklist.

## Print notes

White self-adhesive paper, kiss-cut or through-cut. Keep the cut line as a spot colour named
`CutContour` in the RIP. Artwork is RGB — convert with the printer's profile; for deep black ask
for rich black `C45 M35 Y30 K100`.

## Licence

Code: MIT. Fonts: SIL Open Font License (Poppins). The shop logo and QR belong to
Ghelghelishop.com. Character artwork is generated per project and is **not** included in this
repository — check third-party IP before any commercial print run.
