"""Look and sound switches for the Hindi Shorts renderer (render_hindi.py and render_hindi_overlay.py stay unchanged).

Installed by run_hindi.py, after music_picker.install(), the same way voice_patch is installed. Every switch is read from the payload
(the job file, which a chat package fills; see pipeline/package.py):

  background   plain BLACK portrait screen by default: black above and below the square picture, the hook above the square.
               Only when the payload says "random_bg": true (or "background": "random") is one of the artwork backgrounds picked at random.
  captions     much smaller than before and placed BELOW the square picture with some space (CAPTION_GAP px under its bottom edge),
               for both the black screen and the random backgrounds.
  music        no background music by default. Only when the payload says "bgm": true is a song picked (by mood, music_picker.py).
"""
import json
import os
import random

from PIL import Image

BLACK_SQUARE_TOP = 340        # px from the top of the 1080 x 1920 frame to the top of the square picture (hook goes above it)
CAPTION_GAP = 130             # px from the bottom edge of the square to the middle of the caption block
CAPTION_SIZES = (50, 46, 42, 38, 34)     # was 88 down to 56
CAPTION_STROKE = 5            # was 8, a thinner outline suits the smaller text
_TRUE = ('1', 'true', 'yes', 'y', 'on')


def _flag(v):
    if isinstance(v, bool):
        return v
    return str(v if v is not None else '').strip().lower() in _TRUE


def wants_random_bg(payload):
    if not isinstance(payload, dict):
        return False
    return _flag(payload.get('random_bg')) or str(payload.get('background') or '').strip().lower() == 'random'


def wants_bgm():
    """True only when the job asks for music. render_hindi.main() puts the job (without the scene texts) in the PAYLOAD variable."""
    try:
        payload = json.loads(os.environ.get('PAYLOAD') or '{}')
    except ValueError:
        return False
    return isinstance(payload, dict) and (_flag(payload.get('bgm')) or _flag(payload.get('music')))


def black_layout(w, h):
    top = min(BLACK_SQUARE_TOP, max(0, h - w - 200))
    return {'bg': Image.new('RGB', (w, h), (0, 0, 0)), 'box': (0, top, w, top + w), 'pw': w, 'ph': w, 'hook_h': top}


def install(rh):
    hov = rh.hov
    hov.CAPTION_SIZES = CAPTION_SIZES
    hov.CAPTION_FROM_BOTTOM = -CAPTION_GAP          # the caption block sits CAPTION_GAP px below the square (the original code centred it on the edge)

    orig_init = hov.CaptionTrack.__init__

    def caption_init(self, words):
        orig_init(self, words)
        self.stroke = CAPTION_STROKE

    hov.CaptionTrack.__init__ = caption_init

    orig_setup = hov.setup

    def setup(payload, w, h, here, font_fn, log_fn):
        if wants_random_bg(payload):
            if log_fn:
                log_fn('background: random artwork (the payload asked for random_bg)')
            return orig_setup(payload, w, h, here, font_fn, log_fn)
        try:
            lay = black_layout(w, h)
            hov.CFG.update(W=w, H=h, HERE=here, font=font_fn, log=log_fn)
            hov.STATE['layout'] = lay
            hov.STATE['hook'] = None
            hov.CFG['custom_font'] = hov.pick_custom_font(here, log_fn)
            hov.STATE['hl'] = random.choice(hov.HIGHLIGHTS)
            hov.CFG.update(PW=lay['pw'], PH=lay['ph'], HOOK_H=lay['hook_h'], HOOK_Y_OFFSET=14,
                           CAP_LAST_Y=lay['box'][3] + CAPTION_GAP)
            line, focus = hov.hook_text(payload)
            hov.STATE['hook'] = hov.HookOverlay(line, focus)
            if log_fn:
                log_fn('background: plain black, square picture at y %d-%d, captions below it' % (lay['box'][1], lay['box'][3]))
            return lay
        except Exception as e:  # noqa
            if log_fn:
                log_fn('black background setup failed, using the artwork backgrounds instead: ' + str(e)[:150])
            return orig_setup(payload, w, h, here, font_fn, log_fn)

    hov.setup = setup

    orig_pick = rh.pick_music

    def pick_music(mood):
        if not wants_bgm():
            rh.log('music: off, the payload did not ask for bgm')
            return None, ''
        return orig_pick(mood)

    rh.pick_music = pick_music
