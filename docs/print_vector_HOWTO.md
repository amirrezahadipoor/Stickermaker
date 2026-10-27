# وکتور چاپی (CMYK) از تصویر رستری — راهنمای کامل بازسازی

> فایل‌های خروجی چاپی پاک شده‌اند. با دستورهای زیر از `uploads/soccer.png` دوباره
> ساخته می‌شوند. اسکریپت‌های باقی‌مانده: `rgb2cmyk.py` (+ قطعه‌های آماده در همین سند).

## ابزارها
```bash
pip install vtracer cairosvg pypdf pikepdf pillow numpy
sudo apt-get install -y ghostscript      # فقط اگر از قبل نصب نیست
```

## گام ۱ — ترسیم برداری رنگی (vtracer)
دو برابر بزرگ‌کردن قبل از ترسیم، کیفیت لبه را در چاپ ۳۰۰dpi بالا می‌برد:
```python
from PIL import Image; import vtracer
im = Image.open('uploads/soccer.png')
im.resize((im.width*2, im.height*2), Image.LANCZOS).save('work_2x.png')
vtracer.convert_image_to_svg_py('work_2x.png', 'work_2x.svg',
    colormode='color', hierarchical='stacked', mode='spline',
    filter_speckle=6, color_precision=7, layer_difference=20,
    corner_threshold=60, length_threshold=4.0, max_iterations=10,
    splice_threshold=45, path_precision=2)      # ≈ ۲۳٫۵۶۱ مسیر، ≈۱۵MB
```
نسخه سبک‌تر (وب): `color_precision=5, layer_difference=32, filter_speckle=10` → ≈۲MB.

## گام ۲ — تعریف ابعاد فیزیکی (A6 نسبی، ۳۰۰dpi)
```python
W, H = 2110, 2982                                  # 2× پیکسل اصلی
mm = W / 300 * 25.4                                # 178.65 mm عرض
# سرتگ svg را عوض کنید:
#   width="{mm}mm" height="{h}mm" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet"
```

## گام ۳ — PDF برداری
```python
import cairosvg; cairosvg.svg2pdf(url='vector.svg', write_to='print.pdf')
```

## گام ۴ — CMYK کردن (بدون خراب‌شدن مشکی)
تبدیل داخلی Ghostscript روی مشکی خالص C/M/Y≈100٪ می‌دهد؛ به‌جایش دستورهای رنگ PDF
با اسکریپت `rgb2cmyk.py` بازنویسی می‌شوند:
```bash
python3 rgb2cmyk.py vector/soccer_print_300dpi.pdf vector/soccer_print_CMYK.pdf
```
قاعده‌ها در همان فایل:
* GCR استاندارد: `k = min(c,m,y)` و جداسازی C/M/Y از k.
* مشکی‌های تیره (`max(R,G,B) < 0.10`) → **ریچ بلک** `C45 M35 Y30 K100` برای دانسیتهٔ درست.
* تیرگی‌های خیلی تیره (k>0.85) → CMY × 0.35 تا زیرلایه خیلی سنگین نشود.
* یک `/OutputIntents` با پروفایل `default_cmyk.icc` هم جاسازی می‌شود (چاپخانه می‌تواند
  با FOGRA39 جایگزین کند).

## گام ۵ (اختیاری) — EPS برای Illustrator/Corel
```bash
gs -q -dNOPAUSE -dBATCH -dSAFER -sDEVICE=eps2write -dCompressPages=true \
   -sOutputFile=print.eps print_CMYK.pdf
```
> EPS دست‌ساز با تعریف `m`/`c`/`h` درست کار نمی‌کند (خطای `/undefined in m`)،
> پس مسیر امن: PDF → `eps2write`.

## گام ۶ — زیپ بستهٔ چاپ
```bash
cd vector && zip -q -9 ../soccer_print_package.zip README_FA.txt \
   soccer_print_CMYK.pdf soccer_A3_bleed_CMYK.pdf soccer_print_CMYK.eps soccer_print_300dpi.svg
```

## کنترل کیفیت
```bash
gs -q -o - -sDEVICE=inkcov print_CMYK.pdf      # باید ۴ عدد CMYK بدهد (نه RGB)
python3 -c "from pypdf import PdfReader; b=PdfReader('print_CMYK.pdf').pages[0].mediabox; \
print(float(b.width)/72*25.4, float(b.height)/72*25.4)"   # اندازه mm
```
اعداد مرجع نسخهٔ ساخته‌شده: A6 نسبی = **178.65 × 252.48 mm**، A3+bleed = **303 × 426 mm**،
حجم PDF ≈ ۷.۸MB، حدود ۲۳٬۵۶۱ مسیر برداری.
