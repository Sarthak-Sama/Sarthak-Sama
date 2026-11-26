"""Builds every SVG in ../assets for the profile README.

Concept: a 2000s Japanese portable MiniDisc player and its discs.
  - hero.svg       the player, with an EL-backlit dot-matrix LCD
  - receipt.svg    a konbini receipt of work and study history
  - inbox.svg      a flip phone whose inbox holds testimonials
  - spec.svg       the foil spec sticker from the underside of the device
  - next.svg       a small LCD strip for the footer
  - btn-*.svg      silver hardware buttons for links

Run:  python3 tools/build.py   (needs `pip install fonttools brotli`)
Fonts (OFL) are downloaded into tools/.fonts on first run and subset into each SVG.
"""

import base64
import html
import io
import os
import re
import urllib.request

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
FONT_DIR = os.path.join(ROOT, "tools", ".fonts")

FONTS = {
    "lcd": ("DotGothic16.ttf", "ofl/dotgothic16/DotGothic16-Regular.ttf"),
    "silk": ("BarlowCondensed-SemiBold.ttf", "ofl/barlowcondensed/BarlowCondensed-SemiBold.ttf"),
    "body": ("Barlow-Medium.ttf", "ofl/barlow/Barlow-Medium.ttf"),
}

# ── palette ────────────────────────────────────────────────────────────────
SILVER_HI = "#F3F5F7"
SILVER = "#D3D8DD"
SILVER_LO = "#A7AEB6"
EDGE = "#5E656D"
INK = "#1D232A"
LCD_GLASS = "#0B2532"
LCD_LIT = "#A6F3FF"
LCD_GHOST = "#15394A"
HOLD = "#FF6A13"


# ── fonts ──────────────────────────────────────────────────────────────────
def font_path(key):
    name, remote = FONTS[key]
    path = os.path.join(FONT_DIR, name)
    if not os.path.exists(path):
        os.makedirs(FONT_DIR, exist_ok=True)
        url = "https://github.com/google/fonts/raw/main/" + remote
        print("downloading", url)
        urllib.request.urlretrieve(url, path)
    return path


def font_face(key, chars):
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["kern", "liga", "palt"]
    opts.name_IDs = []
    opts.notdef_outline = True
    font = TTFont(font_path(key))
    sub = subset.Subsetter(opts)
    sub.populate(text=chars + " ")
    sub.subset(font)
    buf = io.BytesIO()
    font.flavor = "woff2"
    font.save(buf)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return "@font-face{font-family:'%s';src:url(data:font/woff2;base64,%s) format('woff2')}" % (key, b64)


def used_chars(svg, key):
    """Collect characters inside elements that use a given font class."""
    chars = set()
    for m in re.finditer(r'class="[^"]*\bf-%s\b[^"]*"[^>]*>(.*?)</(?:text|tspan)>' % key, svg, re.S):
        inner = re.sub(r"<[^>]+>", "", m.group(1))
        chars.update(html.unescape(inner))
    return "".join(sorted(chars))


def finish(name, w, h, title, body, css=""):
    fonts = ""
    for key in FONTS:
        chars = used_chars(body, key)
        if chars:
            fonts += font_face(key, chars)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'role="img" aria-label="{html.escape(title)}"><title>{html.escape(title)}</title>'
        f"<style>{fonts}"
        ".f-lcd{font-family:'lcd',monospace}"
        ".f-silk{font-family:'silk','Arial Narrow',sans-serif;font-weight:600}"
        ".f-body{font-family:'body',Helvetica,Arial,sans-serif;font-weight:500}"
        f"{css}"
        "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
        f"</style>{body}</svg>"
    )
    with open(os.path.join(ASSETS, name), "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"{name:22s} {len(svg)/1024:6.1f} KB")


def esc(s):
    return html.escape(s, quote=False)


def wrap(text, width):
    lines, line = [], ""
    for word in text.split():
        if len(line) + len(word) + (1 if line else 0) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}" if line else word
    if line:
        lines.append(line)
    return lines


# ── shared defs ────────────────────────────────────────────────────────────
def brushed(id_, opacity=0.22):
    # horizontal hairline texture for brushed aluminium
    return (
        f'<filter id="{id_}" x="0" y="0" width="100%" height="100%">'
        '<feTurbulence type="fractalNoise" baseFrequency="0.004 0.85" numOctaves="2" seed="7"/>'
        f'<feColorMatrix values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 {opacity} 0"/>'
        '<feComposite in2="SourceGraphic" operator="in"/></filter>'
    )


