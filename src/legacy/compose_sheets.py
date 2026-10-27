#!/usr/bin/env python3
"""
compose_sheets.py — build the final A6 sticker page for every theme.

Page (105 x 148 mm @ 300 DPI = 1240 x 1748 px, white paper):
    header  : brand logo + "Ghelghelishop.com" wordmark + QR code linking to the shop
    body    : 6 half-body stickers (2 rows x 3), kept at their designed spacing
    footer  : 3 name stickers with three DIFFERENT words, glossy 3-D type

Fonts: Poppins ExtraBold (wordmark + names) with a real gradient + outline,
       so the shop address never looks like a system font.
"""
import os, json
import numpy as np
import cv2
import qrcode
from PIL import Image, ImageDraw, ImageFont, ImageFilter

A6 = (1240, 1748)
DPI = 300
HEADER_H = 236
FOOT_H = 226
MARGIN_X = 40
FONT_XB = 'assets/fonts/Poppins-ExtraBold.ttf'
FONT_SB = 'assets/fonts/Poppins-SemiBold.ttf'
SHOP = 'Ghelghelishop.com'

THEMES = [
    ('01_anime_legends', ['LUFFY', 'NARUTO', 'GOJO'],    (34, 96, 168), 'ANIME LEGENDS'),
    ('02_football_stars', ['MESSI', 'RONALDO', 'MBAPPE'], (18, 62, 130), 'FOOTBALL STARS'),
    ('03_dota2_heroes', ['PUDGE', 'INVOKER', 'AXE'],      (104, 40, 132), 'DOTA 2 HEROES'),
    ('04_cute_pets', ['CAT', 'DOG', 'PUPPY'],             (216, 96, 128), 'CUTE PETS'),
    ('05_anime_cool', ['SUKUNA', 'ZORO', 'TOJI'],         (14, 104, 84),  'ANIME COOL'),
]


# --------------------------------------------------------------------- helpers
def qr_code(url='https://ghelghelishop.com', px=300):
    q = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_H,
                      box_size=16, border=1)
    q.add_data(url)
    q.make(fit=True)
    img = q.make_image(fill_color=(24, 24, 28), back_color='white').convert('RGB')
    return img.resize((px, px), Image.LANCZOS)


def gradient_text(word, rgb, w, h, font_path=FONT_XB, tracking=0):
    """3-D-ish glossy wordmark: dark outline, gradient fill, top gloss highlight."""
    S = 6
    W, H = w * S, h * S
    canvas = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    size = int(H * 0.66)
    while size > 12:
        f = ImageFont.truetype(font_path, size)
        widths = [d.textlength(ch, font=f) for ch in word]
        tw = sum(widths) + tracking * S * (len(word) - 1)
        if tw < W * 0.88:
            break
        size -= 4
    f = ImageFont.truetype(font_path, size)
    widths = [d.textlength(ch, font=f) for ch in word]
    tw = sum(widths) + tracking * S * (len(word) - 1)
    asc, desc = f.getmetrics()
    th = asc + desc
    x = (W - tw) / 2
    y = (H - th) / 2

    # text mask
    mask = Image.new('L', (W, H), 0)
    md = ImageDraw.Draw(mask)
    cx = x
    for ch, cw in zip(word, widths):
        md.text((cx, y), ch, font=f, fill=255)
        cx += cw + tracking * S
    # outline (dilate mask)
    outline = mask.filter(ImageFilter.MaxFilter(9))
    canvas.paste(Image.new('RGBA', (W, H), (28, 26, 40, 255)), (0, 0), outline)
    shadow = mask.filter(ImageFilter.MaxFilter(13)).filter(ImageFilter.GaussianBlur(6 * S / 3))
    canvas.paste(Image.new('RGBA', (W, H), (0, 0, 0, 90)), (0, int(6 * S / 3)), shadow)
    # gradient fill
    light = tuple(min(255, int(c * 0.55 + 120)) for c in rgb)
    dark = tuple(int(c * 0.78) for c in rgb)
    grad = Image.new('RGB', (1, H))
    for i in range(H):
        t = i / H
        grad.putpixel((0, i), tuple(int(light[k] + (dark[k] - light[k]) * t) for k in range(3)))
    grad = grad.resize((W, H))
    canvas.paste(grad, (0, 0), mask)
    # glossy top strip
    gloss = Image.new('L', (W, H), 0)
    gd = ImageDraw.Draw(gloss)
    gd.rectangle([0, 0, W, int(H * 0.42)], fill=70)
    gloss = gloss.filter(ImageFilter.GaussianBlur(4 * S / 3))
    canvas.paste(Image.new('RGBA', (W, H), (255, 255, 255, 255)), (0, 0),
                 Image.composite(gloss, Image.new('L', (W, H), 0), mask))
    return canvas.resize((w, h), Image.LANCZOS)


def wordmark(word, rgb, w, h):
    return gradient_text(word, rgb, w, h, FONT_XB, tracking=1)


def name_chip(word, rgb, w, h):
    """white die-cut chip with red hairline + glossy gradient word."""
    S = 4
    W, H = w * S, h * S
    chip = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(chip)
    pad = int(H * 0.10)
    d.rounded_rectangle([pad, pad, W - pad, H - pad], radius=int(H * 0.30),
                        fill=(255, 255, 255, 255), outline=(226, 44, 44, 255),
                        width=max(2, 3 * S))
    txt = gradient_text(word, rgb, W - 2 * pad - 12 * S, H - 2 * pad - 12 * S)
    chip.alpha_composite(txt, (pad + 6 * S, pad + 6 * S))
    return chip.resize((w, h), Image.LANCZOS)


