#!/usr/bin/env python3
"""Fit a flyer into a Story frame so Instagram cannot clip it.

    scripts/fit-story.py openmic-en-flyer.jpg openmic-en-flyer-9x16-safe.jpg

Stories are 1080x1920, but Instagram draws its own furniture over the frame: the account bar across the top and
the CTA sticker and reply bar across the bottom. Meta's guidance is to keep anything that has to be READ out of
the top 14% and the bottom 20%. A flyer that fills the frame therefore loses its headline and its address, which
is exactly what happened here: "Stand Up in Playa!" was cut off above the fold and "Iguana Comedy Club" sat
under the Registrarte button.

Handing Meta a 4:5 flyer is worse again, because it zooms to fill 9:16 and cuts both ends.

So: the whole flyer, uncropped, inside the safe band, on a blurred enlargement of itself so the frame still
fills edge to edge and reads as designed rather than letterboxed. Nothing is cropped and nothing is covered.
"""

import argparse
import pathlib
import sys

from PIL import Image, ImageEnhance, ImageFilter

STORY = (1080, 1920)
# Meta's own numbers for Stories and Reels.
TOP_RESERVED = 0.14
BOTTOM_RESERVED = 0.20


def backdrop(image, size):
    """The artwork blown up to fill the frame, blurred and dimmed so the flyer on top stays the subject."""
    width, height = size
    scale = max(width / image.width, height / image.height)
    filler = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    left = (filler.width - width) // 2
    top = (filler.height - height) // 2
    filler = filler.crop((left, top, left + width, top + height)).filter(ImageFilter.GaussianBlur(28))
    return ImageEnhance.Brightness(filler).enhance(0.35)


def fit_story(source, destination):
    art = Image.open(source).convert('RGB')
    width, height = STORY
    top = round(height * TOP_RESERVED)
    bottom = round(height * BOTTOM_RESERVED)
    safe_height = height - top - bottom

    scale = min(width / art.width, safe_height / art.height)
    placed = art.resize((round(art.width * scale), round(art.height * scale)), Image.LANCZOS)

    frame = backdrop(art, STORY)
    frame.paste(placed, ((width - placed.width) // 2, top + (safe_height - placed.height) // 2))
    frame.save(destination, 'JPEG', quality=90, optimize=True, progressive=True)
    return placed.size, (top, top + safe_height)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('destination')
    args = parser.parse_args()

    source = pathlib.Path(args.source).expanduser()
    if not source.exists():
        sys.exit(f'no such file: {source}')
    size, band = fit_story(source, pathlib.Path(args.destination).expanduser())
    print(f'{source.name} -> {args.destination}: flyer {size[0]}x{size[1]} inside the safe band y={band[0]}..{band[1]}')


if __name__ == '__main__':
    main()
