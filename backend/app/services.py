import base64
import io
import textwrap
from typing import Tuple

import qrcode
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont

from .config import get_settings


USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"


def fetch_page(url: str) -> Tuple[str, str]:
    settings = get_settings()
    try:
        resp = requests.get(
            url,
            timeout=settings.request_timeout_seconds,
            headers={"User-Agent": USER_AGENT},
        )
        resp.raise_for_status()
    except Exception as exc:
        raise RuntimeError(f"获取网页失败: {exc}")

    soup = BeautifulSoup(resp.text, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else "未找到标题"

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(" ")
    content = " ".join(text.split())
    return title[:200], content


def _build_openai_client() -> OpenAI:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("缺少 OPENAI_API_KEY 环境变量")
    return OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)


def summarize_content(url: str, title: str, content: str) -> str:
    settings = get_settings()
    client = _build_openai_client()
    prompt = (
        "你是一个简明的中文总结助手。给定网页标题、正文文本和链接，"
        "请用不超过120个字的中文概括主要内容，避免赘述。"
    )
    truncated_content = content[:4000]
    messages = [
        {"role": "system", "content": prompt},
        {
            "role": "user",
            "content": f"标题: {title}\n链接: {url}\n正文: {truncated_content}",
        },
    ]

    try:
        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            temperature=0.3,
            max_tokens=200,
        )
    except Exception as exc:
        raise RuntimeError(f"调用 OpenAI 失败: {exc}")

    return resp.choices[0].message.content.strip()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int):
    words = text.split()
    lines = []
    line = ""
    for word in words:
        test_line = f"{line} {word}".strip()
        w, _ = draw.textsize(test_line, font=font)
        if w <= max_width:
            line = test_line
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def generate_qr(url: str, box_size: int = 6) -> Image.Image:
    qr = qrcode.QRCode(box_size=box_size, border=1)
    qr.add_data(url)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


def generate_share_card(url: str, title: str, summary: str) -> str:
    card_width, card_height = 1024, 512
    bg_color = (20, 24, 28)
    accent_color = (111, 202, 255)
    text_color = (240, 244, 248)

    card = Image.new("RGB", (card_width, card_height), color=bg_color)
    draw = ImageDraw.Draw(card)

    title_font = ImageFont.load_default()
    summary_font = ImageFont.load_default()
    label_font = ImageFont.load_default()

    padding = 40
    qr_image = generate_qr(url, box_size=6)
    qr_size = qr_image.size[0]
    qr_pos = (card_width - qr_size - padding, card_height - qr_size - padding)
    card.paste(qr_image, qr_pos)

    draw.text((padding, padding), "ShareCard",
              font=label_font, fill=accent_color)

    max_title_width = card_width - qr_size - padding * 3
    title_lines = textwrap.wrap(title, width=30)[:3]
    y = padding + 24
    for line in title_lines:
        draw.text((padding, y), line, font=title_font, fill=text_color)
        y += 20

    max_summary_width = card_width - qr_size - padding * 3
    wrapped_summary = _wrap_text(
        draw, summary, summary_font, max_summary_width)
    wrapped_summary = wrapped_summary[:8]
    y += 10
    for line in wrapped_summary:
        draw.text((padding, y), line, font=summary_font, fill=(200, 210, 220))
        y += 18

    draw.text((padding, card_height - padding - 16),
              url, font=label_font, fill=(160, 170, 180))

    buffer = io.BytesIO()
    card.save(buffer, format="PNG")
    b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"
