#!/usr/bin/env python3
"""Make the open mic event banners and the default social share images from frames of the hero video.

    scripts/make-banners.py --fonts DIR [--out backend/media/events] [--og-out public/media]

DIR must contain BebasNeue-Regular.ttf and DMSans.ttf (the static TTFs from github.com/google/fonts, OFL; the site
itself ships woff2, which Pillow cannot read). Frames come from public/media/hero.mp4 via ffmpeg.

Each open mic night gets a 16:9 poster (event pages, Facebook) and a 4:5 one (phones, Instagram), written in the
language the show is in. Output is JPEG because Instagram's publishing API only takes JPEG.
"""

import argparse
import pathlib
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
AMBER = (251, 191, 36)
WHITE = (255, 255, 255)
INK = (10, 10, 10)

BANNERS = [
    # (file stem, video second, focus x for 16:9 and 4:5 crops (0 left .. 1 right), kicker, big, second line, pill, footer)
    # Each night gets artwork in both site languages: the Spanish night also has an English-labelled poster for /en/,
    # and the English night a Spanish-labelled one for /es/. The stem suffix is the language of the WORDS.
    ('open-mic-es', 57, (0.44, 0.44), 'CADA MARTES', 'OPEN MIC', 'EN ESPAÑOL', 'ENTRADA GRATIS', 'Iguana Comedy · Playa del Carmen'),
    ('open-mic-es-en', 57, (0.44, 0.44), 'EVERY TUESDAY', 'OPEN MIC', 'IN SPANISH', 'FREE ENTRY', 'Iguana Comedy · Playa del Carmen'),
    ('open-mic-en', 3, (0.62, 0.8), 'EVERY WEDNESDAY', 'OPEN MIC', 'IN ENGLISH', 'FREE ENTRY', 'Iguana Comedy · Playa del Carmen'),
    ('open-mic-en-es', 3, (0.62, 0.8), 'CADA MIÉRCOLES', 'OPEN MIC', 'EN INGLÉS', 'ENTRADA GRATIS', 'Iguana Comedy · Playa del Carmen'),
]
SHARE = [
    ('og-default-en', 3, (0.5, 0.5), 'PLAYA DEL CARMEN', 'STAND-UP COMEDY', 'INTERNATIONAL COMEDY CLUB', 'FREE OPEN MICS TUE & WED', 'iguanacomedy.com'),
    ('og-default-es', 3, (0.5, 0.5), 'PLAYA DEL CARMEN', 'STAND UP EN VIVO', 'CLUB DE COMEDIA INTERNACIONAL', 'OPEN MIC GRATIS MAR Y MIÉ', 'iguanacomedy.com'),
]


def frame(second, workdir):
    path = pathlib.Path(workdir) / f'frame-{second}.png'
    subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(second), '-i', str(ROOT / 'public/media/hero.mp4'),
                    '-frames:v', '1', '-y', str(path)], check=True)
    return Image.open(path).convert('RGB')