def lcd_defs():
    return (
        f'<linearGradient id="lcdbg" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="#0F3242"/><stop offset="1" stop-color="{LCD_GLASS}"/></linearGradient>'
        '<pattern id="dots" width="4" height="4" patternUnits="userSpaceOnUse">'
        '<rect width="4" height="4" fill="#000" opacity=".22"/><rect width="3" height="3" fill="#000" opacity="0"/>'
        '<rect x="3" width="1" height="4" fill="#000" opacity=".28"/><rect y="3" width="4" height="1" fill="#000" opacity=".28"/></pattern>'
        '<filter id="glow" x="-10%" y="-30%" width="120%" height="160%">'
        '<feGaussianBlur stdDeviation="2.2" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
        '<linearGradient id="glare" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#fff" stop-opacity=".10"/><stop offset=".45" stop-color="#fff" stop-opacity=".03"/>'
        '<stop offset=".46" stop-color="#fff" stop-opacity="0"/></linearGradient>'
    )


def lcd_window(x, y, w, h, r=10):
    """Dark plastic bezel + glowing LCD glass. Returns (bezel, glass_overlay)."""
    bezel = (
        f'<rect x="{x-14}" y="{y-14}" width="{w+28}" height="{h+28}" rx="{r+10}" fill="#2B3138"/>'
        f'<rect x="{x-14}" y="{y-13}" width="{w+28}" height="{h+26}" rx="{r+10}" fill="none" stroke="#000" stroke-opacity=".35"/>'
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="url(#lcdbg)"/>'
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="#5FE3FF" opacity=".05"/>'
    )
    overlay = (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="url(#dots)"/>'
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="url(#glare)"/>'
        f'<rect x="{x+.5}" y="{y+.5}" width="{w-1}" height="{h-1}" rx="{r}" fill="none" stroke="#000" stroke-opacity=".5"/>'
    )
    return bezel, overlay


def meter(x, y, n=14, bar_w=10, gap=5, max_h=34, cls="lvl"):
    out = []
    for i in range(n):
        # ghost bar then lit bar that bounces
        bx = x + i * (bar_w + gap)
        out.append(f'<rect x="{bx}" y="{y-max_h}" width="{bar_w}" height="{max_h}" fill="{LCD_GHOST}"/>')
        delay = (i * 0.37) % 1.3
        dur = 0.9 + (i % 4) * 0.17
        out.append(
            f'<rect class="{cls}" x="{bx}" y="{y-max_h}" width="{bar_w}" height="{max_h}" fill="{LCD_LIT}" '
            f'style="animation-delay:-{delay:.2f}s;animation-duration:{dur:.2f}s"/>'
        )
    return "".join(out)


