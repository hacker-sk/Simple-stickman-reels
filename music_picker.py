"""Mood based background music for the Hindi videos.

Songs live in music_hindi/ and are named <mood>_<number>.mp3 where mood is motivational, emotional or neutral
(for example motivational_01.mp3, emotional_03.mp3, neutral_02.mp3).

A video asks for one mood (the "mood" field of the payload). One random song is picked from the songs of that
mood plus the neutral songs. A neutral video picks from the neutral songs only.

If a mood has no songs at all, any song that is named with one of the three moods is used, and if there are none
the old behaviour applies (any file in the folder), so a video never loses its music.

run_hindi.py installs this picker into render_hindi.py. render_hindi.py itself is unchanged.
The same install also swaps in a quieter music mix (mix_audio below). Songs are mastered at very different loudness, so a fixed
volume factor was never reliable: now the song is first levelled to a fixed loudness (MUSIC_LUFS, default -27 LUFS, the voice is
levelled to -15 LUFS), then it ducks further under the voice. Make the song louder or quieter with the MUSIC_LUFS environment
variable (for example -24 louder, -30 quieter).
"""
import os
import random
import subprocess

MOODS = ('motivational', 'emotional', 'neutral')
AUDIO_EXT = ('.mp3', '.wav', '.m4a', '.ogg')
DEFAULT_MUSIC_LUFS = -27.0

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


def music_lufs():
    try:
        v = float(os.environ.get('MUSIC_LUFS', '').strip() or DEFAULT_MUSIC_LUFS)
    except ValueError:
        v = DEFAULT_MUSIC_LUFS
    return min(-14.0, max(-45.0, v))


def install(rh):
    """Replace render_hindi.pick_music with the mood based picker and render_hindi.mix_audio with the quieter mix.
    Same inputs and outputs as the originals."""

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

    def mix_audio(voice, music, total, out):
        fade_out_start = max(0.0, total - 2.0)
        if music:
            lufs = music_lufs()
            rh.log('mix: voice levelled to -15 LUFS, song levelled to ' + format(lufs, '.0f') + ' LUFS, ducked further under the voice')
            fc = (
                f"[0:a]apad=pad_dur=3,atrim=0:{total:.3f},asetpts=N/SR/TB,"
                f"loudnorm=I=-15:TP=-1.5:LRA=7,aresample=44100,asplit=2[v1][v2];"
                f"[1:a]atrim=0:{total:.3f},asetpts=N/SR/TB,"
                f"loudnorm=I={lufs:.1f}:TP=-6:LRA=7,aresample=44100,"
                f"afade=t=in:st=0:d=1,afade=t=out:st={fade_out_start:.3f}:d=2[m];"
                f"[m][v1]sidechaincompress=threshold=0.05:ratio=4:attack=10:release=400:makeup=1[duck];"
                f"[v2][duck]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.95[a]"
            )
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", voice, "-stream_loop", "-1", "-i", music,
                   "-filter_complex", fc, "-map", "[a]", "-ar", "44100", "-ac", "2", out]
        else:
            fc = f"[0:a]apad=pad_dur=3,atrim=0:{total:.3f},loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.95[a]"
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", voice, "-filter_complex", fc,
                   "-map", "[a]", "-ar", "44100", "-ac", "2", out]
        subprocess.run(cmd, check=True)

    rh.pick_music = pick_music
    rh.mix_audio = mix_audio
