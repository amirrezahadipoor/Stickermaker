# DIE-CUT LINE از شیت استیکر — راهنمای کامل بازسازی

> این سند «دانش فنی» پروژه است. همه فایل‌های خروجی پاک شده‌اند؛ با دستورهای زیر
> دقیقاً همان نتایج از روی تصاویر مبدأ (`uploads/`) دوباره ساخته می‌شوند.

---

## ۱) فایل‌های موجود در پروژه

| فایل | نقش |
|---|---|
| `uploads/soccer.png` | شیت مبدأ فوتبالیست‌ها (۱۰۵۵×۱۴۹۱) |
| `uploads/dota2.jpeg` | شیت مبدأ کاراکترهای بازی/پاپ (۸۶۴×۱۲۱۶) |
| `uploads/gen z.png` | شیت مبدأ اشیای y2k (۱۰۵۴×۱۴۹۲) |
| `uploads/anime.png` | شیت مبدأ انیمه (۱۰۶۰×۱۴۸۴) — **۱۴ استیکر** |
| `cutline.py` | موتور اصلی: ماسک → مؤلفه‌ها → صاف‌سازی → مسیر بزیه → دو SVG |
| `verify.py` | بازرسی مستقل SVG نهایی (تعداد/بسته‌بودن/برخورد/لبه) |
| `build_all.py` | اجرای کل خط تولید برای همه شیت‌ها + PDF + پیش‌نمایش + زیپ |
| `rgb2cmyk.py` | تبدیل PDF برداری RGB به CMYK + جاسازی Output Intent (مسیر چاپ) |

---

## ۲) اجرای سریع

```bash
pip install opencv-python-headless shapely cairosvg pypdf numpy pillow

# كل چهار شیت با هم (SVG + PDF + پروف + گزارش + زیپ)
python3 build_all.py

# فقط یک شیت، با کنترل کامل
python3 cutline.py "uploads/gen z.png" cutlines/genz --border --expect=15
python3 verify.py  "cutlines/genz/sticker_cutline_A6.svg" 15
```

سوییچ‌ها:

| سوییچ | کار |
|---|---|
| `--border` | فورگراند = فقط حلقه سفید دور استیکر (پیش‌فرض؛ برای آرت‌های دارای گلو/افکت نور) |
| `--any` | فورگراند = هر پیکسل غیرمشکی (قاعدهٔ تحت‌اللفظی بریف؛ برای شیت‌های بدون گلو) |
| `--expect=N` | تعداد استیکر مورد انتظار (پیش‌فرض ۱۵) |

---

## ۳) خط تولید (چه اتفاقی می‌افتد)

### گام ۱ — آستانه‌گذاری، پر کردن حفره‌ها، مؤلفه‌های همبند
```python
mask = (img.min(axis=2) > 235)          # حالت --border  (یا img.max(axis=2) > 12 برای --any)
mask = cv2.morphologyEx(mask, MORPH_CLOSE, ellipse(5))   # بستن شکاف‌های آنتی‌الیاس حلقه سفید
mask = cv2.dilate(mask, ellipse(2*2+1)); mask = fill_holes(mask)
mask = cv2.erode(mask,  ellipse(2*2+1))                  # برگشت به اندازه اصلی
n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
```
* `fill_holes` = flood-fill از گوشه تصویر؛ هر ناحیه‌ای که پر نشد حفره است.
* نویز: هر بلابی با مساحت `< 0.2٪` کل شیت حذف می‌شود.
* اگر تعداد بلاب‌های باقی‌مانده از `--expect` بیشتر بود، بزرگ‌ترین‌ها نگه داشته و بقیه
  در فیلد `discarded_extra_blobs` گزارش می‌شوند (با `--any` روی شیت‌های دارای گلو
  ستاره/جرقه‌های جدا به‌عنوان استیکر اضافی شمرده می‌شدند).

### گام ۲ — صاف‌سازی کانتور
```python
sub  = close(sub, ellipse(7))            # CLOSE_KERNEL  – بستن بریدگی‌های ریز
up   = resize(sub, x2)                   # کار در ۲× برای دقت ساب‌پیکسل
up   = GaussianBlur(up, sigma=2.6)       # BLUR_SIGMA    – نرم کردن لبه
up   = up > 127; up = fill_holes(up); بزرگ‌ترین بلاب
contour = findContours(up, RETR_EXTERNAL, CHAIN_APPROX_NONE)  # بزرگ‌ترین
poly = Polygon(contour/2 + آفست بلوک)    # shapely؛ اصلاح invalid با buffer(0)
poly = poly.buffer(-1.6, join_style=1)   # CUT_INSET_PX – تیغه کمی داخل لبه چاپ
pts  = resample(poly, 4.0)               # RESAMPLE_SPACING – نقاط یکنواخت (linear referencing)
d    = catmull_rom_closed(pts, tension=0.85)   # → Bézier مکعبی، 'M … C … Z'
```
* چرا inset: تیغه روی خود لبه چاپ نباشد؛ هاله سفید استیکر حفظ شود.
* چرا Catmull-Rom: منحنی بسته و نرم با کنترل «کشش» (`BEZIER_TENSION`) بدون loops.
* تضمین نبود برخورد: اگر فاصله دو مسیر `< MIN_GAP_PX` یا فاصله تا لبه
  `< EDGE_MARGIN_PX` بود، همه مسیرها ۰.۵px داخل‌تر برده می‌شوند (حداکثر ۴ بار).

