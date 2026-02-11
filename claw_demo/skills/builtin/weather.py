from __future__ import annotations

import requests
from pydantic import BaseModel, Field

from claw_demo.skills.models import SkillContext, SkillResult


class WeatherArgs(BaseModel):
    city: str | None = Field(default=None)


def run(args: WeatherArgs, ctx: SkillContext) -> SkillResult:
    city = (args.city or ctx.config.weather.default_city).strip()
    try:
        geo_resp = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "zh"},
            timeout=8,
        )
        geo_resp.raise_for_status()
        results = geo_resp.json().get("results") or []
        if not results:
            return SkillResult(ok=False, text=f"未找到城市: {city}")

        loc = results[0]
        lat, lon = loc["latitude"], loc["longitude"]
        weather_resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current": "temperature_2m,weather_code"},
            timeout=8,
        )
        weather_resp.raise_for_status()
        current = weather_resp.json().get("current", {})
        temp = current.get("temperature_2m", "?")
        code = current.get("weather_code", "?")
        text = f"{city} 当前天气: code={code}, 温度={temp}°C"
        return SkillResult(ok=True, text=text, data={"city": city, "temperature": temp, "code": code})
    except Exception:
        return SkillResult(ok=False, text="天气服务暂不可用")
