@echo off
REM Windows 版本的数据库备份脚本

REM 配置
set BACKUP_DIR=..\data\backups
set DB_FILE=..\data\ecommerce.db
set TIMESTAMP=%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%
set BACKUP_FILE=%BACKUP_DIR%\ecommerce_%TIMESTAMP%.db

REM 创建备份目录
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

REM 检查数据库文件是否存在
if not exist "%DB_FILE%" (
    echo ❌ 错误: 数据库文件不存在: %DB_FILE%
    exit /b 1
)

REM 备份数据库
echo 🔄 开始备份数据库...
copy "%DB_FILE%" "%BACKUP_FILE%" >nul

if %errorlevel% equ 0 (
    echo ✅ 备份成功: %BACKUP_FILE%
    
    REM 显示备份文件大小
    for %%A in ("%BACKUP_FILE%") do (
        echo 📦 备份文件大小: %%~zA 字节
    )
    
    REM 显示最近5个备份
    echo 📋 最近的备份:
    dir /b /o-d "%BACKUP_DIR%\ecommerce_*.db" | findstr /n . | findstr "^[1-5]:"
) else (
    echo ❌ 备份失败
    exit /b 1
)
