$ErrorActionPreference = "Stop"

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 一键打包 Windows 可执行文件
python -m PyInstaller --noconfirm --clean --onefile --windowed --name PRStabilizer --collect-all cv2 --hidden-import numpy app.py

Write-Host "Build completed: dist/PRStabilizer.exe"
