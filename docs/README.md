# Project knowledge base (all heavy outputs removed on purpose)

Everything in this folder is documentation of *how* the deliverables were made,
so they can be regenerated at any time from the source images in `uploads/`.

| doc | content |
|---|---|
| `cutline_HOWTO.md` | die-cut line pipeline (threshold → components → smoothing → Bezier → SVG), verification, reference numbers, spot-color variant, zip |
| `print_vector_HOWTO.md` | raster → print vector (vtracer at 2×, physical size, PDF, RGB→CMYK with rich black, EPS via gs, zip) |

| script | role |
|---|---|
| `cutline.py` | cut-line engine (also the `--any` / `--border` foreground modes) |
| `verify.py` | independent SVG inspection (count, closed, clearance, edge) |
| `build_all.py` | runs the engine for all 4 sheets + PDF/proofs/report |
| `rgb2cmyk.py` | vector-PDF RGB→CMYK + embedded Output Intent |
| `make_zip.sh` | rebuild everything and produce `cutline_packs.zip` |

One-liners:

```bash
bash make_zip.sh                  # full rebuild of the 4 cut-line packs + zip
python3 cutline.py "uploads/gen z.png" cutlines/genz --border --expect=15
python3 verify.py cutlines/genz/sticker_cutline_A6.svg 15
```
