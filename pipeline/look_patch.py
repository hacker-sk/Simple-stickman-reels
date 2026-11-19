"""Look and sound of the simple reels (render_hindi.py and render_hindi_overlay.py stay unchanged). Installed by run_hindi.py.

  background   always plain BLACK portrait screen: black above and below the square picture, the hook above the square.
  captions     small, placed just BELOW the square picture (CAPTION_GAP px under its bottom edge).
  hook         bigger, sits just ABOVE the square (HOOK_GAP px over its top edge); its key words are drawn in a random highlight colour
               (the words named in the package hook "focus", else the longest one or two words).
  music        never.
"""
import random

from PIL import Image, ImageDraw

BLACK_SQUARE_TOP = 340        # px from the top of the 1080 x 1920 frame to the top of the square picture (hook goes above it)
CAPTION_GAP = 85              # px from the bottom edge of the square to the middle of the (first) caption line
CAPTION_SIZES = (62, 58, 54, 50, 46)
CAPTION_STROKE = 6
HOOK_MAX_SIZE = 92
HOOK_GAP = 36                 # px between the bottom of the hook text and the top edge of the square
HOOK_STROKE = 6


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
    hov.CAPTION_FROM_BOTTOM = -CAPTION_GAP

    orig_init = hov.CaptionTrack.__init__

    def caption_init(self, words):
        orig_init(self, words)
        self.stroke = CAPTION_STROKE

    hov.CaptionTrack.__init__ = caption_init
    install_hook(hov)

    def setup(payload, w, h, here, font_fn, log_fn):
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

    hov.setup = setup

    def pick_music(mood):
        rh.log('music: off')
        return None, ''

    rh.pick_music = pick_music
