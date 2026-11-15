"""Gemini text client used by every pipeline step.

Ports the n8n 'Fallback Control' and 'Fallback Handler' nodes: the same model order, up to 6 attempts per
model with exponential backoff for temporary errors, then the next model. API keys rotate on quota errors.
Keys come from the GEMINI_API_KEY, GEMINI_API_KEY_2 ... _6 secrets (the same secrets the renderer uses).
"""
import json
import os
import random
import re
import time

import requests

MODELS = ['gemini-3.1-flash-lite', 'gemini-3.5-flash-lite', 'gemini-3.6-flash', 'gemini-2.5-flash-lite',
          'gemini-3.8-flash', 'gemini-2.5-flash', 'gemini-2.5-pro']
MAX_ATTEMPTS_PER_MODEL = 6
WAIT_BASE = 5
WAIT_MAX = 45
SWITCH_WAIT = 2

TRANSIENT = re.compile(
    r'(^|[^0-9])(408|429|500|502|503|504)([^0-9]|$)|overload|high demand|unavailable|rate.?limit|too many requests'
    r'|resource.?exhausted|quota|timed? ?out|timeout|etimedout|econnreset|econnrefused|enotfound|eai_again'
    r'|socket hang up|network|try again|temporar|internal error|not able to process|bad gateway|gateway|busy'
    r'|capacity|deadline|aborted', re.I)


def log(*a):
    print('[gemini]', *a, flush=True)


def api_keys():
    out = []
    for suffix in ('', '_2', '_3', '_4', '_5', '_6'):
        k = os.environ.get('GEMINI_API_KEY' + suffix, '').strip()
        if k and k not in out:
            out.append(k)
    if not out:
        raise RuntimeError('No GEMINI_API_KEY secret is set')
    return out


def response_text(resp):
    """All non-thought text parts of a generateContent response."""
    cands = resp.get('candidates') or [{}]
    parts = ((cands[0].get('content') or {}).get('parts')) or []
    return ''.join(p.get('text', '') for p in parts if p.get('text') and not p.get('thought'))


def extract_json(raw):
    """Parse the first {...} block of a reply (markdown fences removed). Returns None when it is not valid JSON."""
    raw = re.sub(r'```json', '', raw or '', flags=re.I).replace('```', '')
    s, e = raw.find('{'), raw.rfind('}')
    if s < 0 or e <= s:
        return None
    try:
        return json.loads(raw[s:e + 1])
    except Exception:  # noqa
        return None


def generate(system, user, label, max_tokens=8000, temperature=0.8, search=False, json_mode=False, models=None):
    """One text generation with the n8n fallback behaviour. Returns the reply text."""
    models = models or MODELS
    keys = api_keys()
    key_i = 0
    history = []
    for model in models:
        attempt = 1
        while attempt <= MAX_ATTEMPTS_PER_MODEL:
            body = {'contents': [{'role': 'user', 'parts': [{'text': user}]}],
                    'generationConfig': {'maxOutputTokens': max_tokens, 'temperature': temperature}}
            if system:
                body['systemInstruction'] = {'parts': [{'text': system}]}
            if search:
                body['tools'] = [{'google_search': {}}]
            elif json_mode:
                body['generationConfig']['responseMimeType'] = 'application/json'
            msg = ''
            try:
                r = requests.post('https://generativelanguage.googleapis.com/v1beta/models/' + model + ':generateContent',
                                  headers={'x-goog-api-key': keys[key_i % len(keys)], 'Content-Type': 'application/json'},
                                  data=json.dumps(body), timeout=300)
                if r.status_code == 200:
                    text = response_text(r.json())
                    if text.strip():
                        return text
                    msg = 'empty reply (' + str((r.json().get('candidates') or [{}])[0].get('finishReason')) + ')'
                else:
                    msg = 'HTTP ' + str(r.status_code) + ': ' + r.text[:200]
            except Exception as e:  # noqa
                msg = str(e)
            transient = bool(TRANSIENT.search(msg))
            history.append((model, attempt, transient, msg[:160]))
            log(label + ': ' + model + ' try ' + str(attempt) + ' failed (' + ('temporary' if transient else 'not retryable') + '): ' + msg[:120])
            if 'quota' in msg.lower() or '429' in msg:
                key_i += 1  # rotate to the next API key on quota errors
            if transient and attempt < MAX_ATTEMPTS_PER_MODEL:
                time.sleep(min(WAIT_MAX, WAIT_BASE * 2 ** (attempt - 1)) + random.random())
                attempt += 1
            else:
                time.sleep(SWITCH_WAIT)
                break
    lines = '; '.join(m + ' x' + str(sum(1 for h in history if h[0] == m)) for m in dict.fromkeys(h[0] for h in history))
    raise RuntimeError('All models failed in ' + label + '. ' + lines + ' | last: ' + (history[-1][3] if history else ''))
