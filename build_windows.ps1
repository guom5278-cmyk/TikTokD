python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --onefile --windowed --name TikTokDownloader app.py
Write-Host "Build completed: dist/TikTokDownloader.exe"
