from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import schemas
from .services import fetch_page, summarize_content, generate_share_card

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
        title, content = fetch_page(request.url)
        summary = summarize_content(str(request.url), title, content)
        card_image_base64 = generate_share_card(
            str(request.url), title, summary)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return schemas.PageSummary(
        url=request.url,
        title=title,
        content=content,
        summary=summary,
        card_image_base64=card_image_base64,
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}
