# memory.md — جریان ساخت پک استیکر چاپی Ghelghelishop.com

> این فایل مرجع کامل ساخت پک استیکر A6 آماده‌ی چاپ + برش است.
> هر بار خواستی همین کار را دوباره انجام بدی، فقط همین فایل را بخوان و اجرا کن.
> نسخهٔ نهایی این جریان: **round 5** (تولید کامل با عکس‌های بازتولیدشده).

---

## 1) خروجی نهایی چیست

۵ برگهٔ **A6 (۱۰۵ × ۱۴۸ میلی‌متر) با ۳۰۰ DPI**، پس‌زمینه سفید خالص، هر برگه **۹ استیکر**:
۶ استیکر شخصیت + ۳ استیکر اسم. هر برگه یک هدر برند دارد (لوگو + وردمارک + عنوان پک + QR).

**ست جاری — کمدی / پرفروش (اورجینال + کاربکچر):**

| پوشه | عنوان پک | اسم‌ها | رنگ | ریشهٔ ترند |
|---|---|---|---|---|
| `01_funny_footballers` | FUNNY FOOTBALLERS | HAALAND / NEYMAR / SALAH | (24,132,60) | کاربکچر بازیکن فوتبال (کمدی پرفروش) |
| `02_meme_cats` | MEME CATS | TOFU / BISCUIT / PICKLE | (226,122,40) | گربه‌های meme وایرال |
| `03_funny_food` | FUNNY FOOD | TOASTY / BANANA / DUMPLING | (214,52,46) | غذای کاوایی / character food |
| `04_silly_frogs` | SILLY FROGS | FROGGY / POND / RIBBIT | (86,158,40) | قورباغهٔ meme |
| `05_office_animals` | OFFICE ANIMALS | BOSS / CHIEF / INTERN | (28,68,130) | طنز شرکتی / animals in suits |

> ست‌های قبلی: ترند #۲ (`raccoon_squad`, `squishy_world`, `gargoyles`, `moon_witches`, `cozy_capybara`)،
> ترند #۱ (`ugly_cute`, `designer_toys`, `cyber_robots`, `greek_gods`, `kpop_hunters`)،
> ست اولیه (`anime_legends`, `football_stars`, `dota2_heroes`, `cute_pets`, `anime_cool`).

خروجی نهایی یک زیپ است: `sticker_pack_print_cut.zip` که داخلش پوشهٔ `pack/` با ۵ زیرپوشه + `README.txt` + `all_sheets_overview.png`.

### فایل‌های هر برگه
```
<sheet>_A6_300dpi.png         آرت‌ورک نهایی، دقیقاً 1240×1748 px، dpi=(300,300)
sticker_cutline_A6.svg        فقط خط برش — #FF0000، 0.25pt، fill:none، لایه id="CutLine"
sticker_cutline_A6.pdf        همان، PDF وکتور A6
sticker_cutline_preview.svg   همهٔ مسیرها با fill مشکی (چک فرم)
sticker_cutline_preview.pdf
proof_overlay.png             آرت + خط برش روی هم (چیزی که تیغه دنبال می‌کند)
proof_cutline_600dpi.png      رندر خط برش در ۶۰۰ DPI
verification.json             گزارش خودکار هندسه
README.txt                    نکات چاپ همان برگه
```

---

## 2) پیش‌نیازهای محیط

```bash
pip install opencv-python-headless shapely cairosvg pypdf pillow numpy pikepdf qrcode
```
> نصب pip بین نوبت‌ها باقی نمی‌ماند؛ هر بار باید دوباره اجرا شود. فونت‌ها و فایل‌های ورک‌اسپیس باقی می‌مانند.

فایل‌های ثابتی که باید در ورک‌اسپیس باشند:
```
assets/fonts/Poppins-ExtraBold.ttf
assets/fonts/Poppins-SemiBold.ttf
uploads/logo-fixed-transparent.png     ← لوگوی فروشگاه، RGBA با پس‌زمینهٔ شفاف
```

اسکریپت اصلی: **`make_pack.py`** (کل پایپ‌لاین). مابقی اسکریپت‌ها (`cutline_white.py`, `build_print_pack.py`, `compose_sheets.py`, …) از دورهای قبلی‌اند و برای این جریان لازم نیستند.

---

