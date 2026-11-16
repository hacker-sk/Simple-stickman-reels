#!/usr/bin/env python3
"""Google Flow images for the Hindi Shorts pipeline.

prepare : package JSON -> flow-batch/prompts/shorts_flow.json (prompts with an extra 'Image name: ...' line)
          + flow-batch/prompts/shorts_flow_meta.json (scene index -> short name). Sets the step output flow=true.
match   : (used by render_hindi_flow.py) scenes + Flow images folder -> {scene index: image path}.
          1) descriptive filename vs the scene's short name, 2) Gemini vision for what is left, 3) elimination.
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
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from pipeline import gemini  # noqa: E402

IMG_EXT = ('.png', '.jpg', '.jpeg', '.webp')
META_NAME = 'shorts_flow_meta.json'
NAME_MODELS = ['gemini-2.5-flash-lite', 'gemini-3.1-flash-lite', 'gemini-2.5-flash']
VISION_MODELS = ['gemini-2.5-flash', 'gemini-3.6-flash', 'gemini-2.5-flash-lite']
MIN_SCORE = 0.6
MIN_MARGIN = 0.1


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


def find_images(flow_dir):
    out = []
    for dp, dn, fn in os.walk(flow_dir):
        parts = dp.replace('\\', '/').split('/')
        if 'rejected' in parts or 'debug' in parts or 'raw' in parts:
            continue
        for f in sorted(fn):
            p = os.path.join(dp, f)
            if f.lower().endswith(IMG_EXT) and os.path.getsize(p) >= 10000:
                out.append({'name': f, 'path': os.path.abspath(p), 'slug': slug(f)})
    return out


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
    im.thumbnail((512, 512))
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=70)
    return base64.b64encode(buf.getvalue()).decode()


def vision_match(scene_rows, images):
    """Ask Gemini which image fits which scene. Returns {scene index: filename} (unvalidated)."""
    import requests
    lines = []
    for i, narr, name, prompt in scene_rows:
        lines.append('scene ' + str(i) + ': narration (Hindi): ' + narr[:300].replace('\n', ' ') +
                     ' | intended image: ' + (name or 'unknown') + ' | prompt: ' + prompt[:250].replace('\n', ' '))
    text = ('You match generated images to the scenes of a short video. Scenes:\n' + '\n'.join(lines) +
            '\n\nThe images follow, each preceded by its file name. For every scene choose the ONE image that best shows it, '
            'using each image at most once. Use null for a scene when no image clearly fits. Reply ONLY with JSON: '
            '{"matches": {"<scene number>": "<file name or null>"}}')
    parts = [{'text': text}]
    for img in images:
        parts.append({'text': 'IMAGE FILE: ' + img['name']})
        parts.append({'inline_data': {'mime_type': 'image/jpeg', 'data': thumb_b64(img['path'])}})
    body = {'contents': [{'role': 'user', 'parts': parts}],
            'generationConfig': {'maxOutputTokens': 2000, 'temperature': 0.1, 'responseMimeType': 'application/json'}}
    keys = gemini.api_keys()
    ki = 0
    last = ''
    for model in VISION_MODELS:
        for _ in range(len(keys) + 1):
            try:
                r = requests.post('https://generativelanguage.googleapis.com/v1beta/models/' + model + ':generateContent',
                                  headers={'x-goog-api-key': keys[ki % len(keys)], 'Content-Type': 'application/json'},
                                  data=json.dumps(body), timeout=180)
                if r.status_code == 200:
                    got = gemini.extract_json(gemini.response_text(r.json()))
                    m = (got or {}).get('matches')
                    if isinstance(m, dict):
                        return m
                    last = 'unparseable reply'
                    break
                last = 'HTTP ' + str(r.status_code) + ': ' + r.text[:120]
            except Exception as e:  # noqa
                last = str(e)[:120]
            log('vision ' + model + ' failed: ' + last)
            if '429' in last or 'quota' in last.lower():
                ki += 1
                continue
            break
    raise RuntimeError('Gemini vision failed: ' + last)


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

    # 2) Gemini vision for the leftovers
    left_s = sorted(i for i in submitted if i not in assigned)
    left_i = [im for im in images if im['name'] not in used]
    gemini_ok = False
    if left_s and left_i:
        try:
            rows = [(i, str(scenes[i].get('narration') or ''), names.get(i, ''), str(scenes[i].get('image_prompt') or '')) for i in left_s]
            got = vision_match(rows, left_i)
            gemini_ok = True
            for k, f in got.items():
                try:
                    i = int(k)
                except Exception:  # noqa
                    continue
                if i in left_s and i not in assigned and f in by_name and f not in used and by_name[f] in left_i:
                    assigned[i] = f
                    used.add(f)
                    method[i] = 'gemini'
        except Exception as e:  # noqa
            log('vision matching skipped: ' + str(e)[:200])

    # 3) elimination: one scene and one image left, and every scene produced an image
    left_s = [i for i in sorted(submitted) if i not in assigned]
    left_i = [im for im in images if im['name'] not in used]
    if not gemini_ok and len(left_s) == 1 and len(left_i) == 1 and len(images) == len(submitted):
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