def header(width, logo, qr, title, rgb):
    out = Image.new('RGBA', (width, HEADER_H), (255, 255, 255, 0))
    # left: logo
    lg_h = 132
    lg = logo.resize((int(logo.width * lg_h / logo.height), lg_h), Image.LANCZOS)
    out.alpha_composite(lg, (36, (HEADER_H - lg_h) // 2 - 8))
    # middle: wordmark + pack title
    wm = wordmark(SHOP, rgb, 470, 84)
    out.alpha_composite(wm, (lg.width + 62, 44))
    sub = gradient_text(title, tuple(int(c * 0.75) for c in rgb), 330, 40, FONT_SB, tracking=2)
    out.alpha_composite(sub, (lg.width + 66, 132))
    # right: QR + caption
    qr_px = 132
    qr_i = qr.resize((qr_px, qr_px), Image.LANCZOS).convert('RGBA')
    qx = width - 36 - qr_px
    out.alpha_composite(qr_i, (qx, (HEADER_H - qr_px) // 2 - 6))
    d = ImageDraw.Draw(out)
    f = ImageFont.truetype(FONT_SB, 19)
    cap = 'SCAN TO SHOP'
    cw = d.textlength(cap, font=f)
    d.text((qx + (qr_px - cw) / 2, (HEADER_H - qr_px) // 2 + qr_px + 2), cap, font=f,
           fill=(70, 70, 78, 255))
    # hairline under the header
    d.line([(30, HEADER_H - 2), (width - 30, HEADER_H - 2)], fill=(232, 232, 236, 255), width=2)
    return out


def trim_white(im, pad=4):
    a = np.array(im.convert('RGB'))
    ys, xs = np.where(a.min(axis=2) < 249)
    if len(ys) == 0:
        return im
    return im.crop((max(0, xs.min() - pad), max(0, ys.min() - pad),
                    min(a.shape[1], xs.max() + pad), min(a.shape[0], ys.max() + pad)))


def fit(im, w, h):
    r = min(w / im.width, h / im.height)
    return im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)


def cells(img, rows=2, cols=3):
    """split the generated sheet into rows x cols by the widest white gutters."""
    a = np.array(img.convert('RGB'))
    solid = (a.min(axis=2) < 249).astype(np.uint8)
    prof_y = np.convolve(solid.sum(axis=1), np.ones(15) / 15, mode='same')
    prof_x = np.convolve(solid.sum(axis=0), np.ones(15) / 15, mode='same')
    H, W = solid.shape

    def bounds(prof, n, size):
        e = [0]
        pos = 0
        for i in range(1, n):
            lo = int(pos + 0.55 * (size - pos) / (n - i + 1))
            hi = int(pos + 1.55 * (size - pos) / (n - i + 1))
            lo, hi = max(2, lo), min(size - 3, hi)
            nx = lo + int(np.argmin(prof[lo:hi])) if hi > lo else int(pos + (size - pos) / (n - i + 1))
            e.append(nx)
            pos = nx
        e.append(size)
        return e

    ye, xe = bounds(prof_y, rows, H), bounds(prof_x, cols, W)
    out = []
    for r in range(rows):
        for c in range(cols):
            out.append(img.crop((xe[c], ye[r], xe[c + 1], ye[r + 1])))
    return out


# --------------------------------------------------------------------- main
def main():
    logo = Image.open('uploads/logo-fixed-transparent.png').convert('RGBA')
    qr = qr_code()
    os.makedirs('working', exist_ok=True)
    report = []

    for folder, words, rgb, title in THEMES:
        os.makedirs(f'working/{folder}', exist_ok=True)
        src = f'sheets/{folder}/raw.png'
        art = trim_white(Image.open(src).convert('RGB'), pad=6)

        page = Image.new('RGB', A6, (255, 255, 255))
        page.paste(header(A6[0], logo, qr, title, rgb), (0, 0), header(A6[0], logo, qr, title, rgb))

        body_top = HEADER_H + 6
        body_bottom = A6[1] - FOOT_H
        grid = cells(art, 2, 3)
        cell_w = (A6[0] - 2 * MARGIN_X) // 3
        cell_h = (body_bottom - body_top) // 2
        for i, c in enumerate(grid):
            im = fit(trim_white(c), cell_w - 12, cell_h - 10)
            r, k = divmod(i, 3)
            page.paste(im, (MARGIN_X + k * cell_w + (cell_w - im.width) // 2,
                            body_top + r * cell_h + (cell_h - im.height) // 2))

        chip_w = (A6[0] - 2 * MARGIN_X) // 3 - 8
        chip_h = FOOT_H - 60
        for i, w in enumerate(words):
            chip = name_chip(w, rgb, chip_w, chip_h)
            page.paste(chip, (MARGIN_X + i * (chip_w + 12) + 4,
                              body_bottom + (FOOT_H - chip_h) // 2 - 12), chip)

        out = f'working/{folder}/print_A6.png'
        page.save(out, 'PNG', optimize=True, dpi=(DPI, DPI))
        report.append(dict(folder=folder, title=title, words=words, file=out))
        print(folder, '->', out)

    json.dump(report, open('working/index.json', 'w'), ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
