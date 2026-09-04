import logging
import re
from typing import Any, Dict, List, Optional

from app.database import supabase
from app.db_ops import db_get_claim
from app.email_utils import fetch_new_claim_emails, mark_seen
from app.graph.orchestration import process_claim, resume_claim

logger = logging.getLogger("fnol.inbox")

_CLAIM_TAG_RE = re.compile(r"\[?(CLM-[0-9A-F]{6,})\]?", re.I)
_CLAIM_KEYWORDS = (
    "claim", "policy", "pol-", "accident", "incident", "insurance",
    "damage", "collision", "crash", "loss", "fnol",
)


def find_claim_id_in_subject(subject: str) -> Optional[str]:
    m = _CLAIM_TAG_RE.search(subject or "")
    return m.group(1).upper() if m else None


def find_open_claim_for_sender(email_addr: str) -> Optional[Dict[str, Any]]:
    open_statuses = ("awaiting_info", "needs_manual_followup")
    res = (
        supabase.table("claims").select("*")
        .eq("claimant_email", email_addr)
        .in_("status", open_statuses)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def is_claim_related_email(subject: str, body: str) -> bool:
    text = f"{subject}\n{body}".lower()
    if re.search(r"pol-\d+", text):
        return True
    return any(kw in text for kw in _CLAIM_KEYWORDS)


def process_inbox(max_emails: int = 10) -> List[Dict[str, Any]]:
    conn, messages = fetch_new_claim_emails(max_emails=max_emails)
    results = []
    try:
        for m in messages:
            logger.info("process_inbox: processing message from=%s subject=%r", m["from"], m["subject"])
            tagged_claim_id = find_claim_id_in_subject(m["subject"])

            if tagged_claim_id and db_get_claim(tagged_claim_id):
                logger.info("process_inbox: correlated by subject tag -> %s", tagged_claim_id)
                record = resume_claim(tagged_claim_id, m["body"])
            else:
                open_claim = find_open_claim_for_sender(m["from"])
                if open_claim is not None:
                    logger.info("process_inbox: correlated by sender's open claim -> %s", open_claim["claim_id"])
                    record = resume_claim(open_claim["claim_id"], m["body"])
                elif is_claim_related_email(m["subject"], m["body"]):
                    logger.info("process_inbox: no existing claim matched -- starting a new one for %s", m["from"])
                    record = process_claim(m["body"], m["from"], source="imap")
                else:
                    logger.info("process_inbox: skipping unrelated email from %r (subject=%r)", m["from"], m["subject"])
                    mark_seen(conn, m["uid"])
                    continue

            results.append(record)
            mark_seen(conn, m["uid"])
    finally:
        conn.logout()
        logger.info("process_inbox: IMAP connection closed")
    logger.info("process_inbox: %d claim(s) processed this poll", len(results))
    return results
