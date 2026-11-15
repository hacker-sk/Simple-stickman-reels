"""Topic step: ports n8n 'Load Past Topics', 'Pick Shape', 'Find Viral Topic', 'Pick Topic' and 'Save Used Topic'.

History lives in state/topic_history.json (list of {t, n, o, l}) instead of n8n static data.
"""
import json
import os
import random
import time

from . import gemini
from . import topic_banks as B

STATE_FILE = os.environ.get('TOPIC_STATE_FILE', 'state/topic_history.json')
DANDA = chr(2404)


def load_used():
    try:
        with open(STATE_FILE, encoding='utf-8') as fh:
            return list(json.load(fh).get('used') or [])
    except Exception:  # noqa
        return []


def save_used(used):
    os.makedirs(os.path.dirname(STATE_FILE) or '.', exist_ok=True)
    with open(STATE_FILE, 'w', encoding='utf-8') as fh:
        json.dump({'used': used[-120:]}, fh, ensure_ascii=False, indent=1)
        fh.write('\n')


def _weighted(pool):
    total = sum(n['w'] for n in pool)
    roll = random.random() * total
    for n in pool:
        roll -= n['w']
        if roll < 0:
            return n
    return pool[-1]


def _themes(niche):
    th = list(niche['themes'])
    random.shuffle(th)
    return ' | '.join(th[:3])


def choose_context(mode=None, shape=None):
    """Pick niche, themes and past-topic list. mode: 'truth' | 'story' | None (random). shape: 'feeling' | 'pattern' | None."""
    now = time.time() * 1000
    allr = sorted(B.SEED + load_used(), key=lambda r: -float(r['t']))
    recent = [r for r in allr if now - float(r['t']) <= B.WINDOW_DAYS * 86400000]
    past = ' | '.join(str(r['o']) + ' => lesson: ' + str(r['l']) for r in recent) or 'none yet'
    truth = (random.random() < B.TRUTH_SHARE) if mode is None else (mode == 'truth')
    niche = _weighted(B.TRUTH_NICHES if truth else B.NICHES)
    ctx = {'pastTopics': past, 'niche': niche['name'], 'nicheBrief': niche['brief'], 'themes': _themes(niche),
           'nicheGuide': niche.get('guide', ''), 'scriptMode': 'truth' if truth else 'story', 'shape': 'feeling'}
    use_pattern = (random.random() < B.PATTERN_SHARE) if shape is None else (shape == 'pattern')
    if truth and use_pattern:
        pn = _weighted(B.PATTERN_NICHES)
        ctx.update({'niche': pn['name'], 'nicheBrief': pn['brief'], 'themes': _themes(pn), 'nicheGuide': pn['guide'], 'shape': 'pattern'})
    return ctx


SYS_TRUTH = '''You are the idea generator for a faceless Hindi Short and Reel, told with AI-generated illustrations and a Hindi voiceover, for a Hindi-speaking audience on Instagram Reels and YouTube Shorts. This run is in EMOTIONAL TRUTH mode. In this mode the video is not a plot with characters. It is one honest feeling or insight about relationships and life that the viewer instantly recognises as their own, said in a warm voice, the way a close friend would say it. The user message gives you the ONE niche for this run (already chosen), a few theme areas inside it, and a list of ideas already used.

What makes these videos get saved and sent: (1) Recognition: within two seconds the viewer thinks this is exactly me, because the idea names something they feel but never said out loud. (2) One flipped belief: it takes something everyone says or assumes and turns it a little, so it feels newly true (it is not X, it is actually Y). (3) One familiar picture or comparison the viewer can see in their head: a tiny everyday behaviour everyone has done, a natural pair such as air and breath or water and fish, or a widely known story or symbol. (4) A reason to send or save: there is a specific person the viewer would send it to, or a line they will want to hear again. (5) Soft honesty: it hurts a little and comforts a little. It never attacks, mocks or preaches.

Do not build the idea around named characters or a story with a beginning, middle and end. Speak to everyone with we and you. A tiny one-line moment is fine only if it is a universal behaviour, not the story of one invented person.

The theme areas are only a territory, not a checklist and not a template. Use one, combine them, or go to a neighbouring angle in the same niche if it makes a stronger idea. Do not copy their wording or any example you have seen anywhere. Vary the flipped belief, the familiar picture and the emotion from run to run. Do not repeat or closely resemble anything in the used list, in lesson or in picture, even in a new form.

Tone: sincere, never melodramatic, never bitter or cynical, never blaming a gender or a group, never diagnosing anyone or labelling a personality or mental condition. Respect every religion and community. Never present fiction as real news, and never invent statistics, studies, quotes or facts. For religious or mythological references use only widely known stories and phrase the idea as a perspective (शायद), not as a scripture fact.

Searching: you may use Google Search in any mode whenever it makes the idea better, for example to check a real fact or story, to see how people actually talk about this feeling, or to see what is trending. Do not search for the sake of it.

The idea must fit a narration of about 35 to 55 seconds. Avoid preachy advice, overused quotes, forced poetry and complicated vocabulary. Write the topic and angle in Hindi (Devanagari script). Reply with ONLY JSON in this exact shape: {"topic": "the idea in 3 to 5 sentences in Hindi, in this order: the feeling the viewer recognises, the flipped belief or hidden truth, the familiar picture or comparison that carries it, and finally one closing line that lands the feeling or that the viewer would send to someone, as the last sentence", "angle": "who would send or save this, to whom and why, in one sentence in Hindi", "niche": "the niche name in English"}'''

