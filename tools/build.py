"""Builds the PNGs in ../assets for the profile README.

Concept: the Saklani Engineering Consultations office, told through Japanese
office paperwork. Lavender bathroom tile (as in the avatar), a business card
with a hanko, a hand-filled rirekisho, restaurant menu tags for projects,
speech-bubble reviews and an 営業中 shop sign.

Run:  python3 tools/build.py      (needs `pip install pillow numpy`)
Fonts (OFL) are downloaded into tools/.cache on first run.
Everything is drawn at 2x and downsampled for clean edges.
"""

import math
import os
import random
import urllib.request

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
CACHE = os.path.join(ROOT, "tools", ".cache")
K = 2  # supersampling factor

FONTS = {
    "gothic-black": "ofl/zenkakugothicnew/ZenKakuGothicNew-Black.ttf",
    "gothic-bold": "ofl/zenkakugothicnew/ZenKakuGothicNew-Bold.ttf",
    "gothic": "ofl/zenkakugothicnew/ZenKakuGothicNew-Medium.ttf",
    "mincho": "ofl/zenoldmincho/ZenOldMincho-Bold.ttf",
    "hand": "ofl/kleeone/KleeOne-SemiBold.ttf",
    "brush": "ofl/yujisyuku/YujiSyuku-Regular.ttf",
}

TILE = (217, 206, 213)
GROUT = (194, 181, 190)
INK = (28, 26, 31)
GREY = (104, 99, 110)
PAPER = (251, 248, 241)
HANKO = (211, 58, 44)
PINK = (230, 49, 125)
HILITE = (255, 120, 180)
PEN = (36, 48, 94)
WOOD = (226, 196, 154)
WOOD_DK = (190, 156, 112)

random.seed(4)
np.random.seed(4)
_font_cache = {}


def font(key, size):
    k = (key, size)
    if k not in _font_cache:
        path = os.path.join(CACHE, os.path.basename(FONTS[key]))
        if not os.path.exists(path):
            os.makedirs(CACHE, exist_ok=True)
            url = "https://github.com/google/fonts/raw/main/" + FONTS[key]
            print("downloading", url)
            req = urllib.request.Request(url, headers={"User-Agent": "readme-builder/1.0"})
            with urllib.request.urlopen(req) as r, open(path, "wb") as f:
                f.write(r.read())
        _font_cache[k] = ImageFont.truetype(path, int(size * K))
    return _font_cache[k]


# ── drawing at 1x coordinates on a 2x canvas ───────────────────────────────
class Pen:
    def __init__(self, im):
        self.im = im
        self.d = ImageDraw.Draw(im)

    def s(self, v):
        if isinstance(v, (tuple, list)):
            return [self.s(x) for x in v] if v and isinstance(v[0], (tuple, list)) else tuple(x * K for x in v)
        return v * K

    def rect(self, box, fill=None, outline=None, width=1, r=0):
        if r:
            self.d.rounded_rectangle(self.s(box), radius=r * K, fill=fill, outline=outline, width=int(width * K))
        else:
            self.d.rectangle(self.s(box), fill=fill, outline=outline, width=int(width * K))

    def line(self, pts, fill=INK, width=1):
        self.d.line(self.s(pts), fill=fill, width=int(width * K), joint="curve")

    def ellipse(self, box, fill=None, outline=None, width=1):
        self.d.ellipse(self.s(box), fill=fill, outline=outline, width=int(width * K))

    def poly(self, pts, fill=None):
        self.d.polygon(self.s(pts), fill=fill)

    def text(self, xy, s, f, fill=INK, anchor="la", spacing=0):
        if spacing:
            x, y = xy
            total = sum(self.d.textlength(c, font=f) / K + spacing for c in s) - spacing
            if anchor[0] == "m":
                x -= total / 2
            elif anchor[0] == "r":
                x -= total
            for c in s:
                self.d.text((x * K, y * K), c, font=f, fill=fill, anchor="l" + anchor[1])
                x += self.d.textlength(c, font=f) / K + spacing
            return
        self.d.text(self.s(xy), s, font=f, fill=fill, anchor=anchor)

    def width(self, s, f):
        return self.d.textlength(s, font=f) / K

    def vertical(self, x, y, s, f, fill=INK, step=None):
        step = step or f.size / K * 1.05
        for i, ch in enumerate(s):
            cy = y + i * step + step / 2
            if ch in "、。":
                self.text((x + f.size / K * 0.3, cy - f.size / K * 0.3), ch, f, fill, "mm")
            elif ch in "ー〜":
                g = Image.new("RGBA", (f.size * 2, f.size * 2), (0, 0, 0, 0))
                ImageDraw.Draw(g).text((f.size, f.size), ch, font=f, fill=fill, anchor="mm")
                g = g.rotate(-90)
                self.im.paste(g, (int(x * K - f.size), int(cy * K - f.size)), g)
            else:
                self.text((x, cy), ch, f, fill, "mm")
        return y + len(s) * step

    def wrap(self, s, f, w):
        out = []
        for para in s.split("\n"):
            line = ""
            for word in para.split(" "):
                t = f"{line} {word}".strip()
                if self.width(t, f) > w and line:
                    out.append(line)
                    line = word
                else:
                    line = t
            out.append(line)
        return out