# ── hero: the player ───────────────────────────────────────────────────────
def hero():
    W, H = 1280, 500
    lx, ly, lw, lh = 84, 78, 760, 292
    bezel, overlay = lcd_window(lx, ly, lw, lh)

    marquee = (
        "NOW PLAYING  Antideploy, deploys for coding agents     "
        "HOBBY 100 OF 100  skateboarding     "
        "India → Tokyo on a MEXT scholarship     "
        "WARNING  will notice if your button is 2px off     "
    )

    body = f"""
<defs>
  <linearGradient id="chassis" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{SILVER_HI}"/><stop offset=".55" stop-color="{SILVER}"/><stop offset="1" stop-color="{SILVER_LO}"/>
  </linearGradient>
  <linearGradient id="rim" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#fff"/><stop offset=".5" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".35"/>
  </linearGradient>
  <radialGradient id="dial" cx=".42" cy=".35" r=".75">
    <stop offset="0" stop-color="#FFFFFF"/><stop offset=".55" stop-color="#C9CED4"/><stop offset="1" stop-color="#8D949C"/>
  </radialGradient>
  <radialGradient id="dialC" cx=".45" cy=".35" r=".8">
    <stop offset="0" stop-color="#E9ECEF"/><stop offset="1" stop-color="#A2A9B1"/>
  </radialGradient>
  <linearGradient id="key" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#FAFBFC"/><stop offset="1" stop-color="#B9BFC6"/>
  </linearGradient>
  <filter id="drop" x="-5%" y="-5%" width="110%" height="125%">
    <feGaussianBlur in="SourceAlpha" stdDeviation="10"/><feOffset dy="10"/>
    <feComponentTransfer><feFuncA type="linear" slope=".28"/></feComponentTransfer>
    <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  {brushed("brush")}
  {lcd_defs()}
  <clipPath id="mq"><rect x="{lx+24}" y="{ly+218}" width="470" height="50"/></clipPath>
</defs>

<!-- chassis -->
<g filter="url(#drop)">
  <rect x="24" y="18" width="1232" height="446" rx="64" fill="url(#chassis)"/>
</g>
<rect x="24" y="18" width="1232" height="446" rx="64" fill="#fff" filter="url(#brush)"/>
<rect x="25" y="19" width="1230" height="444" rx="63" fill="none" stroke="url(#rim)" stroke-width="2"/>
<rect x="24.5" y="18.5" width="1231" height="445" rx="63.5" fill="none" stroke="{EDGE}" stroke-opacity=".55"/>

<!-- LCD -->
{bezel}
<g filter="url(#glow)">
  <!-- status row -->
  <text class="f-lcd" x="{lx+24}" y="{ly+40}" font-size="22" fill="{LCD_LIT}">TR 01</text>
  <path d="M{lx+108} {ly+23} l14 9 l-14 9 z" fill="{LCD_LIT}"/>
  <text class="f-lcd" x="{lx+138}" y="{ly+40}" font-size="22" fill="{LCD_LIT}">DISC  SARTHAK-SAMA</text>
  <text class="f-lcd" x="{lx+lw-200}" y="{ly+40}" font-size="22" fill="{LCD_GHOST}">REC</text>
  <text class="f-lcd" x="{lx+lw-140}" y="{ly+40}" font-size="22" fill="{LCD_LIT}">JST</text>
  <g transform="translate({lx+lw-72} {ly+22})">
    <rect x="0" y="0" width="40" height="20" fill="none" stroke="{LCD_LIT}" stroke-width="3"/>
    <rect x="40" y="6" width="5" height="8" fill="{LCD_LIT}"/>
    <rect x="5" y="5" width="8" height="10" fill="{LCD_LIT}"/>
    <rect x="16" y="5" width="8" height="10" fill="{LCD_LIT}"/>
    <rect x="27" y="5" width="8" height="10" fill="{LCD_GHOST}"/>
  </g>
  <rect x="{lx+24}" y="{ly+56}" width="{lw-48}" height="2" fill="{LCD_GHOST}"/>

  <!-- title -->
  <text class="f-lcd" x="{lx+22}" y="{ly+132}" font-size="66" fill="{LCD_LIT}" letter-spacing="2">SARTHAK SAKLANI</text>
  <text class="f-lcd" x="{lx+24}" y="{ly+180}" font-size="30" fill="{LCD_LIT}">フルスタックエンジニア　東京・渋谷</text>

  <!-- scrolling line -->
  <rect x="{lx+24}" y="{ly+206}" width="{lw-48}" height="2" fill="{LCD_GHOST}"/>
  <g clip-path="url(#mq)">
    <g class="mq">
      <text class="f-lcd" x="{lx+24}" y="{ly+252}" font-size="24" fill="{LCD_LIT}" xml:space="preserve">{esc(marquee)}{esc(marquee)}</text>
    </g>
  </g>
  {meter(lx+lw-238, ly+262, n=14, bar_w=10, gap=5, max_h=36)}
</g>
{overlay}

<!-- silkscreen under the LCD -->
<text class="f-silk" x="{lx-12}" y="428" font-size="22" letter-spacing="5" fill="{INK}" opacity=".82">FULL-STACK ENGINEER</text>
<text class="f-silk" x="{lx+lw+12}" y="428" font-size="22" letter-spacing="5" fill="{INK}" opacity=".82" text-anchor="end">SK-26</text>

<!-- jog dial -->
<g transform="translate(1046 196)">
  <circle r="112" fill="#000" opacity=".10" cy="4"/>
  <circle r="108" fill="url(#dial)" stroke="{EDGE}" stroke-opacity=".6"/>
  <circle r="96" fill="none" stroke="#fff" stroke-opacity=".7"/>
  <circle r="44" fill="#000" opacity=".12" cy="2"/>
  <circle r="42" fill="url(#dialC)" stroke="{EDGE}" stroke-opacity=".5"/>
  <!-- play/pause on centre -->
  <path d="M-14 -12 l18 12 l-18 12 z" fill="{INK}"/>
  <rect x="8" y="-12" width="5" height="24" fill="{INK}"/><rect x="16" y="-12" width="5" height="24" fill="{INK}"/>
  <!-- direction glyphs -->
  <g fill="{INK}" opacity=".75">
    <path d="M58 -8 l10 8 l-10 8 z M68 -8 l10 8 l-10 8 z"/>
    <path d="M-58 -8 l-10 8 l10 8 z M-68 -8 l-10 8 l10 8 z"/>
    <text class="f-silk" x="0" y="-62" font-size="17" text-anchor="middle" letter-spacing="2">VOL +</text>
    <text class="f-silk" x="0" y="76" font-size="17" text-anchor="middle" letter-spacing="2">VOL −</text>
  </g>
</g>

<!-- keys -->
<g class="f-silk" font-size="15" letter-spacing="2.5" fill="{INK}">
  <g transform="translate(920 352)">
    <rect width="76" height="34" rx="17" fill="#000" opacity=".12" y="2"/>
    <rect width="76" height="34" rx="17" fill="url(#key)" stroke="{EDGE}" stroke-opacity=".5"/>
    <rect x="29" y="11" width="13" height="13" fill="{INK}"/>
    <text class="f-silk" x="38" y="62" text-anchor="middle" opacity=".75">STOP</text>
  </g>
  <g transform="translate(1012 352)">
    <rect width="76" height="34" rx="17" fill="#000" opacity=".12" y="2"/>
    <rect width="76" height="34" rx="17" fill="url(#key)" stroke="{EDGE}" stroke-opacity=".5"/>
    <text class="f-silk" x="38" y="23" text-anchor="middle" font-size="14">≡</text>
    <text class="f-silk" x="38" y="62" text-anchor="middle" opacity=".75">MENU</text>
  </g>
  <!-- hold slider: orange shows when locked -->
  <g transform="translate(1110 352)">
    <rect width="96" height="34" rx="6" fill="#3A4047"/>
    <rect x="4" y="4" width="40" height="26" rx="3" fill="{HOLD}"/>
    <rect x="48" y="3" width="44" height="28" rx="4" fill="url(#key)" stroke="{EDGE}" stroke-opacity=".6"/>
    <path d="M62 10 v14 M68 10 v14 M74 10 v14 M80 10 v14" stroke="{EDGE}" stroke-opacity=".5"/>
    <text class="f-silk" x="48" y="62" text-anchor="middle" opacity=".75">HOLD</text>
  </g>
</g>
"""
    css = (
        "@keyframes mq{from{transform:translateX(0)}to{transform:translateX(-50%)}}"
        ".mq{animation:mq 38s linear infinite}"
        "@keyframes lvl{0%{transform:scaleY(.15)}35%{transform:scaleY(.95)}60%{transform:scaleY(.45)}80%{transform:scaleY(.75)}100%{transform:scaleY(.15)}}"
        f".lvl{{transform-box:fill-box;transform-origin:50% 100%;animation:lvl 1s ease-in-out infinite alternate}}"
    )
    finish("hero.svg", W, H, "Sarthak Saklani, full-stack engineer in Tokyo. A silver MiniDisc player with its LCD showing his name.", body, css)


