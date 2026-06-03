import io
import logging
import re
import textwrap
from datetime import datetime

import requests
from PIL import Image, ImageDraw, ImageFont

import config

logger = logging.getLogger(__name__)

FONT_PATH = None
FONT_SIZE_TITLE = 42
FONT_SIZE_SMALL = 24
FONT_SIZE_BRAND = 20

CANVAS_W, CANVAS_H = 1200, 630

COLOR_BG_TOP = (10, 10, 46)
COLOR_BG_BOTTOM = (26, 5, 51)
COLOR_TEXT = (255, 255, 255)
COLOR_ACCENT = (100, 180, 255)
COLOR_BRAND = (150, 150, 200)


def _get_font(size: int):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        try:
            return ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", size)
        except Exception:
            return ImageFont.load_default()


def _draw_gradient(draw: ImageDraw):
    for y in range(CANVAS_H):
        r = int(COLOR_BG_TOP[0] + (COLOR_BG_BOTTOM[0] - COLOR_BG_TOP[0]) * y / CANVAS_H)
        g = int(COLOR_BG_TOP[1] + (COLOR_BG_BOTTOM[1] - COLOR_BG_TOP[1]) * y / CANVAS_H)
        b = int(COLOR_BG_TOP[2] + (COLOR_BG_BOTTOM[2] - COLOR_BG_TOP[2]) * y / CANVAS_H)
        draw.line([(0, y), (CANVAS_W, y)], fill=(r, g, b))


def _draw_hex_grid(draw: ImageDraw):
    for x in range(0, CANVAS_W, 40):
        for y in range(0, CANVAS_H, 40):
            draw.ellipse([x - 1, y - 1, x + 1, y + 1], fill=(255, 255, 255, 20))


def generate_image(title: str, source: str) -> io.BytesIO:
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), COLOR_BG_TOP)
    draw = ImageDraw.Draw(img)

    _draw_gradient(draw)
    _draw_hex_grid(draw)

    font_title = _get_font(FONT_SIZE_TITLE)
    font_small = _get_font(FONT_SIZE_SMALL)
    font_brand = _get_font(FONT_SIZE_BRAND)

    draw.text((30, 20), config.BRAND_NAME, font=font_brand, fill=COLOR_BRAND)

    date_str = datetime.now().strftime("%d.%m.%Y")
    date_bbox = draw.textbbox((0, 0), date_str, font=font_small)
    draw.text(
        (CANVAS_W - date_bbox[2] - 30, 22),
        date_str,
        font=font_small,
        fill=COLOR_BRAND,
    )

    max_w = CANVAS_W - 80
    title = re.sub(r"\s+", " ", title).strip()

    wrapped_lines = []
    for line in title.split("\n"):
        wrapped_lines.extend(textwrap.wrap(line, width=35) if line else [""])
    if not wrapped_lines:
        wrapped_lines = [title]

    wrapped_lines = wrapped_lines[:5]

    total_h = sum(
        draw.textbbox((0, 0), l, font=font_title)[3]
        - draw.textbbox((0, 0), l, font=font_title)[1]
        + 8
        for l in wrapped_lines
    )
    y_start = (CANVAS_H - total_h) // 2 - 20

    for line in wrapped_lines:
        bbox = draw.textbbox((0, 0), line, font=font_title)
        line_w = bbox[2] - bbox[0]
        x = (CANVAS_W - line_w) // 2
        draw.text((x, y_start), line, font=font_title, fill=COLOR_TEXT)
        y_start += bbox[3] - bbox[1] + 8

    draw.text(
        (30, CANVAS_H - 50),
        f"Источник: {source}",
        font=font_small,
        fill=COLOR_ACCENT,
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _download_image(url: str) -> io.BytesIO | None:
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "image" not in content_type:
            return None
        return io.BytesIO(resp.content)
    except Exception as e:
        logger.debug("Image download failed: %s", e)
        return None


def prepare_post(article) -> tuple[str, io.BytesIO]:
    title = article.title
    description = article.description[:500]

    text = f"🤖 *{title}*\n\n{description}\n\n📅 Источник: [{article.source}]({article.url})\n{' '.join(config.HASHTAGS)}"

    image_buf = None
    if article.image_url:
        image_buf = _download_image(article.image_url)

    if not image_buf:
        image_buf = generate_image(title, article.source)

    return text, image_buf


async def send_post(bot, chat_id: str, text: str, image_buf: io.BytesIO):
    try:
        await bot.send_photo(
            chat_id=chat_id,
            photo=image_buf,
            caption=text,
            parse_mode="Markdown",
        )
        logger.info("Post sent successfully")
        return True
    except Exception as e:
        logger.error("Failed to send post: %s", e)
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="Markdown",
            )
            logger.info("Fallback: text-only post sent")
            return True
        except Exception as e2:
            logger.error("Fallback also failed: %s", e2)
            return False
