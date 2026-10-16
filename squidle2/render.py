"""Render Squidle2: the Squidle pixel mascot in the Nexus cyan/purple palette.

usage: uv run --with pillow==11.3.0 python render.py <out_dir>
"""
import math
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

CYAN = "#20DCFF"
PURPLE = "#BD5AFF"

# 24x24 grid. Body and tentacles from the original squidle_icon.png; the face from the
# first app icon (nexus_squid_icon.png): 3x3 eyes in a 12-cell head, the pupil low
# and right with a catchlight. b body, c highlight, f shadow, w eye white, d pupil,
# k pupil cell carrying the catchlight, e blush.
GRID = """\
........................
........................
........................
........................
........................
........................
.........bbbbbb.........
........bcccbbbb........
.......bccbbbbbbb.......
......bbwwwbbwwwbb......
......bbwkdbbwkdbb......
......bewddbbwddeb......
.......bbbbbbbffb.......
........bbbbbffb........
.........b.b.b.b........
.........b.b.b.b........
........f..b.b..f.......
........f..f.f..f.......
...........f.f..........
........................
........................
........................
........................
........................""".splitlines()


# --- OKLab / OKLCH -----------------------------------------------------------

def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gam(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def hex_to_oklch(h):
    r, g, b = (_lin(int(h[i:i + 2], 16) / 255) for i in (1, 3, 5))
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    A = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    B = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return L, math.hypot(A, B), math.degrees(math.atan2(B, A)) % 360


def _oklch_to_linear(L, C, H):
    A, B = C * math.cos(math.radians(H)), C * math.sin(math.radians(H))
    l = (L + 0.3963377774 * A + 0.2158037573 * B) ** 3
    m = (L - 0.1055613458 * A - 0.0638541728 * B) ** 3
    s = (L - 0.0894841775 * A - 1.2914855480 * B) ** 3
    return (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)


def oklch_to_rgb(L, C, H):
    """sRGB tuple; chroma is reduced until the colour fits the gamut."""
    lo, hi = 0.0, C
    rgb = _oklch_to_linear(L, 0, H)
    for _ in range(30):
        mid = (lo + hi) / 2
        cand = _oklch_to_linear(L, mid, H)
        if all(-1e-4 <= v <= 1 + 1e-4 for v in cand):
            lo, rgb = mid, cand
        else:
            hi = mid
    if all(-1e-4 <= v <= 1 + 1e-4 for v in _oklch_to_linear(L, C, H)):
        rgb = _oklch_to_linear(L, C, H)
    return tuple(round(255 * _gam(min(1, max(0, v)))) for v in rgb)


A1, A2 = hex_to_oklch(CYAN), hex_to_oklch(PURPLE)


def ramp(t, dip=0.07):
    """Accent 1 to accent 2 the short way round the hue wheel (through blue).

    Lightness dips mid-ramp: blue at the endpoints' lightness is out of sRGB
    gamut, and clipping its chroma would turn the middle pastel.
    """
    t = min(1, max(0, t))
    dh = (A2[2] - A1[2] + 540) % 360 - 180
    L = A1[0] + (A2[0] - A1[0]) * t - dip * math.sin(math.pi * t)
    return (L, A1[1] + (A2[1] - A1[1]) * t, (A1[2] + dh * t) % 360)


def ramp_rgb(t):
    return oklch_to_rgb(*ramp(t))


# --- the mascot --------------------------------------------------------------

def cells():
    for gy, row in enumerate(GRID):
        for gx, ch in enumerate(row):
            if ch != ".":
                yield gx, gy, ch


BODY = [(x, y) for x, y, _ in cells()]
X0, X1 = min(x for x, _ in BODY), max(x for x, _ in BODY)
Y0, Y1 = min(y for _, y in BODY), max(y for _, y in BODY)


# The body is lit along a diagonal: accent 1 at the top left, accent 2 at the
# bottom right, the direction the swoop sweeps. One field over the whole squid,
# so no colour boundary falls between the head and the tentacles.
LIGHT_ANGLE = math.radians(40)
# A shallower dip than the swoop's: on body pixels a dark mid-ramp blue reads as bruising.
BODY_DIP = 0.025


def _along_light(x, y):
    return x * math.cos(LIGHT_ANGLE) + y * math.sin(LIGHT_ANGLE)


_LIT0, _LIT1 = _along_light(X0 + 2, Y0 + 1), _along_light(X1, Y1)


def body_t(gx, gy):
    return min(1, max(0, (_along_light(gx + 0.5, gy + 0.5) - _LIT0) / (_LIT1 - _LIT0)))


def body_ramp(t):
    return ramp(t, BODY_DIP)


def tone(t, ch):
    """Colour of a cell of kind `ch` at position `t` on the body ramp."""
    L, C, H = body_ramp(t)
    if ch == "b":
        return oklch_to_rgb(L, C, H)
    if ch == "c":
        return oklch_to_rgb(min(0.95, L + 0.08), C * 0.6, H - 6)
    if ch == "f":
        # Shadows only darken: one leaning toward accent 2 lands as a violet
        # patch under the right eye and reads as a bruise. Darkened from the
        # body's in-gamut colour, since a darker L fits chroma the body lost to
        # clipping and the shadow would come out more vivid than the body.
        L, C, H = hex_to_oklch("#{:02x}{:02x}{:02x}".format(*oklch_to_rgb(L, C, H)))
        return oklch_to_rgb(L - 0.08, C, H)
    if ch == "w":
        return (255, 255, 255)
    if ch in "dk":
        return oklch_to_rgb(0.17, 0.05, 285)
    if ch == "e":
        # Coral, the original blush: a magenta one sinks into the purple below it.
        return oklch_to_rgb(0.81, 0.10, 12)
    raise ValueError(ch)


def cell_rgb(gx, gy, ch):
    if ch == "f" and gy >= 14:
        # Tentacles are one cell wide: a shadow cell there reads as a gap in the
        # light, not as form.
        ch = "b"
    return tone(body_t(gx, gy), ch)


# The catchlight is smaller than a cell, as in the first app icon: a whole white
# cell would read as a third eye white, not as a glint.
CATCH_OFFSET = (0.33, 0.27)
CATCH_SIDE = 0.6


def catchlights():
    """Top-left corners, in cells, of each pupil's catchlight square."""
    return [(gx + CATCH_OFFSET[0], gy + CATCH_OFFSET[1]) for gx, gy, ch in cells() if ch == "k"]


def draw_mascot(img, size, scale=1.0, offset=(0, 0)):
    d = ImageDraw.Draw(img)
    c = size / 24 * scale
    ox = size / 2 - 12 * c + offset[0]
    oy = size / 2 - 12 * c + offset[1]
    for gx, gy, ch in cells():
        x, y = ox + gx * c, oy + gy * c
        d.rectangle([round(x), round(y), round(x + c) - 1, round(y + c) - 1], fill=cell_rgb(gx, gy, ch) + (255,))
    for gx, gy in catchlights():
        x, y, k = ox + gx * c, oy + gy * c, CATCH_SIDE * c
        d.rectangle([round(x), round(y), round(x + k) - 1, round(y + k) - 1], fill=(255, 255, 255, 255))


def mascot_mask(size, scale, offset):
    m = Image.new("L", (size, size), 0)
    tmp = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw_mascot(tmp, size, scale, offset)
    m.paste(tmp.split()[3])
    return m


def gradient_field(size, angle_deg=35):
    """Full-canvas accent gradient along a diagonal."""
    g = Image.new("RGB", (size, size))
    px = g.load()
    a = math.radians(angle_deg)
    dx, dy = math.cos(a), math.sin(a)
    proj = [(x * dx + y * dy) for x, y in ((0, 0), (size, 0), (0, size), (size, size))]
    lo, hi = min(proj), max(proj)
    lut = [ramp_rgb(i / 255) for i in range(256)]
    for y in range(size):
        for x in range(size):
            px[x, y] = lut[int(255 * ((x * dx + y * dy) - lo) / (hi - lo))]
    return g


# --- compositions ------------------------------------------------------------

def plain(size, bg):
    img = Image.new("RGBA", (size, size), bg)
    draw_mascot(img, size)
    return img


INK = (5, 4, 16)  # near-black indigo for the soft shadows


def premultiplied(layer):
    """RGB with colour scaled by alpha, ready for additive (screen) light."""
    return Image.composite(layer.convert("RGB"), Image.new("RGB", layer.size, (0, 0, 0)), layer.split()[3])


def boost(img, gain):
    return img.point(lambda v: min(255, int(v * gain)))


def orbit_layers(S):
    """The orbit as light: a feathered shade under it, colour body, hot core."""
    shade = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    body = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    core = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sd, bd, cd = ImageDraw.Draw(shade), ImageDraw.Draw(body), ImageDraw.Draw(core)
    cx, cy, rx, ry, tilt = S * 0.5, S * 0.54, S * 0.44, S * 0.15, math.radians(-18)
    a0, a1 = math.radians(200), math.radians(520)
    n = 1600
    for i in range(n + 1):
        u = i / n
        a = a0 + (a1 - a0) * u
        ex, ey = rx * math.cos(a), ry * math.sin(a)
        x = cx + ex * math.cos(tilt) - ey * math.sin(tilt)
        y = cy + ex * math.sin(tilt) + ey * math.cos(tilt)
        taper = math.sin(math.pi * u) ** 0.8
        alpha = min(1, taper * 1.4)
        w = S * 0.036 * taper + 1
        L, C, H = ramp(u)
        k = w * 3.2
        sd.ellipse([x - k / 2, y - k / 2, x + k / 2, y + k / 2], fill=INK + (int(150 * alpha),))
        bd.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=oklch_to_rgb(L, C, H) + (int(255 * alpha),))
        c = w * 0.3
        cd.ellipse([x - c / 2, y - c / 2, x + c / 2, y + c / 2], fill=oklch_to_rgb(min(0.95, L + 0.14), C * 0.6, H) + (int(205 * alpha),))
    # The shade has no edge of its own: it is blurred until it reads only as
    # the surrounding dark deepening toward the light.
    shade = shade.filter(ImageFilter.GaussianBlur(S * 0.016))
    core = core.filter(ImageFilter.GaussianBlur(S * 0.003))
    return shade, body, core


