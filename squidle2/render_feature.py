"""Render the Play Store feature graphic: the Squidle2 launcher composition, Albers squares and
all, beside the wordmark.

usage: uv run --with pillow==11.3.0 python render_feature.py <nexus_sans.ttf> <out_dir> [<site-nexus-syntegra>]

The Play graphic carries the wordmark alone, so one image serves every listing language. With the
site repo given, also writes its English hero, og:image and press-kit copies, which add the title
and tagline.
"""
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from render import draw_mascot, oklch_to_rgb, ramp_rgb
from render_art import GREY_SQUARES, OFF, SCALE, S, quantize_layers

# Play's required size is 1024x500; the master is drawn at twice that and the mascot is redrawn
# crisp at each size, since downsampling the 2x pixels would soften every cell edge.
W, H = 1024, 500

HEADLINE = "NEXUS CHAT"
TITLE = "PRIVATE AI AGENT"
TAGLINE = "On-device AI that browses, codes and sees"


def font(path, px, weight):
    f = ImageFont.truetype(path, px)
    f.set_variation_by_axes([weight])
    return f


def fit(path, text, weight, width, tracking):
    """Largest font whose tracked line fits `width`."""
    px = 400
    while px > 8:
        f = font(path, px, weight)
        if tracked_width(f, text, tracking * px) <= width:
            return f, tracking * px
        px -= 1
    raise ValueError(f"{text!r} cannot fit {width}px")


def tracked_width(f, text, gap):
    return sum(f.getlength(ch) for ch in text) + gap * (len(text) - 1)


def draw_tracked(d, xy, text, f, gap, fill):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill)
        x += f.getlength(ch) + gap


def ramp_fill(size, text_mask, x0, x1):
    """The accent ramp from x0 to x1, held flat outside it, through the mask's alpha."""
    w, h = size
    strip = Image.new("RGB", (w, 1))
    for x in range(w):
        strip.putpixel((x, 0), ramp_rgb((x - x0) / max(1, x1 - x0)))
    layer = strip.resize((w, h))
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    out.paste(layer, mask=text_mask)
    return out


def chamfer(box, cut):
    """The app's plate outline: square corners, top-right and bottom-left cut."""
    x0, y0, x1, y1 = box
    return [(x0, y0), (x1 - cut, y0), (x1, y0 + cut), (x1, y1), (x0 + cut, y1), (x0, y1 - cut)]


def ground(w, h, panel_right):
    """The Albers frame's outermost grey, so the icon's squares sit in the banner with no edge,
    and a faint indigo lift under the type. The lift is held at zero up to the panel's edge:
    the panel is opaque, and any lift it covered would end there as a visible line."""
    bg = Image.new("RGB", (w, h), GREY_SQUARES[0])
    lift = Image.new("L", (w, h), 0)
    ImageDraw.Draw(lift).ellipse([w * 0.44, h * 0.16, w * 0.96, h * 0.84], fill=255)
    lift = lift.filter(ImageFilter.GaussianBlur(h * 0.20))
    ramp_in = w * 0.10
    hold = Image.new("L", (w, 1))
    hold.putdata([round(255 * min(1, max(0, (x - panel_right) / ramp_in))) for x in range(w)])
    bg.paste((12, 11, 24), mask=ImageChops.multiply(lift, hold.resize((w, h))))
    return bg