# ── konbini receipt: work and study history ────────────────────────────────
RECEIPT = [
    ("BA 日本文学", "JNU, New Delhi", "修了"),
    ("BSc DATA SCIENCE", "IIT Madras", "2027予定"),
    ("日本語コース", "Bunka Institute, Tokyo", "2027予定"),
    ("FRONTEND DEV", "Tryp.com, ~400K users/mo", "25-26"),
    ("FULLSTACK INTERN", "Digital Palmy", "2025"),
    ("MEXT SCHOLARSHIP", "thank you, Japan", "¥0"),
    ("IIM ADMISSION", "politely declined", "返品"),
]

PAPER_INK = "#2B2B2E"


def receipt():
    W, H = 600, 1060
    x0, x1, y0, y1, t = 64, 536, 34, 1026, 12
    zig_top = "".join(f"L{x0 + i*t + t/2} {y0 - 7} L{x0 + (i+1)*t} {y0} " for i in range(int((x1 - x0) / t)))
    zig_bot = "".join(f"L{x1 - i*t - t/2} {y1 + 7} L{x1 - (i+1)*t} {y1} " for i in range(int((x1 - x0) / t)))
    paper = f"M{x0} {y0} {zig_top} L{x1} {y1} {zig_bot} Z"

    def c(y, s, size=22, op=1, ls=0):
        return f'<text class="f-lcd" x="300" y="{y}" font-size="{size}" fill="{PAPER_INK}" opacity="{op}" text-anchor="middle" letter-spacing="{ls}">{esc(s)}</text>'

    def lr(y, l, r, size=22, op=1):
        return (f'<text class="f-lcd" x="96" y="{y}" font-size="{size}" fill="{PAPER_INK}" opacity="{op}">{esc(l)}</text>'
                f'<text class="f-lcd" x="504" y="{y}" font-size="{size}" fill="{PAPER_INK}" opacity="{op}" text-anchor="end">{esc(r)}</text>')

    def dash(y):
        return f'<line x1="96" x2="504" y1="{y}" y2="{y}" stroke="{PAPER_INK}" stroke-width="2" stroke-dasharray="6 5" opacity=".7"/>'

    items, y = [], 318
    for name, sub, val in RECEIPT:
        items.append(lr(y, name, val))
        items.append(f'<text class="f-lcd" x="112" y="{y+26}" font-size="17" fill="{PAPER_INK}" opacity=".6">{esc(sub)}</text>')
        y += 66

    bars, bx = [], 196
    seed = [2, 1, 3, 1, 1, 2, 1, 3, 2, 1, 1, 1, 3, 2, 1, 2, 1, 1, 3, 1, 2, 2, 1, 1, 2, 3, 1, 1, 2, 1, 1, 3, 1, 2]
    for i, w in enumerate(seed):
        if i % 2 == 0:
            bars.append(f'<rect x="{bx}" y="938" width="{w*2.4:.1f}" height="44" fill="{PAPER_INK}"/>')
        bx += w * 2.4 + 1.4

    body = f"""
<defs>
  <filter id="drop" x="-10%" y="-5%" width="120%" height="115%">
    <feGaussianBlur in="SourceAlpha" stdDeviation="9"/><feOffset dx="4" dy="10"/>
    <feComponentTransfer><feFuncA type="linear" slope=".35"/></feComponentTransfer>
    <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <linearGradient id="paper" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#FFFFFD"/><stop offset=".6" stop-color="#F6F5EF"/><stop offset="1" stop-color="#ECEAE2"/>
  </linearGradient>
  <filter id="grain" x="0" y="0" width="100%" height="100%">
    <feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="1" seed="3"/>
    <feColorMatrix values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 .07 0"/>
    <feComposite in2="SourceGraphic" operator="in"/>
  </filter>
</defs>
<g transform="rotate(-1.3 300 530)">
  <path d="{paper}" fill="url(#paper)" filter="url(#drop)"/>
  <path d="{paper}" fill="#fff" filter="url(#grain)"/>
  {c(104, "YATO MART", 46, 1, 4)}
  {c(140, "やと商店　東京店")}
  {c(172, "2026年11月26日(木) 17:08", 19, .8)}
  {c(198, "レジ02　担当 サルタク", 19, .8)}
  {dash(220)}
  {c(262, "領　収　書", 30, 1, 6)}
  {dash(282)}
  {"".join(items)}
  {dash(y - 22)}
  {lr(y + 18, "小計", "1 ENGINEER", 24)}
  {lr(y + 54, "お預り", "COFFEE")}
  {lr(y + 88, "お釣り CHANGE", "INDIA→TOKYO")}
  {"".join(bars)}
  {c(1008, "返品不可　deploys are final", 16, .7)}
</g>
"""
    alt = "Receipt from Yato Mart: " + "; ".join(f"{n} ({s}) {v}" for n, s, v in RECEIPT) + ". Subtotal: 1 engineer. Paid in coffee."
    finish("receipt.svg", W, H, alt, body)


