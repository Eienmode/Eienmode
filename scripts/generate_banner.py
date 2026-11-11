"""Generate the animated glitch / code-decode header and footer.

Pure SVG + SMIL/CSS animation (no JavaScript), so it animates inside GitHub READMEs.
Run once after editing the text below:   python scripts/generate_banner.py
"""

import os
import random
from html import escape

OUT_DIR = os.environ.get("CARDS_OUT", "cards")

TITLE = "EIENMODE"
SUBTITLE = "> developer // builder // always shipping"
FOOTER = "// thanks for visiting - see you in the commits"

BG = "#12131f"
BORDER = "#2a2b3d"
PINK = "#ff4f8b"
RED = "#e0245e"
PURPLE = "#9d4edd"
LILAC = "#bb9af7"
WHITE = "#ffe3ee"
MUTED = "#565f89"
MONO = "'Fira Code', 'JetBrains Mono', Consolas, 'Courier New', monospace"

GLYPHS = "!<>-_\\/[]{}=+*^?#$%&01ABCDEFabcdef@~|;:"
CODE_BITS = [
    "const eien = new Mode();", "0x3F", "0xA1", "git push origin main", "if (bug) fix(bug);",
    "while(true) { learn(); }", "#include <dream.h>", "sudo make it-work", "01101001",
    "return 0;", "npm run build", "def glitch(): pass", "0xFF00FF", "SELECT * FROM ideas;",
    "await coffee();", "let x = Math.random();", "{ }", "</>", "=>", "0b1011",
]


def rnd_glyph(rng):
    return escape(rng.choice(GLYPHS))


def frac(t, dur):
    return f"{max(0.0, min(1.0, t / dur)):.4f}"


def show_between(start, end, dur):
    """SMIL: element visible only in [start, end) of each loop."""
    if start <= 0:
        return (f'<animate attributeName="opacity" dur="{dur}s" repeatCount="indefinite" calcMode="discrete" '
                f'keyTimes="0;{frac(end, dur)}" values="1;0"/>')
    if end >= dur:
        return (f'<animate attributeName="opacity" dur="{dur}s" repeatCount="indefinite" calcMode="discrete" '
                f'keyTimes="0;{frac(start, dur)}" values="0;1"/>')
    return (f'<animate attributeName="opacity" dur="{dur}s" repeatCount="indefinite" calcMode="discrete" '
            f'keyTimes="0;{frac(start, dur)};{frac(end, dur)}" values="0;1;0"/>')


def decode_text(rng, text, cx, y, size, char_w, dur, start, step, frames, out_start,
                final_color, scramble_colors, weight=700, from_zero=False):
    """Each character flickers through random glyphs, then locks into the real one,
    holds, and scrambles out again before the loop restarts."""
    out = []
    n = len(text)
    x0 = cx - (n - 1) * char_w / 2
    fdur = 0.06
    for i, ch in enumerate(text):
        x = x0 + i * char_w
        if ch == " ":
            continue
        style = f'font-size:{size}px;font-weight:{weight}'
        resolve = start + i * step + frames * fdur
        out_t = out_start + i * step * 0.4
        # scramble-in frames (from_zero: every char is already scrambling when the loop restarts)
        first = 0.0 if from_zero else start + i * step
        count = max(1, round((resolve - first) / fdur))
        for k in range(count):
            a = first + k * fdur
            if k == count - 1:
                fdur_k = resolve - a
            else:
                fdur_k = fdur
            out.append(f'<text x="{x:.1f}" y="{y}" opacity="0" fill="{rng.choice(scramble_colors)}" '
                       f'style="{style}">{rnd_glyph(rng)}{show_between(a, a + fdur_k, dur)}</text>')
        # locked-in character
        out.append(f'<text x="{x:.1f}" y="{y}" opacity="0" fill="{final_color}" style="{style}">'
                   f'{escape(ch)}{show_between(resolve, out_t, dur)}</text>')
        # scramble-out frames until loop end
        t = out_t
        while t < dur - 1e-6:
            out.append(f'<text x="{x:.1f}" y="{y}" opacity="0" fill="{rng.choice(scramble_colors)}" '
                       f'style="{style}">{rnd_glyph(rng)}{show_between(t, min(t + fdur, dur), dur)}</text>')
            t += fdur
    return "\n".join(out)


