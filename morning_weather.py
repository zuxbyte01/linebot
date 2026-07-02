#!/usr/bin/env python3
"""
Daily good-morning weather card for a LINE group.

Modes:
  generate  - fetch weather, render the card PNG (+ small preview JPG) into images/
  send      - push today's card to the LINE group via the Messaging API
  all       - generate then send (for local use / servers with public hosting)

Environment variables (needed for `send`):
  LINE_CHANNEL_ACCESS_TOKEN  - long-lived channel access token (Messaging API)
  LINE_GROUP_ID              - the group ID (starts with "C...")
  IMAGE_BASE_URL             - public HTTPS base URL where images/ is reachable,
                               e.g. https://raw.githubusercontent.com/<user>/<repo>/main/images

Usage:
  python morning_weather.py generate
  python morning_weather.py send
"""

import json
import os
import random
import sys
import datetime
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
CITY_NAME_ZH = "新北市"
CITY_NAME_EN = "New Taipei City"
LATITUDE = 25.012
LONGITUDE = 121.4657
TIMEZONE = "Asia/Taipei"

IMAGES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")

GREETINGS = [
    "早安！新的一天開始囉 🌞",
    "早安～祝你有美好的一天！",
    "早安！今天也要元氣滿滿！",
    "Good morning! 早安 ☀️",
    "早安！出門前看一下今天的天氣吧～",
]

# WMO weather code -> (zh, en, icon, theme)
# themes: sunny / cloudy / overcast / fog / rain / snow / storm
WMO = {
    0:  ("晴天", "Clear sky", "sun", "sunny"),
    1:  ("大致晴朗", "Mainly clear", "sun_cloud", "sunny"),
    2:  ("局部多雲", "Partly cloudy", "sun_cloud", "cloudy"),
    3:  ("陰天", "Overcast", "cloud", "overcast"),
    45: ("有霧", "Fog", "fog", "fog"),
    48: ("霧凇", "Rime fog", "fog", "fog"),
    51: ("毛毛雨", "Light drizzle", "rain", "rain"),
    53: ("毛毛雨", "Drizzle", "rain", "rain"),
    55: ("濃密毛毛雨", "Dense drizzle", "rain", "rain"),
    56: ("凍雨", "Freezing drizzle", "rain", "rain"),
    57: ("凍雨", "Freezing drizzle", "rain", "rain"),
    61: ("小雨", "Light rain", "rain", "rain"),
    63: ("中雨", "Moderate rain", "rain", "rain"),
    65: ("大雨", "Heavy rain", "heavy_rain", "rain"),
    66: ("凍雨", "Freezing rain", "rain", "rain"),
    67: ("凍雨", "Heavy freezing rain", "heavy_rain", "rain"),
    71: ("小雪", "Light snow", "snow", "snow"),
    73: ("中雪", "Moderate snow", "snow", "snow"),
    75: ("大雪", "Heavy snow", "snow", "snow"),
    77: ("霰", "Snow grains", "snow", "snow"),
    80: ("陣雨", "Light showers", "rain", "rain"),
    81: ("陣雨", "Moderate showers", "rain", "rain"),
    82: ("強陣雨", "Violent showers", "heavy_rain", "rain"),
    85: ("陣雪", "Snow showers", "snow", "snow"),
    86: ("強陣雪", "Heavy snow showers", "snow", "snow"),
    95: ("雷雨", "Thunderstorm", "storm", "storm"),
    96: ("雷雨帶冰雹", "Thunderstorm w/ hail", "storm", "storm"),
    99: ("強雷雨帶冰雹", "Severe thunderstorm", "storm", "storm"),
}

