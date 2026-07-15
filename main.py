import sys
import os
import json
import ssl
import smtplib
import urllib.request
import urllib.error
from email.message import EmailMessage

try:
    import certifi

    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CONTEXT = None


class NotifyError(Exception):
    pass


def send_slack(title: str, message: str) -> None:
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        raise NotifyError("SLACK_WEBHOOK_URL is not set in the agent's environment.")

    text = f"*{title}*\n{message}" if title else message
    request = urllib.request.Request(
        webhook_url,
        data=json.dumps({"text": text}).encode("utf-8"),
        method="POST",
        headers={"content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, context=_SSL_CONTEXT) as response:
            if response.status >= 300:
                raise NotifyError(f"Slack webhook returned status {response.status}.")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8")
        raise NotifyError(f"Slack webhook error {error.code}: {detail}")
    except urllib.error.URLError as error:
        raise NotifyError(f"Failed to reach Slack webhook: {error.reason}")


def send_email(title: str, message: str, to: str) -> None:
    recipients = [address.strip() for address in to.split(",") if address.strip()]
    if not recipients:
        raise NotifyError("Input 'to' is required when channel is 'email'.")

    host = os.environ.get("SMTP_HOST")
    if not host:
        raise NotifyError("SMTP_HOST is not set in the agent's environment.")
    port = int(os.environ.get("SMTP_PORT") or 587)
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    sender = os.environ.get("SMTP_FROM") or user
    if not sender:
        raise NotifyError(
            "SMTP_FROM (or SMTP_USER) is not set in the agent's environment."
        )

    email = EmailMessage()
    email["Subject"] = title or "Notification"
    email["From"] = sender
    email["To"] = ", ".join(recipients)
    email.set_content(message)

    try:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.starttls(context=_SSL_CONTEXT)
            if user and password:
                smtp.login(user, password)
            smtp.send_message(email)
    except (smtplib.SMTPException, OSError) as error:
        raise NotifyError(f"SMTP delivery failed: {error}")


def main():
    inputs = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}

    message = inputs.get("message")
    if not message:
        print("Input 'message' is required.", file=sys.stderr)
        sys.exit(1)

    title = inputs.get("title") or ""
    channel = (inputs.get("channel") or "slack").lower()

    try:
        if channel == "slack":
            send_slack(title, message)
        elif channel == "email":
            send_email(title, message, inputs.get("to") or "")
        else:
            raise NotifyError(
                f"Unsupported channel '{channel}'. Supported: slack, email."
            )
    except NotifyError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)

    print(f"::ok::{json.dumps(True)}")


if __name__ == "__main__":
    main()
