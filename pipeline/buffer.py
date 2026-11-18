"""Buffer publishing: port of the n8n node 'Schedule on Buffer (YouTube + Instagram + Facebook)'.

BUFFER_TOKEN comes from a GitHub Secret. The channel ids come from repository variables:
BUFFER_YOUTUBE_CHANNEL_ID, BUFFER_INSTAGRAM_CHANNEL_ID and (optional) BUFFER_FACEBOOK_CHANNEL_ID.
The token is never logged: every message that leaves this module is passed through redact().

Thumbnail: Buffer's API rejects a custom thumbnail image on a video (thumbnailUrl), so the renderer puts the thumbnail at the very end of the
video (pipeline/thumb_frame.py) and publish() takes the position of that frame in milliseconds. It is sent as the video asset's
metadata.thumbnailOffset. Buffer supports it for Instagram (also TikTok and Pinterest) only, so only the Instagram post gets it; YouTube and
Facebook are posted as before. When Buffer refuses it, the same post is made again without it, with a warning.
"""
import datetime
import json
import os
import re
import time

import requests

API_URL = 'https://api.buffer.com'
NL = chr(10)


def log(*a):
    print('[buffer]', *a, flush=True)


def _token():
    t = os.environ.get('BUFFER_TOKEN', '').strip()
    if not t:
        raise RuntimeError('BUFFER_TOKEN is not set (add it as a GitHub Actions secret)')
    return t


def redact(text):
    t = os.environ.get('BUFFER_TOKEN', '').strip()
    text = str(text)
    return text.replace(t, '***') if t else text


def call(query, token=None, tries=3):
    """One Buffer GraphQL request. Retries temporary failures (HTTP 429/5xx, network errors)."""
    token = token or _token()
    last = ''
    for i in range(tries):
        try:
            r = requests.post(API_URL, headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
                              data=json.dumps({'query': query}), timeout=60)
            if r.status_code in (429, 500, 502, 503, 504):
                last = 'HTTP ' + str(r.status_code)
            else:
                try:
                    body = r.json()
                except Exception:  # noqa
                    raise RuntimeError('Buffer HTTP ' + str(r.status_code) + ': ' + redact(r.text[:200]))
                if body.get('errors'):
                    raise RuntimeError('Buffer error: ' + redact(json.dumps(body['errors'], ensure_ascii=False))[:400])
                if r.status_code != 200:
                    raise RuntimeError('Buffer HTTP ' + str(r.status_code))
                return body.get('data') or {}
        except requests.RequestException as e:
            last = 'network error: ' + redact(e)[:150]
        if i < tries - 1:
            time.sleep(5 * (i + 1))
    raise RuntimeError('Buffer is not reachable (' + last + ')')


def cap_tags(text, n):
    """The description ends with a hashtag line. YouTube gets all of them; Instagram and Facebook the first n."""
    i = text.rfind(NL + NL)
    if i < 0:
        return text
    tail = text[i + 2:].strip().split()
    if not tail or not all(t[:1] == '#' for t in tail):
        return text
    return text[:i] + NL + NL + ' '.join(tail[:n])


def list_channels(token=None):
    orgs = call('query { account { organizations { id } } }', token)
    org_id = orgs['account']['organizations'][0]['id']
    data = call('query { channels(input: { organizationId: ' + json.dumps(org_id) + ' }) { id name service } }', token)
    return data.get('channels') or []


def _create_post(token, channel_id, text, due_at, video_url, metadata, thumb_offset=0):
    video = 'url: ' + json.dumps(video_url)
    if thumb_offset:
        video += ', metadata: { thumbnailOffset: ' + str(int(thumb_offset)) + ' }'
    q = ('mutation { createPost(input: { text: ' + json.dumps(text, ensure_ascii=False) + ', channelId: ' + json.dumps(channel_id) +
         ', schedulingType: automatic, mode: customScheduled, dueAt: ' + json.dumps(due_at) +
         ', assets: [{ video: { ' + video + ' } }], metadata: { ' + metadata +
         ' } }) { ... on PostActionSuccess { post { id dueAt status } } ... on MutationError { message } } }')
    res = call(q, token)
    cp = res.get('createPost') or {}
    if cp.get('message'):
        raise RuntimeError(str(cp['message']))
    return (cp.get('post') or {}).get('id')


