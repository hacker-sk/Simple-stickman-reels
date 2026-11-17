"""Single source for the Hindi Gemini TTS voice text, plus two small patches for render_hindi (which stays unchanged).

Why a patch module: render_hindi.py ignores gemini_voice_name / gemini_voice_desc from the payload and reads its own constants
(DESIGN_NAME, DESIGN_DESC) when it looks up or creates the Gemini designed voice. The voice is made in TWO places and only one of
them runs per reel: the prepare job (pipeline/flow_images.py) or, when prepare/Flow is off or its voice is not reusable, the make job
(run_hindi.py -> render_hindi.main). Both call apply_voice(), so the same description is used wherever the voice is made. When prepare
made the voice, the make job reuses that file and its word timing (render_hindi_flow.py), so nothing is made twice.

apply_forced_alignment() is used by the make job only: when the make job has to time the words itself (no prepare data, hash mismatch,
or saved timing that does not fit), it tries FORCED alignment of the known script first (pipeline/align_forced.py), then the older
WhisperX transcription timing. Prepare already does forced alignment first by itself, so it does not use this patch.
"""

NAME = 'Deep warm Hindi baritone narrator v3'
DESC = 'Deep, warm Indian male baritone with crisp Devanagari pronunciation, rich chest resonance, close-mic proximity, and high studio loudness.'
STYLE = ('Deliver in an expressive, emotionally gripping storytelling tone at a steady, engaging pace. '
         'Read continuous, unpunctuated Devanagari text smoothly, using only brief, natural micro-pauses between complete thoughts\u2014'
         'never long or frequent pauses. Emphasize key feelings and impactful words through stronger vocal projection, chest weight, '
         'and dynamic pitch shifts without dragging out the speed.')


def apply_voice(rh):
    """Make render_hindi create/look up the designed voice from NAME and DESC (a new name makes Gemini design a fresh voice once)."""
    rh.DESIGN_NAME = NAME
    rh.DESIGN_DESC = DESC


def apply_forced_alignment(rh):
    """Wrap render_hindi.align_words: ElevenLabs timestamps if present, else forced alignment, else the original (WhisperX) timing."""
    original = rh.align_words

    def align_words(script_words, duration, audio_path):
        if not getattr(rh, 'EL_ALIGN', None):
            try:
                from pipeline import align_forced
                words = align_forced.forced_words(script_words, duration, audio_path, log=rh.log)
                rh.log('word timing: forced alignment of the known script ok (' + str(len(words)) + ' words)')
                return words
            except Exception as e:  # noqa
                rh.log('word timing: forced alignment not used, falling back to Whisper timing: ' + str(e)[:200])
        return original(script_words, duration, audio_path)

    rh.align_words = align_words