## 3) جریان ساخت — گام به گام

### گام ۰ — پاک‌سازی
```bash
rm -rf pack sheets assets/names sticker_pack_print_cut.zip __pycache__ .cache
mkdir -p sheets assets/names
```

### گام ۱ — تولید ۵ شیت آرت (هر شیت یک پرامپت جدا)
هر شیت یک **گرید ۳ ستون × ۲ ردیف** است: ۶ کاراکتر روی **پس‌زمینهٔ سفید تخت (flat white)**.
شیت‌ها را در `sheets/<folder>/raw.png` ذخیره کن.

قواعد طلایی پرامپت (بدون این‌ها خروجی خراب می‌شود):
- «COMPLETE FULL BODY figure from head to toe, nothing cropped» — وگرنه مولد از کمر می‌برد.
- «a comfortable white margin of empty space around every character»
- «The figures must not touch each other or the image border»
- «Pure flat white background, no panel borders, no frames, no outlines, no text, no logos» — وگرنه مولد یک **قاب مستطیلی نازک** دور هر کاراکتر می‌کشد و خط برش مستطیل می‌شود.
- برای فوتبال: «Photorealistic faces with real human skin texture… realistic 3D characters, not cartoons» + شمارهٔ پیراهن صریح. این نسخه رد (moderation) نمی‌شود؛ ولی توصیف بازیکن واقعی با نام یا سبک کاملاً واقع‌گرای عکس، رد می‌شود.
- ژست و زاویهٔ هر ۶ کاراکتر باید متفاوت باشد.

پرامپت‌های تأییدشدهٔ همین پک:

**01 anime legends**
> A clean 3-column by 2-row grid of six different famous shonen anime heroes, each one a COMPLETE FULL BODY figure standing or posed from head to toe, nothing cropped, a comfortable white margin of empty space around every character. Characters: a cheerful boy in a straw hat, red vest and denim shorts; a blonde ninja with spiky hair, orange and black jacket, kunai in hand; a muscular fighter in an orange martial arts gi with blue belt; a white-haired sorcerer in a dark high-collar uniform with a blindfold; a short dark-haired soldier in a green cloak with dual blades; a boy in a green-and-black checked robe holding a katana with water splash. Edges of the characters must not touch each other or the image border. Pure flat white background, no panel borders, no frames, no outlines, no text, no logos. Premium high-resolution anime illustration, crisp cel shading, rich colour, sharp detail.

**02 football stars**
> A clean 3-column by 2-row grid of six different professional football superstars, each one a COMPLETE FULL BODY figure from head to toe, nothing cropped, a comfortable white margin around each player. Photorealistic faces with real human skin texture, realistic eyes, stubble and hairstyle, shot like a high-end sports studio photograph with soft key light — but the figures are rendered as polished ultra-realistic 3D characters, not cartoons. Plain football kits with NO club crest and NO brand logos, big clear jersey numbers: light blue and white striped shirt with number 10 celebrating with both fists raised; plain red long-sleeve shirt with number 7, arms crossed; royal blue shirt with number 10, pointing one finger to the sky; plain red shirt with number 9, hands behind the back; yellow shirt with green trim and number 7, giving a thumbs up; plain maroon shirt with number 11, holding a football under one arm. Full body visible including boots, varied dynamic poses, pure flat white background, no panel borders, no frames, no outlines, no text other than the jersey numbers.

**03 dota 2 heroes**
> A clean 3-column by 2-row grid of six different fantasy MOBA game heroes, each one a COMPLETE FULL BODY figure from head to toe, nothing cropped, a comfortable white margin around each hero. Heroes: a huge bloated green undead butcher with stitched belly and a rusty hook; an elven mage in ornate purple and gold robes with three floating orbs of fire, ice and lightning; a red-skinned horned barbarian warrior swinging a giant double-bladed axe; an ice queen with a crystal crown and a glowing blue staff; a hooded purple-cloaked assassin crouching with twin daggers; a shadowy spectral wraith with glowing eyes and a curved blade. Highly detailed dark-fantasy game art, dramatic varied dynamic poses, crisp rim light, rich colour. The figures must not touch each other or the image border. Pure flat white background, no panel borders, no frames, no outlines, no text, no logos.

