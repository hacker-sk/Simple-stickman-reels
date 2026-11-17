"""Prebuilt art styles for the Hindi Shorts pipeline.

Six hand-drawn 2D storybook styles. When no style is chosen (no art_style in the chat package and the workflow input
art_style left on random or empty, which is also the case for scheduled runs), one of them is picked at random.
The full style description of each style is kept word for word in 'look'. The image model only reads about the first
250 word pieces of a prompt, so the prompt writer ends every prompt with a short style sentence built from that wording.
"""
import random


def J(a):
    return ' '.join(a)


STYLES = {}


def _add(key, name, look, character, environment, colour, ending):
    STYLES[key] = {
        'name': name,
        'open': '',
        'close': '',
        'look': look,
        'rules': J([
            'THIS VIDEO USES THE ' + name.upper() + ' STYLE described above. Every image follows it exactly.',
            'PROMPT LENGTH: write one English image prompt of 90 to 120 words for every chunk. The image model reads only about the first 250 small word pieces of a prompt, so put the subject and its look first and keep the rest tight.',
            'CHARACTER LOOK: ' + character + ' A fixed appearance means age, face, hair, build, clothing, colours and one distinguishing feature. Every recurring character keeps the same appearance, written with the same words every time; tell different characters apart by clothing colour and one distinguishing item. Emotion comes from the eyes, brows, posture and gesture.',
            'ENVIRONMENTS: ' + environment + ' Use the same recurring places and objects in the same words throughout the video. When the phrase is about an object, an animal, a place, nature, time or an idea, show that directly with no person.',
            'COLOUR AND LIGHT: ' + colour + ' Show mood through light, sky, shadow length and posture, never by changing the art style.',
            'ART STYLE IN EVERY PROMPT: because the image model knows nothing else, end every prompt with one short style sentence of about 25 to 35 words, written in your own words from the ART STYLE description above and using its key wording (outlines, textures, palette, lighting), for example: "' + ending + '" Never mention or mix in any other art style, and never ask for photorealism, 3D, glossy digital or flat vector looks. Never include readable words, letters, numbers, captions, logos or watermarks.',
        ]),
    }


_add(
    'indian_storybook',
    'Polished Indian Storybook Anime',
    'Polished 2D hand-drawn Indian storybook illustration, anime-inspired cartoon aesthetic, bold clean dark outlines, expressive simple characters, warm earthy color palette, soft cel-shading, subtle hand-painted textures, richly detailed rural environments, and beautiful cinematic lighting; consistent character designs and proportions, no text, logos, or watermarks.',
    'Draw expressive simple characters with anime-inspired cartoon faces, bold clean dark outlines and soft cel-shading, in simple Indian clothing with believable folds (kurta, saree, dhoti, shawl; a turban only when the story needs it), with consistent proportions.',
    'Make the environments richly detailed rural Indian settings (village lanes, fields, mud huts, wells, temples, markets, tea stalls) unless the narration points elsewhere, with a layered foreground, middle ground and background.',
    'Warm earthy colour palette with soft cel-shading, subtle hand-painted textures and beautiful cinematic lighting.',
    'Polished 2D hand-drawn Indian storybook illustration, anime-inspired cartoon look, bold clean dark outlines, soft cel-shading, warm earthy palette, subtle hand-painted texture, beautiful cinematic lighting.',
)

_add(
    'sketchbook_doodle',
    'Sketchbook Doodle Storybook',
    'Hand-drawn 2D storybook illustration in a charming sketchbook-doodle style, simple expressive stick-figure characters with bold irregular black ink outlines, detailed natural environments, loose hand-drawn linework, watercolor and colored-pencil textures, subtle paper grain, warm earthy tones, golden-hour cinematic lighting, soft atmospheric shading, highly detailed backgrounds, consistent character design, no text, logos, or watermarks.',
    'Draw simple expressive stick-figure characters: a round head with a simple expressive face, thin stick limbs and bold irregular black ink outlines, plus ONE fixed clothing item in a fixed colour.',
    'Make the environments detailed natural settings (fields, forests, rivers, hills, village paths, huts, trees) with loose hand-drawn linework and highly detailed backgrounds, unless the narration points elsewhere.',
    'Warm earthy tones with watercolor and colored-pencil textures, subtle paper grain, golden-hour cinematic lighting and soft atmospheric shading.',
    'Hand-drawn sketchbook-doodle storybook illustration, loose irregular black ink outlines, watercolor and colored-pencil textures, subtle paper grain, warm earthy tones, golden-hour cinematic light.',
)

