#!/usr/bin/env python3
"""Adds the reel thumbnail as a very short LAST frame of the video and records where that frame is.

Why: Buffer's API does not take a custom thumbnail image for a video (thumbnailUrl is rejected). It takes a frame position instead:
video metadata.thumbnailOffset, in milliseconds (supported by Buffer for Instagram, TikTok and Pinterest). So the portrait thumbnail the
flow job made (THUMB_DIR, artifact flow-thumb) is appended to the end of the video for TAIL seconds, silent, and the middle of that
frame is written to <OUT_DIR>/thumbnail.json as {"offset_ms": N} for pipeline/run_shorts.py -> pipeline/buffer.py.

Installed by run_hindi.py: it wraps render_hindi.upload_video, so the file is changed right before it is uploaded and every host gets
the version with the end frame. Without a thumbnail image, or when ffmpeg fails, the video is left exactly as it was and no
thumbnail.json is written (the post then goes out without a thumbnail offset, never a failed run).
"""
import json
import os
import subprocess

# Seconds the thumbnail stays on screen at the very end. It was 0.3s, which left only ~9 frames: when Buffer rounded the offset down or
# snapped to a neighbouring frame it landed in the black fade-out just before the tail. 1.0s puts the offset (the middle of the tail,
# 0.5s in) well inside the thumbnail, even with some timing error.
TAIL = 1.0
IMG_EXT = ('.png', '.jpg', '.jpeg', '.webp')


def find_thumbnail():
    d = os.environ.get('THUMB_DIR', '').strip()
    if not d or not os.path.isdir(d):
        return ''
    for root, _dirs, files in os.walk(d):
        for f in sorted(files):
            p = os.path.join(root, f)
            if f.lower().endswith(IMG_EXT) and os.path.getsize(p) > 5000:
                return p
    return ''


def probe_duration(path):
    out = subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                                   '-of', 'default=nw=1:nk=1', path]).decode().strip()
    return float(out)


def add_end_frame(path, out_dir, w, h, fps, log):
    """Appends the thumbnail to the video file in place. Returns the frame offset in ms, or 0 when nothing was changed."""
    marker = os.path.join(out_dir, 'thumbnail.json')
    if os.path.exists(marker):
        os.remove(marker)
    img = find_thumbnail()
    if not img:
        log('thumbnail end frame: no thumbnail image, the video stays as it is')
        return 0
    before = probe_duration(path)
    tmp = path + '.thumb.mp4'
    fc = ('[0:v]setsar=1,format=yuv420p[mv];'
          '[1:v]scale=' + str(w) + ':' + str(h) + ':force_original_aspect_ratio=increase,crop=' + str(w) + ':' + str(h) +
          ',setsar=1,fps=' + str(fps) + ',format=yuv420p[tv];'
          '[0:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[ma];'
          '[2:a]aformat=sample_fmts=fltp:channel_layouts=stereo[ta];'
          '[mv][ma][tv][ta]concat=n=2:v=1:a=1[v][a]')
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-i', path,
           '-loop', '1', '-framerate', str(fps), '-t', str(TAIL), '-i', img,
           '-f', 'lavfi', '-t', str(TAIL), '-i', 'anullsrc=r=44100:cl=stereo',
           '-filter_complex', fc, '-map', '[v]', '-map', '[a]',
           '-c:v', 'libx264', '-preset', os.environ.get('X264_PRESET', 'veryfast'), '-crf', '20', '-pix_fmt', 'yuv420p', '-r', str(fps),
           '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', tmp]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0 or not os.path.exists(tmp) or os.path.getsize(tmp) < 100000:
        log('thumbnail end frame: ffmpeg failed, the video stays as it is: ' + (p.stderr or '')[-300:])
        if os.path.exists(tmp):
            os.remove(tmp)
        return 0
    after = probe_duration(tmp)
    if after < before + TAIL * 0.5:
        log('thumbnail end frame: the new video is not longer (' + str(round(before, 2)) + 's -> ' + str(round(after, 2)) + 's), the video stays as it is')
        os.remove(tmp)
        return 0
    os.replace(tmp, path)
    offset_ms = int(round((before + TAIL / 2.0) * 1000))
    with open(marker, 'w', encoding='utf-8') as fh:
        json.dump({'offset_ms': offset_ms, 'tail_seconds': TAIL, 'video_seconds_before': round(before, 3), 'video_seconds_after': round(after, 3)}, fh)
    log('thumbnail end frame added: ' + os.path.basename(img) + ', ' + str(TAIL) + 's, thumbnail offset ' + str(offset_ms) + ' ms (video ' +
        str(round(before, 2)) + 's -> ' + str(round(after, 2)) + 's)')
    return offset_ms


def install(rh):
    """Wraps render_hindi.upload_video so the end frame is added just before the upload."""
    original = rh.upload_video

    def upload_video(path):
        if not getattr(rh, 'FAKE', False):
            try:
                add_end_frame(path, rh.OUT, rh.W, rh.H, rh.FPS, rh.log)
            except Exception as e:  # noqa
                rh.log('thumbnail end frame skipped: ' + str(e)[:200])
        return original(path)

    rh.upload_video = upload_video
