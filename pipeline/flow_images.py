#!/usr/bin/env python3
"""Google Flow images for the Hindi Shorts pipeline (voice + forced-alignment timing + scene-number tags version).

prepare : package JSON -> 1) the voiceover is made FIRST (the same make_voice the renderer uses), 2) the word timing of that voice is
          worked out by FORCED ALIGNMENT of the known narration (pipeline/align_forced.py); if that fails or looks wrong, the renderer's
          own align_words (WhisperX transcription, or ElevenLabs timestamps) is used, and if that fails too the times are estimated from
          the voice length. Every scene's start time is taken from the word timing with the same pause snapping the renderer uses.
          3) every image prompt gets its scene number as a tag at the very beginning, e.g. '[s01] ...', '[s07] ...'. The tag only makes
          each prompt unique; the Flow job matches a Flow image to its prompt through Flow's own media ids, not through the tag.
          Writes flow-batch/prompts/shorts_flow.json (the tagged prompts), shorts_flow_meta.json (scene index -> tag, narration hash,
          timing source), shorts_flow_voice.wav (reused by the renderer, so the times stay true) and, when the word timing worked,
          shorts_flow_words.json (reused by the renderer so Whisper does not run a second time).
          Sets the step output flow=true ONLY when the voice and prompts worked; otherwise Flow is skipped.
          The voice is the Gemini prebuilt voice Iapetus with its description and the delivery style written for this script
          (package field voice_style), built by pipeline/voice_patch.voice_payload(), the same payload the make job uses when it makes the voice itself.
match   : (used by render_hindi_flow.py) the Flow job saves each image as scene_NN.<ext> (NN = the NN-th Flow prompt). This gives each
          scene the image with its number. Older tag-in-file-name matching is kept as a fallback. A scene without a matching image gets
          no Flow image, so the normal providers (Cloudflare ...) make it. If the narration changed since prepare (hash differs), no
          Flow image is used at all.
          Optional extra (off by default): FLOW_VISION_FALLBACK=true lets Gemini 3.1 vision place untagged images.
Everything is best effort: any problem means fewer (or no) Flow images, never a failed video.
"""
import argparse
import base64
import hashlib
import io
import json
import os
import re
import shutil
import sys
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from pipeline import gemini  # noqa: E402

IMG_EXT = ('.png', '.jpg', '.jpeg', '.webp')
META_NAME = 'shorts_flow_meta.json'
VOICE_NAME = 'shorts_flow_voice.wav'
WORDS_NAME = 'shorts_flow_words.json'
VISION_MODELS = ['gemini-3.1-flash-lite', 'gemini-3.1-flash', 'gemini-3.1-pro']
VISION_MIN = 6
MIN_BYTES = 3000

TAG_BRACKET = re.compile(r'\[(\d{1,2})-(\d{1,2})\]')
TAG_LOOSE = re.compile(r'(?<![0-9A-Za-z])(\d{1,2})[-_](\d{1,2})(?![0-9A-Za-z])')
SCENE_FILE = re.compile(r'^scene_(\d+)\.', re.I)


def log(*a):
    print('[flow_images]', *a, flush=True)


def set_output(key, value):
    p = os.environ.get('GITHUB_OUTPUT')
    if p:
        with open(p, 'a', encoding='utf-8') as fh:
            fh.write(key + '=' + str(value) + '\n')


def narration_of(scenes):
    return ' '.join(str(s.get('narration') or '').strip() for s in scenes)


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


# ----------------------------------------------------------------------------- prepare
def scene_starts(scenes, dur):
    """Estimated start second of every scene: the real voice length shared out over the words by letter count.
    Only used when the real word timing could not be made."""
    words, owner = [], []
    for si, s in enumerate(scenes):
        for w in str(s.get('narration') or '').split():
            words.append(w)
            owner.append(si)
    weights = [max(2, len(w)) + 2 for w in words]
    total = float(sum(weights)) or 1.0
    usable = float(dur) * 0.97
    t = 0.0
    starts = {}
    for wt, si in zip(weights, owner):
        starts.setdefault(si, t)
        t += usable * wt / total
    for si in range(len(scenes)):
        starts.setdefault(si, t)
    return starts


