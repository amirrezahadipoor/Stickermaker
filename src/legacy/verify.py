#!/usr/bin/env python3
"""verify.py - independent structural + geometric check of the A6 cut-line SVG."""
import re, sys, math
import xml.etree.ElementTree as ET
import numpy as np
from shapely.geometry import Polygon

SVG = sys.argv[1] if len(sys.argv) > 1 else 'cutlines/sticker_cutline_A6.svg'
EXPECTED = int(sys.argv[2]) if len(sys.argv) > 2 else 15
NS = {'s': 'http://www.w3.org/2000/svg', 'inkscape': 'http://www.inkscape.org/namespaces/inkscape'}

root = ET.parse(SVG).getroot()
W_mm = float(re.sub('[^0-9.]', '', root.get('width')))
H_mm = float(re.sub('[^0-9.]', '', root.get('height')))
vb = [float(v) for v in root.get('viewBox').split()]
canvas_w, canvas_h = vb[2], vb[3]

layer = None
for g in root.iter('{http://www.w3.org/2000/svg}g'):
    if g.get('id') == 'CutLine':
        layer = g
paths = layer.findall('s:path', NS)

def path_polylines(d, steps=10):
    """minimal H/V/C/Z/M parser -> list of sampled rings (supports subpaths)."""
    toks = re.findall(r'[MCZ]|-?\d*\.?\d+', d)
    rings, cur, start, pos = [], [], None, None
    i = 0
    subpaths = 1
    while i < len(toks):
        t = toks[i]
        if t == 'M':
            if cur:
                rings.append(cur)
            pos = (float(toks[i+1]), float(toks[i+2])); start = pos; cur = [pos]; i += 3
        elif t == 'C':
            c1 = (float(toks[i+1]), float(toks[i+2]))
            c2 = (float(toks[i+3]), float(toks[i+4]))
            p = (float(toks[i+5]), float(toks[i+6])); i += 7
            for s in np.linspace(0, 1, steps, endpoint=False)[1:]:
                b = ((1-s)**3)*np.array(pos) + 3*((1-s)**2)*s*np.array(c1) \
                    + 3*(1-s)*s**2*np.array(c2) + s**3*np.array(p)
                cur.append(tuple(b))
            pos = p
        elif t == 'Z':
            if cur:
                rings.append(cur + [start])
                cur = []
            i += 1
            if re.search(r'M', d[i and 0:]) and 'M' in ''.join(toks[i:]):
                subpaths += 1
        else:
            i += 1
    if cur:
        rings.append(cur)
    return rings

issues = []
RES = {'canvas_mm': [W_mm, H_mm], 'path_count': len(paths)}

# --- attributes ---
bad_attr = [p.get('id') for p in paths
            if p.get('fill') != 'none' or p.get('stroke', '').upper() != '#FF0000'
            or p.get('stroke-width') not in ('0.25pt',)]
if bad_attr:
    issues.append(f'bad fill/stroke attrs on {bad_attr}')
RES['stroke_width'] = paths[0].get('stroke-width')
RES['stroke'] = paths[0].get('stroke')
RES['fill'] = paths[0].get('fill')
RES['layer_name'] = layer.get('{http://www.inkscape.org/namespaces/inkscape}label')

# --- closed, single-contour paths ---
closed, multi = 0, []
polys = []
for p in paths:
    d = p.get('d', '').strip()
    rings = path_polylines(d)
    starts_m = d.count('M')
    if d.startswith('M') and d.endswith('Z') and starts_m == 1:
        closed += 1
    else:
        multi.append(p.get('id'))
    poly = Polygon(rings[0])
    if not poly.is_valid:
        poly = poly.buffer(0)
    polys.append(poly)
RES['closed_paths'] = closed
RES['paths_with_multiple_subpaths'] = multi
RES['expected_closed_paths'] = EXPECTED
if closed != EXPECTED:
    issues.append(f'not {EXPECTED} closed single-contour paths: {closed}')

# --- self intersections ---
selfx = [p.get('id') for p, poly in zip(paths, polys) if not poly.is_valid]
RES['self_intersecting'] = selfx
if selfx:
    issues.append(f'self-intersecting: {selfx}')

# --- pairwise clearance ---
mind, pair = 1e9, None
for i in range(len(polys)):
    for j in range(i + 1, len(polys)):
        d = polys[i].distance(polys[j])
        if d < mind:
            mind, pair = d, (paths[i].get('id'), paths[j].get('id'))
RES['min_clearance_uu'] = round(mind, 3)
RES['min_clearance_mm'] = round(mind * W_mm / canvas_w, 3)
if mind <= 0:
    issues.append(f'paths touch/overlap: {pair}')

# --- canvas edge clearance ---
edge = 1e9
for p, poly in zip(paths, polys):
    minx, miny, maxx, maxy = poly.bounds
    edge = min(edge, minx, miny, canvas_w - maxx, canvas_h - maxy)
RES['min_edge_clearance_uu'] = round(edge, 3)
RES['min_edge_clearance_mm'] = round(edge * W_mm / canvas_w, 3)
if edge <= 0:
    issues.append('a path touches the canvas edge')

RES['all_inside_canvas'] = all(polys[i].bounds[0] > 0 and polys[i].bounds[1] > 0 and
                               polys[i].bounds[2] < canvas_w and polys[i].bounds[3] < canvas_h
                               for i in range(len(polys)))
RES['total_area_mm2'] = round(sum(p.area for p in polys) * (W_mm / canvas_w) ** 2, 1)
RES['verdict'] = 'PASS' if not issues else 'FAIL'
RES['issues'] = issues

for k, v in RES.items():
    print(f'{k}: {v}')