**04 cute pets**
> A clean 3-column by 2-row grid of six different cute pets, each one a COMPLETE FULL BODY animal from ears to paws and tail, nothing cropped, a comfortable white margin around each animal. Pets: a fluffy orange tabby kitten reaching one paw up; a smiling corgi jumping towards the camera; a grey French bulldog sitting with a blue bow tie; a black-and-white kitten peeking out of a vintage teacup; a beagle puppy lying on its back with a red bandana; a cream Persian kitten licking its paw. Soft studio photography look, ultra-detailed fur, bright and adorable, varied playful poses. The animals must not touch each other or the image border. Pure flat white background, no panel borders, no frames, no outlines, no text, no logos.

**05 anime cool**
> A clean 3-column by 2-row grid of six different cool male anime characters, each one a COMPLETE FULL BODY figure from head to toe, nothing cropped, a comfortable white margin around each character. Characters: a heavily tattooed villain with four arms and long red hair, hands pressed together; a green-haired swordsman in a dark-green kimono holding three katana; a raven-haired assassin in a black fitted outfit with a spear over his shoulder; a bald caped hero in a yellow suit with red gloves throwing a punch; a white-haired boy in a light-blue kimono crouching with a yo-yo weapon; a short dark-haired man in a green hooded cloak with a curved blade. Dramatic varied poses, cool moody lighting with glowing energy auras, very detailed modern anime game art, crisp linework. The figures must not touch each other or the image border. Pure flat white background, no panel borders, no frames, no outlines, no text, no logos.

**پرامپت‌های ست ۲۰۲۶ (تأییدشده):**

**01 ugly cute**
> A clean 3-column by 2-row grid of six deliberately derpy "ugly cute" cartoon mascot characters, each one a COMPLETE FULL BODY figure from head to toe, nothing cropped, a comfortable white margin of empty space around each character. Characters: a chubby yellow blob creature with tiny arms and a huge goofy grin; a fluffy pink creature with one giant eye and a lolling tongue; a blue potato-shaped creature with giant eyebrows and a smug smirk; a green creature with stretched noodle arms doing a thumbs up; a purple horned creature with too many teeth laughing; an orange round creature with a pirate hat and a silly wink. Intentionally distorted, meme-like, funny, sticker-style cartoon with thick bold outlines and flat bright colours. The characters must not touch each other or the image border. Pure flat white background, no panel borders, no frames, no text, no logos.

**02 designer toys**
> A clean 3-column by 2-row grid of six different collectible designer vinyl toy characters, each one a COMPLETE FULL BODY figure from head to toe, nothing cropped, a comfortable white margin of empty space around each character. Characters: a fluffy white bunny-eared monster with sharp little teeth and a pastel mint hoodie; a round pastel-pink plush creature with tiny arms, a sleepy face and a bow; a mint-green fuzzy monster with big round eyes and a strawberry in its hand; a lilac plush bear with star patches and a sparkly horn; a butter-yellow creature with bunny ears wearing a tiny backpack; a cream plush cat with blushing cheeks and a fish-shaped bag. Glossy toy-plastic and soft plush textures, cute chibi proportions, pastel palette, soft studio lighting, high detail collectible-toy photography look. The characters must not touch each other or the image border. Pure flat white background, no panel borders, no frames, no text, no logos, no brand marks.

**03 cyber robots**
> A clean 3-column by 2-row grid of six different friendly futuristic robot characters, each one a COMPLETE FULL BODY figure from head to toe, nothing cropped, a comfortable white margin of empty space around each robot. Robots: a small round white companion robot with a glowing cyan face screen and antenna; a tall slim chrome android with neon-blue joints striking a peace sign; a boxy retro-futuristic cleaning bot on treads with one big eye; a floating teardrop-shaped drone bot with holographic rings; a heavy industrial mech with orange warning stripes and big fists; a cute cat-shaped house robot with LED whiskers. Glossy metal, plastic panels, glowing accents, clean sci-fi product-render look, varied dynamic poses, crisp reflections. The robots must not touch each other or the image border. Pure flat white background, no panel borders, no frames, no text, no logos, no brand marks.

