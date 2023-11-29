# Required, IMAP enabled in gmail, also less secure access turned on
# see https://myaccount.google.com/u/3/lesssecureapps
import smtplib
from email.mime.text import MIMEText
from config import get_config

def send_email(subject, body, recipients):
    cfg = get_config()['email'] 
    sender = cfg['username']
    passwd = cfg['password']

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
       smtp_server.login(sender, passwd)
       smtp_server.sendmail(sender, recipients, msg.as_string())
    print("Message sent!")

if __name__ == "__main__":
    subject = "Test Email"
    body = "This is the body of the text message"
    recipients = ["scott@protohaven.org"]
    send_email(subject, body, recipients)
