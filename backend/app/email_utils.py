import email as email_lib
import imaplib
import logging
import smtplib
from email.header import decode_header
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional, Tuple

from app.services.settings_service import get_effective_config
from app.database import supabase

logger = logging.getLogger("fnol.email")


def send_email(to_addr: str, body_with_subject: str, claim_id: Optional[str] = None) -> None:
    cfg = get_effective_config()
    if not (cfg.get("smtp_user") and cfg.get("smtp_password")):
        raise RuntimeError(
            "SMTP is not configured. Enter SMTP host/user/password on the "
            "Settings page (an app password, not your login password), or "
            "set SMTP_USER/SMTP_PASSWORD in the backend .env as a fallback."
        )
    subject_line, _, body = body_with_subject.partition("\n\n")
    subject = subject_line.replace("Subject:", "").strip()

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = cfg["smtp_user"]
    msg["To"] = to_addr

    with smtplib.SMTP(cfg["smtp_host"], int(cfg["smtp_port"])) as server:
        if cfg.get("smtp_use_tls", True):
            server.starttls()
        server.login(cfg["smtp_user"], cfg["smtp_password"])
        server.sendmail(cfg["smtp_user"], [to_addr], msg.as_string())
    logger.info("Sent email to %s (subject=%r)", to_addr, subject)

    try:
        supabase.table("email_log").insert({
            "claim_id": claim_id, "direction": "outbound",
            "from_addr": cfg["smtp_user"], "to_addr": to_addr,
            "subject": subject, "body": body,
        }).execute()
    except Exception:
        logger.exception("send_email: failed to write email_log row (non-fatal)")


def test_smtp_connection() -> dict:
    cfg = get_effective_config()
    try:
        if not (cfg.get("smtp_user") and cfg.get("smtp_password")):
            return {"ok": False, "detail": "SMTP user/password not configured."}
        with smtplib.SMTP(cfg["smtp_host"], int(cfg["smtp_port"]), timeout=10) as server:
            if cfg.get("smtp_use_tls", True):
                server.starttls()
            server.login(cfg["smtp_user"], cfg["smtp_password"])
        return {"ok": True, "detail": f"Logged in to {cfg['smtp_host']} as {cfg['smtp_user']}."}
    except Exception as exc:
        return {"ok": False, "detail": str(exc)}


def _extract_plain_text(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get("Content-Disposition"):
                payload = part.get_payload(decode=True)
                return payload.decode(errors="ignore") if payload else ""
        return ""
    payload = msg.get_payload(decode=True)
    return payload.decode(errors="ignore") if payload else ""


def fetch_new_claim_emails(max_emails: int = 10) -> Tuple[Any, List[Dict[str, Any]]]:
    cfg = get_effective_config()
    if not (cfg.get("imap_user") and cfg.get("imap_password")):
        raise RuntimeError(
            "IMAP is not configured. Enter IMAP host/user/password on the "
            "Settings page, or set IMAP_USER/IMAP_PASSWORD in the backend "
            ".env as a fallback."
        )
    conn = imaplib.IMAP4_SSL(cfg["imap_host"], int(cfg["imap_port"]))
    conn.login(cfg["imap_user"], cfg["imap_password"])
    conn.select(cfg["imap_mailbox"])
    logger.info("fetch_new_claim_emails: connected to %s@%s (mailbox=%s)",
                cfg["imap_user"], cfg["imap_host"], cfg["imap_mailbox"])
    _, data = conn.search(None, "UNSEEN")
    ids = data[0].split()[:max_emails]
    logger.info("fetch_new_claim_emails: %d unseen message(s) found (capped at %d)", len(ids), max_emails)

    messages = []
    for eid in ids:
        _, msg_data = conn.fetch(eid, "(BODY.PEEK[])")
        raw = msg_data[0][1]
        msg = email_lib.message_from_bytes(raw)
        from_addr = email_lib.utils.parseaddr(msg.get("From", ""))[1]
        subject_raw, enc = decode_header(msg.get("Subject", ""))[0]
        subject = subject_raw.decode(enc or "utf-8", errors="ignore") if isinstance(subject_raw, bytes) else subject_raw
        logger.info("fetch_new_claim_emails: fetched uid=%s from=%s subject=%r", eid, from_addr, subject)
        body = _extract_plain_text(msg)
        messages.append({"uid": eid, "from": from_addr, "subject": subject, "body": body})
        try:
            supabase.table("email_log").insert({
                "direction": "inbound", "from_addr": from_addr,
                "to_addr": cfg["imap_user"], "subject": subject, "body": body,
            }).execute()
        except Exception:
            logger.exception("fetch_new_claim_emails: failed to write email_log row (non-fatal)")
    return conn, messages


def mark_seen(conn, uid) -> None:
    conn.store(uid, "+FLAGS", "\\Seen")
    logger.info("mark_seen: uid=%s", uid)


def test_imap_connection() -> dict:
    cfg = get_effective_config()
    try:
        if not (cfg.get("imap_user") and cfg.get("imap_password")):
            return {"ok": False, "detail": "IMAP user/password not configured."}
        conn = imaplib.IMAP4_SSL(cfg["imap_host"], int(cfg["imap_port"]), timeout=10)
        conn.login(cfg["imap_user"], cfg["imap_password"])
        conn.select(cfg["imap_mailbox"])
        _, data = conn.search(None, "UNSEEN")
        unseen = len(data[0].split()) if data and data[0] else 0
        conn.logout()
        return {"ok": True, "detail": f"Connected to {cfg['imap_host']} mailbox={cfg['imap_mailbox']}, {unseen} unseen message(s)."}
    except Exception as exc:
        return {"ok": False, "detail": str(exc)}
