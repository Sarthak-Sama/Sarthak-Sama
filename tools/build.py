"""Builds the PNG posters in ../assets for the profile README.

Look: red/black underground zine. Public-domain ukiyo-e prints (Kuniyoshi,
Hokusai) pushed through a halftone screen, blackletter and Mincho type,
NFO-style release boxes, grain, dust and fold creases.

Run:  python3 tools/build.py      (needs `pip install pillow numpy`)
Fonts (OFL) and source prints (public domain, Wikimedia Commons) are
downloaded into tools/.cache on first run.
"""

import json
import math
import os
import random
import urllib.parse
import urllib.request

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
CACHE = os.path.join(ROOT, "tools", ".cache")
UA = {"User-Agent": "readme-builder/1.0"}

FONTS = {
    "black": "ofl/grenzegotisch/GrenzeGotisch%5Bwght%5D.ttf",
    "vt": "ofl/vt323/VT323-Regular.ttf",
    "mincho": "ofl/zenoldmincho/ZenOldMincho-Black.ttf",
    "anton": "ofl/anton/Anton-Regular.ttf",
    "dela": "ofl/delagothicone/DelaGothicOne-Regular.ttf",
}

PRINTS = {
    "skeleton": "File:Takiyasha the Witch and the Skeleton Spectre, by Utagawa Kuniyoshi.jpg",
    "wave": "File:Tsunami by hokusai 19th century.jpg",
    "tiger": "File:Kuniyoshi Utagawa, Tiger.jpg",
    "fuji": "File:Lightnings below the summit.jpg",
    "ghost": "File:Kuniyoshi Utagawa, The ghost of Taira Tomomori, Daimotsu bay.jpg",
}

BLACK = (0, 0, 0)
RED = (232, 0, 11)
BLOOD = (74, 0, 6)
BONE = (232, 226, 212)
ASH = (138, 133, 128)

random.seed(21)
np.random.seed(21)


# ── fetching ───────────────────────────────────────────────────────────────
def fetch(url, path):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        print("downloading", url)
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req) as r, open(path, "wb") as f:
            f.write(r.read())
    return path


def font(key, size):
    path = os.path.join(CACHE, urllib.parse.unquote(os.path.basename(FONTS[key])).replace("[wght]", ""))
    fetch("https://github.com/google/fonts/raw/main/" + FONTS[key], path)
    f = ImageFont.truetype(path, size)
    if key == "black":
        f.set_variation_by_name("Black")
    return f


def source(key):
    path = os.path.join(CACHE, key + ".jpg")
    if not os.path.exists(path):
        api = ("https://commons.wikimedia.org/w/api.php?action=query&prop=imageinfo&iiprop=url"
               "&iiurlwidth=2200&format=json&titles=" + urllib.parse.quote(PRINTS[key]))
        with urllib.request.urlopen(urllib.request.Request(api, headers=UA)) as r:
            info = list(json.load(r)["query"]["pages"].values())[0]["imageinfo"][0]
        fetch(info.get("thumburl", info["url"]), path)
    return Image.open(path).convert("L")


# ── image treatments ───────────────────────────────────────────────────────
def crop(key, box, size, invert=False, gamma=1.0, contrast=1.6):
    """box is fractional (l, t, r, b). Returns float array 0..1 where 1 = ink."""
    im = source(key)
    w, h = im.size
    im = im.crop((int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)))
    im = im.resize(size, Image.LANCZOS)
    a = np.asarray(im, dtype=np.float32) / 255.0
    if not invert:
        a = 1.0 - a
    lo, hi = np.percentile(a, 3), np.percentile(a, 97)
    a = np.clip((a - lo) / max(hi - lo, 1e-3), 0, 1)
    a = np.clip((a - 0.5) * contrast + 0.5, 0, 1) ** gamma
    return a


def halftone(a, cell=7.0, angle=45):
    """Amplitude-modulated dot screen: returns a 0/255 mask."""
    h, w = a.shape
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    t = math.radians(angle)
    u = x * math.cos(t) + y * math.sin(t)
    v = -x * math.sin(t) + y * math.cos(t)
    screen = 0.5 + 0.25 * (np.cos(2 * math.pi * u / cell) + np.cos(2 * math.pi * v / cell))
    return Image.fromarray(((a > screen) * 255).astype(np.uint8))