**04 greek gods**
> A clean 3-column by 2-row grid of six different ancient Greek gods and mythic heroes, each one a COMPLETE FULL BODY figure from head to toe, nothing cropped, a comfortable white margin of empty space around each figure. Figures: a thunder god with a white beard, bronze armour and a crackling lightning bolt; a sea god with a coral crown, trident and flowing teal robes; a dark underworld king in black robes with a burning brazier and a three-headed hound at his feet; a goddess of wisdom in white marble armour with a spear and owl; a winged messenger god with a caduceus staff and winged sandals; a hero in a red cape with a round shield and sword. Epic cinematic mythological art, highly detailed bronze armour and drapery, dramatic varied poses, gold and marble accents. The figures must not touch each other or the image border. Pure flat white background, no panel borders, no frames, no text, no logos.

> ⚠️ پوکمون (۳۰ سالگی) رد شد: پرامپت «electric mouse / fire lizard / seed dinosaur» با `moderation_blocked` برگشت. هر موضوعی که شبیه IP معروف باشد جایش را با موضوع اورجینال عوض کن.

**پرامپت‌های ست ۲۰۲۶ #۲ (تأییدشده — همه یک‌جا پاس شدند):**

قالب مشترک: «A clean 3-column by 2-row grid of six different <موضوع>, each one a COMPLETE FULL BODY … from … to …, nothing cropped, a comfortable white margin of empty space around each one. … The <موضوع> must not touch each other or the image border. Pure flat white background, no panel borders, no frames, no text, no logos.»

| پک | <موضوع> | جزئیات کلیدی |
|---|---|---|
| raccoon_squad | mischievous cartoon raccoons | پیتزا، سطل زباله، خرس عروسکی، عینک گرد+زنجیر طلایی، جعبهٔ مقوایی، پشمک صورتی؛ «sticker-style cartoon, thick clean outlines» |
| squishy_world | glossy squishy sensory toy characters | توپ خاردار صورتی، مکعب آبی شفاف با اکلیل، ستارهٔ رشته‌ای زرد، توپ نعنایی خواب‌آلود، رینگ یاسی اکلیلی، بلاب نارنجی؛ «translucent jelly, kawaii faces» |
| gargoyles | whimsical gargoyle characters | نشسته روی پایه، خمیازه روی ستون، پر خوردن، کتاب خواندن، فانوس، هلال‌ماه؛ «weathered stone with moss» |
| moon_witches | charming young witch characters | عصای ماه، گربهٔ سیاه، کتاب و شمع شناور، گوی کریستال، جارو، دیگ جادو؛ «whimsigoth, moon and star motifs» |
| cozy_capybara | cozy capybara characters | کلاه قارچی+شال، وان چوبی با پرتقال، چای+قورباغه، بارانی+چتر، خواب در برگ‌ها، تاج گل+نارنگی؛ «cottagecore autumn palette» |

> گارگویل‌ها، کاپی‌بارا و اسکویشی‌ها هیچ‌کدام moderation نخوردند؛ برای موضوع‌های شبیه IP (مثل پوکمون) احتمال رد بالاست — از قبل یک تم جایگزین اورجینال در ذهن داشته باش.

**پرامپت‌های ست کمدی (همه یک‌جا پاس شدند):**

| پک | <موضوع> در قالب مشترک | جزئیات کلیدی |
|---|---|---|
| funny_footballers | comedic caricature football players | سر بزرگ کاربکچر + بدن کوچک، چهرهٔ طنز با بافت پوست واقعی، ژست‌های خنده‌دار (دست باز، چشمک+لایک، سالتو، facepalm، توپ روی سر+زبان، شانه بالا)، شماره‌های ۱۰/۷/۷/۱۰/۱۱/۹، «no club crest, no brand logos» |
| meme_cats | hilarious meme cats | جیغ دهان‌باز، نشستن مثل آدم غمگین، زبان‌بیرون+لوچ، خمیازه، صورت له‌شده پشت شیشه، کلاه کاغذی؛ «photographic-real fur» |
| funny_food | funny kawaii food characters | نان تست با شنل و عینک، موز در позای یوگا، دامپلینگ با دمبل، سوشی سوار بر موج سس، توت‌فرنگی بداخلاق با چتر، پیتزا روی دست |
| silly_frogs | hilarious cartoon frogs | بابا تی، جیغ دراماتیک، کابوی سوار حلزون، ورقلمبیده روی نیلوفر، بازو زدن، کلاه جشن و بوق |
| office_animals | funny animals in business suits | سگ گلدن با قهوه و استرس، گربهٔ کت‌وشلوار، لاما با لپ‌تاپ، هامستر زیر کاغذ، اردک با پاپیون، پاگ خوابیده روی میز |

