from __future__ import annotations

import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests
from pydantic import BaseModel, Field, ValidationError

from claw_demo.skills.models import SkillContext, SkillResult


class WeatherToolArgs(BaseModel):
    city: str | None = None


class FileSearchToolArgs(BaseModel):
    query: str = Field(min_length=1)
    path: str = "./"


class FileReadToolArgs(BaseModel):
    path: str


class SummarizeToolArgs(BaseModel):
    text: str = Field(min_length=1)


class EmailToolArgs(BaseModel):
    to: str
    subject: str
    body: str


class TimeToolArgs(BaseModel):
    timezone: str | None = None


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "weather",
            "description": "查询天气",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "file_search",
            "description": "在工作目录中搜索文件名",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "path": {"type": "string"},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "file_read",
            "description": "读取工作目录中的文件内容",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize",
            "description": "总结给定文本",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "email",
            "description": "发送邮件",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["to", "subject", "body"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "time",
            "description": "获取当前时间",
            "parameters": {
                "type": "object",
                "properties": {"timezone": {"type": "string"}},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
]


def _is_under_allowed(path: Path, allowed_roots: list[str], base_root: Path) -> bool:
    resolved = path.resolve()
    for root in allowed_roots:
        root_path = (base_root / root).resolve()
        if resolved == root_path or root_path in resolved.parents:
            return True
    return False


def _run_weather(args: WeatherToolArgs, ctx: SkillContext) -> SkillResult:
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
        weather_resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": loc["latitude"],
                "longitude": loc["longitude"],
                "current": "temperature_2m,weather_code",
            },
            timeout=8,
        )
        weather_resp.raise_for_status()
        current = weather_resp.json().get("current", {})
        temp = current.get("temperature_2m", "?")
        code = current.get("weather_code", "?")
        return SkillResult(ok=True, text=f"{city} 当前天气: code={code}, 温度={temp}°C")
    except Exception:
        return SkillResult(ok=False, text="天气服务暂不可用")


def _run_file_search(args: FileSearchToolArgs, ctx: SkillContext) -> SkillResult:
    root = (ctx.workspace_root / args.path).resolve()
    if not _is_under_allowed(root, ctx.config.file_access.allowed_roots, ctx.workspace_root):
        return SkillResult(ok=False, text="路径不在允许范围内")

    matches: list[str] = []
    q = args.query.lower()
    for p in root.rglob("*"):
        if q in p.name.lower():
            matches.append(str(p.relative_to(ctx.workspace_root)))
        if len(matches) >= 20:
            break

    if not matches:
        return SkillResult(ok=True, text="未找到匹配文件")
    return SkillResult(ok=True, text="\n".join(matches))


def _run_file_read(args: FileReadToolArgs, ctx: SkillContext) -> SkillResult:
    target = (ctx.workspace_root / args.path).resolve()
    if not _is_under_allowed(target, ctx.config.file_access.allowed_roots, ctx.workspace_root):
        return SkillResult(ok=False, text="路径不在允许范围内")
    if not target.exists() or not target.is_file():
        return SkillResult(ok=False, text="文件不存在")
    if target.stat().st_size > ctx.config.file_access.max_read_bytes:
        return SkillResult(ok=False, text="文件超过读取大小限制")
    return SkillResult(ok=True, text=target.read_text(encoding="utf-8", errors="replace"))


def _run_summarize(args: SummarizeToolArgs, ctx: SkillContext) -> SkillResult:
    text = args.text.strip()
    if len(text) <= 220:
        return SkillResult(ok=True, text=text)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return SkillResult(ok=True, text=text[:220])
    if len(lines) == 1:
        return SkillResult(ok=True, text=lines[0][:220])
    return SkillResult(ok=True, text=f"{lines[0]}\n...\n{lines[-1]}")


def _run_email(args: EmailToolArgs, ctx: SkillContext) -> SkillResult:
    smtp = ctx.config.email.smtp
    use_ssl = bool(smtp.use_ssl)
    use_tls = bool(smtp.use_tls)
    timeout = int(smtp.timeout)
    tls_note = "use_ssl=true 时已忽略 use_tls" if use_ssl and use_tls else ""

    from_addr = smtp.from_addr or smtp.username or "bot@example.com"
    host = smtp.host
    port = int(smtp.port)

    if not ctx.config.email.enabled or ctx.config.email.dry_run:
        mode = "SSL" if use_ssl else ("STARTTLS" if use_tls else "PLAIN")
        preview = (
            f"[DRY-RUN] mode={mode}, host={host}:{port}, from={from_addr}, "
            f"to={args.to}, subject={args.subject}, body={args.body[:120]}"
        )
        if tls_note:
            preview = f"{preview}, note={tls_note}"
        return SkillResult(ok=True, text=preview)

    if not host:
        return SkillResult(ok=False, text="缺少 SMTP host 配置")

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = args.to
    msg["Subject"] = args.subject
    msg.set_content(args.body)

    smtp_cls = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    try:
        with smtp_cls(host, port, timeout=timeout) as server:
            if use_tls and not use_ssl:
                server.starttls()
            if smtp.username:
                server.login(smtp.username, smtp.password)
            server.send_message(msg)
        ok_text = "邮件发送成功"
        if tls_note:
            ok_text = f"{ok_text}（{tls_note}）"
        return SkillResult(ok=True, text=ok_text)
    except Exception as exc:  # pragma: no cover
        return SkillResult(ok=False, text=f"邮件发送失败: {exc}")


def _run_time(args: TimeToolArgs, ctx: SkillContext) -> SkillResult:
    tz_name = (args.timezone or ctx.config.app.timezone).strip() or "UTC"
    try:
        from datetime import datetime, timezone

        local_now = datetime.now(ZoneInfo(tz_name))
        utc_now = datetime.now(timezone.utc)
        text = (
            f"当前时间({tz_name}): {local_now.strftime('%Y-%m-%d %H:%M:%S %Z')}\\n"
            f"UTC: {utc_now.strftime('%Y-%m-%d %H:%M:%S %Z')}"
        )
        return SkillResult(ok=True, text=text)
    except Exception:
        return SkillResult(ok=False, text=f"无效时区或获取时间失败: {tz_name}")


class ToolExecutor:
    def execute(self, tool_name: str, tool_args: dict[str, Any], ctx: SkillContext) -> SkillResult:
        try:
            if tool_name == "weather":
                return _run_weather(WeatherToolArgs.model_validate(tool_args), ctx)
            if tool_name == "file_search":
                return _run_file_search(FileSearchToolArgs.model_validate(tool_args), ctx)
            if tool_name == "file_read":
                return _run_file_read(FileReadToolArgs.model_validate(tool_args), ctx)
            if tool_name == "summarize":
                return _run_summarize(SummarizeToolArgs.model_validate(tool_args), ctx)
            if tool_name == "email":
                return _run_email(EmailToolArgs.model_validate(tool_args), ctx)
            if tool_name == "time":
                return _run_time(TimeToolArgs.model_validate(tool_args), ctx)
            return SkillResult(ok=False, text=f"未知工具: {tool_name}")
        except ValidationError as exc:
            return SkillResult(ok=False, text=f"工具参数错误: {exc}")
        except Exception as exc:  # pragma: no cover
            return SkillResult(ok=False, text=f"工具执行失败: {exc}")
