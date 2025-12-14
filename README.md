# ShareCard

一键 Docker 启动的全栈小工具：输入 URL，后端抓取网页标题与正文，用 OpenAI 总结并生成带二维码的分享卡片，前端直接展示。

## 快速开始

1) 配置密钥（在仓库根目录）

```
cp .env .env.local  # 可选，或直接编辑 .env
# 编辑 .env / .env.local，填入你的 OPENAI_API_KEY（可自定义 OPENAI_BASE_URL / OPENAI_MODEL）
```

2) 一键启动

```
docker compose up --build
```

- 前端（Vue + Vite）: http://localhost:5173
- 后端（FastAPI）: http://localhost:8000 ；健康检查 `/api/health`

## 交互流程

1. 前端输入 URL -> POST `/api/summarize`
2. 后端步骤：
	- requests 抓取页面，BeautifulSoup 提取标题与正文
	- 调用 OpenAI Chat Completions 生成中文摘要
	- Pillow + qrcode 生成分享卡片（PNG，Base64 Data URL）
3. 返回 JSON: `{ title, content, summary, card_image_base64, url }`

## 配置

- `OPENAI_API_KEY` 必填
- `OPENAI_BASE_URL` 可选，默认为官方 `https://api.openai.com/v1`
- `OPENAI_MODEL` 可选，默认为 `gpt-4o-mini`

## 主要技术栈

- 后端：Python 3.11, FastAPI, requests, BeautifulSoup4, OpenAI SDK, Pillow, qrcode
- 前端：Vue 3 + Vite, axios
- 部署：Docker / docker-compose

## 开发模式（可选）

前端：`cd frontend && npm install && npm run dev`

后端：`cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload`

## 路由速览

- `POST /api/summarize` body: `{ "url": "https://example.com" }`
- `GET /api/health` 返回 `{ "status": "ok" }`
