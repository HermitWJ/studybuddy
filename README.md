# StudyBuddy 前后端分离平台

Vue 3 (Vite) + Django REST Framework + MySQL 的基础工程，前后端各自独立启动，开箱可跑。

## 目录结构

```
studybuddy/
├── backend/                 # Django 后端
│   ├── config/              # 全局配置（settings / urls / wsgi / asgi）
│   ├── core/                # 业务应用：健康检查 + 示例 Task CRUD
│   ├── .env                 # 本地环境变量（数据库密码等，不入库）
│   ├── .env.example         # 环境变量模板
│   ├── requirements.txt
│   └── manage.py
├── frontend/                # Vue 3 前端
│   ├── src/
│   │   ├── api/             # axios 实例与接口封装
│   │   ├── router/          # 路由
│   │   ├── stores/          # Pinia
│   │   └── views/           # 页面
│   └── vite.config.js       # 含 /api 开发代理
└── README.md
```

## 环境版本

| 组件 | 版本 |
| --- | --- |
| Python | 3.11.10（`backend/.venv`，解释器位于 `C:\Users\Lenovo\AppData\Roaming\uv\python\cpython-3.11.10-windows-x86_64-none\python.exe`） |
| Django | 5.2 |
| MySQL | 8.4（库 `studybuddy`，utf8mb4） |
| Node.js | 24.x |
| Vue / Vite | 3.x / 8.x |

## 首次运行

```powershell
# 1) 后端环境变量（.env 不入库，需从模板复制后填入自己的数据库密码）
cd e:\Desktop\studybuddy\backend
Copy-Item .env.example .env

# 2) 安装依赖
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 3) 建库 + 迁移（MySQL 中需先存在 studybuddy 库）
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS studybuddy DEFAULT CHARACTER SET utf8mb4;"
.\.venv\Scripts\python.exe manage.py migrate
```

前端只需 `npm install` 即可。

## 启动方式

### 1. 后端（http://127.0.0.1:8000）

```powershell
cd e:\Desktop\studybuddy\backend
.\.venv\Scripts\Activate.ps1        # 或直接使用 .\.venv\Scripts\python.exe
python manage.py runserver 127.0.0.1:8000
```

### 2. 前端（http://127.0.0.1:5173）

```powershell
cd e:\Desktop\studybuddy\frontend
npm run dev
```

浏览器打开 <http://127.0.0.1:5173> 即可，`/api` 请求会由 Vite 代理到后端，无跨域问题。

## 接口一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health/` | 健康检查（含 MySQL 连接状态与版本） |
| GET | `/api/tasks/` | 任务列表（分页，20 条/页） |
| POST | `/api/tasks/` | 新增任务 `{"title": "..."}` |
| PATCH | `/api/tasks/{id}/` | 更新任务 |
| DELETE | `/api/tasks/{id}/` | 删除任务 |
| — | `/admin/` | Django 后台（需先建管理员） |

创建后台管理员：

```powershell
cd e:\Desktop\studybuddy\backend
.\.venv\Scripts\python.exe manage.py createsuperuser
```

## 数据库

已在本地 MySQL 中创建库 `studybuddy`（utf8mb4），并执行完全部迁移。
连接信息在 `backend/.env`：

```ini
DB_NAME=studybuddy
DB_USER=root
DB_PASSWORD=******
DB_HOST=127.0.0.1
DB_PORT=3306
```

模型改动后执行：

```powershell
.\.venv\Scripts\python.exe manage.py makemigrations
.\.venv\Scripts\python.exe manage.py migrate
```

## 镜像源（已配置）

| 工具 | 源 |
| --- | --- |
| npm | `https://registry.npmmirror.com` |
| pip | `https://pypi.tuna.tsinghua.edu.cn/simple`（写入 `%APPDATA%\pip\pip.ini`） |

## 生产构建

```powershell
cd e:\Desktop\studybuddy\frontend
npm run build          # 产物在 frontend/dist
```
