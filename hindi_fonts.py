#!/usr/bin/env python3
"""Unicode Hindi caption fonts, installed from run_hindi.py.

The Hindi fonts in assets/hindi_fonts (AMS_*, K26, Kruti-Dev) are old non-Unicode fonts, the renderer rejects them (they draw
empty boxes for real Hindi text) so the plain Noto font was always used. ensure_fonts() downloads a few real Unicode Hindi fonts
into that folder before every render, and the renderer picks one at random.

(Moved out of the removed voice_polish.py. The voice is no longer patched: render_hindi.py makes it natively.)

HINDI_FONTS=false turns the font download off. Everything is best effort: any problem is logged and the renderer carries on.
"""
import os

import requests

FONT_BASE = 'https://raw.githubusercontent.com/google/fonts/main/ofl/'
# real Unicode Hindi fonts with a bold look (file name, folder in google/fonts)
FONTS = [('Hind-Bold.ttf', 'hind'), ('Mukta-ExtraBold.ttf', 'mukta'), ('Khand-Bold.ttf', 'khand'),
         ('Palanquin-Bold.ttf', 'palanquin'), ('Kalam-Bold.ttf', 'kalam'), ('YatraOne-Regular.ttf', 'yatraone'),
         ('RozhaOne-Regular.ttf', 'rozhaone')]


def log(*a):
    print('[hindi_fonts]', *a, flush=True)


def ensure_fonts(here):
    """Download the Unicode Hindi fonts that are not in assets/hindi_fonts yet. Never raises."""
    if os.environ.get('HINDI_FONTS', '').strip().lower() == 'false':
        return
    folder = os.path.join(here, 'assets', 'hindi_fonts')
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError as e:
        log('font folder not usable:', str(e)[:100])
        return
    got = 0
    for name, d in FONTS:
        dest = os.path.join(folder, name)
        if os.path.exists(dest) and os.path.getsize(dest) > 30000:
            got += 1
            continue
        try:
            r = requests.get(FONT_BASE + d + '/' + name, timeout=40)
            if r.status_code == 200 and len(r.content) > 30000:
                with open(dest, 'wb') as fh:
                    fh.write(r.content)
                got += 1
            else:
                log('font not downloaded:', name, 'HTTP', r.status_code)
        except Exception as e:  # noqa
            log('font download failed:', name, str(e)[:100])
    log('Unicode Hindi fonts ready:', got, 'of', len(FONTS))