_add(
    'whimsical_indian',
    'Whimsical Indian Cartoon',
    'Whimsical 2D hand-drawn Indian cartoon illustration, cute simple rounded characters with expressive faces and bold black sketch outlines, clean ink linework, soft watercolor and colored-pencil textures, warm earthy pastel colors, richly detailed everyday Indian settings, charming storybook aesthetic, subtle paper grain, soft natural lighting, balanced cinematic composition, consistent character proportions, no captions, text, logos, or watermarks.',
    'Draw cute, simple, rounded characters with expressive faces, bold black sketch outlines and clean ink linework, in everyday Indian clothing.',
    'Make the environments richly detailed everyday Indian settings (homes, courtyards, streets, markets, tea stalls, schools, railway stations, rooftops) unless the narration points elsewhere, with balanced cinematic composition.',
    'Warm earthy pastel colours with soft watercolor and colored-pencil textures, subtle paper grain and soft natural lighting.',
    'Whimsical 2D hand-drawn Indian cartoon, cute rounded characters, bold black sketch outlines, soft watercolor and colored-pencil texture, warm earthy pastels, subtle paper grain, soft natural light.',
)

_add(
    'editorial_pencil',
    'Editorial Pencil and Watercolor Storybook',
    '2D hand-drawn editorial storybook illustration, expressive cartoon characters with slightly anime-inspired faces, delicate imperfect pencil-and-ink outlines, sketchy cross-hatching, soft watercolor and colored-pencil shading, muted warm beige and earthy pastel palette, detailed realistic backgrounds with architectural perspective, subtle paper texture, soft diffused lighting, emotional storytelling atmosphere, consistent character proportions, clean cinematic composition, no logos or watermarks.',
    'Draw expressive cartoon characters with slightly anime-inspired faces and delicate imperfect pencil-and-ink outlines, with sketchy cross-hatching and soft watercolor shading, in believable Indian clothing.',
    'Make the backgrounds detailed and realistic with clear architectural perspective (old buildings, streets, rooms, courtyards, stations, markets) in believable Indian settings unless the narration points elsewhere.',
    'Muted warm beige and earthy pastel palette, soft diffused lighting, subtle paper texture and an emotional storytelling atmosphere.',
    '2D hand-drawn editorial storybook illustration, delicate imperfect pencil-and-ink outlines, sketchy cross-hatching, soft watercolor shading, muted beige and earthy pastels, subtle paper texture, soft diffused light.',
)

_add(
    'stickman_sepia',
    'Indian Sepia Stickman Cartoon',
    '2D hand-drawn stickman cartoon illustration, minimalist round-headed characters with simple expressive faces and thin black stick limbs, bold clean black ink outlines, detailed sketch-style Indian environments, intricate pencil linework, subtle cross-hatching, soft watercolor and colored-pencil textures, muted beige, sepia and earthy tones with selective bright character accents, warm cinematic daylight, slightly grainy paper texture, detailed crowded backgrounds, consistent stickman character design, no text, logos or watermarks.',
    'Draw minimalist round-headed stickman characters: a round head with a simple expressive face, thin black stick limbs and bold clean black ink outlines, plus one or two clothing details in a bright accent colour that stands out against the muted scene.',
    'Make the environments detailed sketch-style Indian settings with intricate pencil linework and detailed crowded backgrounds (streets, markets, villages, fairs, stations) unless the narration points elsewhere.',
    'Muted beige, sepia and earthy tones with selective bright accents on the characters, warm cinematic daylight and a slightly grainy paper texture.',
    '2D hand-drawn stickman cartoon, round-headed characters with thin black limbs, bold ink outlines, pencil cross-hatching, watercolor texture, muted sepia and earthy tones with bright character accents, grainy paper.',
)

_add(
    'village_storybook',
    'Charming Indian Village Storybook',
    'Charming 2D hand-drawn Indian village storybook illustration, cute cartoon characters with rounded faces and expressive features, slightly childlike proportions, clean bold black ink outlines, detailed pencil-sketch linework, soft watercolor and colored-pencil textures, warm muted beige and earthy pastel palette, traditional Indian rural architecture and surroundings, subtle paper grain, gentle natural sunlight, beautifully detailed backgrounds, consistent character design, cinematic storytelling composition, no text, logos, or watermarks.',
    'Draw cute cartoon characters with rounded faces, expressive features, slightly childlike proportions and clean bold black ink outlines, in simple Indian village clothing.',
    'Make the environments traditional Indian rural settings and architecture (mud and brick houses, thatched roofs, courtyards, wells, farm fields, village lanes, banyan trees) unless the narration points elsewhere, with beautifully detailed backgrounds.',
    'Warm muted beige and earthy pastel palette with detailed pencil-sketch linework, subtle paper grain and gentle natural sunlight.',
    'Charming 2D hand-drawn Indian village storybook illustration, rounded childlike characters, bold black ink outlines, pencil-sketch linework, watercolor texture, muted beige earthy pastels, gentle sunlight, paper grain.',
)


def get_style(key=None):
    """Returns (key, style). An empty, unknown or 'random' key picks one of the styles at random.
    Callers resolve the key once and pass the resolved key on, so one video always keeps one style."""
    k = key if key in STYLES else random.choice(sorted(STYLES))
    return k, STYLES[k]
