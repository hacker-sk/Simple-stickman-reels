#!/usr/bin/env python3
"""Starts the Hindi renderer with the mood based music picker (music_picker.py) installed.

Used by render_hindi.yml (n8n runs) and by pipeline/run_shorts.py (Hindi Shorts / chat packages).
RENDER_TARGET (optional) is the renderer to run: render_hindi.py (default) or render_hindi_flow.py.
The renderers themselves are unchanged; this file only swaps in the new pick_music and then runs them.
"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import render_hindi as rh  # noqa: E402
import music_picker  # noqa: E402

if __name__ == '__main__':
    music_picker.install(rh)
    target = os.environ.get('RENDER_TARGET', '').strip()
    if target and os.path.basename(target) != 'render_hindi.py':
        # render_hindi_flow.py imports render_hindi, which is the module patched above
        runpy.run_path(target, run_name='__main__')
    else:
        rh.main()
