#!/usr/bin/env bash
# Puts ffmpeg and ffprobe on PATH without the slow apt install. apt pulled about 100 packages (105 MB) and took 21 minutes
# on a slow Ubuntu mirror. Order: cached static build -> download a static build (the cache step saves it for the next run)
# -> apt only as the last resort. Used by the prepare job of shorts.yml (the make job still uses apt for its fonts).
set -u
DIR="$HOME/ffmpeg-static"
mkdir -p "$DIR"

if [ ! -x "$DIR/ffmpeg" ] || [ ! -x "$DIR/ffprobe" ]; then
  for url in \
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz" \
    "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"; do
    rm -rf /tmp/ffx /tmp/ffmpeg.tar.xz
    mkdir -p /tmp/ffx
    echo "Downloading a static ffmpeg build: $url"
    if curl -fsSL --retry 2 --connect-timeout 20 --max-time 300 -o /tmp/ffmpeg.tar.xz "$url" && tar -xf /tmp/ffmpeg.tar.xz -C /tmp/ffx; then
      f="$(find /tmp/ffx -type f -name ffmpeg | head -1)"
      p="$(find /tmp/ffx -type f -name ffprobe | head -1)"
      if [ -n "$f" ] && [ -n "$p" ]; then
        cp "$f" "$p" "$DIR/"
        chmod +x "$DIR/ffmpeg" "$DIR/ffprobe"
        break
      fi
    fi
    echo "::warning::could not use that ffmpeg download, trying the next source"
  done
fi

if [ -x "$DIR/ffmpeg" ] && [ -x "$DIR/ffprobe" ] && "$DIR/ffmpeg" -version >/dev/null 2>&1; then
  echo "$DIR" >> "$GITHUB_PATH"
  export PATH="$DIR:$PATH"
  echo "ffmpeg ready: $(ffmpeg -version | head -1)"
  exit 0
fi

echo "::warning::static ffmpeg not available, falling back to apt (slow)"
rm -rf "$DIR"
sudo apt-get update -y && sudo apt-get install -y ffmpeg || echo "::warning::ffmpeg install failed, the voice step will fail and Flow is skipped"
exit 0
