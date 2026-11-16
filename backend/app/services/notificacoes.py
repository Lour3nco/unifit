"""Envio de e-mail (SMTP) e SMS (Twilio, pela API REST, sem SDK).

Configuração no .env (veja o .env.example). Se um canal não estiver configurado, a mensagem vai para o log
do backend em vez de ser enviada: assim o fluxo funciona em desenvolvimento sem conta de e-mail/SMS.
"""
import base64
import json
import logging
import os
import re
import smtplib
import urllib.parse
import urllib.request
from email.message import EmailMessage

log = logging.getLogger("unifit")

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
SMTP_SSL = os.getenv("SMTP_SSL", "false").lower() == "true"  # true: porta 465 (SSL direto); false: STARTTLS

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM = os.getenv("TWILIO_FROM", "")  # número Twilio no formato +15551234567


def telefone_e164(telefone: str) -> str | None:
    """Telefone brasileiro (com ou sem DDI) no formato +55DDNNNNNNNNN; None se não parecer um celular/fixo."""
    digitos = re.sub(r"\D", "", telefone or "")
    if len(digitos) in (12, 13) and digitos.startswith("55"):
        digitos = digitos[2:]
    if len(digitos) not in (10, 11):
        return None
    return f"+55{digitos}"


def enviar_email(para: str, assunto: str, texto: str) -> None:
    if not SMTP_HOST or (SMTP_USER and not SMTP_PASSWORD):  # usuário sem senha: configuração pela metade
        log.warning("SMTP não configurado; e-mail para %s não enviado:\n%s\n%s", para, assunto, texto)
        return
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = SMTP_FROM, para, assunto
    msg.set_content(texto)
    try:
        servidor = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) if SMTP_SSL else smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
        with servidor:
            if not SMTP_SSL:
                servidor.starttls()
            if SMTP_USER:
                servidor.login(SMTP_USER, SMTP_PASSWORD)
            servidor.send_message(msg)
    except Exception:  # roda em segundo plano: a falha não pode derrubar nada, só fica no log
        log.exception("falha ao enviar e-mail para %s", para)


def enviar_sms(telefone: str, texto: str) -> None:
    numero = telefone_e164(telefone)
    if numero is None:
        log.warning("telefone inválido para SMS: %r", telefone)
        return
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM):
        log.warning("Twilio não configurado; SMS para %s não enviado:\n%s", numero, texto)
        return
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    corpo = urllib.parse.urlencode({"To": numero, "From": TWILIO_FROM, "Body": texto}).encode()
    credenciais = base64.b64encode(f"{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}".encode()).decode()
    pedido = urllib.request.Request(url, data=corpo, headers={"Authorization": f"Basic {credenciais}"})
    try:
        with urllib.request.urlopen(pedido, timeout=15) as resp:
            log.info("SMS enviado para %s (sid %s)", numero, json.load(resp).get("sid"))
    except Exception:
        log.exception("falha ao enviar SMS para %s", numero)
