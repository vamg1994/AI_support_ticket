import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

def notify_support_team(ticket):
    """
    Notify the support team about tickets that need human intervention
    """
    try:
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_username = os.getenv("SMTP_USERNAME")
        smtp_password = os.getenv("SMTP_PASSWORD")
        support_email = os.getenv("SUPPORT_EMAIL", "support@example.com")

        message = MIMEMultipart()
        message["From"] = smtp_username
        message["To"] = support_email
        message["Subject"] = f"Support Ticket #{ticket.id} Needs Review"

        body = f"""
        New support ticket requires human review:
        
        Ticket ID: {ticket.id}
        Customer: {ticket.name}
        Email: {ticket.email}
        Category: {ticket.category}
        Description: {ticket.description}
        
        AI Confidence Score: {ticket.confidence_score}
        AI Response: {ticket.ai_response}
        
        Please review and respond to this ticket.
        """

        message.attach(MIMEText(body, "plain"))

        if all([smtp_username, smtp_password]):
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_username, smtp_password)
                server.send_message(message)
                logger.info(f"Notification sent for ticket #{ticket.id}")
        else:
            logger.warning("Email credentials not configured. Skipping notification.")

    except Exception as e:
        logger.error(f"Failed to send notification: {str(e)}")
