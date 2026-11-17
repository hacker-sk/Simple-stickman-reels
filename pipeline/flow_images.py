#!/usr/bin/env python3
"""Google Flow images for the Hindi Shorts pipeline.

prepare : package JSON -> flow-batch/prompts/shorts_flow.json (prompts with an extra 'Image name: ...' line)
          + flow-batch/prompts/shorts_flow_meta.json (scene index -> short name). Sets the step output flow=true.
match   : (used by render_hindi_flow.py) scenes + Flow images folder -> {scene index: image path}.
          1) descriptive filename vs the scene's short name,
          2) Gemini 3.1 vision, ONE request per image (every one of the API keys is tried on any failure),
          3) elimination.
          Scenes without a confident match are left out, so the normal providers make those images.
Everything here is best effort: any problem means fewer (or no) Flow images, never a failed video.
"""
import argparse
import base64
import difflib
import io
import json
import os
import re
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from pipeline import gemini  # noqa: E402

IMG_EXT = ('.png', '.jpg', '.jpeg', '.webp')
META_NAME = 'shorts_flow_meta.json'
NAME_MODELS = ['gemini-3.1-flash-lite', 'gemini-2.5-flash-lite', 'gemini-2.5-flash']
VISION_MODELS = ['gemini-3.1-flash-lite', 'gemini-3.1-flash', 'gemini-3.1-pro']
MIN_SCORE = 0.6
MIN_MARGIN = 0.1
VISION_MIN = 6      # of 10: minimum vision score to accept a scene/image pair
MIN_BYTES = 3000


def log(*a):
    print('[flow_images]', *a, flush=True)


def set_output(key, value):
    p = os.environ.get('GITHUB_OUTPUT')
    if p:
        with open(p, 'a', encoding='utf-8') as fh:
            fh.write(key + '=' + str(value) + '\n')


# ----------------------------------------------------------------------------- prepare
def clean_name(n):
    words = re.sub(r'[^a-z0-9 ]+', ' ', str(n).lower()).split()
    return ' '.join(words[:5])


def fallback_name(i, prompt):
    words = re.findall(r'[A-Za-z]{3,}', prompt)[:4]
    return ' '.join(w.lower() for w in words) or 'scene ' + str(i + 1)


def make_names(items):
    """One short English label per scene (2-4 words) from Gemini; a plain fallback when Gemini fails."""
    names = [fallback_name(i, s['image_prompt']) for i, s in items]
    try:
        listing = '\n'.join(str(k) + ': ' + s['image_prompt'][:300].replace('\n', ' ') for k, (i, s) in enumerate(items))
        text = gemini.generate(
            'You write very short English image labels.',
            'Below are ' + str(len(items)) + ' numbered image prompts. For each one write a label of 2 to 4 lowercase English '
            'words naming its main subject, like "student studying", "clock" or "road to success". Labels must clearly differ '
            'from each other. Reply ONLY with JSON: {"names": [...]} with exactly ' + str(len(items)) + ' strings, in order.\n\n' + listing,
            'flow-names', max_tokens=1500, temperature=0.3, json_mode=True, models=NAME_MODELS)
        got = (gemini.extract_json(text) or {}).get('names')
        if isinstance(got, list) and len(got) == len(items):
            names = [clean_name(g) or names[k] for k, g in enumerate(got)]
        else:
            log('Gemini returned an unusable name list, using fallback names')
    except Exception as e:  # noqa
        log('naming with Gemini failed, using fallback names: ' + str(e)[:150])
    return names


def cmd_prepare(a):
    raw = ''
    if os.path.exists(a.package):
        with open(a.package, encoding='utf-8') as fh:
            raw = fh.read().strip()
    if not raw:
        log('no package given (not a package run), Flow is skipped')
        return 0
    try:
        data = json.loads(raw)
    except Exception as e:  # noqa
        log('package is not valid JSON, Flow is skipped: ' + str(e)[:100])
        return 0
    scenes = data.get('scenes') if isinstance(data, dict) else data
    items = []
    for i, s in enumerate(scenes or []):
        if isinstance(s, dict) and str(s.get('image_prompt') or '').strip():
            items.append((i, {'image_prompt': str(s['image_prompt']).strip()}))
    if not items:
        log('package has no image prompts, Flow is skipped')
        return 0
    names = make_names(items)
    prompts = [s['image_prompt'] + ' Image name: ' + names[k] + '.' for k, (i, s) in enumerate(items)]
    os.makedirs(os.path.dirname(os.path.abspath(a.prompts)), exist_ok=True)
    with open(a.prompts, 'w', encoding='utf-8') as fh:
        json.dump(prompts, fh, ensure_ascii=False, indent=1)
    meta = {'scene_count': len(scenes), 'scenes': [{'index': i, 'name': names[k]} for k, (i, s) in enumerate(items)]}
    with open(a.meta, 'w', encoding='utf-8') as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=1)
    log('wrote ' + str(len(prompts)) + ' Flow prompts: ' + ' | '.join(names))
    set_output('flow', 'true')
    return 0


