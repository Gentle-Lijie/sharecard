from fastapi import FastAPI, HTTPException
from urllib.parse import unquote as url_unquote
from fastapi.middleware.cors import CORSMiddleware

# Support running both as a package (uvicorn -m) and as a script (python main.py)
try:
    # when running as a package (recommended): python -m app.main
    from . import schemas
    from .services import fetch_page, summarize_content, generate_share_card, qr_image_base64, fetch_favicon_base64
except Exception:
    # when running directly as a script: python main.py
    # ensure the parent directory (project root) is on sys.path so `import app` works
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from app import schemas
    from app.services import fetch_page, summarize_content, generate_share_card, qr_image_base64, fetch_favicon_base64

app = FastAPI(title="ShareCard API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/summarize", response_model=schemas.PageSummary)
def summarize(request: schemas.SummarizeRequest):
    try:
        title, content, soup = fetch_page(request.url)
        summary = summarize_content(str(request.url), title, content)
        card_image_base64 = generate_share_card(
            str(request.url), title, summary)
        # produce a QR for frontend preview (320x320) using accent color
        accent_hex = "#6fcaff"
        # generate transparent-background QR without rounded corners or white padding
        qr_b64 = qr_image_base64(str(
            request.url), scale=320, fill_color=accent_hex, back_color='transparent', add_border_px=0)
        # fetch favicon using parsed soup so we pick up <link rel="icon"> if present
        favicon_b64 = fetch_favicon_base64(str(request.url), soup)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return schemas.PageSummary(
        url=url_unquote(str(request.url)),
        title=title,
        content=content,
        summary=summary,
        card_image_base64=card_image_base64,
        qr_image_base64=qr_b64,
        favicon_base64=favicon_b64,
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/fetch", response_model=schemas.FetchResponse)
def fetch(url: str):
    """快速抓取网页标题与正文（不调用 OpenAI / 不生成卡片），用于前端逐步展示流程。"""
    try:
        title, content, soup = fetch_page(url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # 截断正文长度以减小响应体
    truncated = content[:4000]
    # QR for quick preview (320x320) using accent color, transparent background
    accent_hex = "#6fcaff"
    qr_b64 = qr_image_base64(
        url, scale=320, fill_color=accent_hex, back_color='transparent', add_border_px=0)
    favicon_b64 = fetch_favicon_base64(url, soup)
    return schemas.FetchResponse(url=url_unquote(str(url)), title=title, content=truncated, qr_image_base64=qr_b64, favicon_base64=favicon_b64)


if __name__ == "__main__":
    # Allow running the app directly for local development: python main.py
    import uvicorn

    # When running directly as a script, avoid `reload=True` because that
    # requires an importable module path. Use reload=False for simple dev run.
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