def real_timing(rh, scenes, voice_path, dur):
    """(words, bounds, aligner). words = [(word, start, end)], bounds[i] = start second of scene i, aligner = 'forced' or 'whisper'.
    Forced alignment of the known script first; the renderer's own align_words (same pause snapping as render_hindi.main()) as the
    second choice. Raises when neither can make a timing."""
    script_words = narration_of(scenes).split()
    words, aligner = None, ''
    try:
        from pipeline import align_forced
        words = align_forced.forced_words(script_words, dur, voice_path, log=log)
        aligner = 'forced'
    except Exception as e:  # noqa
        words = None
        log('forced alignment not used, falling back to the renderer timing: ' + str(e)[:200])
    if not words:
        words = rh.align_words(script_words, dur, voice_path)
        aligner = 'whisper'
        if not words or len(words) != len(script_words):
            raise RuntimeError('word timing has ' + str(len(words or [])) + ' words, the script has ' + str(len(script_words)))
    first_words = []
    wi = 0
    for s in scenes[:-1]:
        wi += len(str(s.get('narration') or '').split())
        first_words.append(wi)
    sil = rh.find_silences(voice_path)
    bounds = [0.0]
    for wi in first_words:
        b = words[min(wi, len(words) - 1)][1]
        cand = [m for m in sil if abs(m - b) <= 0.1]
        if cand:
            b = min(cand, key=lambda m: abs(m - b))
        bounds.append(max(bounds[-1] + 0.8, b))
    return words, bounds, aligner


def load_scenes(raw):
    data = json.loads(raw)
    try:
        from pipeline import package
        return package.parse(raw)['scenes']
    except Exception as e:  # noqa
        log('package.parse not used (' + str(e)[:80] + '), reading the scenes directly')
    scenes = data.get('scenes') if isinstance(data, dict) else data
    return [s for s in (scenes or []) if isinstance(s, dict)]


def voice_style_of(raw):
    """The delivery style written for this script (package field voice_style), '' when there is none."""
    try:
        from pipeline import package
        return package.parse(raw).get('voice_style') or ''
    except Exception:  # noqa
        try:
            data = json.loads(raw)
            return str(data.get('voice_style') or '').strip() if isinstance(data, dict) else ''
        except Exception:  # noqa
            return ''


def make_voice_file(narration, path, style=''):
    """The renderer's own make_voice (Gemini, then ElevenLabs, then Fish). Returns (duration in seconds, the render_hindi module).
    The voice is made by render_hindi.py from the voice payload of pipeline/voice_patch.voice_payload(): the Gemini prebuilt voice Iapetus,
    its description and the delivery style of this script (style, the default style when empty), the same payload the make job uses."""
    work = os.path.abspath('flow_work')
    os.makedirs(work, exist_ok=True)
    os.environ['WORK_DIR'] = work
    os.environ['OUT_DIR'] = os.path.abspath('flow_out')
    try:
        from pipeline import voice_patch as _vp
        VOICE = _vp.voice_payload(style)
    except Exception:  # noqa
        # last resort: no description or style here, render_hindi.py uses its native defaults
        VOICE = {'language': 'hi', 'gemini_voice': 'Iapetus',
                 'gemini_models': ['gemini-3.8-flash-tts', 'gemini-2.5-flash-preview-tts'],
                 'voice_id': 'ibbx9zDYGvLgtYzRbqqG', 'fish_voice_id': '6366ea69a97d41ada9eb855a64e56fba', 'fish_model': 's2.1-pro-free'}
    os.environ['PAYLOAD'] = json.dumps(VOICE, ensure_ascii=False)
    stub = types.ModuleType('render_hindi_overlay')   # the overlay module is only needed for drawing, not for the voice
    stub.STATE = {}
    sys.modules.setdefault('render_hindi_overlay', stub)
    import render_hindi as rh
    try:
        from pipeline import voice_patch
        voice_patch.apply_voice(rh)
    except Exception as e:  # noqa
        log('voice description patch not installed, render_hindi uses its own defaults: ' + str(e)[:150])
    rh.make_voice(narration, path)
    dur = rh.audio_duration(path)
    if dur > rh.MAX_VOICE_SECONDS:
        raise RuntimeError('voice is ' + str(int(dur)) + 's, over the limit')
    return dur, rh


