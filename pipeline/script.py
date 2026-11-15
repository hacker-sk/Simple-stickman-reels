"""Script step: ports the n8n nodes 'Write Script Build Prompt', 'Write Script', 'Validate Script',
'Prepare Script Retry', 'Prepare Narration' and 'Number Chunks'. Prompts live in script_prompts_truth.py and
script_prompts_story.py and are copied verbatim from the original workflow.
"""
import re
import unicodedata

from . import gemini
from .script_prompts_story import PATTERN_SHAPE_TEXT, SYS_STORY
from .script_prompts_truth import SYS_TRUTH

NL = chr(10)
MOODS = ('inspiring', 'emotional', 'mysterious', 'dramatic', 'upbeat', 'calm')
SCRIPT_LABEL = 'SCRIPT PROVIDED (FINAL, DO NOT WRITE OR CHANGE, EXCEPT WRITE ENGLISH WORDS IN DEVANAGARI): '
PUNCT_RULE = "\n\nPUNCTUATION RULE FOR THE SCENES LIST (very important: the narration is read aloud by a text-to-speech voice that takes ALL of its pauses and pacing from punctuation): when you split the narration into phrases, keep every punctuation mark attached to the word it follows, exactly where it belongs in the sentence. Never strip, drop or move punctuation when you cut the narration into phrases. A phrase that ends a sentence ends with the Hindi full stop । or a question mark ?, a phrase that ends a clause or a natural breath ends with a comma, and the last phrase of the whole narration ends with । or ?. Joining all the phrases with a single space must give back the complete narration with all its commas, full stops and question marks in the right places. In script provided mode keep the user's own punctuation exactly as written; if the user's script has no punctuation at all, add only commas and । or ? at natural sentence and clause ends, without adding or removing any word, and without changing any word except writing English words in Devanagari."
SCRIPT_PHRASES = ['use this as a script', 'use this as my script', 'use this as script', 'use this script',
                  'use it as script', 'this is my script']
_SEP = ':;,-' + chr(8211) + chr(8212) + ' ' + NL + chr(9) + chr(13)
_ENDS_P = re.compile(r'[,;:\u0964?!.]$')


def log(*a):
    print('[script]', *a, flush=True)


# ----------------------------------------------------------------------------- manual input
def parse_manual(idea='', script=''):
    """Port of the 'Latest Part?' rules. Returns (topic, use_as_script).

    A finished script (the workflow's script input) is used as written. An idea that contains one of the old
    'use this as a script' phrases and at least 5 more words is treated as a finished script too."""
    script = (script or '').strip()
    idea = (idea or '').strip()
    if script:
        return script, True
    low = idea.lower()
    for ph in SCRIPT_PHRASES:
        at = low.find(ph)
        if at >= 0:
            rest = idea[:at] + NL + idea[at + len(ph):]
            rest = rest.strip(_SEP)
            if len(rest.split()) >= 5:
                return rest, True
            break
    return idea, False


# ----------------------------------------------------------------------------- prompts
def system_prompt(truth, provided):
    return SYS_TRUTH if (truth and not provided) else SYS_STORY


def build_message(topic, provided=False, ctx=None, retry_note=''):
    """Port of buildMsg. ctx is the topic context (niche, nicheGuide, shape) of an automatic run, or None."""
    msg = (SCRIPT_LABEL if provided else 'Video topic: ') + topic
    if ctx and ctx.get('nicheGuide'):
        msg += (NL + NL + 'NICHE SCRIPT GUIDE for ' + str(ctx.get('niche', '')) +
                ' (a guide only, the idea decides the final shape): ' + ctx['nicheGuide'])
    if ctx and ctx.get('shape') == 'pattern':
        msg += NL + NL + PATTERN_SHAPE_TEXT
    if retry_note:
        msg += NL + NL + 'YOUR PREVIOUS ATTEMPT WAS REJECTED BECAUSE: ' + retry_note + '. Write the whole JSON again and fix exactly this.'
    return msg + PUNCT_RULE


# ----------------------------------------------------------------------------- validation
def _has_latin(scenes):
    return any(re.search(r'[A-Za-z]', str((x or {}).get('narration') or '')) for x in scenes)


