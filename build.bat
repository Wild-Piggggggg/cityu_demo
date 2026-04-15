@echo off
echo Building the executable using Conda environment...

:: 确保当前目录是项目根目录
cd /d %~dp0

:: 激活 Conda 环境（替换为你的环境名）
call conda activate py_3.10

:: 安装 PyInstaller（如果尚未安装）
pip install pyinstaller

:: 使用 PyInstaller 打包 app.py
:: --add-data 添加资源目录，适用于 Windows（使用分号分隔）；macOS/Linux 使用冒号
pyinstaller --noconfirm --onefile --add-data "assets;assets" --add-data "data;data" --add-data "models;models" --add-data "musetalk;musetalk" --add-data "ultralight;ultralight" --add-data "wav2lip;wav2lip" --add-data "web;web" --add-data "llm;llm" --add-data "ernerf;ernerf" 
    app.py

echo Build complete! Check the 'dist' folder for the executable.
pause