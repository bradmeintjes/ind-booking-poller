import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

class Emailer:

    def __init__(self, server: str, port: int, sender: str, pwd: str):
        self.__smtp_server = server
        self.__smtp_port = port
        self.__sender = sender
        self.__pwd = pwd

    def send(self, to, subject: str, text: str, html=""):
        msg = MIMEMultipart("alternative")
        msg['Subject'] = subject
        msg['From'] = self.__sender
        msg['To'] = to

        msg.attach(MIMEText(text, 'plain'))
        if (html):
            msg.attach(MIMEText(html, 'html'))

        with smtplib.SMTP_SSL(self.__smtp_server, self.__smtp_port) as server:
            server.set_debuglevel(1),
            server.ehlo()
            server.login(self.__sender, self.__pwd)
            server.sendmail(self.__sender, to, msg.as_string())