> نکته: کاربکچر بازیکن فوتبال (برخلاف نسخهٔ واقع‌گرا) moderation نمی‌خورد؛ چون چهرهٔ کارتونی/اغراق‌شده است.

### گام ۲ — تولید ۵ استریپ استیکر اسم (مهم‌ترین درس این پروژه)
اسم‌ها **هرگز با فونت تایپ نشوند** — با تولید عکس ساخته شوند. ذخیره در `assets/names/0{1..5}.png`.
هر تصویر: **سه استیکر در یک ردیف افقی**، پس‌زمینه سفید، بدون قاب.

قالب پرامپت:
> Three separate sticker name-plate designs arranged in a horizontal row on a pure flat white background, evenly spaced, not touching. Each one is a die-cut sticker bumper: thick glossy 3D bubble letters with a bold white sticker border, a soft drop shadow and a subtle highlight, sitting on a plain white rounded label. The three words, spelled exactly: "{WORD1}", "{WORD2}", "{WORD3}". Colour scheme: {پالت}. Clean vector-like sticker artwork, sharp edges, no extra text, no background pattern, no frame.

پالت‌های استفاده‌شده: 01 آبی روشن با خط دور سرمهای · 02 سرمهای عمیق با هایلایت نقره‌ای · 03 بنفش-سرخابی با خط دور بنفش تیره · 04 صورتی رز با خط دور صورتی گرم · 05 سبز زمردی با خط دور سبز تیره.

**بعد از هر تولید، املا را حرف‌به‌حرف چک کن.** اگر غلط بود، همان را دوباره تولید کن.

### گام ۳ — کامپوز + خط برش + وریفیکیشن + بسته‌بندی
```bash
python3 make_pack.py       # ۵ برگه، خروجی در pack/
python3 pack_extra.py      # README هر برگه + pack/README.txt دستی + all_sheets_overview.png
zip -9 -r sticker_pack_print_cut.zip pack
```

`make_pack.py` این کارها را می‌کند (به همین ترتیب):

1. **برش شیت به ۶ سلول** — `trim()` کل شیت، بعد `split_cells(img, rows=2, cols=3)`.
   مرزها فقط روی **راهروهای سفید واقعی** انتخاب می‌شوند (میانهٔ ران‌های خالی) و هر مرز ایده‌آل به نزدیک‌ترین راهروی آزاد می‌چسبد. هر سلول ۱۶ px به داخل راهرو باز می‌شود تا آرت به لبه نچسبد.
2. **آلفا** — `sticker_rgba(cell)`: پیکسل‌های `min(RGB) < 249` = مرکب؛ `OPEN` با کرنل ۷ (حذف خط‌های مویی و قاب نازک)، `CLOSE` ۷، بزرگ‌ترین مؤلفهٔ متصل، `dilate` ۱۳، و سفید کردن بیرونِ ماسک. سپس کراپ به bbox با ۲ px حاشیه.
3. **هدر** (`header()`) — لوگو + وردمارک گرادیانی `Ghelghelishop.com` با فونت Poppins ExtraBold + عنوان پک + **QR کد** `https://ghelghelishop.com` (ECC-H, border=1, ۱۱۶ px) + کپشن `SCAN TO SHOP` + خط مویی جداکننده.
4. **چیدمان** — بدنه: ۲×۳ با بزرگ‌نمایی هر استیکر تا جا شدن در سلول (بدون تغییر نسبت)، و بعد **چیدن دو ردیف به‌صورت یک بلوک وسطِ بند بدنه** (`row_h`, `block_h`, `top`) تا فاصلهٔ مردهٔ بین ردیف‌ها نماند. پایین: ۳ استیکر اسم از `assets/names/NN.png` که با `split_cells(rows=1, cols=3)` به سه تکه شکسته می‌شوند.
5. **خط برش** — `smooth_path(alpha)`: OPEN تطبیقی (`k = max(5, 3.5% کوچک‌ترین بُعد)`) → `fill_holes` → dilate ۴ → آپ‌اسکیل ۲× → بلور σ=2.6 → آستانه → بزرگ‌ترین کانتور → ری‌سمپل هر ۵ px → ساده‌سازی → **بزیهٔ کاتمول-رام بسته** (`TENSION 0.85`).
6. **گارد فاصله** — تا ۸ بار، هر مسیری که به دیگری نزدیک‌تر از `MIN_GAP_PX` باشد ۱.۵٪ کوچک می‌شود.
7. **خروجی** — PNG، SVG (CutLine)، SVG پیش‌نمایش سیاه، PDF با cairosvg، پرووها، و `verification.json`.

