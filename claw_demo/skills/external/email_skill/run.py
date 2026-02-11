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
    use_ssl = bool(smtp.get("use_ssl", False))
    use_tls = bool(smtp.get("use_tls", True))
    timeout = int(smtp.get("timeout", 30))
    tls_note = "use_ssl=true 时已忽略 use_tls" if use_ssl and use_tls else ""

    to = args.get("to", "")
    subject = args.get("subject", "")
    body = args.get("body", "")
    from_addr = smtp.get("from", "") or smtp.get("username", "") or "bot@example.com"
    host = smtp.get("host", "")
    port = int(smtp.get("port", 587))
    username = smtp.get("username", "")
    password = smtp.get("password", "")

    if not to:
        print(json.dumps({"ok": False, "text": "缺少收件人"}, ensure_ascii=False))
        return

    if not enabled or dry_run:
        mode = "SSL" if use_ssl else ("STARTTLS" if use_tls else "PLAIN")
        preview = (
            f"[DRY-RUN] mode={mode}, host={host}:{port}, from={from_addr}, "
            f"to={to}, subject={subject}, body={body[:120]}"
        )
        if tls_note:
            preview = f"{preview}, note={tls_note}"
        print(json.dumps({"ok": True, "text": preview}, ensure_ascii=False))
        return

    if not host:
        print(json.dumps({"ok": False, "text": "缺少 SMTP host 配置"}, ensure_ascii=False))
        return
    if not from_addr:
        print(json.dumps({"ok": False, "text": "缺少发件人 from 配置"}, ensure_ascii=False))
        return

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    smtp_cls = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with smtp_cls(host, port, timeout=timeout) as server:
        if use_tls and not use_ssl:
            server.starttls()
        if username:
            server.login(username, password)
        server.send_message(msg)

    ok_text = "邮件发送成功"
    if tls_note:
        ok_text = f"{ok_text}（{tls_note}）"
    print(json.dumps({"ok": True, "text": ok_text}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "text": f"邮件发送失败: {exc}"}, ensure_ascii=False))