def clean_tags(hashtags):
    seen, out = set(), []
    for h in (hashtags if isinstance(hashtags, list) else []):
        t = str(h or '').replace('#', '').replace(' ', '').strip()
        if 2 <= len(t) <= 40 and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def validate(data, truth=False, provided=False, tries=0):
    """Port of 'Validate Script'. Returns a list of problems (empty list = valid)."""
    problems = []
    if not isinstance(data, dict):
        return ['the reply was not valid JSON']
    sc = [x for x in data.get('scenes')] if isinstance(data.get('scenes'), list) else []
    if not sc:
        problems.append('the scenes list was empty')
    words = len(' '.join(str((x or {}).get('narration') or '') for x in sc).split())
    max_words = 125 if truth else 105
    if not provided and words > max_words:
        problems.append('the narration had ' + str(words) + ' Hindi words but the maximum is ' + str(max_words) + ', ' +
                        ('aim for 55 to 110 and cut filler' if truth else 'aim for 80 to 95 and cut filler'))
    if truth and tries < 2 and _has_latin(sc):
        problems.append('the narration still has English letters, write every English word in Devanagari the way a Hindi speaker says it (for example option as ऑप्शन)')
    if provided and tries < 2 and _has_latin(sc):
        problems.append('the narration still has English letters, write every English word in Devanagari the way a Hindi speaker says it (for example Internet as इंटरनेट) and keep everything else exactly as the user wrote it')
    if tries < 2:
        tags = clean_tags(data.get('hashtags'))
        hindi = sum(1 for t in tags if any(2304 <= ord(c) <= 2431 for c in t))
        if len(tags) != 8:
            problems.append('hashtags must be exactly 8 unique hashtags (3 broad, 3 topic-specific, 2 in Hindi Devanagari) but you gave ' + str(len(tags)))
        elif hindi != 2:
            problems.append('exactly 2 of the 8 hashtags must be written in Hindi Devanagari but you gave ' + str(hindi))
    return problems


# ----------------------------------------------------------------------------- generation
def write_script(topic, provided=False, ctx=None):
    """Write Script + Validate Script + Prepare Script Retry. Returns the validated script dict."""
    truth = bool((not provided) and ctx and ctx.get('scriptMode') == 'truth')
    system = system_prompt(truth, provided)
    tries = 0
    note = ''
    while True:
        msg = build_message(topic, provided, ctx, note)
        raw = gemini.generate(system, msg, 'Write Script', max_tokens=12000, temperature=0.8, search=True)
        data = gemini.extract_json(raw)
        problems = validate(data, truth, provided, tries)
        if not problems:
            return data
        log('script attempt ' + str(tries + 1) + ' rejected: ' + '; '.join(problems))
        if tries >= 2:
            raise RuntimeError('Script still failed validation after ' + str(tries + 1) + ' attempts: ' + '; '.join(problems))
        tries += 1
        note = '; '.join(problems)


# ----------------------------------------------------------------------------- narration
def _add_tag(out, seen, h):
    t = re.sub(r'[#\s]+', '', str(h or ''))
    t = ''.join(ch for ch in t if unicodedata.category(ch)[0] in 'LMN' or ch == '_')
    if len(t) < 2 or len(t) > 40:
        return
    if t.lower() in seen:
        return
    seen.add(t.lower())
    out.append('#' + t)


def prepare_narration(data):
    """Port of 'Prepare Narration': final punctuation, hashtag line, tag string. Returns the prep dict."""
    sc = [dict(s) for s in (data.get('scenes') or []) if isinstance(s, dict)]
    ends = lambda t: bool(_ENDS_P.search(str(t).strip()))
    if sc:
        if not any(ends(s.get('narration', '')) for s in sc):
            for i, s in enumerate(sc):
                t = str(s.get('narration', '')).strip()
                if i == len(sc) - 1:
                    s['narration'] = t + '\u0964'
                elif i % 2 == 1:
                    s['narration'] = t + ','
                else:
                    s['narration'] = t
        else:
            last = str(sc[-1].get('narration', '')).strip()
            sc[-1]['narration'] = last if ends(last) else last + '\u0964'
    narration = ' '.join(str(s.get('narration', '')) for s in sc)
    seen, tags_out = set(), []
    for h in (data.get('hashtags') if isinstance(data.get('hashtags'), list) else [])[:10]:
        _add_tag(tags_out, seen, h)
    _add_tag(tags_out, seen, 'Shorts')
    _add_tag(tags_out, seen, 'Hindi')
    return {'title': str(data.get('title') or '')[:90],
            'description': str(data.get('description') or '') + NL + NL + ' '.join(tags_out),
            'tags': ','.join(str(t) for t in (data.get('tags') or [])),
            'mood': str(data.get('mood') or '').lower().strip(),
            'scenes': sc, 'ttsText': narration}


SHOTS_DEFAULT = ['wide establishing shot', 'close-up of a meaningful detail', 'medium shot of the main action',
                 'over-the-shoulder or side view', 'low-angle dramatic view', 'top-down view',
                 'symbolic object close-up', 'silhouette or backlit wide shot']
SHOTS_SEPIA = ['wide establishing shot', 'close-up of a meaningful detail', 'medium shot of the main action', 'side view',
               'low-angle view', 'top-down view', 'close-up of a symbolic object', 'wide scene with a low horizon']


def number_chunks(prep, style_key=''):
    """Port of 'Number Chunks'."""
    shots = SHOTS_SEPIA if style_key == 'sepia' else SHOTS_DEFAULT
    numbered = NL.join(str(i + 1) + '. ' + str(s['narration']).strip() + ' [suggested framing: ' + shots[(i * 3 + 1) % len(shots)] + ']'
                       for i, s in enumerate(prep['scenes']))
    return {'title': prep['title'], 'ttsText': prep['ttsText'], 'count': len(prep['scenes']), 'numbered': numbered}
