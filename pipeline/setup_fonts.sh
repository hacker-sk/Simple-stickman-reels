#!/usr/bin/env bash
# Installs the fonts and text-shaping libraries the make job needs (fonts-noto-core libraqm0 libfribidi0) without paying for a slow
# Ubuntu mirror on every run. Order: already installed -> cached .deb files (installed offline in seconds) -> download the three
# .deb files once (hard time cap, the cache step saves them for the next run) -> give up with a warning.
# Giving up is safe: the renderer falls back to a downloaded Hind Bold font when the Noto fonts are missing.
# ffmpeg is NOT installed here, see pipeline/setup_ffmpeg.sh.
set -u
PKGS="fonts-noto-core libraqm0 libfribidi0"
CACHE="$HOME/apt-debs"

have_all() {
  for p in $PKGS; do dpkg -s "$p" >/dev/null 2>&1 || return 1; done
  return 0
}

if have_all; then echo "font packages already installed"; exit 0; fi

if ls "$CACHE"/*.deb >/dev/null 2>&1; then
  echo "Installing font packages from the cache"
  sudo dpkg -i "$CACHE"/*.deb >/dev/null 2>&1 || true
  if have_all; then echo "font packages ready (from cache)"; exit 0; fi
  echo "::warning::cached font packages did not install, downloading them again"
  rm -rf "$CACHE"
fi

TMP="$(mktemp -d)"
cd "$TMP" || exit 0
echo "Downloading font packages: $PKGS"
if ! timeout 420 apt-get download $PKGS >/dev/null 2>&1; then
  echo "package lists may be missing, running apt-get update once"
  timeout 180 sudo apt-get update -y >/dev/null 2>&1 || true
  timeout 420 apt-get download $PKGS >/dev/null 2>&1 || true
fi

if ls ./*.deb >/dev/null 2>&1; then
  sudo dpkg -i ./*.deb >/dev/null 2>&1 || true
  if have_all; then
    mkdir -p "$CACHE" && cp ./*.deb "$CACHE/"
    echo "font packages ready (downloaded, cached for next run)"
    exit 0
  fi
fi

echo "::warning::font packages could not be installed in time, the renderer will use its fallback fonts"
exit 0