### گام ۴ — بازرسی چشمی (اجباری، هر ۵ برگه)
`pack/<sheet>/proof_overlay.png` را **حتماً باز کن و ببین**:
- خط برش دور خودِ شخصیت/حروف می‌پیچد، نه مستطیل دور سلول.
- هیچ استیکری گم نشده (۶ شخصیت + ۳ اسم).
- هیچ شخصیتی از کادر بریده نشده و سر/پا کامل است.
- هیچ خط اضافه یا دنبالهٔ نازک بیرون از فروم نیست.
- استیکرهای اسم کامل روی صفحه‌اند و به لبهٔ پایین نمی‌چسبند.

### گام ۵ — تست‌های عددی
```bash
python3 - <<'EOF'
import json
for f in ['01_anime_legends','02_football_stars','03_dota2_heroes','04_cute_pets','05_anime_cool']:
    d=json.load(open(f'pack/{f}/verification.json'))
    print(f, d['path_count'], d['min_gap_mm'], d['min_edge_margin_mm'], d['self_intersections'], d['PASS'])
EOF
```
معیار قبولی: `path_count == 9`، `self_intersections == 0`، `touching_pairs == []`، `touching_edge == []`، `min_gap_mm ≥ 0.8`، `min_edge_margin_mm ≥ 2.5`، `PASS == true`.

تست QR (باید `https://ghelghelishop.com` برگردد):
```bash
python3 -c "
import cv2,glob
for f in sorted(glob.glob('pack/*/*_A6_300dpi.png')):
    print(f, cv2.QRCodeDetector().detectAndDecode(cv2.imread(f)[40:175,1055:1215])[0])"
```

### گام ۶ — تحویل و پاک‌سازی
`present_file` روی `pack/all_sheets_overview.png`، تحویل زیپ، و بعد:
```bash
rm -rf sheets pack __pycache__ .cache
```

---

## 4) ثابت‌های فنی (عیناً همین‌ها)

```python
A6   = (1240, 1748)     # 105×148 mm @ 300 DPI
HEADER_H = 210; FOOT_H = 236; MARGIN_X = 40; TOP_GAP = 8
STROKE_PT = 0.25; MIN_GAP_PX = 5.0; EDGE_MARGIN_PX = 5.0
WHITE_T = 249           # پیکسل با min(RGB) < 249 = مرکب
BLUR_SIGMA = 2.6; RESAMPLE = 5.0; TENSION = 0.85
QR: qrcode, ERROR_CORRECT_H, border=1, data='https://ghelghelishop.com', 116 px در هدر
رنگ‌های پک: 01 (30,92,168) · 02 (16,58,128) · 03 (104,40,132) · 04 (214,92,126) · 05 (12,104,84)
```
نتیجهٔ آخر: هر ۵ برگه PASS — فاصلهٔ حداقل ۱.228–۲.186 mm، حاشیهٔ لبه ۳.39–۴.95 mm.

---

## 5) خطاهای ثابت‌شده — دوباره امتحان نکن