def _post(token, name, channel_id, text, due_at, video_url, metadata, thumb_offset, out):
    """With the thumbnail offset first; when Buffer does not take it, the same post again without it (plus a warning)."""
    try:
        return _create_post(token, channel_id, text, due_at, video_url, metadata, thumb_offset)
    except Exception as e:  # noqa
        if not thumb_offset:
            raise
        out['warnings'].append(name + ': thumbnail offset not accepted (' + redact(e)[:150] + '), posted without it')
        log(name + ': thumbnail offset not accepted, posting without it')
        return _create_post(token, channel_id, text, due_at, video_url, metadata, 0)


def due_at(seconds=60):
    d = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=seconds)
    return d.strftime('%Y-%m-%dT%H:%M:%S.') + '%03dZ' % (d.microsecond // 1000)


def publish(video_url, title, description, thumbnail_offset_ms=0):
    """Schedule the video on YouTube and Instagram (required) and Facebook (best effort).

    thumbnail_offset_ms: position of the thumbnail frame in the video (the end frame added by pipeline/thumb_frame.py), 0 = none.
    Sent to Instagram only (the only one of the three channels Buffer supports it for).
    Returns {'results': [...], 'errors': [...], 'warnings': [...], 'post_ids': {...}}.
    'errors' lists YouTube / Instagram failures; the caller decides what that means for the run."""
    token = _token()
    yt_id = os.environ.get('BUFFER_YOUTUBE_CHANNEL_ID', '').strip()
    ig_id = os.environ.get('BUFFER_INSTAGRAM_CHANNEL_ID', '').strip()
    fb_id = os.environ.get('BUFFER_FACEBOOK_CHANNEL_ID', '').strip()
    if not yt_id or not ig_id:
        chans = [{'id': c.get('id'), 'name': c.get('name'), 'service': c.get('service')} for c in list_channels(token)]
        raise RuntimeError('Set the BUFFER_YOUTUBE_CHANNEL_ID and BUFFER_INSTAGRAM_CHANNEL_ID repository variables. '
                           'Your Buffer channels: ' + json.dumps(chans, ensure_ascii=False))
    title = str(title)[:100]
    due = due_at(60)
    out = {'results': [], 'errors': [], 'warnings': [], 'post_ids': {}}
    short = cap_tags(title + NL + NL + description, 5)
    jobs = [('YouTube', yt_id, description, 'youtube: { title: ' + json.dumps(title, ensure_ascii=False) + ', categoryId: "22" }', 0),
            ('Instagram', ig_id, short, 'instagram: { type: reel, shouldShareToFeed: true }', int(thumbnail_offset_ms or 0))]
    for name, cid, text, meta, offset in jobs:
        try:
            pid = _post(token, name, cid, text, due, video_url, meta, offset, out)
            out['results'].append(name + ' scheduled')
            out['post_ids'][name] = pid
            log(name + ' scheduled')
        except Exception as e:  # noqa
            out['errors'].append(name + ': ' + redact(e)[:300])
            log(name + ' failed: ' + redact(e)[:200])
    try:
        if not fb_id:
            fbs = [c for c in list_channels(token) if str(c.get('service')).lower() == 'facebook']
            pick = fbs[0] if len(fbs) == 1 else next((c for c in fbs if re.search(r'8\s*minute', str(c.get('name')), re.I)), None)
            if not pick:
                raise RuntimeError('several Facebook channels found, set BUFFER_FACEBOOK_CHANNEL_ID: ' + json.dumps(fbs, ensure_ascii=False)
                                   if fbs else 'no Facebook channel found in Buffer')
            fb_id = pick['id']
        pid = _post(token, 'Facebook', fb_id, short, due, video_url, 'facebook: { type: reel }', 0, out)
        out['results'].append('Facebook scheduled')
        out['post_ids']['Facebook'] = pid
    except Exception as e:  # noqa
        out['warnings'].append('Facebook: ' + redact(e)[:300])
    return out
