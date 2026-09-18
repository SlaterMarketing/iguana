#!/usr/bin/env python3
"""Fit a promoter's artwork into the two shapes the site uses, without cropping the poster.

    scripts/fit-poster.py --source ~/Downloads/poster.jpg --stem fredy-el-regio-2026-09-25

Guest promoters send square or portrait art, while event pages want 16:9 and phones want 4:5. Cropping a square
to 16:9 eats the title, so the artwork is placed whole on a blurred, darkened enlargement of itself. Output is
JPEG, like the open mic posters, because Instagram's publishing API takes nothing else.
"""

import argparse
import pathlib

from PIL import Image, ImageEnhance, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHAPES = {'16x9': (1600, 900), '4x5': (1080, 1350)}


def backdrop(image, size):
    """The artwork blown up to fill the frame, blurred and dimmed so the poster on top stays the subject."""
    width, height = size
    scale = max(width / image.width, height / image.height)
    filler = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    left = (filler.width - width) // 2
    top = (filler.height - height) // 2
    filler = filler.crop((left, top, left + width, top + height)).filter(ImageFilter.GaussianBlur(28))
    return ImageEnhance.Brightness(filler).enhance(0.45)


def fit(image, size):
    width, height = size
    canvas = backdrop(image, size)
    scale = min(width / image.width, height / image.height)
    art = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    canvas.paste(art, ((width - art.width) // 2, (height - art.height) // 2))
    return canvas


def save(image, path, max_kb=350):
    path.parent.mkdir(parents=True, exist_ok=True)
    for quality in (88, 82, 76, 70):
        image.save(path, 'JPEG', quality=quality, optimize=True, progressive=True)
        if path.stat().st_size <= max_kb * 1024:
            break
    print(f'{path}  {image.size[0]}x{image.size[1]}  {path.stat().st_size // 1024} KB')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--source', required=True, type=pathlib.Path)
    parser.add_argument('--stem', required=True, help='File name stem, e.g. fredy-el-regio-2026-09-25')
    parser.add_argument('--out', type=pathlib.Path, default=ROOT / 'backend/media/events')
    args = parser.parse_args()

    artwork = Image.open(args.source).convert('RGB')
    for name, size in SHAPES.items():
        save(fit(artwork, size), args.out / f'{args.stem}-{name}.jpg')


if __name__ == '__main__':
    main()
