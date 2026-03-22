import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_SERVER = "smtp.mail.ru"
SMTP_PORT = 465
EMAIL_ADDRESS = "no-reply@devoriole.ru"
EMAIL_PASSWORD = os.getenv("SMTP_PASS", "")

def send_password_reset(email: str, login: str, new_password: str) -> None:
    subject = "Сброс пароля - Точка входа"
    body = f"""
    <!doctype html>
    <html>
      <head>
        <meta charset='utf-8'>
        <style amp4email-boilerplate>body{{visibility:hidden}}</style>
        <style>
          body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background-color: #f3eeff;
            margin: 0;
            padding: 0;
            color: #1a0d2e;
          }}
          .background {{
            width: 100%;
            padding: 40px 16px;
          }}
          .container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: #ffffff;
            padding: 0;
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 8px 32px rgba(113, 0, 254, 0.12);
            text-align: center;
            border: 1px solid rgba(113, 0, 254, 0.08);
          }}
          .brand-bar {{
            height: 6px;
            background-color: #7100FE;
            background-image: linear-gradient(90deg, #7100FE 0%, #FF4F12 100%);
          }}
          .inner {{
            padding: 32px 28px 28px;
          }}
          h1 {{
            font-size: 26px;
            color: #7100FE;
            margin: 0 0 8px;
            font-weight: 700;
          }}
          .subtitle {{
            font-size: 15px;
            color: #FF4F12;
            font-weight: 600;
            margin: 0 0 24px;
            letter-spacing: 0.02em;
          }}
          .code {{
            font-size: 22px;
            font-weight: bold;
            letter-spacing: 2px;
            background-color: #faf7ff;
            background-image: linear-gradient(180deg, #faf7ff 0%, #fff5f0 100%);
            padding: 18px 20px;
            border-radius: 12px;
            display: inline-block;
            margin: 20px 0;
            font-family: ui-monospace, monospace;
            word-break: break-all;
            color: #2d1b4e;
            border: 2px solid #7100FE;
            box-shadow: 0 0 0 3px rgba(255, 79, 18, 0.15);
          }}
          p {{
            font-size: 16px;
            line-height: 1.6;
            color: #3d3550;
            margin: 12px 0;
          }}
          strong {{
            color: #7100FE;
          }}
          .footer {{
            margin-top: 28px;
            padding-top: 20px;
            border-top: 1px solid rgba(113, 0, 254, 0.12);
            font-size: 13px;
            color: #6b6080;
          }}
        </style>
      </head>
      <body>
        <div class="background">
          <div class="container">
            <div class="brand-bar"></div>
            <div class="inner">
              <h1>Новый пароль</h1>
              <p class="subtitle">Точка входа</p>
              <p>Вы запросили сброс пароля. Войдите с логином <strong>{login}</strong> и этим паролем:</p>
              <div class="code">{new_password}</div>
              <p>Смените пароль в личном кабинете после входа, если доступна такая возможность.</p>
              <p class="footer">
                Если это были не вы — срочно сообщите администратору.<br>
                <strong style="color:#7100FE;">Ростелеком</strong>
                <span style="color:#FF4F12;"> · </span>
                <span style="color:#3d3550;">точка входа</span>
              </p>
            </div>
          </div>
        </div>
      </body>
    </html>
    """
    message = MIMEMultipart("related")
    message["From"] = EMAIL_ADDRESS
    message["To"] = email
    message["Subject"] = subject
    html_part = MIMEText(body, "html")
    message.attach(html_part)
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, email, message.as_string())
        print(f"Письмо со сбросом пароля отправлено на {email}")
    except Exception as e:
        print(f"Ошибка отправки письма: {e}")
        raise
