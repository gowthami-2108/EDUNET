import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv


# ✅ Load .env file
load_dotenv()


def send_task_email(user_email, df_tasks):
    """
    Sends the user's tasks via email.
    :param user_email: Recipient's email (from login/registration)
    :param df_tasks: Pandas DataFrame of tasks
    """
    sender_email =st.secrets("EDUNET_EMAIL")
    sender_password =st.secrets("EDUNET_EMAIL_PASSWORD")


    if not sender_email or not sender_password:
        raise ValueError("Email sender credentials not set. Set EDUNET_EMAIL and EDUNET_EMAIL_PASSWORD in your .env")


    # Build email
    msg = MIMEMultipart("alternative")
    msg["From"] = sender_email
    msg["To"] = user_email  # 👈 now always the login email
    msg["Subject"] = "Your EDUNET Study Tasks"


    # Plain text version
    text = "Here are your current tasks:\n\n" + df_tasks.to_string(index=False)


    # HTML version (better formatting)
    html = f"""
    <html>
        <body>
            <h2>📚 Your EDUNET Study Tasks</h2>
            {df_tasks.to_html(index=False, border=0)}
            <br>
            <p style="font-size:12px;color:gray;">
                Sent by EDUNET Study Planner
            </p>
        </body>
    </html>
    """


    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))


    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, user_email, msg.as_string())
        print(f"✅ Email sent successfully to {user_email}")
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Authentication failed: {e}. Check if 2FA is enabled and you're using a valid App Password (no spaces).")
        raise
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        raise
