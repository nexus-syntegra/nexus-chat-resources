"""Abstract art studies of the Squidle2 app icon.

usage: python render_art.py <out_dir> [study ...]
"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from render import (
    INK,
    boost,
    cell_rgb,
    draw_mascot,
    gradient_field,
    hex_to_oklch,
    mascot_mask,
    oklch_to_rgb,
    premultiplied,
    ramp,
    ramp_rgb,
)

SIZE = 1024
S = SIZE * 3
SCALE = 1.16
C = S / 24 * SCALE
OX = S / 2 - 12 * C
OY = S / 2 - 12 * C - 0.5 * C
OFF = (0, -0.5 * C)


def square(d, cx, cy, side, ang, fill):
    h = side / 2
    ca, sa = math.cos(ang), math.sin(ang)
    d.polygon([(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in ((-h, -h), (h, -h), (h, h), (-h, h))], fill=fill)


def base():
    bg = Image.new("RGB", (S, S), (0, 0, 0))
    lift = Image.new("L", (S, S), 0)
    ImageDraw.Draw(lift).ellipse([S * 0.2, S * 0.16, S * 0.8, S * 0.8], fill=255)
    bg.paste((12, 10, 30), mask=lift.filter(ImageFilter.GaussianBlur(S * 0.14)))
    return bg


def halo(bg, sil, k=0.42):
    field = gradient_field(S // 4).resize((S, S), Image.BICUBIC)
    h = sil.filter(ImageFilter.GaussianBlur(S * 0.06)).point(lambda v: min(255, int(v * 1.5 * k)))
    bg.paste(field, mask=h)


def falloff(bg, sil, cap=215):
    f = sil.filter(ImageFilter.GaussianBlur(S * 0.011)).point(lambda v: min(cap, int(v * 1.7)))
    bg.paste(INK, mask=f)


def finish(bg):
    out = bg.resize((SIZE, SIZE), Image.LANCZOS).convert("RGBA")
    draw_mascot(out, SIZE, SCALE, (0, OFF[1] / 3))
    return out


def ellipse_pt(u, cx=0.5, cy=0.54, rx=0.44, ry=0.15, tilt=-18):
    a = math.radians(200) + math.radians(320) * u
    ex, ey = rx * S * math.cos(a), ry * S * math.sin(a)
    t = math.radians(tilt)
    return cx * S + ex * math.cos(t) - ey * math.sin(t), cy * S + ex * math.sin(t) + ey * math.cos(t)


# The flare made of pixels: a Saturn ring of quantized light that dissolves at its ends
def ring_particles(rnd):
    """(side, x, y, angle, rgba, front) squares along the orbit."""
    parts = []
    def add(u, spread, side, alpha):
        x, y = ellipse_pt(u)
        x2, y2 = ellipse_pt(min(1, u + 1e-3))
        tx, ty = x2 - x, y2 - y
        n = math.hypot(tx, ty) or 1
        nx, ny = -ty / n, tx / n
        o = rnd.gauss(0, spread)
        x, y = x + nx * o, y + ny * o
        if rnd.random() < 0.7:
            q = C / 4  # most of the light locks to a quarter-pixel grid; the rest drifts free
            x, y, ang = round(x / q) * q, round(y / q) * q, 0.0
        else:
            ang = math.radians(rnd.uniform(-30, 30))
        L, Ch, H = ramp(u)
        col = oklch_to_rgb(min(0.9, L + rnd.uniform(-0.04, 0.05)), Ch, H)
        a = math.radians(200) + math.radians(320) * u
        parts.append((side, x, y, ang, col + (int(alpha),), math.sin(a) > 0.15))
    for i in range(170):
        u = (i + rnd.random()) / 170
        taper = math.sin(math.pi * u) ** 0.8
        add(u, C * 0.12 * (1.3 - taper), C * (0.12 + 0.40 * taper) * rnd.uniform(0.75, 1.0), 255 * min(1, 0.35 + taper))
    for _ in range(90):
        u = rnd.random() ** 2.2 * 0.3
        u = u if rnd.random() < 0.5 else 1 - u
        taper = math.sin(math.pi * u) ** 0.8
        add(u, C * (0.3 + 0.9 * (1 - taper)), C * rnd.uniform(0.07, 0.2), 255 * rnd.uniform(0.35, 0.8))
    return sorted(parts, key=lambda p: -p[0])


def drop_squares():
    """(side, x, y, angle, rgba) pixels shed from each tentacle tip in a shrinking, slowing
    column, in that tip's colour."""
    out = []
    for gx, gy, drift in ((8, 17, -0.12), (11, 18, -0.04), (13, 18, 0.04), (16, 17, 0.12)):
        tip = cell_rgb(gx, gy, "b")
        y = OY + (gy + 1) * C
        for k in range(1, 5):
            side = C * 0.62 * 0.66 ** k
            y += C * 0.38 + side * 0.9 + C * 0.10 * k
            cx = OX + (gx + 0.5) * C + drift * C * k * k * 0.5
            out.append((side, cx, y, math.radians(7 * k * (1 if drift > 0 else -1)), tip + (int(240 - 45 * k),)))
    return out


