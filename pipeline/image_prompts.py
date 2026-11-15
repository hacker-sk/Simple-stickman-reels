"""Image-prompt step: ports the n8n nodes 'Write Image Prompts' and 'Attach Image Prompts'.
The system prompt and the user message template are copied verbatim from the original workflow.
"""
import json

from . import gemini
from . import styles

NL = chr(10)
MAXP = 920
SYS_IMAGE = 'You are an art director who writes the image prompts for a vertical (9:16) YouTube Short and Instagram Reel told through AI-generated illustrations in ONE fixed art style. The user message gives that art style and its STYLE RULES. The STYLE RULES decide everything about how the pictures LOOK and how the prompts are WRITTEN: how characters are drawn and described, how detailed the environments are, the colours and lighting, which framings are allowed, how groups and crowds are described, the style wording, the prompt length and format, and any fixed wording the system adds around your text. Follow them exactly, and nothing below about looks or wording overrides them. Everything else below (story understanding, consistency, relevance, variety) applies to every style. Work in two steps and return both in one JSON answer. STEP 1, STORY CONTEXT. Read the complete narration script first and understand the whole story before you write anything else. Then write a concise internal story summary in the story_context field (under 200 words in total) covering: subject_and_events, the main subject and the events in chronological order; characters, the main characters with their roles and a fixed, complete appearance written exactly the way the STYLE RULES describe characters (including the fixed clothing, colours and distinguishing feature they require), or the word none when the story has no real characters; locations_and_time, the locations, environments and time periods with their key visual details; transitions_and_visual_concepts, the important scene transitions and the visual concepts or metaphors that carry the meaning. Do not invent characters, events or places that the narration does not support. If the script is a reflection or a philosophy rather than a story, describe its central idea and the concrete visual metaphors you will use. STEP 2, IMAGE PROMPTS. Using the story context and the position of each chunk in the story, write exactly one English image prompt for EVERY numbered narration chunk, in the same order, with the length and format the STYLE RULES ask for. Each chunk is a short phrase that stays on screen for only about two to three seconds. The picture must demonstrate and convey what the narrator is saying in that phrase: show what the phrase really means inside this story, not just its keywords, and never turn a phrase into a generic picture of a person or an animal. EVERY PROMPT STANDS ALONE. The image model has no memory: it sees one prompt at a time and knows nothing about the other images, the script or the story. So each prompt must contain everything needed to draw its own picture: the subjects, objects, animals and people in it with their complete identifying looks, their expression, pose and action; the environment, place and time of day; the composition and where things are positioned; the framing and camera angle (only those the STYLE RULES allow the style to draw); and the lighting, colours and mood as far as the STYLE RULES allow. Put the subject and its identifying details first and then the rest in the order the STYLE RULES ask for. CONSISTENCY WITHOUT MEMORY. Whenever a character, animal, object or place from your story_context appears in a prompt, write out its established traits again in that prompt, with the same words every time (the same fixed look, clothing, colours and distinguishing feature the STYLE RULES require for characters; the same layout, materials and colours for a place), written in the wording and order the STYLE RULES ask for. All images of the video must feel like one universe: the same characters, the same recurring places and objects, the same world. Never write \'same character\', \'as before\', \'again\' or refer to another image, the story or the script. Mention only what is actually visible in that image. Change only what the narration needs: pose, expression, action and framing. When the story moves to a new place, time or situation, show a new setting. WHEN TO SHOW PEOPLE. Show a human only when the phrase or its meaning needs one. When the phrase is about an object, a place, nature, an animal, time, a symbol or an abstract idea, show that directly through environments, objects, close-ups of details and visual metaphors, and do not add a person. Always state exactly who is visible and how many people there are. Never add extra figures, groups, families, children or crowds unless the phrase needs them. When a group or a crowd is part of the meaning, describe it exactly the way the STYLE RULES say (when they ask for counts, positions, sizes and clothing of the figures, give all of that for every figure or group); when the STYLE RULES say nothing about groups or crowds, describe them in a simple way, for example a few small figures around the one main subject. When a person is shown, draw and describe them exactly as the STYLE RULES say. COMPOSITION. Every image is a moment from a larger story with one clear focal point and balanced depth. VISUAL VARIETY. Neighbouring prompts must differ in subject, setting, framing and camera angle. Do not show the same person, animal, place or arrangement again and again unless the story requires it. Each chunk carries a suggested framing in square brackets: treat it as a starting point, change it when the narration needs another shot or when the STYLE RULES do not allow it, and never give two neighbouring chunks the same framing. The FIRST prompt must be the most striking, scroll-stopping image of the video, with a clear focal point, using only the colours, lighting and look the STYLE RULES allow. Obey the STYLE RULES about any text in the picture; if they say nothing, never include readable words, letters, numbers, logos or watermarks. Before you answer, read all prompts together as one storyboard and fix anything that repeats a subject, setting or composition without a story reason, that adds a person or extra people where the phrase did not need them, that breaks a STYLE RULE, or that describes a recurring character or place differently from your story_context. Return ONLY valid JSON, no markdown, in this exact shape: {"story_context": {"subject_and_events": "...", "characters": "...", "locations_and_time": "...", "transitions_and_visual_concepts": "..."}, "prompts": ["prompt for chunk 1", "prompt for chunk 2"]} with exactly as many prompts as chunks.'
USER_TEMPLATE = 'ART STYLE for every image: {name}. What it looks like: {look}\n\nSTYLE RULES (follow exactly; they decide how characters and environments are drawn and described, the colours and lighting, the style wording, the prompt length and any fixed wording the system adds, and they override any other look guidance):\n{rules}\n\nVIDEO TITLE: {title}\n\nCOMPLETE NARRATION SCRIPT (read all of it first and understand the story):\n{tts}\n\nNARRATION CHUNKS TO ILLUSTRATE (write exactly {count} prompts, in this order):\n{numbered}'