def cmd_prepare(a):
    raw = ''
    if os.path.exists(a.package):
        with open(a.package, encoding='utf-8') as fh:
            raw = fh.read().strip()
    if not raw:
        log('no package given (not a package run), Flow is skipped')
        return 0
    try:
        scenes = load_scenes(raw)
    except Exception as e:  # noqa
        log('package is not valid JSON, Flow is skipped: ' + str(e)[:100])
        return 0
    items = [i for i, s in enumerate(scenes) if str(s.get('image_prompt') or '').strip()]
    narration = narration_of(scenes)
    if not items or not narration.strip():
        log('package has no image prompts or no narration, Flow is skipped')
        return 0
    try:
        os.makedirs(os.path.dirname(os.path.abspath(a.voice)), exist_ok=True)
        vstyle = voice_style_of(raw)
        log('voice: Iapetus, ' + ('delivery style from the package' if vstyle else 'default delivery style'))
        dur, rh = make_voice_file(narration, a.voice, vstyle)
    except Exception as e:  # noqa
        log('voiceover could not be made, Flow is skipped and the normal image providers are used: ' + str(e)[:200])
        return 0

    # scene start times: forced alignment (else the renderer's word timing), else the old estimate
    timing, aligner, words = 'estimate', '', None
    try:
        words, bounds, aligner = real_timing(rh, scenes, a.voice, dur)
        starts = dict((i, bounds[i]) for i in range(len(scenes)))
        timing = 'audio'
        log('scene start times taken from the ' + aligner + ' word timing of the voice (' + str(len(words)) + ' words)')
    except Exception as e:  # noqa
        words = None
        starts = scene_starts(scenes, dur)
        log('word timing of the voice failed, scene start times are estimated from the voice length instead: ' + str(e)[:200])

    # The tag is the scene number: stable, unique, independent of the timing.
    tags = dict((i, 's%02d' % (i + 1)) for i in items)
    prompts = ['[' + tags[i] + '] ' + str(scenes[i]['image_prompt']).strip() for i in items]
    os.makedirs(os.path.dirname(os.path.abspath(a.prompts)), exist_ok=True)
    with open(a.prompts, 'w', encoding='utf-8') as fh:
        json.dump(prompts, fh, ensure_ascii=False, indent=1)

    nsha = sha(narration)
    words_name = ''
    if words:
        words_path = a.words or os.path.join(os.path.dirname(os.path.abspath(a.voice)), WORDS_NAME)
        try:
            with open(words_path, 'w', encoding='utf-8') as fh:
                json.dump({'narration_sha': nsha, 'voice_seconds': round(dur, 2), 'aligner': aligner,
                           'words': [[w, round(float(s), 3), round(float(e), 3)] for w, s, e in words]}, fh, ensure_ascii=False)
            words_name = os.path.basename(words_path)
        except Exception as e:  # noqa
            log('word timing could not be saved, the renderer will run its own: ' + str(e)[:120])

    meta = {'scene_count': len(scenes), 'narration_sha': nsha, 'voice_file': VOICE_NAME, 'voice_seconds': round(dur, 2),
            'timing': timing, 'aligner': aligner, 'words_file': words_name,
            'scenes': [{'index': i, 'tag': tags[i], 'start': round(starts.get(i, 0.0), 2)} for i in items]}
    with open(a.meta, 'w', encoding='utf-8') as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=1)
    log('voice ' + str(round(dur, 1)) + 's made, timing=' + timing + ' (' + (aligner or 'none') + '), words saved=' + str(bool(words_name)) + '; ' + str(len(prompts)) +
        ' Flow prompts tagged: ' + ' | '.join('[' + m['tag'] + '] starts ' + str(m['start']) + 's' for m in meta['scenes']))
    set_output('flow', 'true')
    return 0


