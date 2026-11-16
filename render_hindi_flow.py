#!/usr/bin/env python3
"""Hindi Shorts renderer that prefers Google Flow images.

run_shorts.py starts this instead of render_hindi.py (RENDER_SCRIPT). It matches the Flow images in FLOW_DIR to the
scenes (pipeline/flow_images.py), then replaces render_hindi.generate_image so a scene with a Flow image uses it and every
other scene goes through the normal providers (HINDI_IMAGE_ORDER). render_hindi.py itself is unchanged.
Any Flow problem just means the normal providers make the images.
"""
import json
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import render_hindi as rh  # noqa: E402
from PIL import Image  # noqa: E402


def log(*a):
    print('[render-flow]', *a, flush=True)


def load_flow_map():
    flow_dir = os.environ.get('FLOW_DIR', '').strip()
    if os.environ.get('FLOW_ENABLED', '').strip().lower() == 'false' or not flow_dir or not os.path.isdir(flow_dir):
        log('no Flow images to use')
        return {}
    try:
        jp = json.loads(os.environ['PAYLOAD']).get('job_path')
        with open(os.path.join(HERE, jp), encoding='utf-8') as fh:
            scenes = json.load(fh)['scenes']
        from pipeline import flow_images
        return flow_images.build_map(scenes, flow_dir, rh.WORK)
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
    fm = load_flow_map()
    log('Flow images will be used for ' + str(len(fm)) + ' scene(s)')
    install(fm)
    rh.main()
