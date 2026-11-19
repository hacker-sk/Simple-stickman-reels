"""Finished package written in Claude chat. It is the only input of the workflow: no topic, script or image-prompt step exists.

{
  "title": "...", "description": "...",
  "hashtags": ["..."],                                               (optional, shown at the end of the description)
  "hook": "opening line shown above the picture"  or  {"line": "...", "focus": "..."},   (optional, default = script opening)
  "art_style": "indian_storybook|sketchbook_doodle|whimsical_indian|editorial_pencil|stickman_sepia|village_storybook",
                                                                     (optional, random when missing)
  "voice_style": "delivery style for this script",                    (optional, default style when empty)
  "scenes": [{"narration": "Hindi in Devanagari", "image_prompt": "English prompt used as written"}, ...]
}

Background is always plain black and there is never background music.
"""
import json
import re
import unicodedata

from . import styles

MAX_PROMPT = 1900
NL = chr(10)
_ENDS_P = re.compile(r'[,;:\u0964?!.]$')


def _s(v):
    return str(v if v is not None else '').strip()


def _style_key(value):
    v = _s(value)
    if not v:
        return None
    if v in styles.STYLES:
        return v
    for k, st in styles.STYLES.items():
        if st['name'].lower() == v.lower():
            return k
    return None


def _add_tag(out, seen, h):
    t = re.sub(r'[#\s]+', '', str(h or ''))
    t = ''.join(ch for ch in t if unicodedata.category(ch)[0] in 'LMN' or ch == '_')
    if len(t) < 2 or len(t) > 40 or t.lower() in seen:
        return
    seen.add(t.lower())
    out.append('#' + t)


def _finish_punctuation(scenes):
    """The voice takes its pauses from punctuation: make sure the narration ends with one and, when it has none at all, add light ones."""
    ends = lambda t: bool(_ENDS_P.search(str(t).strip()))
    if not any(ends(s['narration']) for s in scenes):
        for i, s in enumerate(scenes):
            t = s['narration'].strip()
            if i == len(scenes) - 1:
                s['narration'] = t + '\u0964'
            elif i % 2 == 1:
                s['narration'] = t + ','
    else:
        last = scenes[-1]['narration'].strip()
        scenes[-1]['narration'] = last if ends(last) else last + '\u0964'
    return scenes


def parse(raw):
    """Returns {'prep', 'scenes', 'hook', 'style_key', 'voice_style'}; raises RuntimeError with a readable message when the package is unusable."""
    try:
        b = json.loads(raw)
    except ValueError as e:
        raise RuntimeError('package is not valid JSON: ' + str(e)[:120])
    if not isinstance(b, dict):
        raise RuntimeError('package must be a JSON object')
    title, description = _s(b.get('title')), _s(b.get('description'))
    if not title:
        raise RuntimeError('package: title is missing')
    if not description:
        raise RuntimeError('package: description is missing')
    in_scenes = b.get('scenes') if isinstance(b.get('scenes'), list) else []
    if not in_scenes:
        raise RuntimeError('package: scenes list is empty')
    scenes = []
    for i, s in enumerate(in_scenes):
        s = s if isinstance(s, dict) else {}
        n, p = _s(s.get('narration')), _s(s.get('image_prompt'))
        if not n:
            raise RuntimeError('package: scene %d has no narration' % (i + 1))
        if re.search(r'[A-Za-z]', n):
            raise RuntimeError('package: scene %d narration has Latin letters; write English words in Devanagari' % (i + 1))
        if len(p) < 40:
            raise RuntimeError('package: scene %d has no usable image_prompt' % (i + 1))
        scenes.append({'narration': n, 'image_prompt': p[:MAX_PROMPT]})
    scenes = _finish_punctuation(scenes)
    seen, tags = set(), []
    for h in (b.get('hashtags') if isinstance(b.get('hashtags'), list) else [])[:10]:
        _add_tag(tags, seen, h)
    _add_tag(tags, seen, 'Shorts')
    _add_tag(tags, seen, 'Hindi')
    prep = {'title': title[:90], 'description': description + NL + NL + ' '.join(tags),
            'mood': _s(b.get('mood')).lower() or 'emotional', 'scenes': scenes}
    hook = b.get('hook')
    if isinstance(hook, dict):
        hook = {'line': _s(hook.get('line') or hook.get('text')), 'focus': _s(hook.get('focus'))}
    elif isinstance(hook, str):
        hook = _s(hook)
    else:
        hook = None
    return {'prep': prep, 'scenes': scenes, 'hook': hook or None, 'style_key': _style_key(b.get('art_style') or b.get('artStyle')),
            'voice_style': _s(b.get('voice_style') or b.get('style_instruction') or b.get('gemini_style'))}
