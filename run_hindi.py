#!/usr/bin/env python3
"""Starts the Hindi renderer with the mood based music picker (music_picker.py) installed.

render_hindi.yml runs this instead of render_hindi.py. render_hindi.py itself is unchanged; this file only swaps in
the new pick_music and then runs render_hindi.main().
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import render_hindi as rh  # noqa: E402
import music_picker  # noqa: E402

if __name__ == '__main__':
    music_picker.install(rh)
    rh.main()
