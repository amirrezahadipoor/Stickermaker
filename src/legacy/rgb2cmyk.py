import pikepdf, re, io, sys
from functools import lru_cache

@lru_cache(maxsize=None)
def conv(r, g, b):
    # rich black for large solid dark areas (better density on press than 100% K only)
    if max(r, g, b) < 0.10:
        return (0.45, 0.35, 0.30, 1.0)
    c, m, y = 1 - r, 1 - g, 1 - b
    k = min(c, m, y)
    if k > 0.999999:      # pure black -> K only (keeps solid black clean)
        return (0.0, 0.0, 0.0, 1.0)
    if k >= 1.0:
        return (0.0, 0.0, 0.0, 1.0)
    c, m, y = (c - k) / (1 - k), (m - k) / (1 - k), (y - k) / (1 - k)
    # very dark but not neutral: keep a little warmth, avoid heavy CMY coverage
    if k > 0.85:
        c, m, y = c * 0.35, m * 0.35, y * 0.35
    return (c, m, y, k)

def repl(m):
    r, g, b = (float(x) for x in m.groups())
    c, mm, y, k = conv(round(r, 5), round(g, 5), round(b, 5))
    return f'{c:.4f} {mm:.4f} {y:.4f} {k:.4f} k'.encode()

src, dst = sys.argv[1], sys.argv[2]
pdf = pikepdf.open(src)
page = pdf.pages[0]
data = page.Contents.read_bytes()
new, n = re.subn(rb'([\d.]+) ([\d.]+) ([\d.]+) rg', repl, data)
print('colors converted:', n)
page.Contents = pdf.make_stream(new)

# embed a generic CMYK output intent so prepress software knows the space
icc = open('/usr/share/color/icc/ghostscript/default_cmyk.icc', 'rb').read()
iccp = pdf.make_stream(icc)
iccp.N = 4
iccp['/Alternate'] = pikepdf.Name('/DeviceCMYK')
intent = pdf.make_stream(b'')
oi = pdf.make_indirect(pikepdf.Dictionary({
    '/Type': pikepdf.Name('/OutputIntent'),
    '/S': pikepdf.Name('/GTS_PDFX'),
    '/OutputConditionIdentifier': pikepdf.String('Generic CMYK (default_cmyk.icc)'),
    '/Info': pikepdf.String('Generic CMYK profile - replace with FOGRA39 / GRACoL at the print shop'),
    '/RegistryName': pikepdf.String('http://www.color.org'),
    '/DestOutputProfile': iccp,
}))
pdf.Root['/OutputIntents'] = pikepdf.Array([oi])
pdf.docinfo['/Title'] = pikepdf.String('Football players sticker sheet - print CMYK')
pdf.save(dst, min_version='1.4')
print('saved', dst)
