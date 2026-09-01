import os
import smtplib

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")


def send_email(to_email, subject, message):

    try:

        if not SMTP_EMAIL or not SMTP_PASSWORD:

            print("Email configuration is missing.")

            return False


        msg = MIMEMultipart()

        msg["From"] = f"CivicFlow AI <{SMTP_EMAIL}>"

        msg["To"] = to_email

        msg["Subject"] = subject


        html_message = f"""
        <html>

        <body style="
            font-family: Arial, sans-serif;
            background-color: #f4f7fc;
            padding: 30px;
        ">

            <div style="
                max-width: 600px;
                margin: auto;
                background: white;
                padding: 30px;
                border-radius: 12px;
            ">

                <h2 style="color: #2563eb;">
                    CivicFlow AI
                </h2>

                <hr>

                {message}

                <br><br>

                <p style="color: #64748b;">
                    This is an automated notification from CivicFlow AI.
                </p>

            </div>

        </body>

        </html>
        """


        msg.attach(
            MIMEText(html_message, "html")
        )


        server = smtplib.SMTP(
            "smtp.gmail.com",
            587
        )


        server.starttls()


        server.login(
            SMTP_EMAIL,
            SMTP_PASSWORD
        )


        server.sendmail(
            SMTP_EMAIL,
            to_email,
            msg.as_string()
        )


        server.quit()


        print(f"Email sent successfully to {to_email}")

        return True


    except Exception as e:

        print("Email sending error:", str(e))

        return False