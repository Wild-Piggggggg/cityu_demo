@echo off
setlocal enabledelayedexpansion

echo Starting ERNeRF training process...

:: 第一步：训练 1000000 轮
python -m ernerf.main ernerf/data/ct_man/ --workspace ernerf/trial_ct_man/ -O --iters 100000
if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%

:: 第二步：微调嘴部（finetune lips），迭代 125000 轮
python -m ernerf.main ernerf/data/ct_man/ --workspace ernerf/trial_ct_man/ -O --iters 125000 --finetune_lips --patch_size 32
if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%

:: 第三步：训练躯干（torso），迭代 200000 轮
@REM python -m ernerf.main ernerf/data/ct_man/ --workspace ernerf/trial_ct_man_torso/ -O --torso --head_ckpt ernerf/trial_ct_man/checkpoints/ngp_ep0030.pth --iters 200000
@REM if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%

@REM :: 第四步：测试头部模型
@REM python -m ernerf.main ernerf/data/ct_man/ --workspace ernerf/trial_ct_man/ -O --test
@REM if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%

@REM :: 第五步：测试躯干模型
@REM python -m ernerf.main ernerf/data/ct_man/ --workspace ernerf/trial_ct_man_torso/ -O --torso --test
@REM if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%

@REM python -m ernerf.main ernerf/data/ct_man/ --workspace ernerf/trial_ct_man_torso/ -O --torso --test --test_train --aud ernerf/data/ct_man/aud_eo.npy


echo All ERNeRF tasks completed successfully!
pause
