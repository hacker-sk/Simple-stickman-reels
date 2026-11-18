#!/usr/bin/env python3
"""Starts the Hindi renderer with the mood based music picker (music_picker.py), the Unicode caption fonts (hindi_fonts.py) and the look patch installed.

Used by render_hindi.yml (n8n runs) and by pipeline/run_shorts.py (Hindi Shorts / chat packages).
RENDER_TARGET (optional) is the renderer to run: render_hindi.py (default) or render_hindi_flow.py.
The voice (Gemini prebuilt Iapetus + description + the delivery style of the script) comes from the payload (gemini_voice, gemini_style); the
same voice text is built by pipeline/voice_patch.py for prepare (pipeline/flow_images.py) and for this job, so the voice is the same whichever
job makes it. Forced-alignment-first word timing is installed from there too.
pipeline/look_patch.py switches the look and sound by payload: black background unless random_bg, small captions under the square, no music unless bgm.
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
    try:
        from pipeline import voice_patch
        voice_patch.apply_voice(rh)               # voice description text (the designed voice is no longer used)
        voice_patch.apply_forced_alignment(rh)    # forced alignment first when this job has to time the words
    except Exception as e:  # noqa
        print('[run_hindi] voice/alignment patch not installed, renderer defaults are used: ' + str(e)[:200], flush=True)
    try:
        from pipeline import look_patch
        look_patch.install(rh)                    # black background, small captions under the square, music only on request
    except Exception as e:  # noqa
        print('[run_hindi] look patch not installed, the old look and music are used: ' + str(e)[:200], flush=True)
    target = os.environ.get('RENDER_TARGET', '').strip()
    if target and os.path.basename(target) != 'render_hindi.py':
        # render_hindi_flow.py imports render_hindi, which is the module patched above
        runpy.run_path(target, run_name='__main__')
    else:
        rh.main()
