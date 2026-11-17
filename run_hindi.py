#!/usr/bin/env python3
"""Starts the Hindi renderer with the mood based music picker (music_picker.py) and the voice/font fixes (voice_polish.py) installed.

Used by render_hindi.yml (n8n runs) and by pipeline/run_shorts.py (Hindi Shorts / chat packages).
RENDER_TARGET (optional) is the renderer to run: render_hindi.py (default) or render_hindi_flow.py.
The renderers themselves are unchanged; this file only swaps in the new functions and then runs them.
"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import render_hindi as rh  # noqa: E402
import music_picker  # noqa: E402
import voice_polish  # noqa: E402

if __name__ == '__main__':
    voice_polish.ensure_fonts(HERE)     # real Unicode Hindi fonts for the captions (the fonts in the repo are old non-Unicode ones)
    voice_polish.install(rh)            # brighter, faster voice with short pauses
    music_picker.install(rh)            # quieter song
    target = os.environ.get('RENDER_TARGET', '').strip()
    if target and os.path.basename(target) != 'render_hindi.py':
        # render_hindi_flow.py imports render_hindi, which is the module patched above
        runpy.run_path(target, run_name='__main__')
    else:
        rh.main()
