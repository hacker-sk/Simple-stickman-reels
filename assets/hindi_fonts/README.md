Put your custom Hindi (Devanagari) fonts in this folder: .ttf or .otf files.

For every reel the renderer picks ONE of them at random and uses it for the hook and for all the captions of that reel.
If this folder has no usable font, the renderer keeps the old fonts (Noto Devanagari for captions, Poppins for the hook).

Tips:
- Use bold or heavy styles, they stay readable on the picture.
- English letters inside a Hindi line fall back to Noto Sans / Poppins when your font has no Latin letters.
- A font file that cannot be opened is skipped and another one is tried.
