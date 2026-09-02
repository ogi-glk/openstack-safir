"""Email gonderim modulu.

HTML body + Excel eki ile rapor maili gonderir.
"""

import email.header
import email.mime.text
import email.utils
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

from oslo_config import cfg
from oslo_log import log as logging

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


def send_report_email(to_addr, subject, html_body, excel_bytes=None, excel_filename="weekly_report.xlsx"):
    """Rapor mailini gonderir.

    Args:
        to_addr: Alici email adresi
        subject: Mail konusu
        html_body: HTML formatinda mail icerigi
        excel_bytes: Excel dosyasi icerigi (bytes)
        excel_filename: Excel dosya adi
    """
    msg = MIMEMultipart('mixed')

    # HTML body
    html_part = email.mime.text.MIMEText(html_body, 'html', 'utf-8')
    msg.attach(html_part)

    # Excel eki
    if excel_bytes:
        excel_part = MIMEApplication(
            excel_bytes,
            _subtype='vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        excel_part.add_header('Content-Disposition', 'attachment', filename=excel_filename)
        msg.attach(excel_part)

    msg['Subject'] = email.header.Header(subject, 'utf-8')
    msg['From'] = CONF.email_notifier.smtp_from
    msg['To'] = to_addr
    msg['Date'] = email.utils.formatdate(localtime=True, usegmt=True)

    # SMTP gonder
    smtp_host_port = CONF.email_notifier.smtp_host
    smtp_user = CONF.email_notifier.smtp_user
    smtp_pass = CONF.email_notifier.smtp_pass

    if ':' in smtp_host_port:
        host, port = smtp_host_port.rsplit(':', 1)
        port = int(port)
    else:
        host = smtp_host_port
        port = 587

    try:
        smtp = smtplib.SMTP(host, port, timeout=30)
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        if smtp_user and smtp_pass:
            smtp.login(smtp_user, smtp_pass)
        smtp.sendmail(CONF.email_notifier.smtp_from, to_addr, msg.as_string())
        smtp.quit()
        LOG.info(f"Report email sent to {to_addr}")
        return True
    except (TimeoutError, ConnectionRefusedError, OSError) as e:
        LOG.error(f"SMTP connection error to {host}:{port}: {e}")
        raise Exception(f"SMTP connection error: Could not connect to {host}:{port} - {e}")
    except smtplib.SMTPAuthenticationError as e:
        LOG.error(f"SMTP authentication failed for {smtp_user}: {e}")
        raise Exception(f"SMTP authentication failed: {e}")
    except Exception as e:
        LOG.error(f"Failed to send report email to {to_addr}: {e}", exc_info=True)
        raise Exception(f"Failed to send email: {e}")
