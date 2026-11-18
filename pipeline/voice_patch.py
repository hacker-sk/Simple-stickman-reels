"""Single source for the Hindi Gemini TTS voice, plus two small patches for render_hindi (which stays unchanged).

The voice is the Gemini prebuilt voice Iapetus (VOICE_NAME). DESC is the voice description; it is always sent in front of the delivery style,
and the delivery style is written for every script and travels in the payload as "voice_style" (see pipeline/package.py). When a script
brings no style, the default STYLE is used. voice_payload() builds the voice part of the render job, and it is used in BOTH places where the
voiceover is made: the prepare job (pipeline/flow_images.py) and the make job (run_shorts.py -> render job file -> render_hindi), so the same
voice and style come out wherever it is made. When prepare made the voice, the make job reuses that file and its word timing (render_hindi_flow.py).

apply_voice() still installs DESC as render_hindi's designed-voice text, but the designed voice is no longer used (gemini_voice is Iapetus).

apply_forced_alignment() is used by the make job only: when the make job has to time the words itself (no prepare data, hash mismatch,
or saved timing that does not fit), it tries FORCED alignment of the known script first (pipeline/align_forced.py), then the older
WhisperX transcription timing. Prepare already does forced alignment first by itself, so it does not use this patch.
"""

NAME = 'Deep warm Hindi baritone narrator v4'     # the old designed voice, unused now
VOICE_NAME = 'Iapetus'                              # Gemini prebuilt voice
DESC = ('Smooth, clear Indian male voice in his early 30s with a natural, native Hindi accent and crisp Devanagari articulation. '
        'Balanced lower-middle baritone timbre with warm chest resonance, clean vocal clarity without raspiness, '
        'close-mic studio proximity, and high, forward broadcast loudness.')
# Default delivery style, used only when the script brings none.
STYLE = ('Adapt emotional delivery naturally to match the script\u2014inspiring for motivation, engaging for stories, heartfelt for emotion, and crisp for quotes. '
         'Maintain a steady pace through continuous, unpunctuated Devanagari, using only brief micro-pauses between complete thoughts. '
         'Emphasize key feelings and words through vocal projection and pitch shifts without slowing down.')


def style_for(script_style=''):
    """Voice description + the delivery style written for this script (or the default style)."""
    s = ' '.join(str(script_style or '').split())
    return DESC + ' ' + (s or STYLE)


def voice_payload(script_style=''):
    """The voice part of the render job (also the whole PAYLOAD of the prepare job)."""
    return {
        'language': 'hi', 'gemini_voice': VOICE_NAME,
        'gemini_style': style_for(script_style),
        'gemini_models': ['gemini-3.8-flash-tts', 'gemini-2.5-flash-preview-tts'],
        'voice_id': 'ibbx9zDYGvLgtYzRbqqG', 'tts_model': 'eleven_multilingual_v2',
        'fish_voice_id': '6366ea69a97d41ada9eb855a64e56fba', 'fish_model': 's2.1-pro-free',
    }


def apply_voice(rh):
    """Make render_hindi use NAME and DESC for the designed voice (not used any more: the voice is the prebuilt Iapetus)."""
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