def compose(layers, scale, font_path, words):
    w, h = W * scale, H * scale
    back, front = layers
    side = h
    px, py = round(w * 0.03), 0
    canvas = ground(w, h, px + side)
    canvas.paste(back.resize((side, side), Image.LANCZOS), (px, py))
    canvas = canvas.convert("RGBA")
    mascot = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    draw_mascot(mascot, side, SCALE, (0, OFF[1] * side / S))
    mascot.alpha_composite(front.resize((side, side), Image.LANCZOS))
    canvas.alpha_composite(mascot, (px, py))

    # Type block: wordmark in the accent ramp; with `words`, title in white and tagline on a chamfered plate.
    left, right = round(w * 0.515), round(w * 0.955)
    width = right - left
    head, head_gap = fit(font_path, HEADLINE, 700, width, 0.02)
    title, title_gap = fit(font_path, TITLE, 600, width * 0.80, 0.10)
    seam_gap, plate_pad = round(h * 0.045), round(h * 0.030)
    # The plate's cut runs about 0.04h; the tagline shrinks before the plate would overrun the column.
    tag, _ = fit(font_path, TAGLINE, 500, width - 2 * plate_pad - h * 0.04, 0.0)
    if tag.size > h * 0.046:
        tag = font(font_path, round(h * 0.046), 500)

    head_box = head.getbbox(HEADLINE)
    title_box = title.getbbox(TITLE)
    head_h, title_h = head_box[3] - head_box[1], title_box[3] - title_box[1]
    tag_box = tag.getbbox(TAGLINE)
    plate_h = (tag_box[3] - tag_box[1]) + 2 * plate_pad
    block = head_h + seam_gap * 2 + title_h + round(h * 0.07) + plate_h if words else head_h
    y = round((h - block) / 2)

    mask = Image.new("L", (w, h), 0)
    draw_tracked(ImageDraw.Draw(mask), (left - head_box[0], y - head_box[1]), HEADLINE, head, head_gap, 255)
    head_w = round(tracked_width(head, HEADLINE, head_gap))
    glow = ramp_fill((w, h), mask.filter(ImageFilter.GaussianBlur(h * 0.03)).point(lambda v: v * 0.55), left, left + head_w)
    canvas = Image.alpha_composite(canvas, glow)
    canvas.alpha_composite(ramp_fill((w, h), mask, left, left + head_w))
    y += head_h + seam_gap

    # The seam: a hairline in the ramp, the divider the app draws between plates.
    d = ImageDraw.Draw(canvas)
    seam = max(1, round(h * 0.004))
    for x in range(left, left + head_w):
        u = (x - left) / max(1, head_w - 1)
        a = int(255 * min(1, 1.6 * (1 - u)))
        d.line([(x, y), (x, y + seam - 1)], fill=ramp_rgb(u) + (a,))
    if not words:
        return canvas.convert("RGB")
    y += seam + seam_gap

    draw_tracked(d, (left - title_box[0], y - title_box[1]), TITLE, title, title_gap, (244, 246, 250, 255))
    y += title_h + round(h * 0.07)

    tag_w = round(tag.getlength(TAGLINE))
    cut = round(plate_h * 0.32)
    box = (left, y, left + tag_w + 2 * plate_pad + cut, y + plate_h)
    plate = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pd = ImageDraw.Draw(plate)
    pd.polygon(chamfer(box, cut), fill=oklch_to_rgb(0.19, 0.035, 280) + (235,))
    edge = Image.new("L", (w, h), 0)
    ed = ImageDraw.Draw(edge)
    ed.polygon(chamfer(box, cut), fill=255)
    inner = max(1, round(h * 0.003))
    ed.polygon(chamfer((box[0] + inner, box[1] + inner, box[2] - inner, box[3] - inner), cut - inner * 0.4), fill=0)
    canvas.alpha_composite(plate)
    canvas.alpha_composite(ramp_fill((w, h), edge, box[0], box[2]))
    ImageDraw.Draw(canvas).text((left + plate_pad - tag_box[0], y + plate_pad - tag_box[1]), TAGLINE,
                                font=tag, fill=(214, 220, 236, 255))
    return canvas.convert("RGB")


def main(font_path, out, site=None):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    layers = quantize_layers(frame=True)
    for scale, name, site_name in ((1, "feature_graphic.png", "nexus_feature_graphic.png"),
                                   (2, "feature_graphic_2048.png", "nexus_feature_graphic_large.png")):
        renders = [(out / name, False)] + ([(Path(site) / "public" / site_name, True)] if site else [])
        for path, words in renders:
            img = compose(layers, scale, font_path, words)
            img.save(path, optimize=True)
            print(path, img.size)


if __name__ == "__main__":
    main(*sys.argv[1:4])
