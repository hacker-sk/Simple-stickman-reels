#!/usr/bin/env python3
"""Simple stickman reels: payload (package JSON) -> render (run_hindi.py) -> output check -> Buffer. One job, GitHub Actions.

Environment (set by .github/workflows/shorts.yml):
  PACKAGE      the package JSON from Claude chat, see pipeline/package.py (required)
  ART_STYLE    optional fallback style when the package has no art_style; empty or random = one of the six styles at random

Voice: Gemini prebuilt voice Iapetus with the delivery style written for the script (package voice_style), see pipeline/voice_patch.py.
Images: Flux Schnell on Cloudflare (CF_ACCOUNT_ID / CF_API_TOKEN and the _2 pair). Look: plain black background, no music (pipeline/look_patch.py).
"""
import json
import os
import subprocess
import sys
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pipeline import buffer, package, styles, voice_patch  # noqa: E402

OUT_DIR = os.environ.get('OUT_DIR', 'output')
WORK_DIR = os.environ.get('WORK_DIR', 'work')
RENDER_TIMEOUT = 80 * 60


def log(*a):
    print('[run_shorts]', *a, flush=True)


def env(name):
    return os.environ.get(name, '').strip()


def set_output(key, value):
    path = env('GITHUB_OUTPUT')
    if path:
        with open(path, 'a', encoding='utf-8') as fh:
            fh.write(key + '=' + str(value) + '\n')


def summary(lines):
    path = env('GITHUB_STEP_SUMMARY')
    text = '\n'.join(lines) + '\n'
    if path:
        with open(path, 'a', encoding='utf-8') as fh:
            fh.write(text)
    else:
        print(text)


def build_job(pkg, style):
    """Render payload, read by render_hindi.py from the job file."""
    prep = pkg['prep']
    job = voice_patch.voice_payload(pkg.get('voice_style'))
    job.update({'title': prep['title'], 'mood': prep['mood'], 'art_style': style['name'], 'scenes': pkg['scenes']})
    if pkg.get('hook'):
        job['hook'] = pkg['hook']
    return job


def run_renderer(job):
    os.makedirs(WORK_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)
    for name in ('video.mp4', 'result.json'):
        p = os.path.join(OUT_DIR, name)
        if os.path.exists(p):
            os.remove(p)
    job_path = os.path.abspath(os.path.join(WORK_DIR, 'job.json'))
    with open(job_path, 'w', encoding='utf-8') as fh:
        json.dump(job, fh, ensure_ascii=False)
    child = dict(os.environ)
    child['PAYLOAD'] = json.dumps({'job_path': job_path})
    child.setdefault('WORK_DIR', WORK_DIR)
    child.setdefault('OUT_DIR', OUT_DIR)
    log('starting the renderer (' + str(len(job['scenes'])) + ' scenes)')
    try:
        rc = subprocess.run([sys.executable, os.path.join(ROOT, 'run_hindi.py')], cwd=ROOT, env=child, timeout=RENDER_TIMEOUT).returncode
    except subprocess.TimeoutExpired:
        raise RuntimeError('The renderer ran longer than ' + str(RENDER_TIMEOUT // 60) + ' minutes and was stopped')
    if rc != 0:
        raise RuntimeError('The renderer failed with exit code ' + str(rc) + ', see the "Make the video" log above')


def validate_output():
    """The video must exist, be a real portrait video with sound, and result.json must report success and a URL."""
    video = os.path.join(OUT_DIR, 'video.mp4')
    if not os.path.exists(video) or os.path.getsize(video) < 100000:
        raise RuntimeError('output/video.mp4 is missing or too small')
    probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,width,height', '-show_entries',
                            'format=duration', '-of', 'json', video], capture_output=True, text=True)
    if probe.returncode != 0:
        raise RuntimeError('ffprobe could not read output/video.mp4: ' + probe.stderr[:200])
    info = json.loads(probe.stdout)
    streams = info.get('streams') or []
    vs = [s for s in streams if s.get('codec_type') == 'video']
    if not vs or not any(s.get('codec_type') == 'audio' for s in streams):
        raise RuntimeError('output/video.mp4 has no video or no audio stream')
    if int(vs[0].get('height') or 0) <= int(vs[0].get('width') or 0):
        raise RuntimeError('output/video.mp4 is not portrait (' + str(vs[0].get('width')) + 'x' + str(vs[0].get('height')) + ')')
    duration = float((info.get('format') or {}).get('duration') or 0)
    if not 5 <= duration <= 180:
        raise RuntimeError('video duration ' + str(round(duration, 1)) + 's is outside 5 to 180 seconds')
    rp = os.path.join(OUT_DIR, 'result.json')
    if not os.path.exists(rp):
        raise RuntimeError('output/result.json is missing')
    with open(rp, encoding='utf-8') as fh:
        result = json.load(fh)
    if result.get('status') != 'success':
        raise RuntimeError('Renderer reported: ' + str(result.get('message') or result.get('status')))
    urls = [u for u in (result.get('video_urls') or []) if str(u).startswith('http')]
    if not urls:
        raise RuntimeError('No public video URL (every upload host failed); the video is only in the release copy')
    return result, urls, duration


def publish_to_buffer(urls, title, description):
    """Try each hosted URL until YouTube or Instagram accepts the post."""
    last = None
    for url in urls:
        out = buffer.publish(url, title, description)
        last = out
        if out['post_ids'].get('YouTube') or out['post_ids'].get('Instagram'):
            return out
        log('no required channel accepted ' + url + ', trying the next host')
    return last


def main():
    started = time.time()
    lines = ['## Simple stickman reel run']
    try:
        if not env('PACKAGE'):
            raise RuntimeError('No package given: push jobs/package.json or fill in the package input')
        pkg = package.parse(env('PACKAGE'))
        style_key, style = styles.get_style(pkg['style_key'] or env('ART_STYLE') or None)
        prep = pkg['prep']
        lines += ['- Title: ' + prep['title'], '- Style: ' + style['name'] + ', ' + str(len(pkg['scenes'])) + ' scenes',
                  '- Voice: Iapetus, ' + ('own delivery style' if pkg.get('voice_style') else 'default delivery style') +
                  ' | Background: plain black | Music: off']
        run_renderer(build_job(pkg, style))
        result, urls, duration = validate_output()
        set_output('video_ready', 'true')
        lines += ['- Video: ' + str(round(duration, 1)) + 's, ' + str(result.get('size_mb')) + ' MB', '- Hosted: ' + ', '.join(urls)]
        out = publish_to_buffer(urls, prep['title'], prep['description'])
        scheduled = sorted((out or {}).get('post_ids') or {})
        lines.append('- Buffer scheduled: ' + (', '.join(scheduled) or 'nothing'))
        for w in (out or {}).get('warnings') or []:
            lines.append('- Warning: ' + w)
        errors = (out or {}).get('errors') or []
        if not scheduled or errors:
            raise RuntimeError('Buffer publishing problem: ' + ('; '.join(errors) or 'no channel accepted the video'))
        lines.append('- Done in ' + str(int(time.time() - started)) + 's')
        summary(lines)
        return 0
    except Exception as e:  # noqa
        traceback.print_exc()
        lines += ['', '**FAILED:** ' + buffer.redact(e)[:500]]
        summary(lines)
        return 1


if __name__ == '__main__':
    sys.exit(main())