# ----------------------------------------------------------------------------- match
def parse_tag(filename):
    """(minute, second) tag found in a file name, or None. Legacy: accepts '[0-5]' and the forms a downloader makes of it ('0-5', '0_5')."""
    stem = os.path.splitext(os.path.basename(filename))[0]
    stem = re.sub(r'^\d{10,}-', '', stem)
    m = TAG_BRACKET.search(stem) or TAG_LOOSE.search(stem)
    return (int(m.group(1)), int(m.group(2))) if m else None


def _scan(flow_dir, skip):
    out = []
    for dp, dn, fn in os.walk(flow_dir):
        parts = dp.replace('\\', '/').split('/')
        if any(s in parts for s in skip):
            continue
        for f in sorted(fn):
            p = os.path.join(dp, f)
            if f.lower().endswith(IMG_EXT) and os.path.getsize(p) >= MIN_BYTES:
                out.append({'name': f, 'path': os.path.abspath(p), 'mtime': os.path.getmtime(p)})
    return out


def find_images(flow_dir):
    out = _scan(flow_dir, ('rejected', 'debug', 'raw'))
    if not out:
        out = _scan(flow_dir, ('rejected', 'debug'))
        if out:
            log('no images outside raw/, using the raw folder images')
    seen, uniq = set(), []
    for im in sorted(out, key=lambda x: x['mtime']):
        if im['name'] not in seen:
            seen.add(im['name'])
            uniq.append(im)
    return uniq


def find_meta_dir(flow_dir):
    """(meta dict, folder it lives in) or (None, None)."""
    for dp, dn, fn in os.walk(flow_dir):
        if META_NAME in fn:
            try:
                with open(os.path.join(dp, META_NAME), encoding='utf-8') as fh:
                    return json.load(fh), dp
            except Exception:  # noqa
                return None, None
    return None, None


def voice_status(flow_dir, narration):
    """(status, voice path or None, meta folder or None). status is 'reused' (voice usable), 'no_prep' (no prepare data),
    'voice_missing' (prepare data but no usable audio) or 'hash_mismatch' (the narration changed since prepare)."""
    meta, folder = find_meta_dir(flow_dir)
    if not meta or not folder:
        return 'no_prep', None, None
    p = os.path.join(folder, meta.get('voice_file') or VOICE_NAME)
    if not os.path.isfile(p) or os.path.getsize(p) < 10000:
        return 'voice_missing', None, folder
    if meta.get('narration_sha') != sha(narration):
        return 'hash_mismatch', None, folder
    return 'reused', p, folder


def find_voice(flow_dir, narration):
    """Path of the voice made before Flow when it belongs to exactly this narration, else None."""
    status, p, _ = voice_status(flow_dir, narration)
    if status == 'hash_mismatch':
        log('the saved voice belongs to a different narration, a new voice will be made')
    return p


def find_words(flow_dir, narration):
    """[(word, start, end)] saved by prepare for exactly this narration, else None (the renderer then runs its own word timing)."""
    meta, folder = find_meta_dir(flow_dir)
    if not meta or not folder:
        return None
    name = meta.get('words_file')
    if not name:
        log('no saved word timing, the renderer runs its own')
        return None
    try:
        with open(os.path.join(folder, name), encoding='utf-8') as fh:
            data = json.load(fh)
        if data.get('narration_sha') != sha(narration):
            log('the saved word timing belongs to a different narration, the renderer runs its own')
            return None
        words = [(str(w[0]), float(w[1]), float(w[2])) for w in (data.get('words') or [])]
        if len(words) != len(narration.split()):
            log('the saved word timing has ' + str(len(words)) + ' words, the narration has ' + str(len(narration.split())) + ', the renderer runs its own')
            return None
        return words
    except Exception as e:  # noqa
        log('saved word timing could not be read (' + str(e)[:100] + '), the renderer runs its own')
        return None