THEMES = {
    # top gradient, bottom gradient, accent, text
    "sunny":    ((255, 183, 94),  (255, 236, 179), (234, 88, 12),  (63, 42, 20)),
    "cloudy":   ((147, 197, 253), (224, 242, 254), (2, 132, 199),  (23, 37, 58)),
    "overcast": ((148, 163, 184), (226, 232, 240), (71, 85, 105),  (30, 41, 59)),
    "fog":      ((203, 213, 225), (241, 245, 249), (100, 116, 139),(51, 65, 85)),
    "rain":     ((96, 125, 165),  (191, 210, 232), (30, 64, 120),  (20, 33, 61)),
    "snow":     ((186, 210, 235), (240, 249, 255), (59, 130, 246), (30, 41, 59)),
    "storm":    ((71, 85, 120),   (148, 163, 190), (250, 204, 21), (17, 24, 39)),
}

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "C:\\Windows\\Fonts\\msjh.ttc",
]

WEEKDAYS_ZH = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


def font(size, bold=True):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            if not bold:
                alt = path.replace("Bold", "Regular")
                if os.path.exists(alt):
                    path = alt
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default(size)


# ----------------------------------------------------------------------------
# Weather
# ----------------------------------------------------------------------------
def fetch_weather():
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LATITUDE}&longitude={LONGITUDE}"
        "&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min,"
        "precipitation_probability_max,uv_index_max"
        f"&timezone={TIMEZONE}&forecast_days=1"
    )
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    d = r.json()
    daily, cur = d["daily"], d["current"]
    return {
        "code": int(daily["weather_code"][0]),
        "current_code": int(cur["weather_code"]),
        "temp_now": round(cur["temperature_2m"]),
        "feels_like": round(cur["apparent_temperature"]),
        "humidity": round(cur["relative_humidity_2m"]),
        "temp_max": round(daily["temperature_2m_max"][0]),
        "temp_min": round(daily["temperature_2m_min"][0]),
        "rain_prob": round(daily["precipitation_probability_max"][0] or 0),
        "uv": round(daily["uv_index_max"][0] or 0),
    }


# ----------------------------------------------------------------------------
# Drawing helpers
# ----------------------------------------------------------------------------
def vertical_gradient(size, top, bottom):
    w, h = size
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        c = tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        for x in range(w):
            px[x, y] = c
    return img


