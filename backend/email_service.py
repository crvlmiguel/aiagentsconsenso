"""Simple SMTP / email notification sender."""
import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

logger = logging.getLogger(__name__)


def send_email(cfg: dict, to_email: str, subject: str, html_body: str) -> dict:
    """Send an email using the tenant's SMTP config. Returns {ok, error?}.
    cfg expected keys: host, port, username, password, from_email, secure (tls/ssl/none)."""
    if not cfg or not cfg.get("host") or not cfg.get("from_email"):
        return {"ok": False, "error": "SMTP não configurado"}
    if not to_email:
        return {"ok": False, "error": "Destinatário em falta"}
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = cfg["from_email"]
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        port = int(cfg.get("port") or 587)
        secure = (cfg.get("secure") or "tls").lower()
        if secure == "ssl":
            srv = smtplib.SMTP_SSL(cfg["host"], port, timeout=15)
        else:
            srv = smtplib.SMTP(cfg["host"], port, timeout=15)
            if secure == "tls":
                srv.starttls()
        if cfg.get("username"):
            srv.login(cfg["username"], cfg.get("password", ""))
        srv.sendmail(cfg["from_email"], [to_email], msg.as_string())
        srv.quit()
        return {"ok": True}
    except Exception as e:
        logger.warning(f"SMTP send failed: {e}")
        return {"ok": False, "error": str(e)[:300]}


def render_lead_email(lead: dict) -> str:
    tags = ", ".join(lead.get("tags") or []) or "—"
    return f"""
<html><body style="font-family:Inter,system-ui,sans-serif;color:#0B1324">
  <div style="max-width:560px;margin:0 auto;padding:24px;border:1px solid #E5EAF2;border-radius:12px">
    <div style="color:#0069FE;font-weight:600;letter-spacing:.1em;text-transform:uppercase;font-size:12px">Novo Lead</div>
    <h2 style="margin:8px 0 16px">{lead.get('name','')}</h2>
    <table style="width:100%;border-collapse:collapse;font-size:14px">
      <tr><td style="padding:6px 0;color:#5B6B82">Email</td><td>{lead.get('email') or '—'}</td></tr>
      <tr><td style="padding:6px 0;color:#5B6B82">Telefone</td><td>{lead.get('phone') or '—'}</td></tr>
      <tr><td style="padding:6px 0;color:#5B6B82">Empresa</td><td>{lead.get('company') or '—'}</td></tr>
      <tr><td style="padding:6px 0;color:#5B6B82">Origem</td><td>{lead.get('source','')}</td></tr>
      <tr><td style="padding:6px 0;color:#5B6B82">Score</td><td><b>{lead.get('score',0)}</b></td></tr>
      <tr><td style="padding:6px 0;color:#5B6B82">Tags</td><td>{tags}</td></tr>
      <tr><td style="padding:6px 0;color:#5B6B82">Notas</td><td>{lead.get('notes','')}</td></tr>
    </table>
    <p style="color:#5B6B82;font-size:12px;margin-top:24px">Consenso Plus · AI Business Operating System</p>
  </div>
</body></html>
""".strip()