def canvas(w, h, bg=TILE):
    return Image.new("RGB", (w * K, h * K), bg)


def tiles(im, size=84, offset=(0, 0)):
    p = Pen(im)
    w, h = im.size[0] // K, im.size[1] // K
    ox, oy = offset
    xs = range(-size + ox % size, w + size, size)
    ys = range(-size + oy % size, h + size, size)
    hl = Image.new("L", im.size, 0)
    hd = ImageDraw.Draw(hl)
    for x in xs:
        for y in ys:
            hd.line(((x + 10) * K, (y + 9) * K, (x + size - 24) * K, (y + 9) * K), fill=70, width=3 * K)
    im.paste(Image.new("RGB", im.size, (240, 233, 238)), (0, 0), hl)
    for x in xs:
        p.line(((x, 0), (x, h)), GROUT, 3)
    for y in ys:
        p.line(((0, y), (w, y)), GROUT, 3)


def shadow(im, box_or_mask, offset=(10, 14), blur=14, alpha=90, r=0):
    if isinstance(box_or_mask, Image.Image):
        m = box_or_mask
    else:
        m = Image.new("L", im.size, 0)
        ImageDraw.Draw(m).rounded_rectangle([v * K for v in box_or_mask], radius=r * K, fill=255)
    m = m.transform(m.size, Image.AFFINE, (1, 0, -offset[0] * K, 0, 1, -offset[1] * K))
    m = m.filter(ImageFilter.GaussianBlur(blur * K)).point(lambda v: v * alpha // 255)
    im.paste(Image.new("RGB", im.size, (60, 44, 58)), (0, 0), m)


def paste_rotated(im, layer, center, angle, cast=True):
    """layer is RGBA at 2x; pasted with its centre at `center` (1x) after rotation."""
    rot = layer.rotate(angle, resample=Image.BICUBIC, expand=True)
    x = int(center[0] * K - rot.width / 2)
    y = int(center[1] * K - rot.height / 2)
    if cast:
        m = Image.new("L", im.size, 0)
        m.paste(rot.split()[3], (x, y))
        shadow(im, m, offset=(8, 12), blur=12, alpha=110)
    im.paste(rot, (x, y), rot)


def hanko(text, r=46, angle=-8, color=HANKO):
    """A worn round seal with vertical text."""
    S = int((r * 2 + 20) * K)
    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    p = Pen(layer)
    c = S / K / 2
    p.ellipse((c - r, c - r, c + r, c + r), outline=color, width=5)
    f = font("mincho", r * 0.78)
    step = r * 0.82
    p.vertical(c, c - step * len(text) / 2, text, f, color, step=step)
    a = np.array(layer.split()[3]).astype(np.float32)
    a[np.random.rand(*a.shape) < 0.16] *= 0.25
    layer.putalpha(Image.fromarray(a.astype(np.uint8)))
    return layer.rotate(angle, resample=Image.BICUBIC)


def sunglasses(p, cx, cy, s=1.0, color=INK):
    w, h = 34 * s, 20 * s
    p.ellipse((cx - w - 4 * s, cy - h / 2, cx - 4 * s, cy + h / 2), fill=color)
    p.ellipse((cx + 4 * s, cy - h / 2, cx + w + 4 * s, cy + h / 2), fill=color)
    p.line(((cx - 6 * s, cy - 3 * s), (cx + 6 * s, cy - 3 * s)), color, 3 * s)
    p.line(((cx - w - 2 * s, cy - 4 * s), (cx - w - 16 * s, cy - 8 * s)), color, 3 * s)
    p.line(((cx + w + 2 * s, cy - 4 * s), (cx + w + 16 * s, cy - 8 * s)), color, 3 * s)
    p.ellipse((cx - w + 4 * s, cy - h / 2 + 4 * s, cx - w + 12 * s, cy - h / 2 + 9 * s), fill=(120, 116, 128))
    p.ellipse((cx + 12 * s, cy - h / 2 + 4 * s, cx + 20 * s, cy - h / 2 + 9 * s), fill=(120, 116, 128))


def highlight(im, x, y, w, h=22):
    hl = Image.new("RGBA", (int(w * K), int(h * K)), HILITE + (115,))
    im.paste(hl, (int(x * K), int(y * K)), hl)


def save(im, name):
    out = im.resize((im.width // K, im.height // K), Image.LANCZOS)
    path = os.path.join(ASSETS, name)
    out.save(path, optimize=True)
    print(f"{name:22s} {os.path.getsize(path)/1024:7.1f} KB")


# ── hero: the business card ────────────────────────────────────────────────
def hero():
    W, H = 1280, 640
    im = canvas(W, H)
    tiles(im, offset=(30, 10))

    p = Pen(im)
    p.ellipse((1040, 470, 1180, 610), outline=(176, 140, 120), width=7)
    p.ellipse((1046, 478, 1176, 604), outline=(196, 166, 150), width=2)

    CW, CH = 780, 450
    card = Image.new("RGBA", (CW * K, CH * K), PAPER + (255,))
    c = Pen(card)
    c.text((48, 46), "サクラニ技術相談所", font("mincho", 24))
    c.text((48, 82), "SAKLANI ENGINEERING CONSULTATIONS", font("gothic-bold", 13), GREY, spacing=2.4)
    sunglasses(c, 690, 66, 0.9)
    c.line(((48, 114), (CW - 48, 114)), INK, 1.5)

    c.text((52, 166), "サルタク・サクラニ", font("gothic", 18), GREY, spacing=3)
    c.text((46, 248), "Sarthak Saklani", font("gothic-black", 70), INK, "ls")
    c.text((50, 294), "Full-Stack Engineer", font("gothic-bold", 26), INK)
    c.text((50, 330), "Certified button aligner (self-certified)", font("gothic", 18), GREY)

    rows = (("Web", "sarthak.space"), ("X", "@Sarthak_Sama"), ("Office", "Tokyo (location varies)"))
    for i, (k, v) in enumerate(rows):
        y = 378 + i * 24
        c.text((50, y), k, font("gothic-bold", 15), GREY)
        c.text((122, y), v, font("gothic", 15), INK)
    stamp = hanko("やと", r=50, angle=-12)
    card.paste(stamp, (int(600 * K), int(250 * K)), stamp)

    paste_rotated(im, card, (590, 336), 2.2)

    NW, NH = 250, 220
    note = Image.new("RGBA", (NW * K, NH * K), (249, 198, 218, 255))
    n = Pen(note)
    n.rect((0, 0, NW, 26), fill=(240, 176, 202))
    for i, l in enumerate(["memo:", "hobby no.100 is", "skateboarding.", "it is going about", "as well as you'd", "think."]):
        n.text((20, 44 + i * 27), l, font("hand", 21), PEN)
    paste_rotated(im, note, (1070, 160), -7)
    tape = Image.new("RGBA", (110 * K, 34 * K), (255, 255, 255, 130)).rotate(-14, expand=True, resample=Image.BICUBIC)
    im.paste(tape, (int(1010 * K), int(36 * K)), tape)
    save(im, "hero.png")


# ── rirekisho ─────────────────────────────────────────────────────────────
def rirekisho():
    W, H = 1280, 920
    im = canvas(W, H)
    tiles(im, offset=(50, 40))
    shadow(im, (40, 40, 1240, 880), offset=(10, 14), blur=14, alpha=110)
    p = Pen(im)
    p.rect((40, 40, 1240, 880), fill=PAPER)
    p.line(((640, 40), (640, 880)), (220, 214, 204), 2)

    L = font("mincho", 15)
    hand = font("hand", 21)
    hand_s = font("hand", 18)
    line_c = (70, 64, 74)

    x0, x1 = 72, 612
    p.text((x0, 62), "履 歴 書", font("mincho", 40))
    p.text((x0 + 200, 84), "rirekisho, the Japanese résumé", font("gothic", 14), GREY)
    p.text((470, 120), "2026年 11月 26日現在", font("mincho", 14), INK, "ra")

    p.rect((x0, 146, 470, 330), outline=line_c, width=2)
    for y in (180, 260, 296):
        p.line(((x0, y), (470, y)), line_c, 1)
    p.text((x0 + 10, 156), "ふりがな", L)
    p.text((x0 + 100, 152), "さるたく　さくらに", hand, PEN)
    p.text((x0 + 10, 192), "氏名", L)
    p.text((x0 + 56, 242), "Sarthak Saklani", font("hand", 34), PEN, "ls")
    p.text((x0 + 10, 270), "通称", L)
    p.text((x0 + 70, 266), "Yato (most of the internet)", hand, PEN)
    p.text((x0 + 10, 306), "現住所", L)
    p.text((x0 + 80, 302), "東京都渋谷区  Shibuya, Tokyo", hand, PEN)
    p.text((452, 190), "印", L, GREY)
    st = hanko("やと", r=24, angle=8)
    im.paste(st, (int(408 * K), int(198 * K)), st)

    p.rect((492, 146, 612, 306), outline=line_c, width=2)
    sunglasses(p, 552, 210, 0.95)
    p.text((552, 258), "photo pending", font("hand", 14), GREY, "mm")
    p.text((552, 278), "(he's busy)", font("hand", 14), GREY, "mm")

    rows = [
        ("", "", "学歴  education", "c"),
        ("2026", "6", "JNU, BA Japanese Language & Literature  卒業", ""),
        ("2027", "4", "Bunka Institute of Language, Tokyo  (予定)", ""),
        ("2027", "9", "IIT Madras, BSc Data Science  (予定)", ""),
        ("", "", "IIM  合格 → 辞退  (got in, said no)", "hi"),
        ("", "", "職歴  work", "c"),
        ("2025", "2", "Digital Palmy, Full-Stack Intern", ""),
        ("2025", "8", "Tryp.com, Frontend Developer", ""),
        ("2026", "7", "Tryp.com  退職 (shipped it, left)", ""),
        ("", "", "以上", "r"),
    ]
    ty, rh = 356, 48
    bottom = ty + 34 + rh * len(rows)
    p.rect((x0, ty, x1, bottom), outline=line_c, width=2)
    p.line(((x0, ty + 34), (x1, ty + 34)), line_c, 1.5)
    p.line(((x0 + 70, ty), (x0 + 70, bottom)), line_c, 1)
    p.line(((x0 + 110, ty), (x0 + 110, bottom)), line_c, 1)
    p.text((x0 + 35, ty + 17), "年", L, INK, "mm")
    p.text((x0 + 90, ty + 17), "月", L, INK, "mm")
    p.text((x0 + 325, ty + 17), "学歴・職歴", L, INK, "mm")
    for i, (y_, m_, t, kind) in enumerate(rows):
        y = ty + 34 + i * rh
        if i:
            p.line(((x0, y), (x1, y)), (190, 184, 192), 1)
        cy = y + rh / 2
        if kind == "hi":
            highlight(im, x0 + 118, cy - 10, p.width(t, hand_s) + 14, 22)
        p.text((x0 + 35, cy), y_, hand_s, PEN, "mm")
        p.text((x0 + 90, cy), m_, hand_s, PEN, "mm")
        if kind == "c":
            p.text((x0 + 325, cy), t, hand_s, PEN, "mm")
        elif kind == "r":
            p.text((x1 - 20, cy), t, hand_s, PEN, "rm")
        else:
            p.text((x0 + 124, cy), t, hand_s, PEN, "lm")

    x0, x1 = 668, 1208

    def box(y, h, label, body, size=20):
        p.rect((x0, y, x1, y + h), outline=line_c, width=2)
        p.line(((x0, y + 32), (x1, y + 32)), line_c, 1)
        p.text((x0 + 12, y + 8), label, L)
        f = font("hand", size)
        for i, ln in enumerate(p.wrap(body, f, x1 - x0 - 32)):
            p.text((x0 + 16, y + 44 + i * (size * 1.5)), ln, f, PEN)
        return y + h + 18

    y = 62
    y = box(y, 196, "免許・資格  licences & qualifications",
            "MEXT scholarship (文部科学省)\nHackvatar Tokyo, 2nd place: an AI that negotiates in polite business Japanese\nCan read Sōseki in the original. Still gets lost in Shinjuku station.", size=19)
    y = box(y, 168, "志望動機  why me",
            "I build tools for developers, and things that make Japan less confusing for people moving here. Frontend is where I lose all sense of proportion, in a good way.")
    y = box(y, 150, "趣味・特技  hobbies & special skills",
            "About a hundred hobbies. Currently skateboarding.\nSpecial skill: noticing a 2px misalignment from across the room.")
    y = box(y, 190, "本人希望記入欄  personal requests",
            "A full-stack role on a product team in Tokyo.\nCoffee. A desk, preferably.")
    save(im, "rirekisho.png")


# ── menu tags (projects) ──────────────────────────────────────────────────
MENU = [
    dict(slug="antideploy", jp="デプロイ", price="時価", name="Antideploy",
         desc="Deploys for coding agents. They write it, someone has to ship it."),
    dict(slug="konbini", jp="人生のコンビニ", price="二十四時間", name="Career Konbini",
         desc="Jobs, scholarships and Japanese paperwork on one shelf."),
    dict(slug="matchi", jp="街えらび", price="九三七種", name="Matchi",
         desc="937 Tokyo neighborhoods, ranked by your commute and budget."),
    dict(slug="yomimori", jp="読み物", price="全級", name="Yomimori",
         desc="AI-written Japanese stories at your JLPT level."),
]


def menu_header():
    W, H = 1280, 150
    im = canvas(W, H)
    tiles(im, offset=(0, 70))
    p = Pen(im)
    shadow(im, (300, 26, 980, 124), offset=(6, 8), blur=8, alpha=100, r=6)
    p.rect((300, 26, 980, 124), fill=INK, r=6)
    p.text((640, 66), "本日のお品書き", font("brush", 48), PAPER, "mm")
    p.text((640, 106), "today's menu. the prices are a joke, the projects are real", font("gothic", 15), (200, 196, 204), "mm")
    save(im, "menu-header.png")


def menu_tag(m, i):
    W, H = 320, 980
    im = canvas(W, H)
    tiles(im, offset=(-i * W, 0))
    p = Pen(im)
    x0, x1, y0, y1 = 50, 270, 70, 760
    p.line(((160, 22), (x0 + 40, y0 + 4)), (110, 100, 92), 2)
    p.line(((160, 22), (x1 - 40, y0 + 4)), (110, 100, 92), 2)
    shadow(im, (x0, y0, x1, y1), offset=(8, 12), blur=10, alpha=110, r=4)
    p.rect((x0, y0, x1, y1), fill=WOOD, r=4)
    rnd = random.Random(i)
    for _ in range(9):
        gx = rnd.uniform(x0 + 14, x1 - 14)
        ph = rnd.random() * 6
        pts = [(gx + math.sin(t / 70 + ph) * 6, t) for t in range(y0 + 6, y1 - 4, 16)]
        p.line(pts, WOOD_DK, 1.5)
    p.rect((x0, y0, x1, y1), outline=(160, 124, 84), width=2, r=4)
    p.ellipse((152, 14, 168, 30), fill=(150, 150, 160), outline=INK, width=1.5)

    f = font("brush", 86 if len(m["jp"]) <= 4 else 56)
    step = f.size / K * 1.02
    pf = font("brush", 40 if len(m["price"]) <= 4 else 28)
    pstep = pf.size / K * 1.02
    price_top = y1 - 30 - pstep * len(m["price"])
    top = y0 + 34 + max(0, (price_top - y0 - 80 - step * len(m["jp"])) / 2)
    p.vertical(160, top, m["jp"], f, INK, step=step)
    p.vertical(160, price_top, m["price"], pf, HANKO, step=pstep)

    p.text((160, 812), m["name"], font("gothic-black", 30), INK, "mm")
    for j, ln in enumerate(p.wrap(m["desc"], font("gothic", 19), 260)):
        p.text((160, 852 + j * 28), ln, font("gothic", 19), INK, "mm")
    save(im, f"menu-{m['slug']}.png")


# ── reviews ───────────────────────────────────────────────────────────────
REVIEWS = [
    ("the best frontend engineer i have seen in the entire tpot (this part of twitter)", "Mohammad Harish", "Founder, Infinite Studio"),
    ("quickly adapted to different tech stacks and delivered features with great attention to detail", "Manu Prabhakar", "Co-founder, Digital Palmy"),
    ("delivered the project within a very tight deadline without compromising on quality", "Alok Singh", "Freelance client"),
]


def reviews():
    W, H = 1280, 580
    im = canvas(W, H)
    tiles(im, offset=(20, 30))
    p = Pen(im)
    p.text((640, 54), "お客様の声", font("brush", 46), INK, "mm")
    p.text((640, 96), "what clients said, word for word", font("gothic", 16), GREY, "mm")
    f = font("gothic-bold", 22)
    for i, (q, who, role) in enumerate(REVIEWS):
        cx = 222 + i * 418
        top = 140 + (i % 2) * 28
        lines = p.wrap(f"“{q}”", f, 300)
        bh = 44 + len(lines) * 34
        box = (cx - 182, top, cx + 182, top + bh)
        tail = [(cx - 44, top + bh - 3), (cx - 76, top + bh + 46), (cx + 6, top + bh - 3)]
        shadow(im, box, offset=(6, 8), blur=6, alpha=90, r=36)
        p.rect(box, fill=(255, 255, 255), outline=INK, width=4, r=36)
        p.poly(tail, fill=(255, 255, 255))
        p.line([tail[0], tail[1], tail[2]], INK, 4)
        p.line(((cx - 40, top + bh - 2), (cx + 2, top + bh - 2)), (255, 255, 255), 6)
        for j, ln in enumerate(lines):
            ly = top + 22 + j * 34 + 17
            if i == 0 and j == 0:
                hw = p.width(ln, f)
                highlight(im, cx - hw / 2, ly - 4, hw, 18)
            p.text((cx, ly), ln, f, INK, "mm")
        ny = top + bh + 72
        p.text((cx - 64, ny), who, font("gothic-black", 21), INK, "lm")
        p.text((cx - 64, ny + 28), role, font("gothic", 16), GREY, "lm")
        p.text((cx - 64, ny + 56), "★★★★★", font("gothic-bold", 18), PINK, "lm")
    save(im, "reviews.png")


# ── footer: shop sign ─────────────────────────────────────────────────────
def footer():
    W, H = 1280, 470
    im = canvas(W, H)
    tiles(im, offset=(60, 0))
    p = Pen(im)
    p.line(((640, 34), (420, 120)), (90, 80, 72), 3)
    p.line(((640, 34), (860, 120)), (90, 80, 72), 3)
    board = (330, 112, 950, 392)
    shadow(im, board, offset=(10, 14), blur=12, alpha=120, r=14)
    p.rect(board, fill=PAPER, outline=INK, width=5, r=14)
    p.rect((350, 132, 930, 372), outline=HANKO, width=2, r=8)
    p.ellipse((630, 24, 650, 44), fill=(160, 160, 168), outline=INK, width=2)
    p.text((640, 210), "営業中", font("brush", 104), HANKO, "mm")
    p.text((640, 298), "OPEN for full-stack roles in Tokyo", font("gothic-black", 30), INK, "mm")
    p.text((640, 340), "walk-ins welcome via X or LinkedIn", font("gothic", 19), GREY, "mm")

    tag = Image.new("RGBA", (200 * K, 70 * K), (255, 255, 255, 255))
    t = Pen(tag)
    t.rect((1, 1, 199, 69), outline=INK, width=2)
    t.text((100, 35), "please knock", font("hand", 24), PEN, "mm")
    paste_rotated(im, tag, (1070, 330), 6)
    save(im, "footer.png")


if __name__ == "__main__":
    os.makedirs(ASSETS, exist_ok=True)
    for f in os.listdir(ASSETS):
        if f.endswith(".png"):
            os.remove(os.path.join(ASSETS, f))
    hero()
    rirekisho()
    menu_header()
    for i, m in enumerate(MENU):
        menu_tag(m, i)
    reviews()
    footer()