def thumb_b64(path):
    from PIL import Image
    im = Image.open(path).convert('RGB')
    im.thumbnail((768, 768))
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=75)
    return base64.b64encode(buf.getvalue()).decode()


def vision_scores(image, scene_rows, start_key=0):
    """Optional extra: ask Gemini 3.1 how well ONE image fits each candidate scene. Every API key is tried for every model."""
    import requests
    lines = []
    for i, narr, prompt in scene_rows:
        lines.append('scene ' + str(i) + ': narration (Hindi): ' + narr[:300].replace('\n', ' ') + ' | prompt: ' + prompt[:250].replace('\n', ' '))
    text = ('You are matching ONE generated image to the scenes of a short video. Candidate scenes:\n' + '\n'.join(lines) +
            '\n\nRate from 0 to 10 how well the image shows EACH scene (10 = clearly this scene). Reply ONLY with JSON: '
            '{"scores": {"<scene number>": <0-10>}} with every scene number listed above.')
    body = {'contents': [{'role': 'user', 'parts': [{'text': text}, {'inline_data': {'mime_type': 'image/jpeg', 'data': thumb_b64(image['path'])}}]}],
            'generationConfig': {'maxOutputTokens': 1500, 'temperature': 0.1, 'responseMimeType': 'application/json'}}
    keys = gemini.api_keys()
    last = ''
    for sweep in range(2):
        for model in VISION_MODELS:
            for k in range(len(keys)):
                key = keys[(start_key + k) % len(keys)]
                try:
                    r = requests.post('https://generativelanguage.googleapis.com/v1beta/models/' + model + ':generateContent',
                                      headers={'x-goog-api-key': key, 'Content-Type': 'application/json'}, data=json.dumps(body), timeout=120)
                    if r.status_code == 200:
                        got = gemini.extract_json(gemini.response_text(r.json()))
                        sc = (got or {}).get('scores')
                        if isinstance(sc, dict) and sc:
                            out = {}
                            for kk, v in sc.items():
                                try:
                                    out[int(kk)] = float(v)
                                except Exception:  # noqa
                                    pass
                            if out:
                                return out
                        last = 'unparseable reply'
                    else:
                        last = 'HTTP ' + str(r.status_code) + ': ' + r.text[:100].replace('\n', ' ')
                except Exception as e:  # noqa
                    last = str(e)[:100]
                log('vision ' + model + ' key#' + str((start_key + k) % len(keys) + 1) + ' failed for ' + image['name'] + ': ' + last)
                time.sleep(0.5)
        if sweep == 0:
            time.sleep(5)
    raise RuntimeError('all keys/models failed: ' + last)


