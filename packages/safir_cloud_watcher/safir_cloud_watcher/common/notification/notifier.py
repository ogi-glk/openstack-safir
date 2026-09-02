import logging
import smtplib
import socket
from os.path import basename
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jinja2 import Environment, FileSystemLoader
from datetime import datetime
import os
import re

from oslo_config import cfg


LOG = logging.getLogger(__name__)


notifier_opts = [
    cfg.StrOpt('smtp_host',
               default='',
               help="""
SMTP Host

SMTP Server host which will be used to send notification e-mails.
"""),
    cfg.StrOpt('smtp_port',
               default='',
               help="""
E-mail Host Port number
"""),
    cfg.StrOpt('sender_address',
               default='',
               help="""
Notification e-mail sender address
"""),
    cfg.StrOpt('sender_password',
               default='',
               help="""
Notification e-mail sender password
"""),
    cfg.BoolOpt('use_tls',
               default='True',
               help="""
Use TLS protocol if True.

Possible values:

* True, False
"""),
]


CONF = cfg.CONF
CONF.register_opts(notifier_opts, 'notifier')


PATH = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_ENVIRONMENT = Environment(
    autoescape=False,
    loader=FileSystemLoader(os.path.join(
        PATH,
        './templates')),
    trim_blocks=False)

def is_valid_email(email):
    if email is not None and len(email) > 7:
        if re.match('^[_a-z0-9-]+(\.[_a-z0-9-]+)*@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,4})$', email) is not None:
            return True
    return False


class Notifier:
    def __init__(self):
        self.smtp_host = CONF.notifier.smtp_host
        self.smtp_port = CONF.notifier.smtp_port
        self.login_addr = CONF.notifier.sender_address
        self.password = CONF.notifier.sender_password
        self.mailserver = None

    def connect(self):
        if self.smtp_host is None or self.smtp_port is None or \
                self.login_addr is None or self.password is None:
            return False

        try:
            self.mailserver = smtplib.SMTP(self.smtp_host, self.smtp_port)
            # identify ourselves to smtp client
            self.mailserver.ehlo()
            if CONF.notifier.use_tls:
                # secure our email with tls encryption
                self.mailserver.starttls()
            # re-identify ourselves as an encrypted connection
            self.mailserver.ehlo()
            self.mailserver.login(self.login_addr, self.password)
        except TimeoutError as e:
            LOG.error("Could not connect to SMTP server. Will not send "
                      "Emails.")
            self.mailserver = None
            return False
        except socket.error as e:
            LOG.error("Could not connect to SMTP server. Will not send "
                      "Emails.")
            self.mailserver = None
            return False
        return True

    def disconnect(self):
        if self.mailserver is not None:
            self.mailserver.quit()

    @staticmethod
    def render_template(filename, context):
        return TEMPLATE_ENVIRONMENT.get_template(
            filename).render(context)

    def get_mail_content(self, template_file, data):
        """
        Prepares Email content
        :param template_file: Email template
        :param data: Args dictionary

        Example usage:
        data = {
            'message': message,
            'link': link,
        }
        :return: subject, text, html
        """
        html = self.render_template(template_file,
                                    data)
        text = data['notification_type']

        return text, html

    def send_mail(self, recipients, subject, text, html,
                  attachment_text=None, attachment_text_name=None,
                  files=None):
        try:
            if self.connect():
                msg = MIMEMultipart('alternative')
                msg['From'] = self.login_addr
                msg['To'] = ", ".join(recipients)
                msg['Subject'] = subject

                textpart = MIMEText(text, 'plain', 'utf-8')
                htmlpart = MIMEText(html, 'html', 'utf-8')

                msg.attach(textpart)
                msg.attach(htmlpart)

                if attachment_text is not None and \
                        attachment_text_name is not None:
                    part = MIMEApplication(
                        attachment_text,
                        Name=attachment_text_name
                    )
                    part['Content-Disposition'] = \
                        'attachment; filename="%s"' % attachment_text_name
                    msg.attach(part)

                for f in files or []:
                    with open(f, "rb") as fil:
                        part = MIMEApplication(
                            fil.read(),
                            Name=basename(f)
                        )
                        part['Content-Disposition'] = \
                            'attachment; filename="%s"' % basename(f)
                        msg.attach(part)

                self.mailserver.sendmail(self.login_addr,
                                         recipients,
                                         msg.as_string())
                self.disconnect()
        except Exception as ex:
            LOG.error('ERROR: Email notification not sent. ' + ex.message)

    def send_notification_mail(self, notification_type, notification_address):
        """Construct e-mail content and send notification e-mail.
        """
        LOG.info('Sending notification email for operation %s.',
                 notification_type)

        if not is_valid_email(notification_address):
            LOG.error("Notification e-mail address is not valid: %s", notification_address)
            return

        now = datetime.now()
        now_str = now.strftime("%d/%m/%Y, %H:%M:%S")
        # Create content for e-mail template parameters

        subject = "[Safir Bulut] Lisans Bildirimi"
        recipients = [notification_address]
        template_file = 'licence_notification.html'
        data = {
            'notification_type': notification_type,
            'notification_time': now_str,
        }
        text, html = self.get_mail_content(template_file, data)
        self.send_mail(recipients, subject, text, html)
