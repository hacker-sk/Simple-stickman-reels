#!/usr/bin/env python3
"""Downloads the background songs listed in music_hindi/music_manifest.json from the shared Google Drive folder.

Each manifest entry: {"id": Drive file id, "name": file name in music_hindi/, "size": expected bytes}.
A song that is already there with the right size is skipped. Every download is checked (size, and not an HTML
error page) before it replaces anything. If any song fails the script exits with an error and nothing is committed.
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, 'music_hindi')


def fetch(item):
    dest = os.path.join(DIR, item['name'])
    want = int(item.get('size') or 0)
    if os.path.exists(dest) and want and os.path.getsize(dest) == want:
        print('already there:', item['name'])
        return True
    url = 'https://drive.usercontent.google.com/download?id=' + item['id'] + '&export=download&confirm=t'
    part = dest + '.part'
    for attempt in range(1, 4):
        rc = subprocess.run(['curl', '-fsSL', '--retry', '3', '-o', part, url]).returncode
        if rc == 0 and os.path.exists(part):
            size = os.path.getsize(part)
            with open(part, 'rb') as fh:
                head = fh.read(1)
            if head != b'<' and size > 100000 and (not want or size == want):
                os.replace(part, dest)
                print('downloaded:', item['name'], size, 'bytes')
                return True
            print('try', attempt, item['name'], 'looks wrong (size', size, 'expected', want or 'any', ')')
        else:
            print('try', attempt, item['name'], 'curl exit code', rc)
        if os.path.exists(part):
            os.remove(part)
    return False


def main():
    with open(os.path.join(DIR, 'music_manifest.json'), encoding='utf-8') as fh:
        songs = json.load(fh)['songs']
    failed = [s['name'] for s in songs if not fetch(s)]
    if failed:
        print('FAILED:', ', '.join(failed))
        return 1
    print('all', len(songs), 'songs are in music_hindi/')
    return 0


if __name__ == '__main__':
    sys.exit(main())