def app_icon(size, ribbon):
    S = size * 3
    scale = 1.04
    off = (0, -0.5 * S / 24 * scale)
    bg = Image.new("RGBA", (S, S), (0, 0, 0, 255))
    lift = Image.new("L", (S, S), 0)
    ImageDraw.Draw(lift).ellipse([S * 0.2, S * 0.16, S * 0.8, S * 0.8], fill=255)
    lift = lift.filter(ImageFilter.GaussianBlur(S * 0.14))
    bg.paste(Image.new("RGBA", (S, S), (12, 10, 30, 255)), mask=lift)

    field = gradient_field(S // 4).resize((S, S), Image.BICUBIC).convert("RGBA")
    sil = mascot_mask(S, scale, off)
    halo = sil.filter(ImageFilter.GaussianBlur(S * 0.06)).point(lambda v: min(255, int(v * 1.5)))
    bg.paste(field, mask=halo.point(lambda v: int(v * 0.42)))

    if not ribbon:
        # With no orbit to light the scene, the mascot is the light source:
        # its own colours bloom outward, cyan from the head, purple below.
        own = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        draw_mascot(own, S, scale, off)
        light = premultiplied(own)
        wide = boost(light.filter(ImageFilter.GaussianBlur(S * 0.045)), 1.6)
        tight = boost(light.filter(ImageFilter.GaussianBlur(S * 0.016)), 0.9)
        bg = ImageChops.screen(ImageChops.screen(bg.convert("RGB"), wide), tight).convert("RGBA")
    if ribbon:
        shade, body, core = orbit_layers(S)
        bg.alpha_composite(shade)
        # Bloom is added as light (screen), so it brightens what is under it
        # instead of painting over it: a wide soft bloom and a tight hot one.
        light = premultiplied(body)
        wide = boost(light.filter(ImageFilter.GaussianBlur(S * 0.03)), 1.5)
        tight = boost(light.filter(ImageFilter.GaussianBlur(S * 0.008)), 0.8)
        bg = ImageChops.screen(bg.convert("RGB"), wide).convert("RGBA")
        bg.alpha_composite(body)
        bg.alpha_composite(core)
        bg = ImageChops.screen(bg.convert("RGB"), tight).convert("RGBA")

    # Soft shade around the mascot: dark at its edge, fading to nothing, so
    # the pixels stand off the glow without a drawn outline.
    falloff = sil.filter(ImageFilter.GaussianBlur(S * 0.011)).point(lambda v: min(215, int(v * 1.7)))
    bg.paste(Image.new("RGBA", (S, S), INK + (255,)), mask=falloff)

    out = bg.resize((size, size), Image.LANCZOS)
    draw_mascot(out, size, scale, (off[0] / 3, off[1] / 3))
    return out


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    plain(1024, (255, 255, 255, 255)).save(out / "squidle2_icon.png")
    plain(1024, (0, 0, 0, 0)).save(out / "squidle2_icon_transparent.png")
    app_icon(1024, ribbon=False).save(out / "squidle2_app_icon_glow.png")
    app_icon(1024, ribbon=True).save(out / "squidle2_app_icon_flare.png")
    print("A1", A1, "A2", A2, "mid", ramp(0.5), ramp_rgb(0.5))


if __name__ == "__main__":
    main(sys.argv[1])
