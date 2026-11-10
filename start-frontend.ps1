# 启动 Vue 3 前端开发服务器
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontend = Join-Path $root 'frontend'

Set-Location $frontend
if (-not (Test-Path '.\node_modules')) {
    Write-Host '未找到依赖，正在安装...' -ForegroundColor Yellow
    npm install
}

Write-Host '前端启动中：http://127.0.0.1:5173' -ForegroundColor Cyan
npm run dev