def log(*a):
    print('[image_prompts]', *a, flush=True)


def build_user_message(style, chunks):
    """style is a styles.STYLES entry, chunks is the result of script.number_chunks."""
    return (USER_TEMPLATE.replace('{name}', style['name']).replace('{look}', style['look']).replace('{rules}', style['rules'])
            .replace('{title}', str(chunks['title'])).replace('{tts}', str(chunks['ttsText']))
            .replace('{count}', str(chunks['count'])).replace('{numbered}', str(chunks['numbered'])))


def _cap(t, budget):
    if len(t) <= budget:
        return t
    cut = t[:budget]
    m = max(cut.rfind('. '), cut.rfind('! '), cut.rfind('? '))
    if m > budget * 0.6:
        return cut[:m + 1]
    sp = cut.rfind(' ')
    if sp > 0:
        cut = cut[:sp]
    return cut.rstrip(' \t\r\n,;:') + '.'


def _wrap(t, opening, closing):
    t = str(t).strip()
    if not opening:
        return _cap(t, 1900)
    if t.startswith(opening):
        t = t[len(opening):].strip()
    ci = t.rfind(closing)
    if ci >= 0 and ci + len(closing) >= len(t) - 2:
        t = t[:ci].strip()
    t = t.rstrip(' \t\r\n,')
    if not t or t[-1] not in '.!?':
        t += '.'
    t = _cap(t, MAXP - len(opening) - len(closing) - 2)
    return opening + ' ' + t + ' ' + closing


def attach(prep, style, data):
    """Port of 'Attach Image Prompts'. Returns the scenes list [{narration, image_prompt}] and the story context.
    Raises when the number of prompts differs from the number of phrases, so images never drift out of sync."""
    prompts = data.get('prompts') if isinstance(data, dict) and isinstance(data.get('prompts'), list) else []
    if len(prompts) != len(prep['scenes']):
        raise RuntimeError('Image prompt count mismatch: Gemini returned ' + str(len(prompts)) + ' prompts for ' +
                           str(len(prep['scenes'])) + ' phrases. Stopped so the images do not shift out of sync with the narration.')
    scenes = []
    for i, s in enumerate(prep['scenes']):
        ip = str(prompts[i] or '').strip()
        if len(ip) < 40:
            ip = 'A new, specific visual that shows this moment of the story: ' + str(s['narration']).strip() + '. A distinct subject, environment, framing and lighting.'
        scenes.append({'narration': s['narration'], 'image_prompt': _wrap(ip, style.get('open', ''), style.get('close', ''))})
    return scenes, (data.get('story_context') if isinstance(data, dict) else None)


def write_image_prompts(prep, chunks, style_key):
    """Write Image Prompts (+ its model fallback) and Attach Image Prompts. Returns (scenes, story_context).
    A prompt-count mismatch is asked again up to two more times before the run stops."""
    key, style = styles.get_style(style_key)
    user = build_user_message(style, chunks)
    last = None
    for attempt in range(3):
        raw = gemini.generate(SYS_IMAGE, user, 'Write Image Prompts', max_tokens=16000, temperature=0.8, json_mode=True)
        data = gemini.extract_json(raw) or {}
        try:
            return attach(prep, style, data)
        except RuntimeError as e:
            last = e
            log('attempt ' + str(attempt + 1) + ' failed: ' + str(e)[:200])
    raise last