# ----------------------------------------------------------------------------- match
def slug(filename):
    stem = os.path.splitext(os.path.basename(filename))[0].lower()
    stem = re.sub(r'^\d{10,}-', '', stem)
    stem = re.sub(r'[-_ ]\d{1,2}$', '', stem)
    toks = re.sub(r'[^a-z0-9]+', ' ', stem).split()
    return ' '.join(t for t in toks if not (len(t) >= 8 and re.search(r'\d', t)))


def score(a, b):
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    jac = inter / float(len(ta | tb))
    cont = inter / float(min(len(ta), len(tb)))
    seq = difflib.SequenceMatcher(None, a, b).ratio()
    return max(jac, 0.85 * cont, 0.9 * seq)


def _scan(flow_dir, skip):
    out = []
    for dp, dn, fn in os.walk(flow_dir):
        parts = dp.replace('\\', '/').split('/')
        if any(s in parts for s in skip):
            continue
        for f in sorted(fn):
            p = os.path.join(dp, f)
            if f.lower().endswith(IMG_EXT) and os.path.getsize(p) >= MIN_BYTES:
                out.append({'name': f, 'path': os.path.abspath(p), 'slug': slug(f), 'mtime': os.path.getmtime(p)})
    return out


def find_images(flow_dir):
    out = _scan(flow_dir, ('rejected', 'debug', 'raw'))
    if not out:  # the images may sit in a folder we normally skip
        out = _scan(flow_dir, ('rejected', 'debug'))
        if out:
            log('no images outside raw/, using the raw folder images')
    # keep one entry per file name
    seen, uniq = set(), []
    for im in out:
        if im['name'] not in seen:
            seen.add(im['name'])
            uniq.append(im)
    return uniq


def find_meta(flow_dir):
    for dp, dn, fn in os.walk(flow_dir):
        if META_NAME in fn:
            try:
                with open(os.path.join(dp, META_NAME), encoding='utf-8') as fh:
                    return json.load(fh)
            except Exception:  # noqa
                return None
    return None


def thumb_b64(path):
    from PIL import Image
    im = Image.open(path).convert('RGB')
    im.thumbnail((768, 768))
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=75)
    return base64.b64encode(buf.getvalue()).decode()