def build_map(scenes, flow_dir, work_dir=None):
    """{scene index: absolute image path}. First choice: files named scene_NN.<ext> (NN = position of the prompt in the Flow batch,
    which is the position in meta['scenes']). Second choice: the legacy tag in the file name. Optional third: Gemini vision."""
    images = find_images(flow_dir)
    if not images:
        log('no Flow images found in ' + flow_dir + ', the normal providers make every image')
        return {}
    meta, _ = find_meta_dir(flow_dir)
    if not meta or not isinstance(meta.get('scenes'), list) or meta.get('scene_count') != len(scenes):
        log('Flow meta is missing or does not fit these scenes, the normal providers make every image')
        return {}
    if meta.get('narration_sha') and meta.get('narration_sha') != sha(narration_of(scenes)):
        log('hash mismatch: the narration changed since the Flow images were made, so they may not fit. The normal providers make every image')
        return {}
    log(str(len(images)) + ' Flow images: ' + ', '.join(im['name'] for im in images))
    assigned, method, used = {}, {}, set()

    # 1) scene_NN files written by the Flow job (matched there through Flow's media ids)
    by_pos = {}
    for im in images:
        mm = SCENE_FILE.match(im['name'])
        if mm:
            by_pos.setdefault(int(mm.group(1)), im)
    for pos, m in enumerate(meta['scenes'], 1):
        i = m.get('index')
        im = by_pos.get(pos)
        if im and isinstance(i, int) and 0 <= i < len(scenes) and im['name'] not in used:
            assigned[i] = im
            used.add(im['name'])
            method[i] = 'scene_file'
    log('scene_NN files placed ' + str(len(assigned)) + ' of ' + str(len(meta['scenes'])) + ' scenes')

    # 2) legacy: tag in the file name (never touches scene_/unmatched_ files)
    legacy = [im for im in images if not re.match(r'^(scene|unmatched)_', im['name'], re.I)]
    by_tag = {}
    for im in legacy:
        t = parse_tag(im['name'])
        if t:
            by_tag.setdefault(t, []).append(im)
    for m in meta['scenes']:
        i, tag = m.get('index'), str(m.get('tag') or '')
        mm = re.match(r'^(\d+)-(\d+)$', tag)
        if not isinstance(i, int) or i in assigned or not mm or not (0 <= i < len(scenes)):
            continue
        cands = [c for c in by_tag.get((int(mm.group(1)), int(mm.group(2))), []) if c['name'] not in used]
        if cands:
            assigned[i] = cands[0]
            used.add(cands[0]['name'])
            method[i] = 'tag'

    if os.environ.get('FLOW_VISION_FALLBACK', '').strip().lower() == 'true':
        left_s = sorted(m['index'] for m in meta['scenes'] if isinstance(m.get('index'), int) and m['index'] not in assigned)
        left_i = [im for im in images if im['name'] not in used]
        if left_s and left_i:
            rows = [(i, str(scenes[i].get('narration') or ''), str(scenes[i].get('image_prompt') or '')) for i in left_s]
            cand = []
            for n, im in enumerate(left_i):
                try:
                    sc = vision_scores(im, rows, start_key=n)
                    cand += [(v, i, im) for i, v in sc.items() if i in left_s]
                except Exception as e:  # noqa
                    log('vision failed for ' + im['name'] + ': ' + str(e)[:150])
            for v, i, im in sorted(cand, key=lambda x: -x[0]):
                if v >= VISION_MIN and i not in assigned and im['name'] not in used:
                    assigned[i] = im
                    used.add(im['name'])
                    method[i] = 'gemini'

    result = dict((i, im['path']) for i, im in assigned.items())
    log('Flow images will be used for ' + str(len(result)) + ' of ' + str(len(scenes)) + ' scenes: ' +
        ', '.join(str(i + 1) + '=' + assigned[i]['name'] + ' (' + method[i] + ')' for i in sorted(assigned)) +
        ' | the other scenes use the normal providers (' + ', '.join(str(i + 1) for i in range(len(scenes)) if i not in assigned and any(m.get('index') == i for m in meta['scenes'])) + ')')
    if work_dir:
        try:
            os.makedirs(work_dir, exist_ok=True)
            with open(os.path.join(work_dir, 'flow_map.json'), 'w', encoding='utf-8') as fh:
                json.dump({'scenes': dict((str(i), p) for i, p in result.items()), 'method': dict((str(i), m) for i, m in method.items())}, fh, indent=1)
        except Exception:  # noqa
            pass
    return result


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--package', required=True)
    p.add_argument('--prompts', required=True)
    p.add_argument('--meta', required=True)
    p.add_argument('--voice', default='flow-batch/prompts/' + VOICE_NAME)
    p.add_argument('--words', default='')
    m = sub.add_parser('match')
    m.add_argument('--job', required=True)
    m.add_argument('--flow-dir', required=True)
    a = ap.parse_args()
    if a.cmd == 'prepare':
        return cmd_prepare(a)
    with open(a.job, encoding='utf-8') as fh:
        job = json.load(fh)
    print(json.dumps(build_map(job['scenes'], a.flow_dir), indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