def tip_drops(d):
    for side, x, y, ang, col in drop_squares():
        square(d, x, y, side, ang, col)


def pixel_ring():
    rnd = random.Random(7)
    bg = base()
    sil = mascot_mask(S, SCALE, OFF)
    halo(bg, sil)
    parts = ring_particles(rnd)
    back = Image.new("RGB", (S, S), (0, 0, 0))
    bd = ImageDraw.Draw(back, "RGBA")
    front = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    fd = ImageDraw.Draw(front)
    glow = Image.new("RGB", (S, S), (0, 0, 0))
    gd = ImageDraw.Draw(glow, "RGBA")
    for side, x, y, ang, col, is_front in parts:
        square(gd, x, y, side, ang, col)
        square(fd if is_front else bd, x, y, side, ang, col)
    tip_drops(bd)
    tip_drops(gd)
    falloff(bg, sil, cap=170)
    bg = ImageChops.screen(bg, boost(glow.filter(ImageFilter.GaussianBlur(S * 0.028)), 1.2))
    bg = ImageChops.screen(bg, boost(glow.filter(ImageFilter.GaussianBlur(S * 0.007)), 0.55))
    bg = ImageChops.screen(bg, back)
    out = finish(bg)
    out.alpha_composite(front.resize((SIZE, SIZE), Image.LANCZOS))
    return out


# Light quantizing: the flare is continuous where it is brightest
# and breaks into pixels toward its ends, the same pixels Squidle is made of.
def lifted(squares, swoop):
    """Loose pixels set off from what lies under them: a short dark dip that fades out close
    to the pixel, a soft bloom in the pixel's own colour, then the crisp pixel. Without them,
    cyan pixels over the cyan head dissolve into it.

    `swoop` is the ribbon's coverage. No dip falls on it: pixels there belong to the ribbon
    and should melt into its light, not be cut out of it."""
    ink = Image.new("L", (S, S), 0)
    halo = Image.new("L", (S, S), 0)
    tint = Image.new("RGB", (S, S), (0, 0, 0))
    crisp = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    idr, hd, td, cd = ImageDraw.Draw(ink), ImageDraw.Draw(halo), ImageDraw.Draw(tint), ImageDraw.Draw(crisp)
    # Falloff and bloom are drawn grown from each pixel and only lightly blurred: one blur
    # wide enough for the big pixels averages the small ones down to nothing.
    for side, x, y, ang, col in sorted(squares, key=lambda p: -p[0]):
        a = col[3]
        square(idr, x, y, side * 1.5 + S * 0.0015, ang, a)
        square(hd, x, y, side * 1.2, ang, int(a * 0.6))
        # The bloom's colour is spread wider than any bloom reaches, so its edge never shows.
        L, Ch, H = hex_to_oklch("#{:02x}{:02x}{:02x}".format(*col[:3]))
        square(td, x, y, side * 3 + S * 0.004, ang, oklch_to_rgb(min(0.92, L + 0.05), Ch, H))
        square(cd, x, y, side, ang, col)
    out = Image.new("RGBA", (S, S), INK + (0,))
    # Gain on a short blur: dark up close, then a fast fade.
    ink = ink.filter(ImageFilter.GaussianBlur(S * 0.0025)).point(lambda v: min(235, int(v * 1.7)))
    # High gain: where the ribbon dissolves into its pixels its own alpha is faint, and a dip
    # there would cut the pixels out of the ribbon they continue.
    away = swoop.filter(ImageFilter.GaussianBlur(S * 0.012)).point(lambda v: 255 - min(255, int(v * 8)))
    out.putalpha(ImageChops.multiply(ink, away))
    bloom = tint.filter(ImageFilter.GaussianBlur(S * 0.002))
    bloom.putalpha(halo.filter(ImageFilter.GaussianBlur(S * 0.0045)))
    out.alpha_composite(bloom)
    out.alpha_composite(crisp)
    return out