| مشکل | علت | راه‌حل |
|---|---|---|
| خط برش مستطیل مستطیل شد | مولد دور هر کاراکتر یک **قاب نازک بسته** می‌کشد و `fill_holes` آن را پر می‌کند | `OPEN` با کرنل ۷ قبل از `fill_holes` + در پرامپت «no frames, no outlines» |
| مستطیل بلند تا پای صفحه | `fill_holes` بدون حاشیه: شکلی که به لبه می‌چسبد بوم را دو نیم می‌کند و نوار خالی «حفره» حساب می‌شد | `fill_holes` بعد از `copyMakeBorder(2px)` و کراپ برگشتی |
| ستون وسط گم شد / دو استیکر ناپدید | انتخاب مرز سلول با پنجرهٔ نسبی، مرز را داخل راهروی اشتباه می‌گذاشت | مرز فقط روی میانهٔ «ران سفید» واقعی |
| یک کاراکتر کل شیت را قورت داد (مثلاً بازیکن وارونه) | برش روی «ران سفید سراسری» انجام می‌شد و وقتی یک ژست وارونه/هالهٔ آرت همهٔ ردیف را پر می‌کرد، مرز پیدا نمی‌شد | `split_cols_then_rows()`: اول ستون‌ها (که همیشه جدا می‌شوند) بعد برش ردیف داخل هر ستون؛ و اگر ورودی گرید نامنظم بود `split_by_components()` با ادغام قطعه‌های کوچک |
| خار/موی نازک بیرون از فرم | باقی‌ماندهٔ خط نازک آرت | `OPEN` تطبیقی در `smooth_path` |
| حذف سایهٔ استودیویی، جوراب و کفش سفید را خورد | قاعدهٔ «خاکستری روشن = سایه» روی سفیدی لباس هم اعمال می‌شد | سایه را نگه دار؛ داخل خط برش بماند، فقط پرامپت «no shadow» بده |
| بازیکن واقعی/عکس‌واقعی | `moderation_blocked` (۴ بار تجربه شد) | «photorealistic faces … ultra-realistic 3D characters» بدون نام |
| اسم ایتالیک/فونت بدشکل | تایپ با فونت هرگز به کیفیت استیکر نمی‌رسد | استیکر اسم = تولید عکس (گام ۲) |
| `alpha_composite` → images do not match | لایه‌ها باید هم‌اندازه و RGBA باشند | `.convert('RGBA')` و resize دقیق |
| cairosvg ضخامت 0.25pt را نادیده می‌گیرد | محدودیت رندر | فقط در پرووها خط را ضخیم کن؛ SVG نهایی ۰.۲۵pt بماند |
| نصب‌ها بین نوبت نمی‌مانند | سندباکس | هر بار `pip install` |

---

## 6) نکات چاپ (به مشتری/چاپخانه بگو)
- کاغذ برچسب سفید، kiss-cut یا through-cut؛ bleed لازم نیست.
- خط برش را در RIP به‌عنوان **spot color با نام `CutContour`** تعریف کن، یا به اپراتور بگو `#FF0000` لایهٔ برش است و نباید به‌عنوان مرکب چاپ شود.
- آرت RGB است؛ تبدیل CMYK با پروفایل چاپخانه. برای مشکی عمیق: rich black **C45 M35 Y30 K100**.

## 7) هشدار حقوقی (همیشه در تحویل تکرار شود)
شخصیت‌های انیمه، چهرهٔ بازیکن‌ها و قهرمان‌های Dota 2 **مالکیت فکری شخص ثالث** هستند. برای استفادهٔ شخصی یا نمونهٔ چاپی مشکلی نیست؛ تولید انبوه و فروش عمومی نیازمند مجوز از صاحب حق است. شیت حیوانات بدون شخصیت شخص ثالث است.

---

## 8) پرامپت کلی (این را بده، کل جریان اجرا می‌شود)

