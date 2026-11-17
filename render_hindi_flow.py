#!/usr/bin/env python3
"""Hindi Shorts renderer that prefers Google Flow images.

run_shorts.py starts this instead of render_hindi.py (RENDER_SCRIPT). It
  1. reuses the voiceover that was made BEFORE Flow (so the time tags on the Flow prompts stay true), when it belongs to this narration,
  2. reuses the word timing saved with that voice (so Whisper does not run a second time), only together with that same voice,
  3. matches the Flow images in FLOW_DIR to the scenes by the [minute-second] tag in their file names (pipeline/flow_images.py),
  4. replaces render_hindi.generate_image so a scene with a tagged Flow image uses it and every other scene goes through the
     normal providers (HINDI_IMAGE_ORDER).
When the voice is regenerated, render_hindi makes its own voice and runs its own word timing (fresh Whisper) as before.
render_hindi.py itself is unchanged. Any Flow problem just means the normal providers make the images.
One log line starts with 'VOICE CASE:' and says which case happened: reused, regenerated (and why) or hash mismatch.
"""
import json
import os
import shutil
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import render_hindi as rh  # noqa: E402
from PIL import Image  # noqa: E402


def log(*a):
    print('[render-flow]', *a, flush=True)


def flow_dir():
    d = os.environ.get('FLOW_DIR', '').strip()
    if os.environ.get('FLOW_ENABLED', '').strip().lower() == 'false' or not d or not os.path.isdir(d):
        return ''
    return d


def load_scenes():
    try:
        jp = json.loads(os.environ['PAYLOAD']).get('job_path')
        with open(os.path.join(HERE, jp), encoding='utf-8') as fh:
            return json.load(fh)['scenes']
    except Exception:  # noqa
        log('could not read the job scenes')
        traceback.print_exc()
        return None


CASE_TEXT = {
    'reused': 'REUSED the voiceover and word timing made before Flow',
    'no_prep': 'REGENERATED: no prepare data was found, the renderer makes its own voice and runs its own Whisper',
    'voice_missing': 'REGENERATED: the saved voice file is missing or too small, the renderer makes its own voice and runs its own Whisper',
    'hash_mismatch': 'HASH MISMATCH: the narration changed since prepare, the renderer makes its own voice and runs its own Whisper, Flow images are not used',
}


def use_flow_voice(scenes, fdir):
    """Reuse the voice made before Flow when it was made from exactly this narration. Returns True when it is reused."""
    try:
        from pipeline import flow_images
        narration = flow_images.narration_of(scenes)
        status, vp, _ = flow_images.voice_status(fdir, narration)
        log('VOICE CASE: ' + CASE_TEXT.get(status, status))
        if not vp:
            return False

        def make_voice(text, path):
            shutil.copyfile(vp, path)
            rh.log('voice: reused the voiceover made before Flow')

        rh.make_voice = make_voice
        return True
    except Exception:  # noqa
        log('VOICE CASE: REGENERATED: voice reuse failed, the renderer makes its own voice and runs its own Whisper')
        traceback.print_exc()
        return False


def use_flow_words(scenes, fdir):
    """Reuse the saved word timing. Only called when the saved voice is reused, so the timing belongs to this exact audio."""
    try:
        from pipeline import flow_images
        words = flow_images.find_words(fdir, flow_images.narration_of(scenes))
        if not words:
            return False
        original = rh.align_words

        def align_words(script_words, duration, audio_path):
            if len(script_words) == len(words) and all(w[0] == s for w, s in zip(words, script_words)):
                rh.log('word timing: reused the timing saved before Flow (' + str(len(words)) + ' words), Whisper not run again')
                return words
            rh.log('word timing: the saved timing does not fit this script, running the word timing again')
            return original(script_words, duration, audio_path)

        rh.align_words = align_words
        log('the word timing saved before Flow will be reused')
        return True
    except Exception:  # noqa
        log('saved word timing could not be used, the renderer runs its own')
        traceback.print_exc()
        return False


def load_flow_map(scenes, fdir):
    if not fdir or not scenes:
        log('no Flow images to use')
        return {}
    try:
        from pipeline import flow_images
        return flow_images.build_map(scenes, fdir, rh.WORK)
    except Exception:  # noqa
        log('Flow matching failed, using the normal image providers for every scene')
        traceback.print_exc()
        return {}


def install(flow_map):
    original = rh.generate_image

    def generate_image(idx, prompt, compact, order):
        path = flow_map.get(idx)
        if path:
            try:
                im = Image.open(path)
                im.load()
                rh.log('image ' + str(idx + 1) + ': ok via flow (' + os.path.basename(path) + ')')
                return im.convert('RGB'), 'flow'
            except Exception as e:  # noqa
                rh.log('image ' + str(idx + 1) + ': Flow image unreadable (' + str(e)[:100] + '), using the normal providers')
        return original(idx, prompt, compact, order)

    rh.generate_image = generate_image


if __name__ == '__main__':
    fdir = flow_dir()
    scenes = load_scenes() if fdir else None
    if fdir and scenes:
        if use_flow_voice(scenes, fdir):
            use_flow_words(scenes, fdir)
    else:
        log('VOICE CASE: REGENERATED: no Flow data for this run, the renderer makes its own voice and runs its own Whisper')
    fm = load_flow_map(scenes, fdir)
    log('Flow images will be used for ' + str(len(fm)) + ' scene(s)')
    install(fm)
    rh.main()
