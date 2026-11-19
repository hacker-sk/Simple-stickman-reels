# pipeline

- `run_shorts.py` orchestrator (package -> render -> check -> Buffer)
- `package.py` payload parser and format
- `styles.py` the six art styles
- `voice_patch.py` Gemini Iapetus voice + forced-alignment patch
- `look_patch.py` black background, captions, hook; no music
- `align_forced.py` forced word alignment
- `buffer.py` Buffer posting
- `setup_ffmpeg.sh`, `setup_fonts.sh` cached installs
