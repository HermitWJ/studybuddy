# 启动 Django 后端开发服务器
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root 'backend'

Set-Location $backend
if (-not (Test-Path '.\.venv\Scripts\python.exe')) {
    Write-Host '未找到虚拟环境，正在创建...' -ForegroundColor Yellow
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
}

Write-Host '后端启动中：http://127.0.0.1:8000' -ForegroundColor Cyan
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
