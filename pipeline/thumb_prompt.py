#!/usr/bin/env python3
"""Writes the Google Flow prompt file for the reel THUMBNAIL from the package (see .github/workflows/shorts.yml, prepare job).

The package carries an optional field "thumbnail_prompt": one English image prompt for a vertical 9:16 thumbnail (with the art style text at its
end, like every other image prompt). When it is there, this writes flow-batch/prompts/shorts_thumb.json (a list with that one prompt); the flow job
then makes it first, in PORTRAIT, switches Flow back to the square scene settings and makes the scene images. Without the field no file is written
and no thumbnail is made. Plain JSON handling only, so it needs no Python packages.
"""
import argparse
import json
import os
import sys

MAX_PROMPT = 1900


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--package', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    if os.path.exists(a.out):
        os.remove(a.out)
    try:
        with open(a.package, encoding='utf-8') as fh:
            data = json.load(fh)
    except Exception as e:  # noqa
        print('[thumb_prompt] package not readable, no thumbnail: ' + str(e)[:100])
        return 0
    prompt = ''
    if isinstance(data, dict):
        prompt = str(data.get('thumbnail_prompt') or data.get('thumbnailPrompt') or '').strip()
    prompt = ' '.join(prompt.split())[:MAX_PROMPT]
    if len(prompt) < 40:
        print('[thumb_prompt] the package has no thumbnail_prompt, no thumbnail this time')
        return 0
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, 'w', encoding='utf-8') as fh:
        json.dump([prompt], fh, ensure_ascii=False, indent=1)
    print('[thumb_prompt] thumbnail prompt written (' + str(len(prompt)) + ' characters)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
