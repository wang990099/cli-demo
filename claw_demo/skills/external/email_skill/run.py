from __future__ import annotations

import json
import smtplib
import sys
from email.message import EmailMessage


def main() -> None:
    payload = json.loads(sys.stdin.read() or "{}")
    cfg = payload.get("config", {})
    args = payload.get("args", {})

    enabled = bool(cfg.get("enabled", False))
    dry_run = bool(cfg.get("dry_run", True))
    smtp = cfg.get("smtp", {})

    to = args.get("to", "")
    subject = args.get("subject", "")
    body = args.get("body", "")

    if not to:
        print(json.dumps({"ok": False, "text": "缺少收件人"}, ensure_ascii=False))
        return

    if not enabled or dry_run:
        preview = f"[DRY-RUN] to={to}, subject={subject}, body={body[:120]}"
        print(json.dumps({"ok": True, "text": preview}, ensure_ascii=False))
        return

    msg = EmailMessage()
    msg["From"] = smtp.get("from", "")
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(smtp.get("host", ""), int(smtp.get("port", 587)), timeout=15) as server:
        server.starttls()
        username = smtp.get("username", "")
        password = smtp.get("password", "")
        if username:
            server.login(username, password)
        server.send_message(msg)

    print(json.dumps({"ok": True, "text": "邮件发送成功"}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "text": f"邮件发送失败: {exc}"}, ensure_ascii=False))