### گام ۳ — خروجی SVG

الف) خط برش — `sticker_cutline_A6.svg`
```xml
<svg width="105.0mm" height="148.0mm" viewBox="0 0 1055 1491">
  <rect width="1055" height="1491" fill="#FFFFFF"/>
  <g id="CutLine" inkscape:groupmode="layer" inkscape:label="CutLine"
     fill="none" stroke="#FF0000" stroke-width="0.25pt">
    <path id="cut-01" fill="none" stroke="#FF0000" stroke-width="0.25pt" d="M … C … Z"/>
    …
```
ب) پیش‌نمایش — `sticker_cutline_preview.svg`: همان مسیرها با `fill="#000000"` روی سفید.

نکته چاپ: `1 user unit = 105/عرض‌پیکسل mm`. رشتهٔ `0.25pt` در SVG یعنی ۰.۲۵ پوینت
واقعی و مستقل از مقیاس است؛ در گزارش هم معادل user-unit آن نوشته می‌شود.

### گام ۴ — بازرسی (`verify.py`)
SVG نهایی دوباره parse می‌شود (مستقل از کدی که ساخته) و این‌ها چک می‌شوند:
تعداد مسیر، `fill/stroke/stroke-width`، بسته‌بودن (`M…Z` و تک‌زیرمسیر)،
خودتقاطعی (shapely validity)، کمترین فاصله مسیر↔مسیر، کمترین فاصله تا لبه بوم،
داخل‌بودن کامل، مساحت کل. خروجی: `verification.json` + `verification.txt`.

---

## ۴) نتایج مرجع (برای مقایسه پس از بازسازی)

| شیت | مسیر | تعداد | فاصله خط↔خط | فاصله تا لبه | self-intersect | وضعیت |
|---|---|---|---|---|---|---|
| soccer | `cutlines/soccer` | 15 | 0.87 mm | 2.05 mm | 0 | PASS |
| dota2  | `cutlines/dota2`  | 15 | 1.54 mm | 3.60 mm | 0 | PASS |
| genz   | `cutlines/genz`   | 15 | 1.60 mm | 2.85 mm | 0 | PASS |
| anime  | `cutlines/anime`  | **14** | 1.17 mm | 1.50 mm | 0 | PASS (۱۴/۱۴) |

شیت انیمه در خود آرت‌ورک ۱۴ استیکر دارد (ردیف آخر ۲ عدد)؛ با `--expect=15` عمداً
`count_ok:false` می‌دهد تا اختلاف قابل ردیابی باشد.

---

## ۵) زیپ کردن خروجی‌ها

```bash
# در build_all.py خروجی‌ها زیر cutlines/<sheet>/ ساخته می‌شوند
zip -q -r -9 cutline_packs.zip cutlines

# یا با اسکریپت آماده:
bash make_zip.sh
```

`make_zip.sh` بازسازی کامل + زیپ را با هم انجام می‌دهد و حجم/فهرست را چاپ می‌کند.
نکته: پوشهٔ `cutlines/` را قبل از زیپ نپاکید؛ زیپ از همان‌جا ساخته می‌شود.

---

## ۶) پارامترهای قابل تنظیم (بالای `cutline.py`)

| پارامتر | پیش‌فرض | اثر |
|---|---|---|
| `CUT_INSET_PX` | 1.6 | بزرگ‌تر = استیکر کوچک‌تر، هالهٔ سفید بیشتر |
| `BLUR_SIGMA` | 2.6 | بزرگ‌تر = نرم‌تر، جزئیات کمتر (انگشت، بند کفش، دسته جام) |
| `CLOSE_KERNEL` | 7 | بزرگ‌تر = شکاف‌های باریک (زیر بغل) پر می‌شود |
| `RESAMPLE_SPACING` | 4.0 | کوچک‌تر = نقاط بیشتر، فایل بزرگ‌تر |
| `BEZIER_TENSION` | 0.85 | کشش منحنی |
| `MIN_GAP_PX` / `EDGE_MARGIN_PX` | 2.0 / 2.0 | حداقل فاصله مجاز؛ آفست خودکار اضافه می‌کند |
| `WHITE_MIN_CHANNEL` | 235 | آستانهٔ حلقه سفید در حالت `--border` |
| `MIN_AREA_FRAC` | 0.002 | حذف نویزهای کوچک |

---

## ۷) اگر چاپخانه چیز دیگری خواست

```bash
# Spot color برای دستگاه برش (Roland/Graphtec):
sed -i 's/stroke="#FF0000"/stroke="CutContour"/' cutlines/*/sticker_cutline_A6.svg
# تعریف swatch: نام CutContour با مقدار 100M 100Y (یا ماژنت خالص) در فایل Illustrator

# PDF برداری از SVG:
python3 -c "import cairosvg; cairosvg.svg2pdf(url='…svg', write_to='…pdf')"

# ۳ میلی‌متر آفست دور استیکر (تیغه/هاله):
# در cutline.py مقدار CUT_INSET_PX را منفی بگذارید (مثلاً -12 در ۳۰۰dpi)
```
