#!/usr/bin/env bash
# Rebuild every die-cut pack from the source artwork in uploads/ and zip the result.
#   bash make_zip.sh          -> full rebuild + cutline_packs.zip
#   bash make_zip.sh ziponly  -> only re-zip whatever is already in cutlines/
set -euo pipefail
cd "$(dirname "$0")"

if [[ "${1:-}" != "ziponly" ]]; then
  python3 -m pip install -q opencv-python-headless shapely cairosvg pypdf numpy pillow
  python3 build_all.py
fi

rm -f cutline_packs.zip
zip -q -r -9 cutline_packs.zip cutlines
echo
echo "== cutline_packs.zip =="
ls -lh cutline_packs.zip
unzip -l cutline_packs.zip | tail -n +1
