#!/usr/bin/env python3
"""Starts the Hindi renderer (render_hindi.py) with the simple-reel patches:

- Unicode Hindi caption fonts (hindi_fonts.py)
- forced-alignment word timing first, Whisper timing as fallback (pipeline/voice_patch.py)
- plain black background, small captions under the square, no music (pipeline/look_patch.py)
- voice: Gemini only (GEMINI_API_KEY, GEMINI_API_KEY_2)
- images: Cloudflare only (CF_ACCOUNT_ID / CF_API_TOKEN and the _2 pair)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import render_hindi as rh  # noqa: E402
import hindi_fonts  # noqa: E402
from pipeline import look_patch, voice_patch  # noqa: E402

if __name__ == '__main__':
    hindi_fonts.ensure_fonts(HERE)            # real Unicode Hindi fonts for the captions
    voice_patch.apply_forced_alignment(rh)    # forced alignment first when this job times the words
    look_patch.install(rh)                    # black background, small captions, no music

    rh.make_voice = rh.make_voice_gemini      # no ElevenLabs / Fish fallback
    rh.PROVIDERS = {'cloudflare': rh.img_cloudflare}
    _generate_image = rh.generate_image
    rh.generate_image = lambda idx, prompt, compact, order: _generate_image(idx, prompt, compact, ['cloudflare'])
    rh.main()