def code_rain(rng, width, height, rows, size, color, opacity):
    """Rows of faint code scrolling sideways at different speeds."""
    out = []
    gap = height / rows
    for r in range(rows):
        bits = []
        while len(" ".join(bits)) < 260:
            bits.append(rng.choice(CODE_BITS))
        raw = "   ".join(bits) + "   "
        copy_w = len(raw) * size * 0.6  # monospace advance ~0.6em
        line = escape(raw)
        speed = rng.uniform(25, 50)
        direction = 1 if r % 2 else -1
        y = gap * r + gap * 0.7
        x = -copy_w if direction > 0 else 0
        out.append(
            f'<g opacity="{opacity}"><text class="left" x="{x:.0f}" y="{y:.1f}" fill="{color}" '
            f'textLength="{copy_w * 2:.0f}" lengthAdjust="spacing" '
            f'style="font-size:{size}px" xml:space="preserve">{line}{line}'
            f'<animateTransform attributeName="transform" type="translate" from="0 0" to="{copy_w * direction:.0f} 0" '
            f'dur="{speed:.1f}s" repeatCount="indefinite"/></text></g>'
        )
    return "\n".join(out)


def glitch_bars(rng, width, height, dur, bursts, count):
    out = []
    for _ in range(count):
        a, b = rng.choice(bursts)
        w = rng.uniform(60, 320)
        x = rng.uniform(0, width - w)
        y = rng.uniform(10, height - 10)
        h = rng.choice([2, 3, 4, 6, 9])
        c = rng.choice([PINK, RED, PURPLE, LILAC])
        out.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h}" fill="{c}" opacity="0">'
                   f'{show_between(a, b, dur)}</rect>')
    return "\n".join(out)


def jitter(dur, bursts, offsets):
    """Discrete translate jumps during glitch bursts."""
    times, values = ["0"], ["0 0"]
    for (a, b), (dx, dy) in zip(bursts, offsets):
        times += [frac(a, dur), frac(b, dur)]
        values += [f"{dx} {dy}", "0 0"]
    return (f'<animateTransform attributeName="transform" type="translate" dur="{dur}s" '
            f'repeatCount="indefinite" calcMode="discrete" keyTimes="{";".join(times)}" '
            f'values="{";".join(values)}"/>')


def rgb_split(text, cx, y, size, char_w, dur, bursts, clip_id, height):
    """Red and purple copies of the word, sliced into bands, flashing during bursts."""
    n = len(text)
    x0 = cx - (n - 1) * char_w / 2
    chars = "".join(
        f'<tspan x="{x0 + i * char_w:.1f}">{escape(ch)}</tspan>' for i, ch in enumerate(text) if ch != " ")
    out = []
    for color, sign, cid in ((RED, -1, f"{clip_id}a"), (PURPLE, 1, f"{clip_id}b")):
        ys, hs, times = ["0"], ["0"], ["0"]
        offs = ["0 0"]
        for j, (a, b) in enumerate(bursts):
            times += [frac(a, dur), frac(b, dur)]
            band_y = (y - size * 0.8) + ((j * 37 + (11 if sign > 0 else 29)) % int(size * 0.7))
            ys += [f"{band_y:.0f}", "0"]
            hs += [str(int(size * 0.25 + (j % 3) * 6)), "0"]
            offs += [f"{sign * (6 + j % 3 * 3)} 0", "0 0"]
        kt = ";".join(times)
        out.append(
            f'<clipPath id="{cid}"><rect x="0" width="840" y="0" height="0">'
            f'<animate attributeName="y" dur="{dur}s" repeatCount="indefinite" calcMode="discrete" keyTimes="{kt}" values="{";".join(ys)}"/>'
            f'<animate attributeName="height" dur="{dur}s" repeatCount="indefinite" calcMode="discrete" keyTimes="{kt}" values="{";".join(hs)}"/>'
            f'</rect></clipPath>'
            f'<g clip-path="url(#{cid})"><text y="{y}" fill="{color}" style="font-size:{size}px;font-weight:800">{chars}'
            f'<animateTransform attributeName="transform" type="translate" dur="{dur}s" repeatCount="indefinite" '
            f'calcMode="discrete" keyTimes="{kt}" values="{";".join(offs)}"/></text></g>'
        )
    return "\n".join(out)