def vision_scores(image, scene_rows, start_key=0):
    """Ask Gemini 3.1 how well ONE image fits each candidate scene. Returns {scene index: score 0-10}.
    For every model, every API key is tried (rotating on ANY failure). Raises only when all keys failed on all models."""
    import requests
    lines = []
    for i, narr, name, prompt in scene_rows:
        lines.append('scene ' + str(i) + ': narration (Hindi): ' + narr[:300].replace('\n', ' ') +
                     ' | intended image: ' + (name or 'unknown') + ' | prompt: ' + prompt[:250].replace('\n', ' '))
    text = ('You are matching ONE generated image to the scenes of a short video. Candidate scenes:\n' + '\n'.join(lines) +
            '\n\nLook at the image (file name: ' + image['name'] + ') and rate from 0 to 10 how well it shows EACH scene '
            '(10 = clearly this scene, 0 = unrelated). Reply ONLY with JSON: {"scores": {"<scene number>": <0-10>}} '
            'with every scene number listed above.')
    body = {'contents': [{'role': 'user', 'parts': [
        {'text': text},
        {'inline_data': {'mime_type': 'image/jpeg', 'data': thumb_b64(image['path'])}}]}],
        'generationConfig': {'maxOutputTokens': 1500, 'temperature': 0.1, 'responseMimeType': 'application/json'}}
    keys = gemini.api_keys()
    last = ''
    for sweep in range(2):  # second sweep catches short-lived overload/rate limits
        for model in VISION_MODELS:
            for k in range(len(keys)):
                key = keys[(start_key + k) % len(keys)]
                try:
                    r = requests.post('https://generativelanguage.googleapis.com/v1beta/models/' + model + ':generateContent',
                                      headers={'x-goog-api-key': key, 'Content-Type': 'application/json'},
                                      data=json.dumps(body), timeout=120)
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
    """Returns {scene index: absolute image path} for the scenes that got a confident Flow image."""
    images = find_images(flow_dir)
    if not images:
        log('no Flow images found in ' + flow_dir)
        return {}
    log(str(len(images)) + ' Flow images: ' + ', '.join(i['name'] for i in images))
    meta = find_meta(flow_dir)
    names = {}
    submitted = set(i for i, s in enumerate(scenes) if str(s.get('image_prompt') or '').strip())
    if meta and meta.get('scene_count') == len(scenes) and isinstance(meta.get('scenes'), list):
        submitted = set()
        for m in meta['scenes']:
            i = m.get('index')
            if isinstance(i, int) and 0 <= i < len(scenes):
                submitted.add(i)
                names[i] = clean_name(m.get('name') or '')
    elif meta:
        log('scene count differs from the Flow meta, ignoring the short names')
    elif not meta:
        log('no Flow meta file found, filename matching is skipped; Gemini vision decides')
    assigned = {}
    method = {}
    used = set()
    by_name = dict((im['name'], im) for im in images)

    # 1) filename vs short name
    pairs = []
    by_s, by_i = defaultdict(list), defaultdict(list)
    for i in sorted(submitted):
        if not names.get(i):
            continue
        for im in images:
            sc = score(names[i], im['slug'])
            pairs.append((sc, i, im['name']))
            by_s[i].append(sc)
            by_i[im['name']].append(sc)

    def clear(lst, sc):
        second = sorted(lst, reverse=True)[1] if len(lst) > 1 else 0.0
        return sc - second >= MIN_MARGIN

    for sc, i, f in sorted(pairs, key=lambda x: -x[0]):
        if sc < MIN_SCORE or i in assigned or f in used:
            continue
        if clear(by_s[i], sc) and clear(by_i[f], sc):
            assigned[i] = f
            used.add(f)
            method[i] = 'filename'
    log('filename step matched ' + str(len(assigned)) + ' scene(s)')

    # 2) Gemini 3.1 vision, one request per remaining image, all keys tried on failure
    left_s = sorted(i for i in submitted if i not in assigned)
    left_i = [im for im in images if im['name'] not in used]
    vision_failed = 0
    if left_s and left_i:
        rows = [(i, str(scenes[i].get('narration') or ''), names.get(i, ''), str(scenes[i].get('image_prompt') or '')) for i in left_s]
        cand = []  # (score, scene, image name)
        for n, im in enumerate(left_i):
            try:
                sc = vision_scores(im, rows, start_key=n)
                log('vision scores for ' + im['name'] + ': ' + ', '.join(str(i + 1) + '=' + str(int(v)) for i, v in sorted(sc.items())))
                for i, v in sc.items():
                    if i in left_s:
                        cand.append((v, i, im['name']))
            except Exception as e:  # noqa
                vision_failed += 1
                log('vision failed for ' + im['name'] + ': ' + str(e)[:150])
        for v, i, f in sorted(cand, key=lambda x: -x[0]):
            if v < VISION_MIN or i in assigned or f in used:
                continue
            assigned[i] = f
            used.add(f)
            method[i] = 'gemini'

    # 3) elimination: one scene and one image left, vision found nothing for it, and every scene produced an image
    left_s = [i for i in sorted(submitted) if i not in assigned]
    left_i = [im for im in images if im['name'] not in used]
    if len(left_s) == 1 and len(left_i) == 1 and len(images) == len(submitted):
        assigned[left_s[0]] = left_i[0]['name']
        method[left_s[0]] = 'elimination'

    result = dict((i, by_name[f]['path']) for i, f in assigned.items())
    log('matched ' + str(len(result)) + ' of ' + str(len(scenes)) + ' scenes: ' +
        ', '.join(str(i + 1) + '=' + assigned[i] + ' (' + method[i] + ')' for i in sorted(assigned)))
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
