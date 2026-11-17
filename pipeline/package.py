"""Finished package written in Claude chat (the old n8n 'Claude Script Input' webhook, now the `package` workflow input).

The package carries everything the renderer needs, so no topic, script or image-prompt step runs:

{
  "title": "...", "description": "...", "mood": "emotional",          (mood: motivational|emotional|neutral; the older inspiring|mysterious|dramatic|upbeat|calm still work)
  "hashtags": ["..."], "tags": ["..."],                              (optional, same handling as the script step)
  "hook": "opening line shown above the picture"  or  {"line": "...", "focus": "..."},   (optional, default = script opening)
  "art_style": "painterly|sepia|night|golden",                       (optional, default = the art_style input)
  "scenes": [{"narration": "Hindi in Devanagari", "image_prompt": "English prompt used as written"}, ...]
}

The mood picks the background music: one random song named <mood>_NN or neutral_NN in music_hindi/ (see music_picker.py).

Same checks as the n8n 'Claude Package' node.
"""
import json

from . import script, styles

MAX_PROMPT = 1900
MUSIC_MOODS = ('motivational', 'emotional', 'neutral')


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


def parse(raw):
    """Returns {'prep', 'scenes', 'hook', 'style_key'}; raises RuntimeError with a readable message when the package is unusable."""
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
    mood = _s(b.get('mood')).lower()
    if mood not in MUSIC_MOODS and mood not in script.MOODS:
        raise RuntimeError('package: mood must be one of ' + ', '.join(MUSIC_MOODS))
    in_scenes = b.get('scenes') if isinstance(b.get('scenes'), list) else []
    if not in_scenes:
        raise RuntimeError('package: scenes list is empty')
    scenes = []
    for i, s in enumerate(in_scenes):
        s = s if isinstance(s, dict) else {}
        n, p = _s(s.get('narration')), _s(s.get('image_prompt'))
        if not n:
            raise RuntimeError('package: scene %d has no narration' % (i + 1))
        if script._has_latin([{'narration': n}]):
            raise RuntimeError('package: scene %d narration has Latin letters; write English words in Devanagari' % (i + 1))
        if len(p) < 40:
            raise RuntimeError('package: scene %d has no usable image_prompt' % (i + 1))
        scenes.append({'narration': n, 'image_prompt': p[:MAX_PROMPT]})
    prep = script.prepare_narration({'title': title, 'description': description, 'hashtags': b.get('hashtags'),
                                     'tags': [_s(t) for t in (b.get('tags') or []) if _s(t)] if isinstance(b.get('tags'), list) else [],
                                     'mood': mood, 'scenes': scenes})
    scenes = [{'narration': _s(s['narration']), 'image_prompt': _s(s['image_prompt'])} for s in prep['scenes']]
    hook = b.get('hook')
    if isinstance(hook, dict):
        hook = {'line': _s(hook.get('line') or hook.get('text')), 'focus': _s(hook.get('focus'))}
    elif isinstance(hook, str):
        hook = _s(hook)
    else:
        hook = None
    return {'prep': prep, 'scenes': scenes, 'hook': hook or None, 'style_key': _style_key(b.get('art_style') or b.get('artStyle'))}
