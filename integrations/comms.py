"""Discord, email, and potentially other communications

Required, IMAP enabled in gmail, also less secure access turned on
see https://myaccount.google.com/u/3/lesssecureapps
"""
import smtplib
from email.mime.text import MIMEText

import requests

from config import get_config

cfg = get_config()["comms"]


def send_email(subject, body, recipients):
    """Sends an email via GMail API"""
    sender = cfg["email_username"]
    passwd = cfg["email_password"]
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp_server:
        smtp_server.login(sender, passwd)
        smtp_server.sendmail(sender, recipients, msg.as_string())


def send_discord_message(content):
    """Sends a message to the techs-live channel"""
    result = requests.post(cfg["techs_live"], json={"content": content}, timeout=5.0)
    result.raise_for_status()


def send_help_wanted(content):
    """Sends a message to the help-wanted channel"""
    result = requests.post(cfg["help_wanted"], json={"content": content}, timeout=5.0)
    result.raise_for_status()


def send_board_message(content):
    """Sends a message to the board-private channel"""
    result = requests.post(cfg["board_private"], json={"content": content}, timeout=5.0)
    result.raise_for_status()
