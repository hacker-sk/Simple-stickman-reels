#!/usr/bin/env python3
"""Starts the Hindi renderer with the mood based music picker (music_picker.py) and the Unicode caption fonts (hindi_fonts.py) installed.

Used by render_hindi.yml (n8n runs) and by pipeline/run_shorts.py (Hindi Shorts / chat packages).
RENDER_TARGET (optional) is the renderer to run: render_hindi.py (default) or render_hindi_flow.py.
The voice is NOT patched here: render_hindi.py makes it natively from the voice description and delivery style in the payload
(gemini_voice_desc, gemini_style), with its own defaults when the payload has none.
"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import render_hindi as rh  # noqa: E402
import music_picker  # noqa: E402
import hindi_fonts  # noqa: E402

if __name__ == '__main__':
    hindi_fonts.ensure_fonts(HERE)      # real Unicode Hindi fonts for the captions (the fonts in the repo are old non-Unicode ones)
    music_picker.install(rh)            # quieter song
    target = os.environ.get('RENDER_TARGET', '').strip()
    if target and os.path.basename(target) != 'render_hindi.py':
        # render_hindi_flow.py imports render_hindi, which is the module patched above
        runpy.run_path(target, run_name='__main__')
    else:
        rh.main()
