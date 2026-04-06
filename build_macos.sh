#!/usr/bin/env bash
set -euo pipefail

python3 -m pip install -r requirements.txt
python3 -m PyInstaller --noconfirm --windowed --name TikTokDownloader app.py

echo "Build completed: dist/TikTokDownloader.app"