def crop_to(image, width, height, focus_x):
    """Crop to the target aspect ratio around focus_x (0 left, 1 right), then resize."""
    target = width / height
    w, h = image.size
    if w / h > target:
        new_w = round(h * target)
        left = min(max(round(w * focus_x - new_w / 2), 0), w - new_w)
        image = image.crop((left, 0, left + new_w, h))
    else:
        new_h = round(w / target)
        image = image.crop((0, (h - new_h) // 2, w, (h - new_h) // 2 + new_h))
    return image.resize((width, height), Image.LANCZOS)


def shade(image, direction):
    """Darken towards the text side so white type stays readable on any frame."""
    width, height = image.size
    overlay = Image.new('L', (width, height))
    draw = ImageDraw.Draw(overlay)
    steps = width if direction == 'left' else height
    for i in range(steps):
        t = 1 - i / steps if direction == 'left' else i / steps
        alpha = int(40 + 185 * max(0.0, min(1.0, t * 1.35 - 0.1)))
        if direction == 'left':
            draw.line([(i, 0), (i, height)], fill=alpha)
        else:
            draw.line([(0, i), (width, i)], fill=alpha)
    return Image.composite(Image.new('RGB', image.size, INK), image, overlay)


def spaced(draw, xy, text, font, fill, spacing):
    x, y = xy
    for char in text:
        draw.text((x, y), char, font=font, fill=fill)
        x += draw.textlength(char, font=font) + spacing
    return x


def spaced_width(draw, text, font, spacing):
    return sum(draw.textlength(c, font=font) + spacing for c in text) - spacing


def logo(height):
    mark = Image.open(ROOT / 'public/media/logo-hero.png').convert('RGBA')
    mark = mark.resize((round(mark.width * height / mark.height), height), Image.LANCZOS)
    white = Image.new('RGBA', mark.size, WHITE + (255,))
    white.putalpha(mark.getchannel('A'))
    return white


def render(base, size, focus_x, texts, fonts, layout, share=False):
    kicker, big, line2, pill, footer = texts
    width, height = size
    image = shade(crop_to(base, width, height, focus_x), 'left' if layout == 'left' else 'bottom')
    draw = ImageDraw.Draw(image)
    scale = width / 1600 if layout == 'left' else width / 1080
    bebas = lambda px: ImageFont.truetype(str(fonts / 'BebasNeue-Regular.ttf'), round(px * scale))

    def sans(px, weight):
        font = ImageFont.truetype(str(fonts / 'DMSans.ttf'), round(px * scale))
        font.set_variation_by_axes([14, weight])
        return font

    pad = round(90 * scale)
    mark = logo(round(64 * scale))
    image.paste(mark, (pad, pad), mark)

    # Share images carry longer lines on a smaller canvas, so their type is set smaller.
    k = 0.72 if share else 1.0
    blocks = [
        ('kicker', kicker, sans(34 * k, 700), WHITE, round(8 * scale)),
        ('big', big, bebas((250 if layout == 'left' else 230) * k), WHITE, 0),
        ('line2', line2, bebas((120 if layout == 'left' else 112) * k), WHITE, round(2 * scale)),
        ('pill', pill, bebas(76 * k), INK, round(2 * scale)),
        ('footer', footer, sans(34 * k, 500), (230, 230, 230), 0),
    ]
    gaps = {'kicker': 22, 'big': 22, 'line2': 36, 'pill': 36, 'footer': 0}
    heights = []
    for kind, text, font, _, spacing in blocks:
        top, bottom = font.getbbox(text)[1], font.getbbox(text)[3]
        heights.append((bottom - top) + (round(46 * scale) if kind == 'pill' else 0))
    total = sum(heights) + sum(round(gaps[k] * scale) for k, *_ in blocks[:-1])
    y = height - pad - total if layout == 'bottom' else (height - total) // 2 + round(40 * scale)

    for (kind, text, font, fill, spacing), block_h in zip(blocks, heights):
        text_w = spaced_width(draw, text, font, spacing)
        if kind == 'pill':
            box_w = text_w + round(56 * scale)
            x = pad if layout == 'left' else (width - box_w) // 2
            draw.rounded_rectangle([x, y, x + box_w, y + block_h], radius=round(16 * scale), fill=AMBER)
            spaced(draw, (x + round(28 * scale), y + round(23 * scale) - font.getbbox(text)[1]), text, font, fill, spacing)
        else:
            x = pad if layout == 'left' else (width - text_w) // 2
            spaced(draw, (x, y - font.getbbox(text)[1]), text, font, fill, spacing)
        y += block_h + round(gaps[kind] * scale)
    return image


def save(image, path, max_kb=350):
    path.parent.mkdir(parents=True, exist_ok=True)
    for quality in (88, 82, 76, 70):
        image.save(path, 'JPEG', quality=quality, optimize=True, progressive=True)
        if path.stat().st_size <= max_kb * 1024:
            break
    print(f'{path.relative_to(ROOT)}  {image.size[0]}x{image.size[1]}  {path.stat().st_size // 1024} KB')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--fonts', required=True, type=pathlib.Path)
    parser.add_argument('--out', type=pathlib.Path, default=ROOT / 'backend/media/events')
    parser.add_argument('--og-out', type=pathlib.Path, default=ROOT / 'public/media')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as workdir:
        for stem, second, focus_x, *texts in BANNERS:
            base = frame(second, workdir)
            save(render(base, (1600, 900), focus_x[0], texts, args.fonts, 'left'), args.out / f'{stem}-16x9.jpg')
            save(render(base, (1080, 1350), focus_x[1], texts, args.fonts, 'bottom'), args.out / f'{stem}-4x5.jpg')
        for stem, second, focus_x, *texts in SHARE:
            save(render(frame(second, workdir), (1200, 630), focus_x[0], texts, args.fonts, 'left', share=True),
                 args.og_out / f'{stem}.jpg', 250)


if __name__ == '__main__':
    main()
