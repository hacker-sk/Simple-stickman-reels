"""Mood based background music for the Hindi videos.

Songs live in music_hindi/ and are named <mood>_<number>.mp3 where mood is motivational, emotional or neutral
(for example motivational_01.mp3, emotional_03.mp3, neutral_02.mp3).

A video asks for one mood (the "mood" field of the payload). One random song is picked from the songs of that
mood plus the neutral songs. A neutral video picks from the neutral songs only.

If a mood has no songs at all, any song that is named with one of the three moods is used, and if there are none
the old behaviour applies (any file in the folder), so a video never loses its music.

run_hindi.py installs this picker into render_hindi.py. render_hindi.py itself is unchanged.
"""
import os
import random

MOODS = ('motivational', 'emotional', 'neutral')
AUDIO_EXT = ('.mp3', '.wav', '.m4a', '.ogg')

# the payload may still carry an older mood word; map each one to one of the three moods
ALIASES = {
    'motivational': 'motivational', 'motivation': 'motivational', 'inspiring': 'motivational',
    'inspirational': 'motivational', 'upbeat': 'motivational', 'dramatic': 'motivational',
    'energetic': 'motivational', 'hopeful': 'motivational',
    'emotional': 'emotional', 'sad': 'emotional', 'touching': 'emotional', 'nostalgic': 'emotional',
    'neutral': 'neutral', 'calm': 'neutral', 'mysterious': 'neutral', 'curious': 'neutral',
}


def normalize_mood(mood):
    """One of motivational, emotional, neutral. Anything unknown or empty counts as neutral."""
    key = str(mood or '').strip().lower().replace('-', '_').replace(' ', '_')
    return ALIASES.get(key, 'neutral')


def pool_for(files, mood):
    """The songs a video of this mood may use: its own mood plus neutral (neutral videos: neutral only)."""
    prefixes = ('neutral_',) if mood == 'neutral' else (mood + '_', 'neutral_')
    pool = [n for n in files if n.lower().startswith(prefixes)]
    if pool:
        return pool
    named = [n for n in files if n.lower().startswith(tuple(m + '_' for m in MOODS))]
    return named or files


def install(rh):
    """Replace render_hindi.pick_music with the mood based picker. Same inputs and outputs as the original."""

    def pick_music(mood):
        try:
            folder = os.path.join(rh.HERE, 'music_hindi')
            files = []
            if os.path.isdir(folder):
                files = sorted(n for n in os.listdir(folder) if n.lower().endswith(AUDIO_EXT))
            if not files:
                raise RuntimeError('no music files in the music_hindi folder')
            wanted = normalize_mood(mood)
            pool = pool_for(files, wanted)
            name = random.choice(pool)
            rh.log('music: payload mood', repr(mood), '-> ' + wanted + ', picked', name, 'from', len(pool), 'songs')
            return os.path.join(folder, name), name
        except Exception as e:  # noqa
            rh.log('No music this time:', str(e)[:150])
            return None, ''

    rh.pick_music = pick_music