# ── flip phone: testimonials in the inbox ──────────────────────────────────
MAIL = [
    ("Mohammad Harish", "the best frontend engineer i have seen in the entire tpot (this part of twitter)"),
    ("Manu Prabhakar", "quickly adapted to different tech stacks and delivered features with great attention to detail"),
    ("Alok Singh", "delivered the project within a very tight deadline without compromising on quality"),
]


def keitai():
    W, H = 600, 1060
    sx, sy, sw, sh = 124, 96, 352, 380
    entries, y = [], sy + 76
    for i, (who, msg) in enumerate(MAIL):
        lines = wrap(msg, 38)
        if len(lines) > 2:
            lines = lines[:2]
            lines[1] = lines[1][:35] + "…"
        h = 34 + 22 * len(lines) + 12
        if i == 0:
            entries.append(f'<rect x="{sx}" y="{y}" width="{sw}" height="{h}" fill="#FFE6CC"/>'
                           f'<rect x="{sx}" y="{y}" width="6" height="{h}" fill="{HOLD}"/>')
        # envelope icon
        entries.append(f'<g transform="translate({sx+16} {y+11})"><rect width="22" height="15" fill="#fff" stroke="#3A5A8C" stroke-width="2"/>'
                       f'<path d="M1 1 L11 9 L21 1" fill="none" stroke="#3A5A8C" stroke-width="2"/></g>')
        entries.append(f'<text class="f-lcd" x="{sx+48}" y="{y+26}" font-size="20" fill="#14253F">{esc(who)}</text>')
        for j, l in enumerate(lines):
            entries.append(f'<text class="f-lcd" x="{sx+18}" y="{y+52+22*j}" font-size="16" fill="#3C4656">{esc(l)}</text>')
        entries.append(f'<line x1="{sx}" x2="{sx+sw}" y1="{y+h}" y2="{y+h}" stroke="#C9D2DE"/>')
        y += h

    kana = [("1", "あ"), ("2", "か"), ("3", "さ"), ("4", "た"), ("5", "な"), ("6", "は"),
            ("7", "ま"), ("8", "や"), ("9", "ら"), ("*", "゛"), ("0", "わ"), ("#", "、")]
    keys = []
    for i, (n, k) in enumerate(kana):
        kx = 116 + (i % 3) * 128
        ky = 752 + (i // 3) * 66
        keys.append(
            f'<g transform="translate({kx} {ky})">'
            f'<rect y="3" width="112" height="52" rx="24" fill="#000" opacity=".15"/>'
            f'<rect width="112" height="52" rx="24" fill="url(#key)" stroke="{EDGE}" stroke-opacity=".45"/>'
            f'<text class="f-silk" x="40" y="36" font-size="28" fill="{INK}" text-anchor="middle">{esc(n)}</text>'
            f'<text class="f-lcd" x="74" y="34" font-size="18" fill="{INK}" opacity=".6" text-anchor="middle">{esc(k)}</text></g>'
        )

    body = f"""
<defs>
  <linearGradient id="pearl" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#F7F8FA"/><stop offset=".5" stop-color="#D7DCE2"/><stop offset="1" stop-color="#AEB5BD"/>
  </linearGradient>
  <linearGradient id="hinge" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#8E959D"/><stop offset=".45" stop-color="#EEF1F4"/><stop offset="1" stop-color="#7D848C"/>
  </linearGradient>
  <linearGradient id="bar" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#3B7FE6"/><stop offset="1" stop-color="#1C4FB0"/>
  </linearGradient>
  <linearGradient id="key" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#C3C9CF"/>
  </linearGradient>
  <linearGradient id="glass" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#fff" stop-opacity=".35"/><stop offset=".4" stop-color="#fff" stop-opacity=".06"/>
    <stop offset=".41" stop-color="#fff" stop-opacity="0"/>
  </linearGradient>
  <filter id="drop" x="-10%" y="-5%" width="120%" height="115%">
    <feGaussianBlur in="SourceAlpha" stdDeviation="9"/><feOffset dy="10"/>
    <feComponentTransfer><feFuncA type="linear" slope=".3"/></feComponentTransfer>
    <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  {brushed("brush", .2)}
  <clipPath id="scr"><rect x="{sx}" y="{sy}" width="{sw}" height="{sh}"/></clipPath>
</defs>

<!-- lower half -->
<g filter="url(#drop)"><rect x="84" y="548" width="432" height="494" rx="44" fill="url(#pearl)"/></g>
<rect x="84" y="548" width="432" height="494" rx="44" fill="#fff" filter="url(#brush)"/>
<rect x="84.5" y="548.5" width="431" height="493" rx="44" fill="none" stroke="{EDGE}" stroke-opacity=".5"/>

<!-- upper half -->
<g filter="url(#drop)"><rect x="80" y="18" width="440" height="510" rx="48" fill="url(#pearl)"/></g>
<rect x="80" y="18" width="440" height="510" rx="48" fill="#fff" filter="url(#brush)"/>
<rect x="80.5" y="18.5" width="439" height="509" rx="48" fill="none" stroke="{EDGE}" stroke-opacity=".5"/>
<rect x="262" y="46" width="76" height="8" rx="4" fill="{EDGE}" opacity=".6"/>

<!-- hinge, with the new-mail LED -->
<rect x="104" y="516" width="392" height="44" rx="20" fill="url(#hinge)" stroke="{EDGE}" stroke-opacity=".5"/>
<circle class="led" cx="300" cy="538" r="7" fill="{HOLD}"/>

<!-- screen -->
<rect x="{sx-14}" y="{sy-14}" width="{sw+28}" height="{sh+28}" rx="16" fill="#1D2228"/>
<g clip-path="url(#scr)">
  <rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" fill="#FBFCFE"/>
  <rect x="{sx}" y="{sy}" width="{sw}" height="30" fill="#E6ECF4"/>
  <g fill="#14253F">
    <rect x="{sx+12}" y="{sy+19}" width="4" height="5"/><rect x="{sx+19}" y="{sy+15}" width="4" height="9"/>
    <rect x="{sx+26}" y="{sy+11}" width="4" height="13"/><rect x="{sx+33}" y="{sy+7}" width="4" height="17"/>
    <rect x="{sx+sw-44}" y="{sy+8}" width="26" height="14" fill="none" stroke="#14253F" stroke-width="2"/>
    <rect x="{sx+sw-18}" y="{sy+12}" width="3" height="6"/>
    <rect x="{sx+sw-41}" y="{sy+11}" width="6" height="8"/><rect x="{sx+sw-33}" y="{sy+11}" width="6" height="8"/>
  </g>
  <text class="f-lcd" x="{sx+sw/2}" y="{sy+22}" font-size="18" fill="#14253F" text-anchor="middle">17:08</text>
  <rect x="{sx}" y="{sy+30}" width="{sw}" height="42" fill="url(#bar)"/>
  <text class="f-lcd" x="{sx+16}" y="{sy+59}" font-size="22" fill="#fff">受信BOX</text>
  <text class="f-lcd" x="{sx+sw-16}" y="{sy+59}" font-size="18" fill="#fff" opacity=".85" text-anchor="end">3件</text>
  {"".join(entries)}
  <rect x="{sx}" y="{sy+sh-34}" width="{sw}" height="34" fill="#DDE4EC"/>
  <text class="f-lcd" x="{sx+16}" y="{sy+sh-11}" font-size="17" fill="#14253F">戻る</text>
  <text class="f-lcd" x="{sx+sw/2}" y="{sy+sh-11}" font-size="17" fill="#14253F" text-anchor="middle">選択</text>
  <text class="f-lcd" x="{sx+sw-16}" y="{sy+sh-11}" font-size="17" fill="#14253F" text-anchor="end">返信</text>
  <rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" fill="url(#glass)"/>
</g>

<!-- nav cluster -->
<g>
  <rect x="116" y="590" width="96" height="40" rx="20" fill="url(#key)" stroke="{EDGE}" stroke-opacity=".45"/>
  <rect x="388" y="590" width="96" height="40" rx="20" fill="url(#key)" stroke="{EDGE}" stroke-opacity=".45"/>
  <g transform="translate(150 600)"><rect width="28" height="20" fill="none" stroke="{INK}" stroke-width="2.5"/><path d="M1 1 L14 11 L27 1" fill="none" stroke="{INK}" stroke-width="2.5"/></g>
  <text class="f-silk" x="436" y="619" font-size="24" fill="{INK}" text-anchor="middle">i</text>
  <circle cx="300" cy="652" r="62" fill="url(#key)" stroke="{EDGE}" stroke-opacity=".45"/>
  <g fill="{INK}" opacity=".55">
    <path d="M300 600 l-8 10 h16 z"/><path d="M300 704 l-8 -10 h16 z"/>
    <path d="M248 652 l10 -8 v16 z"/><path d="M352 652 l-10 -8 v16 z"/>
  </g>
  <circle cx="300" cy="652" r="28" fill="url(#pearl)" stroke="{EDGE}" stroke-opacity=".5"/>
  <text class="f-lcd" x="300" y="660" font-size="18" fill="{INK}" text-anchor="middle">決定</text>
  <rect x="116" y="660" width="96" height="40" rx="20" fill="url(#key)" stroke="{EDGE}" stroke-opacity=".45"/>
  <rect x="388" y="660" width="96" height="40" rx="20" fill="url(#key)" stroke="{EDGE}" stroke-opacity=".45"/>
  <rect x="146" y="676" width="36" height="8" rx="4" fill="#2F9B57"/>
  <rect x="418" y="676" width="36" height="8" rx="4" fill="#D2463C"/>
</g>
{"".join(keys)}
"""
    css = "@keyframes led{0%,60%{opacity:1}70%,100%{opacity:.15}}.led{animation:led 1.6s steps(1) infinite}"
    alt = "A flip phone inbox with three messages. " + " ".join(f'{w}: "{m}".' for w, m in MAIL)
    finish("inbox.svg", W, H, alt, body, css)


# ── spec sticker ───────────────────────────────────────────────────────────
SPEC = [
    ("Languages", "TypeScript, JavaScript, Python"),
    ("Frontend", "React, Next.js, Redux, Tailwind CSS, Vite"),
    ("Backend", "Node.js, Express, Fastify"),
    ("Data", "PostgreSQL and PostGIS, MongoDB"),
    ("Shipping", "Docker, Vercel, Git"),
    ("AI", "Gemini, coding agents"),
]


def spec():
    W = 1280
    row_h = 46
    top = 130
    H = top + row_h * len(SPEC) + 40
    rows = []
    for i, (k, v) in enumerate(SPEC):
        y = top + i * row_h
        rows.append(
            f'<text class="f-silk" x="72" y="{y+31}" font-size="23" letter-spacing="2" fill="{INK}" opacity=".6">{esc(k)}</text>'
            f'<text class="f-body" x="290" y="{y+31}" font-size="25" fill="{INK}">{esc(v)}</text>'
            f'<line x1="56" x2="868" y1="{y+row_h}" y2="{y+row_h}" stroke="{INK}" stroke-opacity=".18"/>'
        )
    # barcode-ish serial strip: deterministic bars
    bars, bx = [], 930
    seed = [3, 1, 2, 1, 1, 3, 2, 1, 1, 2, 3, 1, 2, 2, 1, 1, 3, 1, 2, 1, 1, 2, 1, 3, 1, 1, 2, 2, 1, 3, 1, 2, 1, 1, 2, 1, 3, 2, 1, 1]
    for i, w in enumerate(seed):
        if i % 2 == 0:
            bars.append(f'<rect x="{bx}" y="{H-150}" width="{w*2.6:.1f}" height="74" fill="{INK}"/>')
        bx += w * 2.6 + 1.6
    body = f"""
<defs>
  <linearGradient id="foil" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#E7EAED"/><stop offset=".5" stop-color="#F7F8F9"/><stop offset="1" stop-color="#CDD2D7"/>
  </linearGradient>
  {brushed("brush", .25)}
</defs>
<rect x="20" y="12" width="{W-40}" height="{H-24}" rx="14" fill="url(#foil)"/>
<rect x="20" y="12" width="{W-40}" height="{H-24}" rx="14" fill="#fff" filter="url(#brush)"/>
<rect x="20.5" y="12.5" width="{W-41}" height="{H-25}" rx="14" fill="none" stroke="{INK}" stroke-opacity=".35"/>
<rect x="36" y="28" width="{W-72}" height="{H-56}" rx="6" fill="none" stroke="{INK}" stroke-opacity=".7" stroke-width="2"/>

<text class="f-lcd" x="72" y="92" font-size="40" fill="{INK}">仕様</text>
<text class="f-silk" x="172" y="90" font-size="30" letter-spacing="6" fill="{INK}">SPECIFICATIONS</text>
<text class="f-silk" x="868" y="90" font-size="24" letter-spacing="4" fill="{INK}" opacity=".6" text-anchor="end">MODEL SK-26</text>
<line x1="56" x2="868" y1="{top-6}" y2="{top-6}" stroke="{INK}" stroke-width="2"/>
{"".join(rows)}

<line x1="904" x2="904" y1="56" y2="{H-56}" stroke="{INK}" stroke-opacity=".35"/>
<text class="f-silk" x="930" y="92" font-size="26" letter-spacing="3" fill="{INK}">MADE IN INDIA</text>
<text class="f-silk" x="930" y="126" font-size="26" letter-spacing="3" fill="{INK}">ASSEMBLED IN TOKYO</text>
<text class="f-lcd" x="930" y="170" font-size="22" fill="{INK}" opacity=".7">インド製　東京で組立</text>
<text class="f-body" x="930" y="228" font-size="19" fill="{INK}" opacity=".7">Batteries not included.</text>
<text class="f-body" x="930" y="256" font-size="19" fill="{INK}" opacity=".7">Coffee required.</text>
{"".join(bars)}
<text class="f-lcd" x="930" y="{H-52}" font-size="17" fill="{INK}" opacity=".75" letter-spacing="3">S/N SARTHAK-SAMA</text>
"""
    finish("spec.svg", W, H, "Specifications. " + ". ".join(f"{k}: {v}" for k, v in SPEC) + ". Made in India, assembled in Tokyo.", body)


# ── footer LCD strip ───────────────────────────────────────────────────────
def next_up():
    W, H = 1280, 150
    lx, ly, lw, lh = 34, 30, W - 68, 90
    bezel, overlay = lcd_window(lx, ly, lw, lh, r=8)
    line = "次の曲、東京のプロダクトチームへ。     NEXT TRACK  Joining a product team in Tokyo. Open to full-stack roles.     "
    body = f"""
<defs>{lcd_defs()}<clipPath id="mq"><rect x="{lx+190}" y="{ly}" width="{lw-210}" height="{lh}"/></clipPath></defs>
<rect x="6" y="4" width="{W-12}" height="{H-8}" rx="30" fill="{SILVER}"/>
<rect x="6.5" y="4.5" width="{W-13}" height="{H-9}" rx="30" fill="none" stroke="{EDGE}" stroke-opacity=".5"/>
{bezel}
<g filter="url(#glow)">
  <text class="f-lcd" x="{lx+24}" y="{ly+57}" font-size="26" fill="{LCD_LIT}">NEXT ▶▶</text>
  <rect x="{lx+168}" y="{ly+18}" width="2" height="{lh-36}" fill="{LCD_GHOST}"/>
  <g clip-path="url(#mq)"><g class="mq">
    <text class="f-lcd" x="{lx+196}" y="{ly+57}" font-size="26" fill="{LCD_LIT}" xml:space="preserve">{esc(line)}{esc(line)}</text>
  </g></g>
</g>
{overlay}
"""
    css = "@keyframes mq{from{transform:translateX(0)}to{transform:translateX(-50%)}}.mq{animation:mq 30s linear infinite}"
    finish("next.svg", W, H, "Next track: joining a product team in Tokyo. Open to full-stack roles.", body, css)


# ── link buttons ───────────────────────────────────────────────────────────
BUTTONS = [("site", "sarthak.space"), ("x", "X  @Sarthak_Sama"), ("linkedin", "LinkedIn")]


def buttons():
    for slug, label in BUTTONS:
        W, H = 96 + int(15.5 * len(label)), 76
        body = f"""
<defs>
  <linearGradient id="key" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#FAFBFC"/><stop offset="1" stop-color="#B9BFC6"/>
  </linearGradient>
</defs>
<rect x="6" y="9" width="{W-12}" height="{H-14}" rx="{(H-14)/2}" fill="#000" opacity=".22"/>
<rect x="6" y="5" width="{W-12}" height="{H-14}" rx="{(H-14)/2}" fill="url(#key)" stroke="{EDGE}" stroke-opacity=".6"/>
<rect x="9" y="7" width="{W-18}" height="{(H-14)/2}" rx="{(H-14)/4}" fill="#fff" opacity=".45"/>
<circle cx="40" cy="{5+(H-14)/2}" r="6" fill="{HOLD}"/>
<text class="f-silk" x="{(W+56)/2}" y="{5+(H-14)/2+9}" font-size="27" letter-spacing="2" fill="{INK}" text-anchor="middle" xml:space="preserve">{esc(label)}</text>
"""
        finish(f"btn-{slug}.svg", W, H, label, body)


if __name__ == "__main__":
    os.makedirs(ASSETS, exist_ok=True)
    hero()
    receipt()
    keitai()
    spec()
    next_up()
    buttons()