```
یک پک استیکر A6 آمادهٔ چاپ و برش برای فروشگاه Ghelghelishop.com بساز، دقیقاً بر اساس
memory.md که در ورک‌اسپیس هست. ۵ برگه، هر برگه ۹ استیکر (۶ شخصیت کامل‌قد + ۳ استیکر اسم).

قواعد غیرقابل‌عبور:
1. هر شیت آرت را با یک پرامپت جداگانه تولید کن: گرید ۳×۲، شش کاراکتر «COMPLETE FULL BODY
   from head to toe», حاشیهٔ سفید دور هر کاراکتر، «pure flat white background, no frames,
   no outlines, no text, no logos». هیچ کاراکتری بریده یا به لبه چسبیده نباشد.
2. شیت فوتبال باید چهرهٔ واقع‌گرای فتوشاپی داشته باشد (photorealistic faces, ultra-realistic
   3D, not cartoon) با شمارهٔ پیراهن درشت و واضح و بدون نشان باشگاه/برند.
3. استیکرهای اسم را با «تولید عکس» بساز، نه با فونت: هر برگه یک تصویر افقی با سه استیکر
   حروف حبابی سه‌بعدی براق روی سفید، و بعد املا را حرف‌به‌حرف چک کن.
4. هدر هر برگه: لوگو (uploads/logo-fixed-transparent.png) + وردمارک Ghelghelishop.com
   + عنوان پک + QR کد واقعی به https://ghelghelishop.com با کپشن SCAN TO SHOP.
5. خط برش: SVG با #FF0000، 0.25pt، fill:none، لایهٔ CutLine، بوم 105×148 mm، ۹ مسیر بسته،
   بدون خودتقاطع، بدون تماس با لبهٔ تریم، فاصلهٔ حداقل ۰.۸ mm.
6. خودت بازرسی کن: هر ۵ فایل proof_overlay.png را باز و نگاه کن، verification.json همه باید
   PASS باشند و QR باید درست دیکود شود. تا وقتی این‌ها پاس نشده تحویل نده.
7. بسته‌بندی: pack/<sheet>/ با PNG ۳۰۰DPI + SVG/PDF + پرووها + verification.json + README،
   به‌همراه all_sheets_overview.png و README کلی، همه در sticker_pack_print_cut.zip.
8. در پایان فایل‌های موقت (sheets/, pack/, زیپ قدیمی) را پاک کن، زیپ نهایی را تحویل بده و
   هشدار حقوقی شخصیت‌های شخص ثالث را بنویس. پاسخ فارسی باشد.
```


---

## 9) استفاده در ایجنت‌های دیگر (مخزن گیت‌هاب)

مخزن: `amirrezahadipoor/Stickermaker` — شامل `src/make_pack.py` + `src/pack_extra.py` + `memory.md` + `assets/brand/logo.png` + `assets/brand/qr-ghelghelishop.png` + فونت‌ها.

```bash
git clone https://github.com/amirrezahadipoor/Stickermaker.git
cd Stickermaker
pip install -r requirements.txt
python3 src/make_pack.py      # ۵ برگه در pack/
python3 src/pack_extra.py     # README + all_sheets_overview.png
zip -9 -r sticker_pack_print_cut.zip pack
```

هر ایجنت تازه، فقط این را بدهد:

> «طبق memory.md مخزن Stickermaker یک پک استیکر A6 بساز؛ تم‌های تازه در لیست THEMES
> در `src/make_pack.py` تعریف می‌شوند. آرت هر شیت و استریپ اسم هر شیت را با تولید تصویر
> بساز، بعد `make_pack.py` و `pack_extra.py` را اجرا کن، هر ۵ `proof_overlay.png` را
> بازبینی کن، `verification.json` باید PASS و QR باید دیکود شود، آخر زیپ بده و
> فایل‌های موقت را پاک کن. پاسخ فارسی.»

### افزودن تم تازه
1. در `THEMES` در `src/make_pack.py` یک تاپل اضافه کن: `(folder, TITLE, [NAME1, NAME2, NAME3], (r,g,b))`.
2. شیت آرت را در `sheets/<folder>/raw.png` بگذار (گرید ۳×۲، سفید، بدون قاب).
3. استریپ اسم را در `assets/names/<NN>.png` بگذار (سه کلمه در یک ردیف).
4. `python3 src/make_pack.py` — تم‌هایی که استریپ اسم ندارند خودکار SKIP می‌شوند.

### سهمیه‌ها
تولید تصویر **۱۰ تصویر در هر نوبت**. برای ۵ تم یعنی ۵ شیت آرت + ۵ استریپ اسم = دقیقاً سقف؛
هیچ جا برای تلاش دوباره نمی‌ماند. اگر خروجی مشکل داشت، ۴ تم را کامل کن و پنجمی را نوبت بعد.

### چک‌لیست تحویل
- [ ] ۹ مسیر در هر برگه، `PASS: true` در همهٔ `verification.json`
- [ ] هر ۵ `proof_overlay.png` با چشم دیده شده
- [ ] QR روی صفحهٔ ۳۰۰DPI دیکود شده
- [ ] استیکرهای اسم حرف‌به‌حرف درست
- [ ] `zip` سالم (`python3 -c "import zipfile;print(zipfile.ZipFile('x.zip').testzip())"`)
- [ ] فایل‌های موقت پاک، هشدار حقوقی نوشته شده
