#!/usr/bin/env python3
"""Hindi Shorts renderer that prefers Google Flow images.

run_shorts.py starts this instead of render_hindi.py (RENDER_SCRIPT). It
  1. reuses the voiceover that was made BEFORE Flow (so the time tags on the Flow prompts stay true), when it belongs to this narration,
  2. matches the Flow images in FLOW_DIR to the scenes by the [minute-second] tag in their file names (pipeline/flow_images.py),
  3. replaces render_hindi.generate_image so a scene with a tagged Flow image uses it and every other scene goes through the
     normal providers (HINDI_IMAGE_ORDER).
render_hindi.py itself is unchanged. Any Flow problem just means the normal providers make the images.
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


def use_flow_voice(scenes, fdir):
    """Reuse the voice made before Flow when it was made from exactly this narration."""
    try:
        from pipeline import flow_images
        narration = flow_images.narration_of(scenes)
        vp = flow_images.find_voice(fdir, narration)
        if not vp:
            log('no matching saved voice, the renderer makes its own voice')
            return

        def make_voice(text, path):
            shutil.copyfile(vp, path)
            rh.log('voice: reused the voiceover made before Flow')

        rh.make_voice = make_voice
        log('the voiceover made before Flow will be reused')
    except Exception:  # noqa
        log('voice reuse failed, the renderer makes its own voice')
        traceback.print_exc()


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
        use_flow_voice(scenes, fdir)
    fm = load_flow_map(scenes, fdir)
    log('Flow images will be used for ' + str(len(fm)) + ' scene(s)')
    install(fm)
    rh.main()
