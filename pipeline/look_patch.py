"""Look and sound switches for the Hindi Shorts renderer (render_hindi.py and render_hindi_overlay.py stay unchanged).

Installed by run_hindi.py, after music_picker.install(), the same way voice_patch is installed. Every switch is read from the payload
(the job file, which a chat package fills; see pipeline/package.py):

  background   plain BLACK portrait screen by default: black above and below the square picture, the hook above the square.
               Only when the payload says "random_bg": true (or "background": "random") is one of the artwork backgrounds picked at random.
  captions     a little smaller than the old 88 px, placed just BELOW the square picture (CAPTION_GAP px under its bottom edge),
               for both the black screen and the random backgrounds.
  hook         bigger, sits just ABOVE the square (HOOK_GAP px over its top edge); its key words are drawn in a random highlight colour
               (the words named in the package hook "focus", else the longest one or two words).
  music        no background music by default. Only when the payload says "bgm": true is a song picked (by mood, music_picker.py).
"""
import json
import os
import random

from PIL import Image, ImageDraw

BLACK_SQUARE_TOP = 340        # px from the top of the 1080 x 1920 frame to the top of the square picture (hook goes above it)
CAPTION_GAP = 85              # px from the bottom edge of the square to the middle of the (first) caption line
CAPTION_SIZES = (62, 58, 54, 50, 46)     # was 88 down to 56, then 50 down to 34
CAPTION_STROKE = 6
HOOK_MAX_SIZE = 92            # was 78
HOOK_GAP = 36                 # px between the bottom of the hook text and the top edge of the square
HOOK_STROKE = 6
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


def key_indices(hov, tokens, focus):
    """Which hook words get the colour: the words of the package hook focus, else the longest one or two words."""
    fw = [hov._norm(x) for x in str(focus or '').split() if hov._norm(x)]
    idx = set(i for i, t in enumerate(tokens) if hov._norm(t) in fw) if fw else set()
    if idx:
        return idx
    order = sorted(range(len(tokens)), key=lambda i: -len(hov._norm(tokens[i])))
    n = 1 if len(tokens) <= 3 else 2
    return set(i for i in order[:n] if len(hov._norm(tokens[i])) >= 3)


def install_hook(hov):
    orig_init = hov.HookOverlay.__init__

    def hook_init(self, line, focus=''):
        self.img = None
        self.focus = focus
        if not line:
            return
        try:
            self.img = self._build(line)
            hov._log('hook:', line)
        except Exception as e:  # noqa
            hov._log('hook skipped:', str(e)[:150])

    def hook_build(self, line):
        W, top_h = hov.CFG['W'], hov.CFG['HOOK_H']
        custom = hov.CFG.get('custom_font') or ''
        fp = custom or hov._hook_font_path()
        latin_fp = hov._hook_font_path()
        tokens = line.split(' ')
        max_w = hov.CFG['PW'] - 90
        chosen = None
        for size in range(HOOK_MAX_SIZE, 35, -3):
            fonts = [hov._font(latin_fp if (custom and hov._font_kind(t) == 'latin') else fp, size) for t in tokens]
            space = size * 0.30
            wid = [fonts[i].getlength(t) for i, t in enumerate(tokens)]
            lh = int(size * 1.3)

            def width(a, b):
                return sum(wid[a:b]) + space * (b - a - 1)

            n = len(tokens)
            if width(0, n) <= max_w and lh <= top_h - 40:
                chosen = (fonts, size, space, wid, [(0, n)], lh)
                break
            best = None
            for cut in range(1, n):
                m = max(width(0, cut), width(cut, n))
                if best is None or m < best[0]:
                    best = (m, cut)
            if best and best[0] <= max_w and 2 * lh <= top_h - 24:
                chosen = (fonts, size, space, wid, [(0, best[1]), (best[1], n)], lh)
                break
        if not chosen:
            raise RuntimeError('hook does not fit')
        fonts, size, space, wid, spans, lh = chosen
        keys = key_indices(hov, tokens, getattr(self, 'focus', ''))
        pool = [c for c in hov.HIGHLIGHTS if c != hov.STATE.get('hl')] or list(hov.HIGHLIGHTS)
        key_colour = random.choice(pool)
        hov._log('hook key words:', [tokens[i] for i in sorted(keys)], 'colour', key_colour)
        layer = Image.new('RGBA', (W, top_h), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        block = lh * len(spans)
        bottom = max(block + 4, top_h - HOOK_GAP)          # the text block ends HOOK_GAP px above the square
        y_first = bottom - block + lh / 2.0
        for li, (a, b) in enumerate(spans):
            tw = sum(wid[a:b]) + space * (b - a - 1)
            x = (W - tw) / 2
            cy = y_first + li * lh
            for i in range(a, b):
                colour = key_colour if i in keys else hov.HOOK_WHITE
                d.text((x, cy), tokens[i], font=fonts[i], fill=colour, anchor='lm', stroke_width=HOOK_STROKE, stroke_fill=hov.OUTLINE)
                x += wid[i] + space
        return layer

    hov.HookOverlay.__init__ = hook_init
    hov.HookOverlay._build = hook_build


def install(rh):
    hov = rh.hov
    hov.CAPTION_SIZES = CAPTION_SIZES
    hov.CAPTION_FROM_BOTTOM = -CAPTION_GAP          # the caption sits CAPTION_GAP px below the square (the original code centred it on the edge)

    orig_init = hov.CaptionTrack.__init__

    def caption_init(self, words):
        orig_init(self, words)
        self.stroke = CAPTION_STROKE

    hov.CaptionTrack.__init__ = caption_init

    try:
        install_hook(hov)
    except Exception as e:  # noqa
        rh.log('hook patch not installed, the old hook is used: ' + str(e)[:150])

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