def smoothstep(a, b, x):
    t = min(1, max(0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def continuity(u):
    return smoothstep(0.04, 0.30, u) * (1 - smoothstep(0.52, 0.74, u))


def quantize_layers(frame=False):
    """(background RGB, front RGBA) at the supersampled size: the mascot goes between them."""
    rnd = random.Random(5)
    bg = albers_field(*GREY_SQUARES) if frame else base()
    sil = mascot_mask(S, SCALE, OFF)
    halo(bg, sil)
    shade = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    body = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    core = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sd, bd, cd = ImageDraw.Draw(shade), ImageDraw.Draw(body), ImageDraw.Draw(core)
    for i in range(1601):
        u = i / 1600
        k = continuity(u)
        if k <= 0.002:
            continue
        x, y = ellipse_pt(u)
        taper = math.sin(math.pi * u) ** 0.8
        alpha = min(1, taper * 1.4) * k
        w = (S * 0.036 * taper + 1) * (0.55 + 0.45 * k)
        L, Ch, H = ramp(u)
        q = w * 3.2
        sd.ellipse([x - q / 2, y - q / 2, x + q / 2, y + q / 2], fill=INK + (int(150 * alpha),))
        bd.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=oklch_to_rgb(L, Ch, H) + (int(255 * alpha),))
        c = w * 0.3
        cd.ellipse([x - c / 2, y - c / 2, x + c / 2, y + c / 2], fill=oklch_to_rgb(min(0.95, L + 0.14), Ch * 0.6, H) + (int(205 * alpha),))
    bg.paste(INK, mask=shade.filter(ImageFilter.GaussianBlur(S * 0.016)).split()[3])

    glow = Image.new("RGB", (S, S), (0, 0, 0))
    gd = ImageDraw.Draw(glow, "RGBA")
    parts, fronts, backs = [], [], drop_squares()

    def put(u, o, side, ang, alpha):
        x, y = ellipse_pt(u)
        x2, y2 = ellipse_pt(min(1, u + 1e-3))
        n = math.hypot(x2 - x, y2 - y) or 1
        x, y = x - (y2 - y) / n * o, y + (x2 - x) / n * o
        if ang == 0:
            g = C / 4
            x, y = round(x / g) * g, round(y / g) * g
        L, Ch, H = ramp(u)
        col = oklch_to_rgb(min(0.9, L + rnd.uniform(-0.04, 0.05)), Ch, H)
        front = math.sin(math.radians(200) + math.radians(320) * u) > 0.15
        parts.append((side, x, y, ang, col + (int(alpha),), front))

    def chain(u0, u1):
        """The ribbon rasterized: a band of pixels that thins, shrinks and spreads out."""
        u, sign = u0, 1 if u1 > u0 else -1
        w0 = S * 0.036 * math.sin(math.pi * u0) ** 0.8
        while (u1 - u) * sign > 0.005:
            prog = (u - u0) / (u1 - u0)
            side = w0 * 0.42 * (1 - prog) ** 0.85 + C * 0.07
            band = w0 * (1 - prog) ** 0.7
            across = max(1, round(band / side))
            for j in range(across):
                if rnd.random() < 0.12 + 0.45 * prog:
                    continue
                o = (j - (across - 1) / 2) * side * 1.05 + rnd.gauss(0, C * 0.6 * prog ** 1.5)
                free = rnd.random() < 0.15 + 0.5 * prog
                ang = math.radians(rnd.uniform(-35, 35)) * prog if free else 0
                put(u, o, side * rnd.uniform(0.8, 1.0), ang, 255 * (1 - 0.55 * prog))
            x, y = ellipse_pt(u)
            x2, y2 = ellipse_pt(u + 1e-3 * sign)
            per_u = math.hypot(x2 - x, y2 - y) / 1e-3
            u += sign * side * (1.05 + 1.5 * prog ** 1.6) / per_u

    chain(0.60, 0.985)
    chain(0.24, 0.02)

    # A corner pixel's echo drifts off the head, turning as it goes.
    for gx, gy, side, rot, alpha in ((15.55, 5.45, 0.62, 9, 235), (16.75, 4.35, 0.4, 21, 200), (17.7, 3.55, 0.24, 34, 160)):
        echo = (side * C, OX + gx * C, OY + gy * C, math.radians(rot), ramp_rgb(0) + (alpha,))
        square(gd, *echo[1:3], echo[0], *echo[3:])
        fronts.append(echo)
    for side, x, y, ang, col, is_front in sorted(parts, key=lambda p: -p[0]):
        square(gd, x, y, side, ang, col)
        (fronts if is_front else backs).append((side, x, y, ang, col))
    tip_drops(gd)

    light = premultiplied(body)
    swoop = body.getchannel("A")
    bg = ImageChops.screen(bg, boost(light.filter(ImageFilter.GaussianBlur(S * 0.03)), 1.5))
    bg = ImageChops.screen(bg, boost(glow.filter(ImageFilter.GaussianBlur(S * 0.024)), 1.1))
    bg = bg.convert("RGBA")
    bg.alpha_composite(body)
    bg.alpha_composite(core)
    bg = ImageChops.screen(bg.convert("RGB"), boost(light.filter(ImageFilter.GaussianBlur(S * 0.008)), 0.8))
    bg = ImageChops.screen(bg, boost(glow.filter(ImageFilter.GaussianBlur(S * 0.006)), 0.5)).convert("RGBA")
    # After the screens: a screened glow laid over the ink falloff would wash it back out.
    bg.alpha_composite(lifted(backs, swoop))
    bg = bg.convert("RGB")
    # Over the lighter grey squares a full-strength shade would read as a dark aura.
    falloff(bg, sil, cap=150 if frame else 215)
    return bg, lifted(fronts, swoop)


def quantize(frame=False):
    bg, front = quantize_layers(frame)
    out = finish(bg)
    out.alpha_composite(front.resize((SIZE, SIZE), Image.LANCZOS))
    return out


# Homage to the Square (Albers): stepped fields, pixels slip out of the frame
def albers_field(outer, steps):
    """Nested squares, each sitting low in the one around it (Albers' rhythm)."""
    bg = Image.new("RGB", (S, S), outer)
    d = ImageDraw.Draw(bg)
    for w, col in steps:
        gap = (1 - w) * S
        d.rectangle([S / 2 - w * S / 2, gap * 0.6, S / 2 + w * S / 2, gap * 0.6 + w * S], fill=col)
    return bg


# Neutral greys a few steps apart: the squares stay behind the colour.
GREY_SQUARES = ((10, 10, 11), ((0.86, (15, 15, 17)), (0.72, (21, 21, 23)), (0.60, (27, 27, 29)), (0.48, (34, 34, 37))))


def albers():
    bg = albers_field(oklch_to_rgb(0.13, 0.035, 288),
                      [(w, oklch_to_rgb(L, Ch, H)) for w, L, Ch, H in
                       ((0.86, 0.175, 0.06, 286), (0.72, 0.225, 0.09, 280), (0.60, 0.28, 0.12, 268))])
    sil = mascot_mask(S, SCALE, OFF)
    halo(bg, sil, k=0.5)
    falloff(bg, sil, cap=180)
    light = Image.new("RGB", (S, S), (0, 0, 0))
    ld = ImageDraw.Draw(light, "RGBA")
    # A diagonal of shrinking pixels leaves the head through the frame's corner.
    x, y = OX + 17.6 * C, OY + 6.2 * C
    for k in range(5):
        side = C * 0.7 * 0.7 ** k
        square(ld, x, y, side, math.radians(-9 * k), ramp_rgb(0.05 * k) + (255 - 30 * k,))
        x += side * 0.9 + C * 0.35
        y -= side * 0.75 + C * 0.25
    tip_drops(ld)
    bg = ImageChops.screen(bg, boost(light.filter(ImageFilter.GaussianBlur(S * 0.02)), 1.0))
    bg = ImageChops.screen(bg, light)
    return finish(bg)


def swoop():
    return quantize(frame=True)


STUDIES = {"swoop": swoop, "quantize": quantize, "pixel_ring": pixel_ring, "albers": albers}


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    names = sys.argv[2:] or list(STUDIES)
    imgs = []
    for n in names:
        im = STUDIES[n]()
        im.save(out / f"squidle2_art_{n}.png")
        imgs.append(im)
    sheet = Image.new("RGB", (512 * len(imgs) + 16 * (len(imgs) + 1), 544 + 112), (24, 24, 28))
    mask = Image.new("L", (96, 96), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, 95, 95], fill=255)
    for i, im in enumerate(imgs):
        sheet.paste(im.resize((512, 512), Image.LANCZOS), (16 + i * 528, 16))
        # Launcher-size preview: the adaptive icon's visible 72/108 crop, circle-masked.
        crop = im.crop((171, 171, 853, 853)).resize((96, 96), Image.LANCZOS)
        sheet.paste(crop, (16 + i * 528 + 208, 544), mask)
    sheet.save(out / "squidle2_art_sheet.png")


if __name__ == "__main__":
    main(sys.argv[1])
