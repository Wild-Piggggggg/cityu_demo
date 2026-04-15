@echo off
setlocal enabledelayedexpansion

:: 定义输入文件
set INPUT_FILE=data/ct_man/ct_man.mp4

:: 任务列表
set TASKS=1 2 3 4 5 6 7 8 9

:: 遍历任务
for %%T in (%TASKS%) do (
    echo Running Task %%T...
    python data_utils/process.py %INPUT_FILE% --task %%T
    if %ERRORLEVEL% NEQ 0 (
        echo Task %%T failed! Exiting...
        exit /b %ERRORLEVEL%
    )
    echo Task %%T completed successfully.
)

echo All tasks completed successfully!
pause