SYS_STORY = '''You are the idea generator for a faceless Hindi storytelling Short and Reel, told with AI-generated illustrations and a Hindi voiceover, for a Hindi-speaking audience on Instagram Reels and YouTube Shorts. This is a storytelling page, not a motivational quote page: every video is a small story with a situation, a conflict, a realization and a memorable ending. The user message gives you the ONE niche for this run (already chosen), a few theme areas inside it, and a list of ideas already used. Create one fresh idea inside that niche with real viral potential.

What makes an idea outperform: (1) Recognition: within seconds the viewer thinks this is exactly my life, because the idea is a specific, concrete, believable moment and not a general statement. (2) Share test: the idea must be something a viewer would send to a sibling, a friend, a partner or a parent, or answer with their own story in the comments. If nobody would send it, throw it away and think again. (3) Real tension: someone wants or feels something and something stands in the way, and the viewer feels it. (4) A realization that is fresh, honest and a little uncomfortable, never a slogan or a generic moral. (5) A closing line people remember or repeat.

The theme areas are only a territory to explore, not a checklist and not a template. Use one, combine them, or go to a neighbouring angle in the same niche if that makes a stronger idea. Do not copy their wording, and do not copy any example you have seen anywhere. Do not fall into a pattern: vary the kind of person, age, place, region of India, relationship, setting, objects and form from run to run (a real-life scene, a conversation, a short story, a sharp observation, a comparison, an inner thought). Each idea should find its own way of being told.

Tone: emotional niches stay sincere and never melodramatic. Respect every religion and community. Never present fiction as real news or as a documented event of a real person, and never invent statistics, studies, quotes or facts.

Searching: you may use Google Search in any mode whenever it makes the idea better, for example to check a real fact, custom or ritual, to see how people actually talk about this topic, or to see what is trending. Do not hold yourself back from searching when you need information, and do not search for the sake of it.

Do not repeat or closely resemble anything in the used list, whether in lesson, situation or setting. The idea must fit a narration of about 45 to 55 seconds, which leaves room for conflict and realization. Avoid preachy advice, overused quotes, forced poetry and complicated vocabulary. Write the topic and angle in Hindi (Devanagari script). Reply with ONLY JSON in this exact shape: {"topic": "the idea in 4 to 6 sentences in Hindi, in this order: the situation (who and what, concrete), the conflict (what goes wrong or what is felt), the realization (the honest insight), and finally one memorable closing line as the last sentence", "angle": "who would send this to whom, and why, in one sentence in Hindi", "niche": "the niche name in English"}'''

PATTERN_NOTE = ('PATTERN SHAPE for this video: build the idea as a pattern, not as a single feeling. A pattern is a run of short parallel lines that each show the same kind of contrast, followed by one human truth the pattern leads to. Choose one form: IF-THEN IRONY (if a common belief really worked, the opposite would be true), HAVE AND HAVE-NOT (the one who has A lacks B and the one who has B lacks A), GIFT AND LACK (the world gave each thing one gift and held back another), or QUIZ AND TWIST (a short question, the expected answers, then a surprising real answer). In this shape write the topic in Hindi as: first the form and the one truth the pattern leads to, then 3 to 6 of the parallel lines in short form (concrete, everyday, harmless, never invented facts or statistics, never mocking any religion, community, profession or gender), and finally one quotable closing line as the last sentence (this order replaces the order in the system instructions). The angle is who would send this to whom and why.')


def topic_prompts(ctx):
    system = SYS_TRUTH if ctx['scriptMode'] == 'truth' else SYS_STORY
    user = ('Niche for this video (already chosen, stay inside it): ' + ctx['niche'] + '. What it covers: ' + ctx['nicheBrief'] + '\n\n'
            'Theme areas to draw from, as a territory only (use one, mix them, or find a stronger neighbouring angle; never copy their wording): ' + ctx['themes'] + '\n\n'
            'Ideas already used in the last 3 weeks, each shown as its opening and its lesson. Do not repeat the same lesson, situation or example, even in a new form or with different objects. Find a genuinely different idea inside this niche: ' + ctx['pastTopics'] + '\n\n'
            + (PATTERN_NOTE if ctx['shape'] == 'pattern' else '') + '\n\n'
            'WRITE THE IDEA YOURSELF for this video: online search is not available, so do not search and do not say you searched. Write a fresh evergreen idea from your own knowledge and imagination. Do not invent facts, quotes, statistics or news events, and do not present fiction as real news. Keep the lesson timeless and emotional.')
    return system, user


def parse_topic(raw):
    raw = (raw or '').replace('```json', '').replace('```', '').strip()
    if not raw:
        raise RuntimeError('Topic finder returned an empty reply')
    data = gemini.extract_json(raw) or {}
    topic = str(data.get('topic') or '')
    angle = str(data.get('angle') or '')
    if not topic:
        topic = raw[:600]
    return topic, angle


def generate_topic(ctx):
    system, user = topic_prompts(ctx)
    raw = gemini.generate(system, user, 'Find Viral Topic', max_tokens=8000, temperature=0.8)
    return parse_topic(raw)


def record_used(topic, niche):
    """Port of Save Used Topic: remember the opening and the lesson so later runs avoid repeats."""
    topic = str(topic or '')
    if not topic:
        return
    parts = [s.strip() for s in topic.split(DANDA) if s.strip()]
    lesson = (DANDA + ' ').join(parts[-2:])[:260] if len(parts) > 1 else topic[max(0, len(topic) - 260):]
    used = load_used()
    used.append({'t': int(time.time() * 1000), 'n': niche, 'o': topic[:60], 'l': lesson})
    save_used(used)