def draw_sun(draw, cx, cy, r, color=(255, 200, 60)):
    for i in range(12):
        import math
        a = i * math.pi / 6
        x1 = cx + math.cos(a) * r * 1.35
        y1 = cy + math.sin(a) * r * 1.35
        x2 = cx + math.cos(a) * r * 1.75
        y2 = cy + math.sin(a) * r * 1.75
        draw.line([x1, y1, x2, y2], fill=color, width=max(6, int(r // 10)))
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    draw.ellipse([cx - r * 0.72, cy - r * 0.72, cx + r * 0.72, cy + r * 0.72],
                 fill=(255, 224, 130))


def draw_cloud(draw, cx, cy, s, color=(255, 255, 255)):
    draw.ellipse([cx - s, cy - s * 0.35, cx - s * 0.15, cy + s * 0.5], fill=color)
    draw.ellipse([cx - s * 0.55, cy - s * 0.85, cx + s * 0.45, cy + s * 0.2], fill=color)
    draw.ellipse([cx - s * 0.1, cy - s * 0.5, cx + s, cy + s * 0.5], fill=color)
    draw.rectangle([cx - s * 0.85, cy + s * 0.05, cx + s * 0.85, cy + s * 0.5], fill=color)


def draw_drops(draw, cx, cy, s, n=3, color=(80, 130, 200)):
    step = (s * 1.5) / max(n - 1, 1)
    x0 = cx - s * 0.75
    for i in range(n):
        x = x0 + step * i
        y = cy + (s * 0.15 if i % 2 else 0)
        draw.line([x, y, x - s * 0.18, y + s * 0.5], fill=color, width=max(8, int(s * 0.14)))


def draw_bolt(draw, cx, cy, s, color=(250, 204, 21)):
    pts = [(cx + s * 0.15, cy - s * 0.1), (cx - s * 0.25, cy + s * 0.45),
           (cx - 2, cy + s * 0.45), (cx - s * 0.15, cy + s * 0.95),
           (cx + s * 0.3, cy + s * 0.3), (cx + s * 0.05, cy + s * 0.3)]
    draw.polygon(pts, fill=color)


def draw_snowflakes(draw, cx, cy, s, color=(255, 255, 255)):
    import math
    for i, (dx, dy) in enumerate([(-0.6, 0.2), (0, 0.45), (0.6, 0.2)]):
        x, y, r = cx + dx * s, cy + dy * s + s * 0.25, s * 0.14
        for k in range(3):
            a = k * math.pi / 3
            draw.line([x - math.cos(a) * r, y - math.sin(a) * r,
                       x + math.cos(a) * r, y + math.sin(a) * r],
                      fill=color, width=max(4, int(s * 0.05)))


def draw_fog_lines(draw, cx, cy, s, color=(255, 255, 255)):
    for i in range(3):
        y = cy + s * (0.15 + 0.28 * i)
        off = s * 0.12 * (1 if i % 2 else -1)
        draw.rounded_rectangle([cx - s + off, y, cx + s + off, y + s * 0.14],
                               radius=int(s * 0.07), fill=color)


def draw_icon(draw, kind, cx, cy, s):
    if kind == "sun":
        draw_sun(draw, cx, cy, s * 0.62)
    elif kind == "sun_cloud":
        draw_sun(draw, cx - s * 0.35, cy - s * 0.35, s * 0.45)
        draw_cloud(draw, cx + s * 0.15, cy + s * 0.25, s * 0.62)
    elif kind == "cloud":
        draw_cloud(draw, cx, cy, s * 0.8)
    elif kind == "fog":
        draw_cloud(draw, cx, cy - s * 0.35, s * 0.6)
        draw_fog_lines(draw, cx, cy, s * 0.7)
    elif kind == "rain":
        draw_cloud(draw, cx, cy - s * 0.2, s * 0.7)
        draw_drops(draw, cx, cy + s * 0.42, s * 0.7, n=3)
    elif kind == "heavy_rain":
        draw_cloud(draw, cx, cy - s * 0.2, s * 0.7, color=(226, 232, 240))
        draw_drops(draw, cx, cy + s * 0.42, s * 0.8, n=4)
    elif kind == "snow":
        draw_cloud(draw, cx, cy - s * 0.25, s * 0.7)
        draw_snowflakes(draw, cx, cy + s * 0.15, s * 0.9)
    elif kind == "storm":
        draw_cloud(draw, cx, cy - s * 0.25, s * 0.75, color=(203, 213, 225))
        draw_bolt(draw, cx, cy + s * 0.15, s * 0.75)


def rounded_panel(img, box, radius, fill, alpha=170):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.rounded_rectangle(box, radius=radius, fill=fill + (alpha,))
    img.alpha_composite(overlay)


# ----------------------------------------------------------------------------
# Card
# ----------------------------------------------------------------------------
def generate_card(w, out_path, preview_path):
    W, H = 1000, 1250
    zh, en, icon, theme = WMO.get(w["code"], ("多雲", "Cloudy", "cloud", "cloudy"))
    top, bottom, accent, text = THEMES[theme]

    img = vertical_gradient((W, H), top, bottom).convert("RGBA")
    draw = ImageDraw.Draw(img)

    now = datetime.datetime.now(ZoneInfo(TIMEZONE))
    date_zh = f"{now.year}年{now.month}月{now.day}日 {WEEKDAYS_ZH[now.weekday()]}"

    # Header
    draw.text((70, 70), "早安", font=font(96), fill=text)
    draw.text((70, 190), "GOOD MORNING", font=font(38), fill=accent)
    draw.text((70, 260), date_zh, font=font(40, bold=False), fill=text)
    draw.text((70, 318), f"{CITY_NAME_ZH} · {CITY_NAME_EN}", font=font(34, bold=False), fill=text)

    # Weather icon
    draw_icon(draw, icon, W - 230, 240, 170)

    # Big current temperature
    draw.text((70, 430), f"{w['temp_now']}°", font=font(230), fill=text)
    tw = draw.textlength(f"{w['temp_now']}°", font=font(230))
    draw.text((80 + tw, 530), zh, font=font(64), fill=text)
    draw.text((80 + tw, 615), en, font=font(36, bold=False), fill=accent)
    draw.text((75, 700), f"體感溫度 {w['feels_like']}°C", font=font(38, bold=False), fill=text)

    # Stats panel
    panel_top = 790
    rounded_panel(img, (60, panel_top, W - 60, panel_top + 330), 36, (255, 255, 255), alpha=175)
    draw = ImageDraw.Draw(img)

    stats = [
        ("最高 / 最低", f"{w['temp_max']}° / {w['temp_min']}°"),
        ("降雨機率", f"{w['rain_prob']}%"),
        ("濕度", f"{w['humidity']}%"),
        ("紫外線指數", f"{w['uv']}"),
    ]
    cell_w = (W - 120) / 4
    for i, (label, value) in enumerate(stats):
        cx = 60 + cell_w * i + cell_w / 2
        lw = draw.textlength(label, font=font(30, bold=False))
        vw = draw.textlength(value, font=font(52))
        draw.text((cx - lw / 2, panel_top + 70), label, font=font(30, bold=False),
                  fill=(90, 100, 115))
        draw.text((cx - vw / 2, panel_top + 150), value, font=font(52), fill=(30, 41, 59))
        if i:
            x = 60 + cell_w * i
            draw.line([x, panel_top + 70, x, panel_top + 260], fill=(200, 208, 218), width=2)

    # Tip line (use symbols that exist in Noto Sans CJK — color emoji won't render)
    if w["rain_prob"] >= 60:
        tip = "☂ 降雨機率高，出門記得帶傘！"
    elif w["temp_max"] >= 33:
        tip = "☀ 天氣炎熱，記得多喝水、注意防曬！"
    elif w["temp_min"] <= 14:
        tip = "❄ 早晚偏涼，出門記得加件外套～"
    elif w["uv"] >= 8:
        tip = "☀ 紫外線很強，防曬做好做滿！"
    else:
        tip = "♪ 天氣不錯，祝你有美好的一天！"
    draw.text((70, panel_top + 350), tip, font=font(42), fill=text)

    draw.text((70, H - 46), "資料來源：Open-Meteo", font=font(24, bold=False), fill=text)

    out = img.convert("RGB")
    out.save(out_path, "PNG", optimize=True)
    prev = out.resize((300, 375))
    prev.save(preview_path, "JPEG", quality=80)
    return out_path


# ----------------------------------------------------------------------------
# LINE push
# ----------------------------------------------------------------------------
def send_to_line(image_name, preview_name):
    token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    group_id = os.environ["LINE_GROUP_ID"]
    base = os.environ["IMAGE_BASE_URL"].rstrip("/")

    r = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
        data=json.dumps({
            "to": group_id,
            "messages": [
                {"type": "text", "text": random.choice(GREETINGS)},
                {"type": "image",
                 "originalContentUrl": f"{base}/{image_name}",
                 "previewImageUrl": f"{base}/{preview_name}"},
            ],
        }),
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"LINE push failed: {r.status_code} {r.text}")
    print("Pushed to LINE group ✅")


# ----------------------------------------------------------------------------
def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    os.makedirs(IMAGES_DIR, exist_ok=True)
    today = datetime.datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d")
    image_name = f"weather-{today}.png"
    preview_name = f"weather-{today}-preview.jpg"
    image_path = os.path.join(IMAGES_DIR, image_name)
    preview_path = os.path.join(IMAGES_DIR, preview_name)

    if mode in ("generate", "all"):
        if os.environ.get("MOCK_WEATHER"):
            w = json.loads(os.environ["MOCK_WEATHER"])
        else:
            w = fetch_weather()
        print("Weather:", w)
        generate_card(w, image_path, preview_path)
        print(f"Card saved: {image_path}")
        # keep only the last 30 days of images (older LINE messages would lose
        # their picture if we deleted the file too soon)
        keep = sorted(f for f in os.listdir(IMAGES_DIR) if f.startswith("weather-"))
        for old in keep[:-60]:  # 30 days x (image + preview)
            os.remove(os.path.join(IMAGES_DIR, old))

    if mode in ("send", "all"):
        send_to_line(image_name, preview_name)


if __name__ == "__main__":
    main()