def dither(a, scale=3):
    """Chunky Floyd-Steinberg dither, upscaled with hard pixels."""
    h, w = a.shape
    small = Image.fromarray((a * 255).astype(np.uint8)).resize((w // scale, h // scale), Image.LANCZOS)
    return small.convert("1").convert("L").resize((w, h), Image.NEAREST)


def ink(canvas, mask, color, at=(0, 0)):
    layer = Image.new("RGB", mask.size, color)
    canvas.paste(layer, at, mask)


def noise_mask(size, density, blur=0.0, scale=1):
    w, h = size
    n = np.random.rand(h // scale + 1, w // scale + 1)
    im = Image.fromarray((n * 255).astype(np.uint8)).resize((w, h), Image.NEAREST if scale > 1 else Image.BILINEAR)
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    return im.point(lambda p: 255 if p < density * 255 else 0)


def distress(mask, amount=0.18):
    """Eat random holes into a text/shape mask so it reads as worn print."""
    holes = noise_mask(mask.size, amount, blur=1.2, scale=3)
    holes = holes.point(lambda p: 0 if p > 0 else 255)
    return ImageChops.multiply(mask, holes)


def grime(canvas, creases=True):
    """Grain, dust, scratches and fold lines over the whole poster."""
    w, h = canvas.size
    grain = (np.random.rand(h, w) * 40 - 20).astype(np.int16)
    arr = np.asarray(canvas).astype(np.int16) + grain[..., None]
    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(out)
    for _ in range(int(w * h / 2500)):
        x, y = random.randrange(w), random.randrange(h)
        r = random.choice([0.6, 0.8, 1, 1, 1.5, 2.2])
        c = random.choice([BONE, ASH, (40, 40, 40)])
        d.ellipse((x - r, y - r, x + r, y + r), fill=c)
    for _ in range(8):
        x = random.randrange(w)
        d.line((x, random.randrange(h), x + random.randint(-30, 30), random.randrange(h)), fill=(70, 66, 62), width=1)
    if creases:
        for line in ((w * 0.5, 0, w * 0.5 + 4, h), (0, h * 0.5, w, h * 0.5 - 3)):
            band = Image.new("L", (w, h), 0)
            ImageDraw.Draw(band).line(line, fill=90, width=3)
            band = band.filter(ImageFilter.GaussianBlur(2.5))
            out.paste(Image.new("RGB", (w, h), BONE), (0, 0), band.point(lambda p: p // 3))
    return out


# ── type helpers ───────────────────────────────────────────────────────────
def text_mask(size, xy, s, f, anchor="la"):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).text(xy, s, font=f, fill=255, anchor=anchor)
    return m


def vertical(size, x, y, s, f, step=None):
    """Top-to-bottom Japanese, one glyph per line, centred on x."""
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    step = step or f.size * 1.08
    for i, ch in enumerate(s):
        cy = y + i * step + step / 2
        if ch in "、。":
            d.text((x + f.size * 0.3, cy - f.size * 0.3), ch, font=f, fill=255, anchor="mm")
        elif ch == "・":
            d.text((x, cy), "・", font=f, fill=255, anchor="mm")
        else:
            d.text((x, cy), ch, font=f, fill=255, anchor="mm")
    return m


def misprint(canvas, mask, fg, shadow=RED, off=(6, 4), worn=0.16):
    """Two-colour print with slight misregistration."""
    m = distress(mask, worn)
    ink(canvas, ImageChops.offset(m, *off), shadow)
    ink(canvas, m, fg)


def frame(d, w, h, inset=22, color=ASH):
    d.rectangle((inset, inset, w - inset, h - inset), outline=color, width=2)
    t = 18
    for cx, cy, sx, sy in ((inset, inset, 1, 1), (w - inset, inset, -1, 1), (inset, h - inset, 1, -1), (w - inset, h - inset, -1, -1)):
        d.line((cx - sx * 10, cy, cx + sx * t, cy), fill=BONE, width=4)
        d.line((cx, cy - sy * 10, cx, cy + sy * t), fill=BONE, width=4)


def barcode(d, x, y, h, color=BONE, n=34):
    rnd = random.Random(7)
    for _ in range(n):
        w = rnd.choice([1, 1, 2, 3, 4])
        d.rectangle((x, y, x + w, y + h), fill=color)
        x += w + rnd.choice([2, 2, 3, 4])
    return x


def save(im, name):
    path = os.path.join(ASSETS, name)
    im.convert("RGB").quantize(colors=96, method=Image.MEDIANCUT, dither=Image.NONE).save(path, optimize=True)
    print(f"{name:24s} {os.path.getsize(path)/1024:7.1f} KB")


def text_wall(canvas, line, f, color, line_h, shift=0.37):
    d = ImageDraw.Draw(canvas)
    w, h = canvas.size
    unit = d.textlength(line, font=f)
    for i, y in enumerate(range(-4, h, line_h)):
        x = -unit * ((i * shift) % 1)
        while x < w:
            d.text((x, y), line, font=f, fill=color)
            x += unit


def wrap(text, f, width, d):
    words, lines, line = text.split(), [], ""
    for w_ in words:
        test = f"{line} {w_}".strip()
        if d.textlength(test, font=f) > width and line:
            lines.append(line)
            line = w_
        else:
            line = test
    lines.append(line)
    return lines


# ── hero ───────────────────────────────────────────────────────────────────
def hero():
    W, H = 1280, 720
    im = Image.new("RGB", (W, H), BLACK)
    text_wall(im, "I CODE LIKE I'M RUNNING OUT OF TIME. ", font("vt", 30), (46, 0, 4), 26)

    # skeleton spectre, halftoned red
    sk = crop("skeleton", (0.40, 0.0, 0.80, 0.80), (800, 760), invert=True, gamma=1.6, contrast=2.1)
    ink(im, halftone(sk, cell=6.5, angle=38), RED, (470, -20))

    d = ImageDraw.Draw(im)

    # red column with vertical Mincho, Eva-style
    d.rectangle((56, 56, 168, 664), fill=RED)
    col = vertical((W, H), 112, 74, "時間がないかのように書く", font("mincho", 46), step=49)
    ink(im, distress(col, .1), BLACK)

    # HUD box
    vt = font("vt", 30)
    d.rectangle((200, 56, 610, 196), fill=BLACK, outline=RED, width=2)
    d.rectangle((200, 56, 610, 86), fill=RED)
    d.text((405, 58), "WELCOME", font=vt, fill=BLACK, anchor="ma")
    for i, (k, v) in enumerate((("USER", "YATO"), ("LOCATION", "TOKYO, JP"), ("CLASS", "FULL-STACK ENGINEER"))):
        d.text((216, 92 + i * 32), k + ":", font=vt, fill=RED)
        d.text((596, 92 + i * 32), v, font=vt, fill=BONE, anchor="ra")

    # name
    bl = font("black", 168)
    name = Image.new("L", (W, H), 0)
    nd = ImageDraw.Draw(name)
    nd.text((196, 360), "Sarthak", font=bl, fill=255, anchor="ls")
    nd.text((262, 530), "Saklani", font=bl, fill=255, anchor="ls")
    # black knockout so the name sits on top of the dots
    ink(im, name.filter(ImageFilter.MaxFilter(13)), BLACK)
    misprint(im, name, BONE, RED, off=(7, 5), worn=.14)

    d = ImageDraw.Draw(im)
    d.text((268, 560), "BUILDS FOR DEVELOPERS AND FOR PEOPLE MOVING TO JAPAN", font=font("anton", 30), fill=BONE)

    # katakana name down the right edge
    kat = vertical((W, H), 1222, 56, "サルタク・サクラニ", font("mincho", 34), step=38)
    ink(im, kat.filter(ImageFilter.MaxFilter(9)), BLACK)
    ink(im, kat, RED)

    # status box + barcode
    d.rectangle((842, 596, 1188, 664), fill=BLACK, outline=RED, width=2)
    d.text((858, 600), "NOW SHIPPING:", font=vt, fill=RED)
    d.text((1174, 630), "ANTIDEPLOY", font=vt, fill=BONE, anchor="ra")
    barcode(d, 268, 610, 40)
    d.text((268, 654), "INDIA >> TOKYO  //  MEXT", font=font("vt", 22), fill=ASH)

    frame(d, W, H)
    save(grime(im), "hero.png")


# ── section headers ────────────────────────────────────────────────────────
def header(slug, title, jp):
    W, H = 1280, 170
    im = Image.new("RGB", (W, H), BLACK)
    bl = font("black", 112)
    misprint(im, text_mask((W, H), (40, 128), title, bl, anchor="ls"), BONE, RED, off=(6, 4), worn=.12)
    d = ImageDraw.Draw(im)
    tw = d.textlength(title, font=bl)
    d.line((40 + tw + 30, 104, W - 230, 104), fill=RED, width=3)
    d.text((W - 40, 104), jp, font=font("mincho", 40), fill=RED, anchor="rm")
    save(grime(im, creases=False), f"h-{slug}.png")


# ── tiger plate (floats beside the bio) ────────────────────────────────────
def tiger():
    W, H = 600, 940
    im = Image.new("RGB", (W, H), BLACK)
    a = crop("tiger", (0.02, 0.16, 0.98, 0.86), (560, 860), invert=True, gamma=1.1, contrast=1.7)
    ink(im, halftone(a, cell=6, angle=22), RED, (20, 20))
    d = ImageDraw.Draw(im)
    d.rectangle((20, 20, W - 20, 880), outline=BONE, width=2)
    m = vertical((W, H), 520, 44, "虎", font("mincho", 120))
    ink(im, m.filter(ImageFilter.MaxFilter(9)), BLACK)
    misprint(im, m, BONE, RED, off=(5, 4), worn=.1)
    d = ImageDraw.Draw(im)
    d.text((24, 900), "FIG.1  UTAGAWA KUNIYOSHI, TIGER", font=font("vt", 26), fill=ASH)
    save(grime(im, creases=False), "tiger.png")


# ── NFO release information ────────────────────────────────────────────────
def nfo():
    W, H = 1280, 1190
    vt = font("vt", 31)
    rows_h = 46
    im = Image.new("RGB", (W, H), BLACK)
    d = ImageDraw.Draw(im)

    # blocky ANSI-style logo: tiny render, checker shade, hard upscale
    small = Image.new("L", (190, 60), 0)
    ImageDraw.Draw(small).text((95, 32), "YATO", font=font("dela", 46), fill=255, anchor="mm")
    logo = small.resize((760, 240), Image.NEAREST)
    ink(im, ImageChops.offset(logo, 12, 12), BLOOD, (260, 20))
    checker = Image.fromarray((((np.indices((240, 760)).sum(axis=0) // 4) % 2) * 255).astype(np.uint8))
    ink(im, ImageChops.multiply(logo, checker), ASH, (260, 20))
    ink(im, logo.filter(ImageFilter.MinFilter(9)), BONE, (260, 20))
    d.text((1022, 222), "TM", font=font("vt", 26), fill=BONE)
    d.text((640, 272), "y a t o   p r o d u c t i o n s", font=vt, fill=RED, anchor="ma")

    x0, x1 = 60, W - 60
    y = 318
    d.rectangle((x0, y, x1, H - 70), outline=ASH, width=2)
    d.rectangle((x0 + 50, y + 18, x1 - 50, y + 66), outline=BONE, width=2)
    d.text((640, y + 26), "RELEASE INFORMATION", font=vt, fill=BONE, anchor="ma")
    tw = d.textlength("RELEASE INFORMATION", font=vt) / 2
    d.line((640 - tw - 70, y + 43, 640 - tw - 16, y + 43), fill=BONE, width=2)
    d.line((640 + tw + 16, y + 43, 640 + tw + 70, y + 43), fill=BONE, width=2)
    y += 84
    d.text((640, y), "··Yato Productions proudly presents··", font=vt, fill=ASH, anchor="ma")
    y += 52

    def rule(y):
        d.line((x0, y - 8, x1, y - 8), fill=ASH, width=1)

    def row(label, value, y, right=None):
        rule(y)
        d.text((x0 + 22, y), label, font=vt, fill=RED)
        d.text((x0 + 220, y), f"[ {value}", font=vt, fill=BONE)
        if right:
            mid = 660
            d.text((mid - 16, y), "]", font=vt, fill=BONE)
            d.line((mid, y - 8, mid, y + rows_h - 8), fill=ASH, width=1)
            d.text((mid + 22, y), right[0], font=vt, fill=RED)
            d.text((mid + 200, y), f"[ {right[1]}", font=vt, fill=BONE)
        d.text((x1 - 22, y), "]", font=vt, fill=BONE, anchor="ra")
        return y + rows_h

    y = row("File Name", "sarthak-saklani.zip", y)
    y = row("Title", "Full-Stack Engineer, Tokyo Edition", y)
    y = row("Origin", "New Delhi, India", y, ("Running In", "Shibuya, Tokyo"))
    y = row("Packaged By", "MEXT Scholarship", y, ("Speaks", "EN / Japanese"))

    def block(label, lines, y):
        rule(y)
        d.text((x0 + 22, y), label, font=vt, fill=RED)
        for i, (l, r, strong) in enumerate(lines):
            d.text((x0 + 220, y + i * 38), l, font=vt, fill=BONE if strong else ASH)
            if r:
                d.text((x1 - 22, y + i * 38), r, font=vt, fill=BONE, anchor="ra")
        return y + len(lines) * 38 + 22

    y = block("Experience", [
        ("Frontend Developer, Tryp.com", "Aug 2025 - Jul 2026", True),
        ("  Owned the frontend of a travel marketplace, 400K users a month.", "", False),
        ("  Cart, promo codes, package filters, offline bookings.", "", False),
        ("Full-Stack Intern, Digital Palmy", "Feb 2025 - Jul 2025", True),
        ("  Automated AWS CloudWatch alarms, 75% less manual setup.", "", False),
    ], y)
    y = block("Education", [
        ("BA Japanese Language & Literature, JNU", "2026", True),
        ("BSc Data Science & Programming, IIT Madras", "2027", True),
        ("Japanese Language Course, Bunka Institute", "2027", True),
    ], y)

    rule(y)
    d.text((x0 + 22, y), "Support", font=vt, fill=RED)
    for i, (on, label) in enumerate(((1, "Frontend"), (1, "Backend"), (1, "AI agents"), (0, "IIM"))):
        bx = x0 + 220 + i * 230
        d.text((bx, y), f"[ ] {label}", font=vt, fill=BONE)
        if on:
            d.rectangle((bx + 12, y + 10, bx + 24, y + 22), fill=RED)
    y += rows_h
    rule(y)
    d.text((x0 + 22, y), "Additional releases can be located via sarthak.space", font=vt, fill=BONE)
    d.text((640, H - 54), "Made in India, assembled in Tokyo", font=vt, fill=ASH, anchor="ma")
    tw = d.textlength("Made in India, assembled in Tokyo", font=vt) / 2
    for sx in (-1, 1):
        d.line((640 + sx * (tw + 20), H - 37, 640 + sx * (tw + 220), H - 37), fill=ASH, width=2)
    save(grime(im, creases=False), "nfo.png")


# ── release strips (projects) ──────────────────────────────────────────────
RELEASES = [
    dict(slug="antideploy", no="01", title="ANTIDEPLOY", jp="デプロイ", src="fuji", box=(0.45, 0.30, 1.0, 1.0), inv=True,
         desc="Deploys for coding agents. The agents write the code; somebody still has to ship it.",
         meta="antideploy.com  //  in progress"),
    dict(slug="konbini", no="02", title="CAREER KONBINI", jp="人生のコンビニ", src="ghost", box=(0.52, 0.0, 0.98, 1.0), inv=False,
         desc="Jobs, scholarships and Japanese-format paperwork for life in Japan, all on one shelf.",
         meta="TypeScript"),
    dict(slug="matchi", no="03", title="MATCHI", jp="街えらび", src="wave", box=(0.0, 0.05, 0.62, 0.95), inv=False,
         desc="Ranks 937 Tokyo neighborhoods by your commute, budget and lifestyle.",
         meta="TypeScript  Next.js  Fastify  PostGIS"),
    dict(slug="yomimori", no="04", title="YOMIMORI", jp="読み物", src="skeleton", box=(0.0, 0.05, 0.34, 0.95), inv=False,
         desc="AI-written Japanese stories at your JLPT level, with furigana and a built-in dictionary.",
         meta="React  Express  MongoDB  Gemini"),
]


def release(r):
    W, H = 1280, 320
    im = Image.new("RGB", (W, H), BLACK)
    pw = 470
    a = crop(r["src"], r["box"], (pw, H - 40), invert=r["inv"], gamma=1.1, contrast=1.8)
    ink(im, halftone(a, cell=5.5, angle=30 + int(r["no"]) * 12), RED, (20, 20))
    d = ImageDraw.Draw(im)
    d.rectangle((20, 20, 20 + pw, H - 20), outline=BONE, width=2)
    vt = font("vt", 30)
    x = 530
    d.text((x, 34), f"REL.{r['no']}", font=vt, fill=RED)
    d.text((x + 110, 34), "//  SARTHAK-SAMA", font=vt, fill=ASH)
    misprint(im, text_mask((W, H), (x - 4, 150), r["title"], font("anton", 92), anchor="ls"), BONE, RED, off=(5, 4), worn=.1)
    d = ImageDraw.Draw(im)
    for i, l in enumerate(wrap(r["desc"], vt, 630, d)):
        d.text((x, 170 + i * 32), l, font=vt, fill=BONE)
    d.text((x, 266), r["meta"], font=font("vt", 26), fill=RED)
    d.line((1176, 24, 1176, H - 24), fill=BLOOD, width=1)
    ink(im, vertical((W, H), 1222, 30, r["jp"], font("mincho", 36), step=38), RED)
    save(grime(im, creases=False), f"rel-{r['slug']}.png")


# ── footer ─────────────────────────────────────────────────────────────────
def footer():
    W, H = 1280, 460
    im = Image.new("RGB", (W, H), BLACK)
    a = crop("wave", (0.0, 0.08, 1.0, 0.92), (W, H), invert=False, gamma=1.2, contrast=1.7)
    ink(im, dither(a * 0.55, scale=3), BLOOD)
    ink(im, halftone(a, cell=8, angle=15), RED)
    d = ImageDraw.Draw(im)
    d.rectangle((70, 120, 840, 340), fill=BLACK, outline=RED, width=2)
    d.rectangle((70, 120, 840, 152), fill=RED)
    d.text((86, 122), "NEXT  //", font=font("vt", 30), fill=BLACK)
    d.text((188, 136), "次回", font=font("mincho", 24), fill=BLACK, anchor="lm")
    misprint(im, text_mask((W, H), (90, 262), "OPEN TO FULL-STACK ROLES", font("anton", 74), anchor="ls"), BONE, RED, off=(5, 4), worn=.08)
    d = ImageDraw.Draw(im)
    d.text((92, 286), "Joining a product team in Tokyo. Say hi on X or LinkedIn.", font=font("vt", 30), fill=BONE)
    col = vertical((W, H), 1170, 40, "求職中", font("mincho", 96), step=100)
    ink(im, col.filter(ImageFilter.MaxFilter(11)), BLACK)
    misprint(im, col, BONE, RED, off=(6, 5), worn=.1)
    frame(d, W, H)
    save(grime(im), "footer.png")


if __name__ == "__main__":
    os.makedirs(ASSETS, exist_ok=True)
    hero()
    header("who", "who am i", "自己紹介")
    header("releases", "releases", "作品集")
    header("activity", "activity", "活動記録")
    tiger()
    nfo()
    for r in RELEASES:
        release(r)
    footer()
