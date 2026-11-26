"""Builds the PNG posters in ../assets for the profile README.

Look: a late-90s Japanese sports tabloid with a delinquent-teacher-manga
streak. Newsprint, black ink, red and yellow headline boxes, manga focus
lines, a school report card, tabloid clippings and a classifieds page.
Halftone photos are public-domain ukiyo-e (Kuniyoshi, Hokusai).

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
    "boku": "ofl/yujiboku/YujiBoku-Regular.ttf",
    "mincho-b": "ofl/zenoldmincho/ZenOldMincho-Bold.ttf",
    "gothic": "ofl/zenkakugothicnew/ZenKakuGothicNew-Bold.ttf",
    "hand": "ofl/kleeone/KleeOne-SemiBold.ttf",
}

PRINTS = {
    "skeleton": "File:Takiyasha the Witch and the Skeleton Spectre, by Utagawa Kuniyoshi.jpg",
    "wave": "File:Tsunami by hokusai 19th century.jpg",
    "tiger": "File:Kuniyoshi Utagawa, Tiger.jpg",
    "fuji": "File:Lightnings below the summit.jpg",
    "ghost": "File:Kuniyoshi Utagawa, The ghost of Taira Tomomori, Daimotsu bay.jpg",
}

PAPER = (237, 230, 214)
INK = (20, 20, 20)
INDIGO = (46, 58, 110)
TINT = (218, 209, 190)
ASH = (110, 103, 92)
RED = (214, 36, 30)
YELLOW = (244, 198, 46)
PEN = (36, 48, 94)

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
    grain = (np.random.rand(h, w) * 22 - 11).astype(np.int16)
    arr = np.asarray(canvas).astype(np.int16) + grain[..., None]
    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(out)
    for _ in range(int(w * h / 9000)):
        x, y = random.randrange(w), random.randrange(h)
        r = random.choice([0.6, 0.8, 1, 1, 1.5, 2.2])
        c = random.choice([ASH, (90, 84, 76)])
        d.ellipse((x - r, y - r, x + r, y + r), fill=c)
    for _ in range(4):
        x = random.randrange(w)
        d.line((x, random.randrange(h), x + random.randint(-30, 30), random.randrange(h)), fill=(196, 186, 168), width=1)
    if creases:
        for line in ((w * 0.5, 0, w * 0.5 + 4, h), (0, h * 0.5, w, h * 0.5 - 3)):
            band = Image.new("L", (w, h), 0)
            ImageDraw.Draw(band).line(line, fill=90, width=3)
            band = band.filter(ImageFilter.GaussianBlur(2.5))
            out.paste(Image.new("RGB", (w, h), (150, 138, 118)), (0, 0), band.point(lambda p: p // 3))
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


def misprint(canvas, mask, fg, shadow=INDIGO, off=(6, 4), worn=0.16):
    """Two-colour print with slight misregistration."""
    m = distress(mask, worn)
    ink(canvas, ImageChops.offset(m, *off), shadow)
    ink(canvas, m, fg)


def frame(d, w, h, inset=22, color=ASH):
    d.rectangle((inset, inset, w - inset, h - inset), outline=color, width=2)
    t = 18
    for cx, cy, sx, sy in ((inset, inset, 1, 1), (w - inset, inset, -1, 1), (inset, h - inset, 1, -1), (w - inset, h - inset, -1, -1)):
        d.line((cx - sx * 10, cy, cx + sx * t, cy), fill=INK, width=4)
        d.line((cx, cy - sy * 10, cx, cy + sy * t), fill=INK, width=4)


def barcode(d, x, y, h, color=INK, n=34):
    rnd = random.Random(7)
    for _ in range(n):
        w = rnd.choice([1, 1, 2, 3, 4])
        d.rectangle((x, y, x + w, y + h), fill=color)
        x += w + rnd.choice([2, 2, 3, 4])
    return x


def save(im, name):
    path = os.path.join(ASSETS, name)
    im.convert("RGB").quantize(colors=256, method=Image.Quantize.MAXCOVERAGE, dither=Image.Dither.NONE).save(path, optimize=True)
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


# ── tabloid helpers ────────────────────────────────────────────────────────
def vtext(d, x, y, s, f, fill, step=None):
    """Vertical Japanese drawn straight onto a canvas; rotates ー and 〜."""
    step = step or f.size * 1.04
    for i, ch in enumerate(s):
        cy = y + i * step + step / 2
        if ch in "ー〜":
            g = Image.new("L", (f.size * 2, f.size * 2), 0)
            ImageDraw.Draw(g).text((f.size, f.size), ch, font=f, fill=255, anchor="mm")
            g = g.rotate(-90)
            d._image.paste(Image.new("RGB", g.size, fill), (int(x - f.size), int(cy - f.size)), g)
        elif ch in "、。":
            d.text((x + f.size * 0.3, cy - f.size * 0.3), ch, font=f, fill=fill, anchor="mm")
        else:
            d.text((x, cy), ch, font=f, fill=fill, anchor="mm")
    return y + len(s) * step


def stroked(im, xy, s, f, fill, stroke, width, anchor="la", angle=0):
    """Manga-style lettering: thick outline, optional tilt."""
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).text(xy, s, font=f, fill=fill, anchor=anchor, stroke_width=width, stroke_fill=stroke)
    if angle:
        layer = layer.rotate(angle, center=xy, resample=Image.BICUBIC)
    im.paste(layer, (0, 0), layer)


def speed_lines(im, center, box, n=150, inner=(260, 120), color=INK, seed=3):
    """Manga focus lines converging on `center`, kept out of an inner ellipse."""
    rnd = random.Random(seed)
    m = Image.new("L", im.size, 0)
    d = ImageDraw.Draw(m)
    cx, cy = center
    R = 1600
    for i in range(n):
        a = (i / n) * 2 * math.pi + rnd.uniform(-0.01, 0.01)
        w = rnd.uniform(0.002, 0.009)
        r0 = rnd.uniform(0.95, 1.4)
        ex = inner[0] * r0 * math.cos(a)
        ey = inner[1] * r0 * math.sin(a)
        p0 = (cx + ex, cy + ey)
        p1 = (cx + R * math.cos(a - w), cy + R * math.sin(a - w))
        p2 = (cx + R * math.cos(a + w), cy + R * math.sin(a + w))
        d.polygon([p0, p1, p2], fill=255)
    clip = Image.new("L", im.size, 0)
    ImageDraw.Draw(clip).rectangle(box, fill=255)
    ink(im, ImageChops.multiply(m, clip), color)


def block(d, box, fill=None, outline=INK, width=2):
    d.rectangle(box, fill=fill, outline=outline, width=width)


def para(d, x, y, text, f, width, fill=INK, lh=None):
    lh = lh or f.size * 1.35
    lines = wrap(text, f, width, d)
    for i, l in enumerate(lines):
        d.text((x, y + i * lh), l, font=f, fill=fill)
    return y + len(lines) * lh


def seal(im, center, text, r=40, color=RED, angle=-10):
    S = r * 2 + 16
    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse((8, 8, S - 8, S - 8), outline=color, width=4)
    f = font("mincho", int(r * 0.7))
    vtext(d, S / 2, S / 2 - r * 0.72 * len(text) / 2, text, f, color, step=r * 0.72)
    a = np.array(layer.split()[3]).astype(np.float32)
    a[np.random.rand(*a.shape) < 0.15] *= 0.3
    layer.putalpha(Image.fromarray(a.astype(np.uint8)))
    layer = layer.rotate(angle, resample=Image.BICUBIC)
    im.paste(layer, (int(center[0] - S / 2), int(center[1] - S / 2)), layer)


def hanamaru(d, cx, cy, r=34, color=RED):
    """The red flower-circle teachers draw on good work."""
    pts = []
    for i in range(260):
        t = i / 260 * 2 * math.pi * 1.15
        rr = r * (1 + 0.04 * i / 260)
        pts.append((cx + rr * math.cos(t), cy + rr * 0.86 * math.sin(t)))
    d.line(pts, fill=color, width=4)
    for k in range(7):
        a = k / 7 * 2 * math.pi
        px, py = cx + (r + 14) * math.cos(a), cy + (r + 12) * 0.9 * math.sin(a)
        d.arc((px - 12, py - 12, px + 12, py + 12), math.degrees(a) - 100, math.degrees(a) + 100, fill=color, width=4)


# ── hero: tabloid front page ───────────────────────────────────────────────
def hero():
    W, H = 1280, 800
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)

    # focus lines behind everything in the main area
    speed_lines(im, (760, 640), (262, 118, W - 20, H - 20), n=170, inner=(430, 70))
    d = ImageDraw.Draw(im)

    # masthead
    d.rectangle((20, 20, W - 20, 104), fill=RED)
    d.text((44, 62), "やとスポ", font=font("dela", 60), fill=PAPER, anchor="lm")
    d.text((330, 36), "YATO SPORTS", font=font("anton", 34), fill=PAPER)
    d.text((332, 76), "夕刊  EVENING EDITION  第21号", font=font("gothic", 18), fill=PAPER)
    d.rectangle((W - 300, 32, W - 34, 92), fill=PAPER)
    d.text((W - 167, 48), "2026年11月26日(木)", font=font("gothic", 18), fill=INK, anchor="mm")
    d.text((W - 167, 76), "定価 140円", font=font("gothic", 18), fill=INK, anchor="mm")
    d.line((20, 112, W - 20, 112), fill=INK, width=3)

    # yellow vertical headline
    d.rectangle((20, 124, 250, H - 20), fill=YELLOW, outline=INK, width=3)
    vtext(d, 135, 140, "2pxのズレも許さん！！", font("dela", 50), INK, step=53)

    # red headline block
    d.rectangle((272, 124, 800, 290), fill=RED, outline=INK, width=3)
    d.text((292, 168), "フルスタック番長、", font=font("dela", 50), fill=PAPER, anchor="lm")
    d.text((292, 240), "渋谷に現る！！", font=font("dela", 64), fill=YELLOW, anchor="lm")

    # article
    d.rectangle((272, 302, 800, 556), fill=PAPER, outline=INK, width=2)
    body = ("TOKYO — Sarthak Saklani arrived from India on a MEXT scholarship after studying "
            "Japanese literature at JNU. He turned down IIM to come here, which his relatives are "
            "still processing. He builds tools for developers and for people moving to Japan. "
            "Asked for comment, he said the button on this page is two pixels off.")
    f = font("mincho-b", 16)
    words = body.split()
    # two columns
    col_w, x_a, x_b, y0 = 236, 288, 548, 316
    lines = wrap(body, f, col_w, d)
    half = (len(lines) + 1) // 2
    for i, l in enumerate(lines):
        x = x_a if i < half else x_b
        y = y0 + (i if i < half else i - half) * 22
        d.text((x, y), l, font=f, fill=INK)
    d.line((536, 314, 536, 462), fill=INK, width=1)

    # fortune column
    d.rectangle((284, 474, 788, 546), fill=YELLOW, outline=INK, width=2)
    d.rectangle((284, 474, 400, 546), fill=INK)
    d.text((342, 496), "今日の運勢", font=font("gothic", 18), fill=YELLOW, anchor="mm")
    d.text((342, 526), "FORTUNE", font=font("anton", 18), fill=PAPER, anchor="mm")
    d.text((414, 492), "大吉!", font=font("dela", 24), fill=RED, anchor="lm")
    d.text((486, 492), "Your build passes on the first try.", font=font("mincho-b", 16), fill=INK, anchor="lm")
    d.text((414, 526), "Lucky item: a semicolon. Avoid: Fridays.", font=font("mincho-b", 16), fill=INK, anchor="lm")

    # photo
    a = crop("tiger", (0.0, 0.12, 1.0, 0.62), (420, 420), invert=False, gamma=1.25, contrast=1.7)
    d.rectangle((818, 124, 1260, 566), fill=PAPER)
    ink(im, halftone(a, cell=5.5, angle=24), INK, (829, 134))
    d.rectangle((818, 124, 1260, 566), outline=INK, width=3)
    d.rectangle((818, 528, 1260, 566), fill=INK)
    d.text((834, 547), "写真はイメージです。本人ではありません。", font=font("gothic", 16), fill=PAPER, anchor="lm")
    stroked(im, (850, 190), "ドン！！", font("dela", 76), INK, PAPER, 6, angle=12)
    d = ImageDraw.Draw(im)
    # the tiger disagrees with its caption
    d.ellipse((1046, 330, 1250, 430), fill=PAPER, outline=INK, width=3)
    d.polygon([(1080, 412), (1040, 470), (1110, 424)], fill=PAPER)
    d.line([(1084, 414), (1040, 470), (1106, 425)], fill=INK, width=3)
    d.text((1148, 368), "…本人です。", font=font("gothic", 24), fill=INK, anchor="mm")
    d.text((1148, 402), "(it's me.)", font=font("mincho-b", 16), fill=ASH, anchor="mm")
    # extra-edition starburst
    burst(im, (800, 112), 62, "号外", "EXTRA!")

    # name band
    d = ImageDraw.Draw(im)
    name = "SARTHAK SAKLANI"
    nf = font("anton", 118)
    tw = d.textlength(name, font=nf)
    d.rectangle((272, 580, 284 + tw + 24, 718), fill=PAPER)
    misprint(im, text_mask(im.size, (290, 712), name, nf, anchor="ls"), INK, RED, off=(6, 5), worn=.06)
    d = ImageDraw.Draw(im)
    deck = "Full-stack engineer lands in Shibuya. Will not tolerate a 2px misalignment."
    df = font("mincho-b", 22)
    dw = d.textlength(deck, font=df)
    d.rectangle((272, 726, 300 + dw, 766), fill=YELLOW)
    d.text((288, 746), deck, font=df, fill=INK, anchor="lm")

    save(grime(im, creases=True), "hero.png")


# ── section heads ─────────────────────────────────────────────────────────
def yoroshiku():
    W, H = 1280, 230
    im = Image.new("RGB", (W, H), PAPER)
    m = text_mask((W, H), (36, 188), "夜露死苦", font("boku", 150), anchor="ls")
    misprint(im, m, INK, RED, off=(7, 5), worn=.08)
    d = ImageDraw.Draw(im)
    stroked(im, (680, 34), "YOROSHIKU!!", font("anton", 76), RED, INK, 4)
    d = ImageDraw.Draw(im)
    d.text((684, 136), "nice to meet you, written the scary way.", font=font("mincho-b", 24), fill=INK)
    d.line((684, 172, W - 40, 172), fill=INK, width=3)
    d.line((684, 180, W - 40, 180), fill=INK, width=1)
    save(grime(im, creases=False), "h-yoroshiku.png")


def section(slug, jp, en, note):
    W, H = 1280, 120
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    d.rectangle((20, 18, W - 20, 102), fill=INK)
    d.rectangle((20, 18, 60, 102), fill=RED)
    d.text((84, 60), jp, font=font("dela", 46), fill=PAPER, anchor="lm")
    jw = d.textlength(jp, font=font("dela", 46))
    d.text((110 + jw, 60), en, font=font("anton", 40), fill=YELLOW, anchor="lm")
    d.text((W - 44, 60), note, font=font("mincho-b", 18), fill=PAPER, anchor="rm")
    save(grime(im, creases=False), f"h-{slug}.png")


# ── nobori flag (floats beside the bio) ───────────────────────────────────
def nobori():
    W, H = 300, 940
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    d.rectangle((30, 20, 42, H - 20), fill=(90, 80, 66))
    d.rectangle((42, 40, 270, 64), fill=(90, 80, 66))
    flag = (54, 70, 264, 860)
    d.rectangle(flag, fill=RED, outline=INK, width=3)
    d.rectangle((54, 70, 264, 140), fill=INK)
    d.text((159, 106), "かかってこい", font=font("dela", 26), fill=YELLOW, anchor="mm")
    vtext(d, 159, 160, "バグ上等", font("boku", 150), PAPER, step=158)
    for y in range(150, 850, 70):
        d.ellipse((46, y, 62, y + 16), fill=PAPER, outline=INK, width=2)
    d.text((159, 896), "BRING ON THE BUGS", font=font("anton", 30), fill=INK, anchor="mm")
    save(grime(im, creases=False), "nobori.png")


# ── report card ───────────────────────────────────────────────────────────
GRADES = [
    ("国語", "Japanese", "4", "Reads Sōseki in the original. Still gets lost in Shinjuku station."),
    ("数学", "Data science", "4", "IIT Madras. Writes pandas and keigo in the same afternoon."),
    ("美術", "Frontend", "5", "Fixes classmates' CSS without being asked. Please stop."),
    ("技術", "Backend", "4", "Node, Express, Fastify, Postgres. Reliable. Quiet about it."),
    ("理科", "AI agents", "5", "Building Antideploy. Will tell you about it."),
    ("体育", "P.E.", "2", "Took up skateboarding. Pavement 1, Saklani 0."),
]


def report():
    W, H = 1280, 1010
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    d.rectangle((24, 20, W - 24, H - 20), fill=(246, 241, 229), outline=INK, width=4)
    d.rectangle((34, 30, W - 34, H - 30), outline=INK, width=1)

    d.text((60, 52), "通 知 表", font=font("mincho", 58), fill=INK)
    d.text((364, 66), "REPORT CARD", font=font("anton", 34), fill=RED)
    d.text((364, 106), "令和8年度  2026 school year", font=font("mincho-b", 18), fill=ASH)
    d.text((W - 60, 66), "氏名  サクラニ・サルタク", font=font("mincho-b", 24), fill=INK, anchor="ra")
    d.text((W - 60, 104), "Sarthak Saklani  (a.k.a. Yato)", font=font("mincho-b", 20), fill=ASH, anchor="ra")
    d.line((60, 146, W - 60, 146), fill=INK, width=3)

    # grades
    x0, x1, y0, rh = 60, 790, 166, 96
    d.rectangle((x0, y0, x1, y0 + 44 + rh * len(GRADES)), outline=INK, width=2)
    d.rectangle((x0, y0, x1, y0 + 44), fill=INK)
    for x, t in ((x0 + 90, "教科  subject"), (x0 + 272, "評定"), (x0 + 520, "所見  teacher's comment")):
        d.text((x, y0 + 22), t, font=font("mincho-b", 18), fill=PAPER, anchor="mm")
    for x in (x0 + 200, x0 + 340):
        d.line((x, y0, x, y0 + 44 + rh * len(GRADES)), fill=INK, width=1)
    hand = font("hand", 20)
    for i, (jp, en, g, c) in enumerate(GRADES):
        y = y0 + 44 + i * rh
        if i:
            d.line((x0, y, x1, y), fill=INK, width=1)
        d.text((x0 + 100, y + 36), jp, font=font("mincho", 28), fill=INK, anchor="mm")
        d.text((x0 + 100, y + 70), en, font=font("mincho-b", 16), fill=ASH, anchor="mm")
        d.text((x0 + 270, y + rh / 2), g, font=font("dela", 48), fill=INK, anchor="mm")
        if g == "5":
            hanamaru(d, x0 + 270, y + rh / 2, r=30)
        for j, l in enumerate(wrap(c, hand, 350, d)):
            d.text((x0 + 362, y + 24 + j * 30), l, font=hand, fill=PEN)

    # right column
    rx0, rx1 = 820, W - 60

    def panel(y, h, jp, en, lines, color=PEN):
        d.rectangle((rx0, y, rx1, y + h), outline=INK, width=2)
        d.rectangle((rx0, y, rx1, y + 38), fill=INK)
        d.text((rx0 + 14, y + 19), jp, font=font("mincho-b", 18), fill=PAPER, anchor="lm")
        d.text((rx1 - 14, y + 19), en, font=font("anton", 18), fill=YELLOW, anchor="rm")
        yy = y + 52
        for text, hi in lines:
            ls = wrap(text, hand, rx1 - rx0 - 32, d)
            if hi:
                w = max(d.textlength(l, font=hand) for l in ls)
                d.rectangle((rx0 + 12, yy - 2, rx0 + 22 + w, yy + 26 * len(ls)), fill=YELLOW)
            for l in ls:
                d.text((rx0 + 16, yy), l, font=hand, fill=color)
                yy += 28
            yy += 6
        return y + h + 16

    y = panel(166, 276, "進路", "PATH", [
        ("JNU, BA Japanese Language & Literature. 卒業 2026", False),
        ("IIT Madras, BSc Data Science. 2027", False),
        ("Bunka Institute of Language, Tokyo. 2027", False),
        ("IIM: 合格 → 辞退 (got in, said no)", True),
    ])
    y = panel(y, 214, "職場体験", "WORK EXPERIENCE", [
        ("Tryp.com, Frontend Developer. Aug 2025 – Jul 2026. Travel marketplace, ~400K users a month.", False),
        ("Digital Palmy, Full-Stack Intern. Feb – Jul 2025.", False),
    ])
    y = panel(y, H - 46 - y, "担任より", "FROM THE TEACHER", [
        ("Turned down IIM to come to Japan. Works hard, talks fast, ships things. Please hire him so his relatives can relax.", False),
    ], color=RED)
    seal(im, (rx1 - 60, H - 110), "担任", r=40)
    save(grime(im, creases=True), "report.png")


# ── tabloid clippings (projects) ──────────────────────────────────────────
CLIPS = [
    dict(slug="antideploy", tag="速報", tag_en="BREAKING", tagc="red", src="fuji", box=(0.35, 0.0, 0.95, 0.75),
         jp="AIエージェント、自力でデプロイ！？", title="ANTIDEPLOY",
         desc="A deploy platform built for coding agents. The agents write the code; somebody still has to ship it.",
         meta="antideploy.com  /  in progress"),
    dict(slug="konbini", tag="独占", tag_en="EXCLUSIVE", tagc="yellow", src="ghost", box=(0.52, 0.0, 0.98, 1.0),
         jp="人生、コンビニで全部そろう！！", title="CAREER KONBINI",
         desc="Jobs, scholarships and Japanese-format paperwork for life in Japan, all on one shelf.",
         meta="TypeScript"),
    dict(slug="matchi", tag="衝撃", tag_en="SHOCK", tagc="red", src="wave", box=(0.0, 0.05, 0.62, 0.95),
         jp="東京937の街、全部ランキング！！", title="MATCHI",
         desc="Ranks 937 Tokyo neighborhoods by your commute, budget and lifestyle.",
         meta="TypeScript  /  Next.js  /  Fastify  /  PostGIS"),
    dict(slug="yomimori", tag="話題", tag_en="TRENDING", tagc="yellow", src="skeleton", box=(0.0, 0.05, 0.34, 0.95),
         jp="AIが書いた物語で日本語を読む！？", title="YOMIMORI",
         desc="AI-written Japanese stories at your JLPT level, with furigana and a built-in dictionary.",
         meta="React  /  Express  /  MongoDB  /  Gemini"),
]


def clip(c, i):
    W, H = 1280, 352
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    d.rectangle((20, 14, W - 20, H - 14), outline=INK, width=3)
    pw = 420
    a = crop(c["src"], c["box"], (pw, H - 52), invert=False, gamma=1.2, contrast=1.7)
    ink(im, halftone(a, cell=5, angle=30 + i * 15), INK, (34, 26))
    d.rectangle((34, 26, 34 + pw, H - 26), outline=INK, width=2)

    x = 486
    bg, fg = (RED, PAPER) if c["tagc"] == "red" else (YELLOW, INK)
    tf = font("dela", 30)
    tw = d.textlength(c["tag"], font=tf)
    d.rectangle((x, 34, x + tw + 128, 80), fill=bg, outline=INK, width=2)
    d.text((x + 14, 57), c["tag"], font=tf, fill=fg, anchor="lm")
    d.text((x + tw + 28, 57), c["tag_en"], font=font("anton", 24), fill=fg, anchor="lm")
    d.text((x, 124), c["jp"], font=font("dela", 38), fill=INK, anchor="lm")
    misprint(im, text_mask(im.size, (x - 2, 222), c["title"], font("anton", 76), anchor="ls"), INK, RED, off=(5, 4), worn=.05)
    d = ImageDraw.Draw(im)
    para(d, x, 236, c["desc"], font("mincho-b", 20), 740, lh=28)
    d.text((x, 314), c["meta"], font=font("anton", 18), fill=ASH, anchor="lm")
    save(grime(im, creases=False), f"clip-{c['slug']}.png")


def burst(im, center, r, jp, en=None, fill=None, spikes=18, angle=-8):
    fill = fill or YELLOW
    d = ImageDraw.Draw(im)
    cx, cy = center
    pts = []
    for i in range(spikes * 2):
        a = math.radians(angle) + i * math.pi / spikes
        rr = r if i % 2 == 0 else r * 0.74
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=fill, outline=INK, width=3)
    if jp:
        d.text((cx, cy - (r * 0.12 if en else 0)), jp, font=font("dela", int(r * 0.42)), fill=INK, anchor="mm")
    if en:
        d.text((cx, cy + r * 0.3), en, font=font("anton", int(r * 0.24)), fill=RED, anchor="mm")


SKIN = (242, 214, 184)
SUIT = (112, 112, 122)
HAIR = (236, 186, 70)
TIE = (232, 120, 170)


def guy(im, cx, cy, s=1.0, mouth="smile", sweat=False, blown=False, laptop=True):
    """The sunglasses guy: blond spikes, grey suit, pink tie."""
    d = ImageDraw.Draw(im)
    S = lambda v: v * s
    d.polygon([(cx - S(34), cy + S(42)), (cx + S(34), cy + S(42)), (cx + S(56), cy + S(140)), (cx - S(56), cy + S(140))],
              fill=SUIT, outline=INK, width=3)
    d.polygon([(cx - S(13), cy + S(42)), (cx + S(13), cy + S(42)), (cx, cy + S(72))], fill=(250, 250, 250), outline=INK)
    d.polygon([(cx - S(5), cy + S(50)), (cx + S(5), cy + S(50)), (cx + S(8), cy + S(96)), (cx, cy + S(106)), (cx - S(8), cy + S(96))],
              fill=TIE, outline=INK, width=2)
    # hair behind head
    pts = []
    n = 13
    for i in range(n + 1):
        a = math.radians(190 + i * 160 / n)
        if blown:
            rr = S(78) if i % 2 else S(44)
            a -= math.radians(10)
        else:
            rr = S(60) if i % 2 else S(40)
        pts.append((cx + rr * math.cos(a), cy - S(4) + rr * math.sin(a)))
    pts += [(cx + S(40), cy + S(6)), (cx - S(40), cy + S(6))]
    d.polygon(pts, fill=HAIR, outline=INK, width=3)
    d.ellipse((cx - S(38), cy - S(36), cx + S(38), cy + S(42)), fill=SKIN, outline=INK, width=3)
    # fringe
    d.polygon([(cx - S(38), cy - S(6)), (cx - S(30), cy - S(34)), (cx + S(10), cy - S(40)), (cx + S(38), cy - S(12)),
               (cx + S(20), cy - S(20)), (cx + S(6), cy - S(8)), (cx - S(8), cy - S(22)), (cx - S(22), cy - S(8))],
              fill=HAIR, outline=INK, width=2)
    # sunglasses
    for sx in (-1, 1):
        d.ellipse((cx + sx * S(17) - S(15), cy - S(2) - S(9), cx + sx * S(17) + S(15), cy - S(2) + S(9)), fill=INK)
    d.line((cx - S(4), cy - S(5), cx + S(4), cy - S(5)), fill=INK, width=max(2, int(S(3))))
    d.ellipse((cx - S(26), cy - S(8), cx - S(20), cy - S(4)), fill=(150, 150, 160))
    my = cy + S(22)
    if mouth == "smile":
        d.arc((cx - S(14), my - S(10), cx + S(14), my + S(6)), 20, 160, fill=INK, width=max(2, int(S(3))))
    elif mouth == "flat":
        d.line((cx - S(10), my, cx + S(10), my), fill=INK, width=max(2, int(S(3))))
    elif mouth == "open":
        d.ellipse((cx - S(12), my - S(8), cx + S(12), my + S(12)), fill=(120, 30, 40), outline=INK, width=2)
    elif mouth == "o":
        d.ellipse((cx - S(5), my - S(4), cx + S(5), my + S(6)), fill=INK)
    if sweat:
        for ox, oy in ((S(46), -S(26)), (S(54), S(2))):
            x, y = cx + ox, cy + oy
            d.polygon([(x, y - S(12)), (x + S(7), y + S(2)), (x - S(7), y + S(2))], fill=(150, 200, 240), outline=INK)
            d.ellipse((x - S(7), y - S(5), x + S(7), y + S(9)), fill=(150, 200, 240), outline=INK)
    if laptop:
        d.rectangle((cx - S(62), cy + S(84), cx + S(62), cy + S(150)), fill=(190, 192, 200), outline=INK, width=3)
        d.ellipse((cx - S(10), cy + S(108), cx + S(10), cy + S(128)), fill=PAPER, outline=INK, width=2)


def bubble(im, box, lines, tail=None, f=None):
    d = ImageDraw.Draw(im)
    f = f or font("gothic", 20)
    d.rounded_rectangle(box, radius=22, fill=(255, 255, 255), outline=INK, width=3)
    if tail:
        (bx, by), (tx, ty) = tail
        d.polygon([(bx - 12, by), (tx, ty), (bx + 12, by)], fill=(255, 255, 255))
        d.line([(bx - 12, by), (tx, ty), (bx + 12, by)], fill=INK, width=3)
    cx = (box[0] + box[2]) / 2
    h = f.size * 1.3
    y = (box[1] + box[3]) / 2 - h * (len(lines) - 1) / 2
    for i, l in enumerate(lines):
        d.text((cx, y + i * h), l, font=f, fill=INK, anchor="mm")


def yonkoma():
    W, H = 1280, 440
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    d.rectangle((20, 16, W - 20, 64), fill=INK)
    d.text((40, 40), "四コマ漫画「締切」", font=font("dela", 26), fill=PAPER, anchor="lm")
    d.text((330, 40), "4-PANEL COMIC: DEADLINE", font=font("anton", 24), fill=YELLOW, anchor="lm")
    d.text((W - 40, 40), "作・やと  based on a true story", font=font("mincho-b", 16), fill=PAPER, anchor="rm")

    PW, PH = 296, 330
    caps = ["“Deadline's tomorrow.” “Easy.”", "3 a.m.", "Deploy!!", "“…it's 2px off.”"]
    for i in range(4):
        p = Image.new("RGB", (PW, PH), PAPER)
        pd = ImageDraw.Draw(p)
        if i == 0:
            bubble(p, (12, 12, 176, 66), ["締切、明日です。"], tail=((60, 66), (30, 96)), f=font("gothic", 18))
            pd.text((20, 104), "client", font=font("mincho-b", 13), fill=ASH)
            guy(p, 160, 176, 0.82, mouth="smile")
            bubble(p, (172, 82, 286, 132), ["余裕っす。"], tail=((214, 132), (190, 150)), f=font("gothic", 18))
        elif i == 1:
            night = halftone(np.full((PH, PW), 0.62, np.float32), cell=5, angle=45)
            ink(p, night, (40, 44, 70))
            pd.ellipse((222, 18, 266, 62), fill=PAPER)
            pd.ellipse((236, 12, 280, 56), fill=(40, 44, 70))
            guy(p, 148, 168, 0.82, mouth="flat", sweat=True)
            stroked(p, (16, 60), "カタカタ", font("dela", 30), PAPER, INK, 3, angle=8)
            for k, ch in enumerate("\u30b4" * 3):
                stroked(p, (262, 120 + k * 40), ch, font("dela", 32), PAPER, INK, 3, anchor="mm", angle=-8)
        elif i == 2:
            burst(p, (PW / 2, 170), 150, None, fill=YELLOW, spikes=16)
            burst(p, (PW / 2, 170), 100, None, fill=RED, spikes=14, angle=4)
            guy(p, PW / 2, 166, 0.82, mouth="open", blown=True)
            stroked(p, (PW / 2, 42), "デプロイ！！", font("dela", 38), PAPER, INK, 4, anchor="mm", angle=-6)
        else:
            speed_lines(p, (PW / 2, 150), (0, 0, PW, PH), n=90, inner=(120, 120), seed=9)
            guy(p, PW / 2, 170, 1.55, mouth="o", laptop=False)
            bubble(p, (40, 14, 256, 64), ["…2pxズレてる。"], f=font("gothic", 20))
        pd = ImageDraw.Draw(p)
        pd.rectangle((0, PH - 34, PW, PH), fill=PAPER)
        pd.line((0, PH - 34, PW, PH - 34), fill=INK, width=2)
        pd.text((PW / 2, PH - 17), caps[i], font=font("mincho-b", 15), fill=INK, anchor="mm")
        x = 24 + i * (PW + 12)
        im.paste(p, (x, 82))
        d.rectangle((x, 82, x + PW, 82 + PH), outline=INK, width=4)
    save(grime(im, creases=False), "yonkoma.png")


# ── classifieds footer ────────────────────────────────────────────────────
def classifieds():
    W, H = 1280, 560
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    d.rectangle((20, 18, W - 20, 86), fill=INK)
    d.text((40, 52), "求人・求職", font=font("dela", 38), fill=PAPER, anchor="lm")
    d.text((272, 52), "CLASSIFIEDS", font=font("anton", 36), fill=YELLOW, anchor="lm")
    d.text((W - 40, 52), "掲載無料  free listing", font=font("mincho-b", 18), fill=PAPER, anchor="rm")

    # main ad
    d.rectangle((20, 102, 780, H - 20), outline=INK, width=4)
    d.rectangle((30, 112, 770, H - 30), outline=INK, width=1)
    stroked(im, (52, 190), "求職中！！", font("dela", 92), RED, INK, 4, anchor="ls")
    d = ImageDraw.Draw(im)
    d.text((54, 214), "FULL-STACK ENGINEER SEEKS", font=font("anton", 44), fill=INK)
    d.text((54, 266), "PRODUCT TEAM IN TOKYO", font=font("anton", 44), fill=INK)
    para(d, 56, 334, "Frontend obsessive, backend capable, building with AI agents. "
                     "Reads Japanese. Brings own keyboard. Will align your buttons for free.",
         font("mincho-b", 22), 680, lh=32)
    d.rectangle((54, 452, 746, 510), fill=YELLOW, outline=INK, width=2)
    d.text((400, 481), "連絡先  X @Sarthak_Sama  /  LinkedIn  /  sarthak.space", font=font("mincho-b", 21), fill=INK, anchor="mm")

    small = [
        ("売ります", "FOR SALE", "One IIM seat. Never used. Original owner moved to Tokyo."),
        ("落とし物", "LOST", "Sense of direction. Shinjuku Station, east exit, probably."),
        ("求む", "WANTED", "A desk, preferably."),
    ]
    y = 102
    hgt = (H - 20 - 102 - 2 * 14) / 3
    for jp, en, body in small:
        d.rectangle((796, y, W - 20, y + hgt), outline=INK, width=2)
        d.text((812, y + 30), jp, font=font("dela", 26), fill=RED, anchor="lm")
        d.text((812 + d.textlength(jp, font=font("dela", 26)) + 12, y + 30), en, font=font("anton", 22), fill=INK, anchor="lm")
        para(d, 812, y + 54, body, font("mincho-b", 19), 430, lh=26)
        y += hgt + 14
    save(grime(im, creases=True), "classifieds.png")


if __name__ == "__main__":
    os.makedirs(ASSETS, exist_ok=True)
    for f in os.listdir(ASSETS):
        if f.endswith(".png"):
            os.remove(os.path.join(ASSETS, f))
    hero()
    yoroshiku()
    section("tech", "テック面", "THE TECH PAGE", "all stories true, headlines exaggerated")
    section("attendance", "出席簿", "ATTENDANCE", "contributions, last 30 days")
    nobori()
    report()
    for i, c in enumerate(CLIPS):
        clip(c, i)
    yonkoma()
    classifieds()
