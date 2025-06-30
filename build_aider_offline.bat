@echo off
chcp 65001 > nul
title Aider 离线包构建器

echo ===============================================
echo           Aider 离线包构建器
echo ===============================================
echo.
echo 这个脚本将自动构建 Aider 的完全离线 Windows 版本
echo 适用于内网环境，通过 OpenAI Compatible API 使用
echo.

REM 检查Python是否已安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Python，请先安装Python 3.10或更高版本
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [信息] 检测到Python版本:
python --version

echo.
echo 开始构建过程...
echo 这可能需要几分钟时间，请耐心等待...
echo.

REM 运行构建脚本
python build_offline_windows_package.py

if errorlevel 1 (
    echo.
    echo [错误] 构建失败，请检查上面的错误信息
    pause
    exit /b 1
)

echo.
echo ===============================================
echo              构建完成！
echo ===============================================
echo.
echo 生成的文件位于 dist 目录中：
echo - aider_windows_offline/          (解压后的目录)
echo - aider_windows_offline.zip       (压缩包)
echo.
echo 接下来：
echo 1. 将 aider_windows_offline.zip 复制到目标Windows机器
echo 2. 解压到任意目录
echo 3. 编辑 .aider.conf.yml 设置您的API参数
echo 4. 运行 start_aider.bat 开始使用
echo.

pause 