def svg_wrap(width, height, title, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">
<title>{escape(title)}</title>
<style>
  text {{ font-family: {MONO}; text-anchor: middle; }}
  .left {{ text-anchor: start; }}
  .blink {{ animation: blink 1s steps(1) infinite; }}
  @keyframes blink {{ 50% {{ opacity: 0; }} }}
</style>
<defs>
  <pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse">
    <rect width="4" height="1" fill="#000" opacity=".35"/>
  </pattern>
  <clipPath id="frame"><rect width="{width}" height="{height}" rx="10"/></clipPath>
</defs>
<g clip-path="url(#frame)">
<rect width="{width}" height="{height}" fill="{BG}"/>
{body}
<rect width="{width}" height="{height}" fill="url(#scan)"/>
</g>
<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10" fill="none" stroke="{BORDER}"/>
</svg>
"""


def header():
    rng = random.Random(7)
    W, H, dur = 840, 250, 9.0
    bursts = [(2.6, 2.72), (2.85, 2.92), (4.9, 5.0), (6.3, 6.36), (6.5, 6.62), (8.1, 8.2)]
    parts = [code_rain(rng, W, H, 11, 12, PURPLE, 0.16)]
    # terminal title bar
    parts.append(f'<rect width="{W}" height="30" fill="#0c0d16" opacity=".85"/>')
    for i, c in enumerate([RED, PINK, PURPLE]):
        parts.append(f'<circle cx="{20 + i * 18}" cy="15" r="5" fill="{c}"/>')
    parts.append(f'<text x="80" y="20" class="left" fill="{MUTED}" style="font-size:12px">eienmode@github: ~/profile</text>')
    parts.append(f'<text x="{W - 18}" y="20" fill="{MUTED}" style="font-size:12px;text-anchor:end">'
                 f'[ status: online ]<tspan fill="{PINK}" class="blink"> _</tspan></text>')
    # big decoding title with jitter + rgb split
    title = decode_text(rng, TITLE, W / 2, 140, 76, 58, dur, start=0.2, step=0.12, frames=10,
                        out_start=8.3, final_color=WHITE, scramble_colors=[PINK, PURPLE, LILAC, RED], from_zero=True)
    parts.append(rgb_split(TITLE, W / 2, 140, 76, 58, dur, bursts, "split", H))
    parts.append(f'<g>{title}{jitter(dur, bursts, [(-4, 0), (3, 1), (5, 0), (-3, -1), (2, 0), (-5, 0)])}</g>')
    # subtitle decode
    parts.append(decode_text(rng, SUBTITLE, W / 2, 196, 17, 10.6, dur, start=0.5, step=0.025, frames=6,
                             out_start=8.45, final_color=PINK, scramble_colors=[PURPLE, LILAC, MUTED], weight=500))
    parts.append(glitch_bars(rng, W, H, dur, bursts, 18))
    return svg_wrap(W, H, "Eienmode", "\n".join(parts))


def footer():
    rng = random.Random(21)
    W, H, dur = 840, 90, 7.0
    bursts = [(2.3, 2.4), (4.1, 4.16), (4.3, 4.4), (6.0, 6.08)]
    parts = [code_rain(rng, W, H, 5, 11, PURPLE, 0.14)]
    line = decode_text(rng, FOOTER, W / 2, 52, 16, 10, dur, start=0.1, step=0.02, frames=6,
                       out_start=6.4, final_color=PINK, scramble_colors=[PURPLE, LILAC, MUTED], weight=600, from_zero=True)
    parts.append(f'<g>{line}{jitter(dur, bursts, [(-4, 0), (3, 0), (-2, 1), (4, 0)])}</g>')
    parts.append(glitch_bars(rng, W, H, dur, bursts, 10))
    return svg_wrap(W, H, "Thanks for visiting", "\n".join(parts))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, svg in (("header.svg", header()), ("footer.svg", footer())):
        with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"wrote {name} ({len(svg) // 1024} KB)")


if __name__ == "__main__":
    main()
