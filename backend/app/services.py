import base64
import io
import textwrap
from typing import Tuple

import qrcode
import requests
from bs4 import BeautifulSoup
from urllib.parse import unquote as url_unquote
from PIL import Image, ImageDraw, ImageFont

from .config import get_settings


USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"


def fetch_page(url: str) -> Tuple[str, str, BeautifulSoup]:
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
    # return the soup as well so callers can parse favicon or other metadata
    return title[:200], content, soup


def summarize_content(url: str, title: str, content: str) -> str:
    """
    使用 OpenAI REST API（requests）生成摘要，避免依赖 openai 客户端造成的兼容性问题。
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("缺少 OPENAI_API_KEY 环境变量")

    prompt = (
        "你是一个简明的中文总结助手。给定网页标题、正文文本和链接，"
        "请用不超过60个字的中文概括主要内容，避免赘述。你的返回值应该以：本页面开头，如果这是一个博客文章，就写博客文章的概述；如果是一个 webapp，就写这个 webapp 的功能。你不需要在你的输出中包含网页链接。"
    )
    truncated_content = content[:4000]
    messages = [
        {"role": "system", "content": prompt},
        {
            "role": "user",
            "content": f"标题: {title}\n链接: {url}\n正文: {truncated_content}",
        },
    ]

    payload = {
        "model": settings.openai_model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 200,
    }
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    endpoint = settings.openai_base_url.rstrip('/') + '/chat/completions'

    try:
        resp = requests.post(endpoint, json=payload,
                             headers=headers, timeout=15)
        resp.raise_for_status()
    except Exception as exc:
        raise RuntimeError(f"调用 OpenAI 失败: {exc}")

    data = resp.json()
    try:
        return data['choices'][0]['message']['content'].strip()
    except Exception:
        return str(data)


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int):
    words = text.split()
    lines = []
    line = ""
    for word in words:
        test_line = f"{line} {word}".strip()
        # Pillow versions differ: prefer textbbox for width calculation
        try:
            bbox = draw.textbbox((0, 0), test_line, font=font)
            w = bbox[2] - bbox[0]
        except Exception:
            # Fallback to textlength if available
            try:
                w = draw.textlength(test_line, font=font)
            except Exception:
                # As a final fallback, approximate by character count
                w = len(test_line) * \
                    (font.size if hasattr(font, 'size') else 8)
        if w <= max_width:
            line = test_line
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def generate_qr(url: str, box_size: int = 6, border: int = 0, scale: int | None = None, add_border_px: int = 0, fill_color: str | tuple = "black", back_color: str | tuple = "white") -> Image.Image:
    """
    Generate a QR PIL Image with minimal outer white margin.

    - border: qrcode library quiet zone in modules (we set 0 by default to avoid extra margins)
    - scale: if provided, resize final image to (scale x scale) pixels
    - add_border_px: after trimming the QR's internal white area, optionally add a small white border for contrast
    Returns an RGBA image.
    """
    # If transparent background requested, draw QR modules manually onto an RGBA canvas
    if back_color in (None, 'transparent'):
        qr = qrcode.QRCode(box_size=1, border=border)
        qr.add_data(url)
        qr.make(fit=True)
        matrix = qr.get_matrix()  # list of lists of booleans
        n = len(matrix)

        # determine module pixel size
        if scale:
            target_px = int(scale)
            module_px = max(1, target_px // n)
            img_size = module_px * n
        else:
            module_px = max(1, box_size)
            img_size = module_px * n

        img = Image.new("RGBA", (img_size, img_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # convert fill_color to RGBA tuple
        def _parse_color(c):
            if isinstance(c, tuple):
                return (c[0], c[1], c[2], 255) if len(c) == 3 else c
            if isinstance(c, str) and c.startswith('#') and len(c) in (7, 9):
                r = int(c[1:3], 16)
                g = int(c[3:5], 16)
                b = int(c[5:7], 16)
                return (r, g, b, 255)
            # fallback
            return (0, 0, 0, 255)

        fill_rgba = _parse_color(fill_color)

        for y, row in enumerate(matrix):
            for x, val in enumerate(row):
                if val:
                    x0 = x * module_px
                    y0 = y * module_px
                    x1 = x0 + module_px
                    y1 = y0 + module_px
                    draw.rectangle([x0, y0, x1 - 1, y1 - 1], fill=fill_rgba)

        # optionally add border (transparent by default if add_border_px=0)
        if add_border_px and add_border_px > 0:
            new_w, new_h = img_size + add_border_px * 2, img_size + add_border_px * 2
            bg = Image.new("RGBA", (new_w, new_h), (255, 255, 255, 255))
            bg.paste(img, (add_border_px, add_border_px), img)
            img = bg

        # final scaling if requested and module_px calculation didn't match target exactly
        if scale and (img.size[0] != int(scale)):
            img = img.resize((int(scale), int(scale)), resample=Image.LANCZOS)

        return img
    else:
        qr = qrcode.QRCode(box_size=box_size, border=border)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color=fill_color,
                            back_color=back_color).convert("RGBA")

    # Trim outer white area by finding the bbox of non-white pixels
    try:
        gray = img.convert("L")
        # build mask of non-almost-white pixels (threshold slightly less than 255)
        mask = gray.point(lambda p: 255 if p < 250 else 0)
        bbox = mask.getbbox()
        if bbox:
            img = img.crop(bbox)
    except Exception:
        # if trimming fails, keep original
        pass

    # Optionally add a fixed border (default 0 - no border)
    if add_border_px and add_border_px > 0:
        w, h = img.size
        new_w, new_h = w + add_border_px * 2, h + add_border_px * 2
        # use a white border by default
        bg = Image.new("RGBA", (new_w, new_h), (255, 255, 255, 255))
        bg.paste(img, (add_border_px, add_border_px), img)
        img = bg

    # Optional scaling to a target pixel size
    if scale:
        img = img.resize((scale, scale), resample=Image.LANCZOS)

    return img


def qr_image_base64(url: str, box_size: int = 6, scale: int | None = None, fill_color: str | tuple = "black", back_color: str | tuple = "white", add_border_px: int = 0) -> str:
    img = generate_qr(url, box_size=box_size, border=0,
                      scale=scale, add_border_px=add_border_px, fill_color=fill_color, back_color=back_color)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def fetch_favicon_base64(page_url: str, soup: BeautifulSoup = None) -> str | None:
    """尝试从页面中解析 favicon，如果失败则尝试 {origin}/favicon.ico，返回 data:image/png;base64 或 None。"""
    settings = get_settings()
    try:
        base = page_url
        if soup:
            icon_link = None
            for rel in ("icon", "shortcut icon", "apple-touch-icon"):
                tag = soup.find("link", rel=lambda x: x and rel in x)
                if tag and tag.get("href"):
                    icon_link = tag.get("href")
                    break
            if icon_link:
                icon_url = requests.compat.urljoin(base, icon_link)
            else:
                icon_url = requests.compat.urljoin(base, "/favicon.ico")
        else:
            icon_url = requests.compat.urljoin(base, "/favicon.ico")

        resp = requests.get(icon_url, timeout=settings.request_timeout_seconds)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "image/x-icon")
        # Convert to PNG if needed by loading with PIL and saving PNG
        try:
            img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            return f"data:image/png;base64,{b64}"
        except Exception:
            b64 = base64.b64encode(resp.content).decode("utf-8")
            return f"data:{content_type};base64,{b64}"
    except Exception:
        return None


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
    # choose a QR pixel size - use fixed 320x320 for high-quality rendering
    qr_target = 320
    # convert accent_color tuple to hex string for qrcode library
    accent_hex = '#%02x%02x%02x' % accent_color
    qr_image = generate_qr(url, box_size=6, border=0, scale=qr_target,
                           add_border_px=8, fill_color=accent_hex, back_color='white')
    qr_size = qr_image.size[0]
    qr_pos = (card_width - qr_size - padding, card_height - qr_size - padding)
    card.paste(qr_image, qr_pos, qr_image)

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
              url, font=label_font, fill=accent_color)

    buffer = io.BytesIO()
    card.save(buffer, format="PNG")
    b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"
