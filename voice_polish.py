#!/usr/bin/env python3
"""Voice and caption-font fixes for the Hindi Shorts, installed from run_hindi.py and pipeline/flow_images.py.

NO audio editing: the voice comes out of Gemini TTS exactly as generated. Speed, brightness and pauses are controlled only by
the voice design (DESIGN_DESC) and the delivery style (STYLE) sent with every TTS call.

  1. Slow / dim / many pauses: the saved 'designed' Gemini voice was described as a deep, warm, steady-pace baritone, which is
     what made the voice slow and dull. A new bright, fast voice is designed (the voice name changes, so a new one is created
     once per Gemini key; if that fails the old voice is used). The delivery style of every TTS call is replaced by STYLE below.
  2. Captions: the Hindi fonts in assets/hindi_fonts (AMS_*, K26, Kruti-Dev) are old non-Unicode fonts, the renderer rejects
     them (they draw empty boxes for real Hindi text) so the plain Noto font was always used. ensure_fonts() downloads a few
     real Unicode Hindi fonts into that folder before every render, and the renderer picks one at random.

HINDI_FONTS=false turns the font download off. Everything is best effort: any problem is logged and the renderer carries on.
"""
import json
import os

import requests

STYLE = ('Speak as a bright, energetic, confident young Indian male reel creator in fluent, natural, conversational Hindi. '
         'Pace: fast and fluent, clearly quicker than a relaxed reading, about 1.3 times normal speed, every sentence flowing '
         'straight into the next. Pauses: almost none, only a tiny natural breath at commas and a very short beat at the end of a '
         'sentence (well under half a second), never a long silence anywhere, not even before important lines. '
         'Tone: bright, lively, smiling, forward and clear, full of energy and a strong, present, projected voice from the first '
         'word to the last. Keep the excitement and emotion in pitch and intonation only, never by slowing down, dragging or '
         'stretching words, or dropping the volume. Never slow, sleepy, flat, dull, dim, muffled, breathy, soft, whispery or husky.')

DESIGN_NAME = 'Bright fast Hindi reel narrator'
DESIGN_DESC = ('A bright, clear, lively Indian male in his mid-20s speaking fast, fluent, conversational Hindi like a popular reel '
               'creator. Energetic, forward and crisp, with a smiling tone, strong projection and a bright, present timbre. Quick, '
               'flowing pace with very short breaths and no long pauses. Not deep, not slow, not husky, not muffled, not a formal '
               'newsreader.')

FONT_BASE = 'https://raw.githubusercontent.com/google/fonts/main/ofl/'
# real Unicode Hindi fonts with a bold look (file name, folder in google/fonts)
FONTS = [('Hind-Bold.ttf', 'hind'), ('Mukta-ExtraBold.ttf', 'mukta'), ('Khand-Bold.ttf', 'khand'),
         ('Palanquin-Bold.ttf', 'palanquin'), ('Kalam-Bold.ttf', 'kalam'), ('YatraOne-Regular.ttf', 'yatraone'),
         ('RozhaOne-Regular.ttf', 'rozhaone')]


def log(*a):
    print('[voice_polish]', *a, flush=True)


# ----------------------------------------------------------------------------- fonts
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


# ----------------------------------------------------------------------------- voice
def install(rh):
    """Patch render_hindi: new voice design and new delivery style. The audio itself is never edited. Safe to call twice."""
    try:
        if getattr(rh.make_voice, '_styled', False):
            return
        old_name, old_desc = rh.DESIGN_NAME, rh.DESIGN_DESC
        rh.DESIGN_NAME, rh.DESIGN_DESC = DESIGN_NAME, DESIGN_DESC
        orig_designed = rh.designed_voice_id

        def designed_voice_id(label, key):
            v = orig_designed(label, key)
            if v:
                return v
            log('the new designed voice could not be made, using the old one')
            rh.DESIGN_NAME, rh.DESIGN_DESC = old_name, old_desc
            try:
                return orig_designed(label, key)
            finally:
                rh.DESIGN_NAME, rh.DESIGN_DESC = DESIGN_NAME, DESIGN_DESC

        rh.designed_voice_id = designed_voice_id
        orig = rh.make_voice

        def make_voice(text, path):
            try:
                p = json.loads(os.environ.get('PAYLOAD') or '{}')
                p['gemini_style'] = STYLE
                os.environ['PAYLOAD'] = json.dumps(p, ensure_ascii=False)
            except Exception as e:  # noqa
                log('could not set the voice style:', str(e)[:100])
            orig(text, path)

        make_voice._styled = True
        rh.make_voice = make_voice
        log('installed: bright fast voice design and delivery style (no audio editing)')
    except Exception as e:  # noqa
        log('install failed, the old voice settings stay:', str(e)[:150])
