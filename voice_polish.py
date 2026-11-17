#!/usr/bin/env python3
"""Voice and caption-font fixes for the Hindi Shorts, installed from run_hindi.py and pipeline/flow_images.py.

What it fixes
  1. Slow / dim / many pauses: the saved 'designed' Gemini voice was described as a deep, warm, steady-pace baritone, which
     is exactly what made the voice slow and dull. A new bright, fast voice is designed (the voice name changes, so a new one is
     created once per Gemini key; if that fails the old voice is used). The delivery style sent with every TTS call is
     replaced by a fast, bright, no-long-pauses style (STYLE below).
  2. After the voice is made it is polished with ffmpeg: long pauses are cut down to a short breath, the voice is sped up a
     little (pitch kept) and given a small presence boost + gentle compression so it sounds brighter and louder in the mix.
     Word timing is worked out AFTER this, so captions stay in sync.
  3. Captions: the Hindi fonts in assets/hindi_fonts (AMS_*, K26, Kruti-Dev) are old non-Unicode fonts, the renderer rejects
     them (they draw empty boxes for real Hindi text) so the plain Noto font was always used. ensure_fonts() downloads a few
     real Unicode Hindi fonts into that folder before every render, and the renderer picks one at random.

Tuning (environment variables, all optional)
  VOICE_TEMPO   speed-up of the finished voice, default 1.15 (1.0 = off, max 1.30)
  PAUSE_KEEP    seconds of silence left where a long pause was cut, default 0.18
  VOICE_POLISH  'false' turns the ffmpeg polish off
  HINDI_FONTS   'false' turns the font download off
Everything is best effort: any problem is logged and the renderer simply carries on as before.
"""
import json
import os
import subprocess

import requests

STYLE = ('A bright, energetic, confident young Indian male reel narrator speaking fluent Hindi. Fast, punchy, continuous delivery, '
         'about 1.3 times faster than a relaxed reading, with no long pauses: only tiny natural breaths between phrases and under '
         '0.3 seconds between sentences. A lively, smiling, forward and clear voice with strong projection, a bright present '
         'timbre and crisp consonants, full of energy from the first word to the last. Emotion comes from pitch and tone, never '
         'from slowing down, stretching words or going quiet. Never slow, sleepy, flat, dull, dim, muffled, breathy, soft or husky.')

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


def _num(name, default, lo, hi):
    try:
        v = float(os.environ.get(name, '').strip() or default)
    except ValueError:
        v = default
    return min(hi, max(lo, v))


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
def polish_file(rh, path):
    """Cut long pauses, speed the voice up a little, make it brighter. Keeps the original file when anything looks wrong."""
    if os.environ.get('VOICE_POLISH', '').strip().lower() == 'false':
        return
    try:
        before = rh.audio_duration(path)
        tempo = _num('VOICE_TEMPO', 1.15, 1.0, 1.30)
        keep = _num('PAUSE_KEEP', 0.18, 0.05, 0.6)
        chain = ','.join([
            'silenceremove=start_periods=1:start_duration=0.02:start_threshold=-50dB:stop_periods=-1:stop_duration=0.30:'
            'stop_threshold=-42dB:stop_silence=' + format(keep, '.2f'),
            'atempo=' + format(tempo, '.3f'),
            'highpass=f=70',
            'equalizer=f=250:t=q:w=1:g=-2',
            'equalizer=f=3200:t=q:w=1.2:g=3.5',
            'acompressor=threshold=0.1:ratio=3:attack=5:release=60:makeup=2',
            'alimiter=limit=0.95',
        ])
        tmp = path + '.polish.wav'
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', path, '-af', chain, '-ar', '24000', '-ac', '1', tmp], check=True)
        after = rh.audio_duration(tmp)
        if after < max(2.0, before * 0.4):
            log('polish looked wrong (' + format(before, '.1f') + 's -> ' + format(after, '.1f') + 's), keeping the original voice')
            os.remove(tmp)
            return
        os.replace(tmp, path)
        log('voice polished: ' + format(before, '.1f') + 's -> ' + format(after, '.1f') + 's (pauses cut to ' + format(keep, '.2f') +
            's, tempo x' + format(tempo, '.2f') + ', brighter)')
    except Exception as e:  # noqa
        log('voice polish failed, keeping the original voice:', str(e)[:150])


def install(rh):
    """Patch render_hindi: new voice design, new delivery style, polish after every voice that is made. Safe to call twice."""
    try:
        if getattr(rh.make_voice, '_polished', False):
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
            polish_file(rh, path)

        make_voice._polished = True
        rh.make_voice = make_voice
        log('installed: bright fast voice style, pause cutting and tempo x' + format(_num('VOICE_TEMPO', 1.15, 1.0, 1.30), '.2f'))
    except Exception as e:  # noqa
        log('install failed, the old voice settings stay:', str(e)[:150])
