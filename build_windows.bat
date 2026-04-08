@echo off
setlocal

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m unittest discover -s tests -p "test_*.py"
if errorlevel 1 (
  echo Unit tests failed.
  exit /b 1
)

python -m PyInstaller --noconfirm --onefile --windowed --name TikTokDownloader app.py
if errorlevel 1 (
  echo Build failed.
  exit /b 1
)

echo Build completed: dist\TikTokDownloader.exe
endlocal
