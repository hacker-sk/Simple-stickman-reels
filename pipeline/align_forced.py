"""Forced alignment of the KNOWN narration against the generated voice.

Whisper transcription has to recover the whole script by listening (it heard 87 of 118 words in the last run). Forced alignment already knows
the words and only has to find WHERE each one is spoken (WhisperX wav2vec2 alignment model, CPU). Words the model cannot place (digits,
latin text, punctuation-only) are interpolated between their timed neighbours.

forced_words() returns [(word, start, end)] with exactly one entry per script word, or raises when the result is not trustworthy, so the
caller can fall back to the older Whisper timing and then to the proportional estimate.
"""

MIN_TIMED = 0.85      # at least this share of the words must have been placed by the model itself
MAX_FIRST_START = 3.0  # seconds: the first word must start near the beginning of the audio
MIN_LAST_END = 0.80    # the last word must end in the last 20% of the audio at the earliest


def _place(script_words, got):
    """Walk both lists in order. A script word is 'placed' when the aligner returned the same word with a start and an end."""
    out = [None] * len(script_words)
    j = 0
    for k, w in enumerate(script_words):
        if j < len(got) and str(got[j].get('word', '')) == w:
            g = got[j]
            j += 1
            if g.get('start') is not None and g.get('end') is not None:
                out[k] = (float(g['start']), float(g['end']))
    return out


def _fill(script_words, placed, dur):
    """Give every unplaced word a time by sharing the gap between its timed neighbours out by letter count."""
    n = len(script_words)
    res = list(placed)
    k = 0
    while k < n:
        if res[k] is not None:
            k += 1
            continue
        a = k
        while k < n and res[k] is None:
            k += 1
        b = k  # res[a:b] are empty
        t0 = res[a - 1][1] if a > 0 else 0.0
        t1 = res[b][0] if b < n else float(dur)
        if t1 < t0:
            t1 = t0
        weights = [max(1, len(script_words[i])) for i in range(a, b)]
        total = float(sum(weights)) or 1.0
        t = t0
        for i, wt in zip(range(a, b), weights):
            step = (t1 - t0) * wt / total
            res[i] = (t, t + step)
            t += step
    return res


def forced_words(script_words, dur, voice_path, language='hi', log=print):
    import whisperx

    script_words = [w for w in script_words if w]
    if not script_words:
        raise RuntimeError('no script words')
    text = ' '.join(script_words)
    audio = whisperx.load_audio(voice_path)
    model, meta = whisperx.load_align_model(language_code=language, device='cpu')
    res = whisperx.align([{'text': text, 'start': 0.0, 'end': float(dur)}], model, meta, audio, 'cpu', return_char_alignments=False)
    got = []
    for seg in res.get('segments', []) or []:
        for w in seg.get('words', []) or []:
            got.append(w)
    placed = _place(script_words, got)
    timed = sum(1 for p in placed if p is not None)
    share = timed / float(len(script_words))
    log('forced alignment placed ' + str(timed) + ' of ' + str(len(script_words)) + ' words (' + str(int(share * 100)) + '%)')
    if share < MIN_TIMED:
        raise RuntimeError('only ' + str(int(share * 100)) + '% of the words could be placed')

    full = _fill(script_words, placed, dur)
    words = []
    prev_s = 0.0
    for w, (s, e) in zip(script_words, full):
        s = min(max(s, prev_s), float(dur))
        e = min(max(e, s), float(dur))
        words.append((w, s, e))
        prev_s = s

    if words[0][1] > MAX_FIRST_START:
        raise RuntimeError('first word starts at ' + str(round(words[0][1], 1)) + 's, not plausible')
    if words[-1][2] < float(dur) * MIN_LAST_END:
        raise RuntimeError('last word ends at ' + str(round(words[-1][2], 1)) + 's of ' + str(round(float(dur), 1)) + 's, not plausible')
    return words
