from pydantic import BaseModel, HttpUrl


class SummarizeRequest(BaseModel):
    url: HttpUrl


class PageSummary(BaseModel):
    url: HttpUrl
    title: str
    content: str
    summary: str
    card_image_base64: str
