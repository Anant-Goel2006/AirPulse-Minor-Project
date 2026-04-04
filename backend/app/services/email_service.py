"""
Email Service Module — Professional email sending using Python built-in modules.

Uses:
  - smtplib: SMTP protocol implementation
  - email.mime.text.MIMEText: Plain text & HTML email bodies
  - email.mime.multipart.MIMEMultipart: Multi-part emails
  - ssl: Secure TLS/SSL connections

Configuration: Read from .env
  - SMTP_HOST: SMTP server (e.g., smtp.gmail.com)
  - SMTP_PORT: SMTP port (usually 587 for TLS, 465 for SSL)
  - SMTP_USER: Sender email address
  - SMTP_PASSWORD: SMTP password or app-specific token
  - SMTP_FROM_EMAIL: "From" address for emails
  - SMTP_USE_TLS: Enable TLS encryption (True/False)

Example:
  from backend.app.services.email_service import send_email
  
  result = send_email(
      to_email="recipient@example.com",
      subject="AQI Alert",
      html_body="<h1>Air Quality Has Worsened</h1>...",
      text_body="Air Quality Has Worsened..."
  )
  
  if result['success']:
      print(f"Email sent! Message ID: {result['message_id']}")
  else:
      print(f"Failed: {result['error']}")
"""

import os
import smtplib
import ssl
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from typing import Dict, Optional, List

# Configure logger
logger = logging.getLogger(__name__)


class EmailConfig:
    """Encapsulate SMTP configuration from environment variables."""
    
    def __init__(self):
        self.host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.port = int(os.getenv("SMTP_PORT", 587))
        self.user = os.getenv("SMTP_USER", "").strip()
        self.password = os.getenv("SMTP_PASSWORD", "").strip()
        self.from_email = os.getenv("SMTP_FROM_EMAIL", "").strip()
        self.use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        
    def is_configured(self) -> bool:
        """Check if all required SMTP settings are configured."""
        return bool(self.host and self.user and self.password and self.from_email)
    
    def validate(self) -> tuple[bool, str]:
        """Validate configuration and return (is_valid, error_message)."""
        if not self.host:
            return False, "SMTP_HOST not configured"
        if not self.user:
            return False, "SMTP_USER not configured"
        if not self.password:
            return False, "SMTP_PASSWORD not configured"
        if not self.from_email:
            return False, "SMTP_FROM_EMAIL not configured"
        return True, ""


class SMTPEmailSender:
    """Send emails via SMTP with TLS/SSL support."""
    
    def __init__(self, config: EmailConfig):
        self.config = config
        self.session = None
    
    def connect(self) -> tuple[bool, str]:
        """
        Establish secure SMTP connection.
        Returns: (success, error_message)
        """
        try:
            if self.config.use_tls:
                # TLS: Start with plain connection, then STARTTLS
                context = ssl.create_default_context()
                self.session = smtplib.SMTP(self.config.host, self.config.port, timeout=10)
                self.session.starttls(context=context)
                logger.info(f"Connected to {self.config.host}:{self.config.port} with TLS")
            else:
                # SSL: Secure from the start (port 465 typical)
                context = ssl.create_default_context()
                self.session = smtplib.SMTP_SSL(self.config.host, self.config.port, context=context, timeout=10)
                logger.info(f"Connected to {self.config.host}:{self.config.port} with SSL")
            
            # Authenticate
            self.session.login(self.config.user, self.config.password)
            logger.info(f"Authenticated as {self.config.user}")
            return True, ""
            
        except smtplib.SMTPAuthenticationError as e:
            error = f"SMTP Authentication failed: {str(e)}"
            logger.error(error)
            return False, error
        except smtplib.SMTPException as e:
            error = f"SMTP error: {str(e)}"
            logger.error(error)
            return False, error
        except Exception as e:
            error = f"Connection error: {str(e)}"
            logger.error(error)
            return False, error
    
    def disconnect(self):
        """Safely close SMTP connection."""
        if self.session:
            try:
                self.session.quit()
                logger.info("SMTP connection closed")
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")
                self.session.close()
    
    def send_message(self, message: MIMEMultipart, to_addresses: List[str]) -> tuple[bool, str, Optional[str]]:
        """
        Send a MIME message to recipients.
        
        Args:
            message: MIMEMultipart message object
            to_addresses: List of recipient email addresses
        
        Returns: (success, error_message, message_id)
        """
        try:
            if not self.session:
                return False, "SMTP session not established", None
            
            # Set Message-ID and Date headers
            message['Message-ID'] = f"<{datetime.now().timestamp()}@{self.config.host}>"
            message['Date'] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")
            
            # Send message
            self.session.sendmail(self.config.from_email, to_addresses, message.as_string())
            message_id = message['Message-ID']
            logger.info(f"Email sent to {', '.join(to_addresses)} | Message-ID: {message_id}")
            return True, "", message_id
            
        except smtplib.SMTPRecipientsRefused as e:
            error = f"Recipient rejected: {e.recipients}"
            logger.error(error)
            return False, error, None
        except smtplib.SMTPException as e:
            error = f"SMTP error during send: {str(e)}"
            logger.error(error)
            return False, error, None
        except Exception as e:
            error = f"Error sending email: {str(e)}"
            logger.error(error)
            return False, error, None


def send_email(
    to_email: str,
    subject: str,
    html_body: Optional[str] = None,
    text_body: Optional[str] = None,
    cc_emails: Optional[List[str]] = None,
    bcc_emails: Optional[List[str]] = None,
    reply_to: Optional[str] = None,
    attachments: Optional[List[Dict]] = None,
) -> Dict:
    """
    Send a professional HTML/plain-text email via SMTP.
    
    Args:
        to_email (str): Recipient email address
        subject (str): Email subject line
        html_body (str, optional): HTML email body (default: None)
        text_body (str, optional): Plain text fallback body (default: None)
        cc_emails (list, optional): CC recipients (default: None)
        bcc_emails (list, optional): BCC recipients (default: None)
        reply_to (str, optional): Reply-To header (default: None)
        attachments (list, optional): List of {'filepath': str, 'filename': str}
    
    Returns (dict):
        {
            'success': bool,
            'message': str,
            'message_id': str or None,
            'error': str or None
        }
    
    Example:
        result = send_email(
            to_email="user@example.com",
            subject="Welcome!",
            html_body="<h1>Welcome to AirPulse!</h1>",
            text_body="Welcome to AirPulse!"
        )
    """
    
    # Load configuration
    config = EmailConfig()
    
    # Validate configuration
    is_valid, error_msg = config.validate()
    if not is_valid:
        return {
            'success': False,
            'message': f"Email not sent: {error_msg}",
            'message_id': None,
            'error': error_msg
        }
    
    # Create sender instance
    sender = SMTPEmailSender(config)
    
    try:
        # Connect to SMTP server
        connected, conn_error = sender.connect()
        if not connected:
            return {
                'success': False,
                'message': "Failed to connect to SMTP server",
                'message_id': None,
                'error': conn_error
            }
        
        # Build MIME message
        message = MIMEMultipart("alternative")
        message['Subject'] = subject
        message['From'] = config.from_email
        message['To'] = to_email
        
        if cc_emails:
            message['Cc'] = ", ".join(cc_emails)
        if reply_to:
            message['Reply-To'] = reply_to
        
        # Attach text and HTML parts (MIME best practice: text first, then HTML)
        if text_body:
            message.attach(MIMEText(text_body, "plain", _charset="utf-8"))
        if html_body:
            message.attach(MIMEText(html_body, "html", _charset="utf-8"))
        
        # If no body provided, return error
        if not text_body and not html_body:
            return {
                'success': False,
                'message': "No email body provided",
                'message_id': None,
                'error': "Either text_body or html_body must be provided"
            }
        
        # Attach files if provided
        if attachments:
            for attachment in attachments:
                filepath = attachment.get('filepath')
                filename = attachment.get('filename', os.path.basename(filepath))
                
                try:
                    with open(filepath, 'rb') as attachment_file:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(attachment_file.read())
                        encoders.encode_base64(part)
                        part.add_header('Content-Disposition', f'attachment; filename= {filename}')
                        message.attach(part)
                        logger.info(f"Attached file: {filename}")
                except FileNotFoundError:
                    logger.warning(f"Attachment file not found: {filepath}")
        
        # Prepare recipient list
        recipients = [to_email]
        if cc_emails:
            recipients.extend(cc_emails)
        if bcc_emails:
            recipients.extend(bcc_emails)
        
        # Send email
        success, send_error, message_id = sender.send_message(message, recipients)
        
        if success:
            return {
                'success': True,
                'message': f"Email sent successfully to {to_email}",
                'message_id': message_id,
                'error': None
            }
        else:
            return {
                'success': False,
                'message': "Failed to send email",
                'message_id': None,
                'error': send_error
            }
    
    finally:
        sender.disconnect()


def send_aqi_alert_email(
    to_email: str,
    city: str,
    aqi_value: int,
    aqi_category: str,
    pollutants: Dict = None,
    recommendation: str = None,
) -> Dict:
    """
    Send a specialized AQI alert email.
    
    Args:
        to_email: Recipient email
        city: City name
        aqi_value: Current AQI value (0-500+)
        aqi_category: AQI category (Good, Moderate, Poor, etc.)
        pollutants: Dict of pollutants and levels {'PM2.5': 45.2, ...}
        recommendation: Health recommendation text
    
    Returns: Result dict from send_email()
    """
    
    # Build HTML body with styling
    html_body = f"""
    <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
                .alert-header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
                .alert-body {{ background: #f5f5f5; padding: 20px; border-radius: 0 0 8px 8px; }}
                .value-box {{ background: white; padding: 15px; margin: 10px 0; border-left: 4px solid #667eea; border-radius: 4px; }}
                .pollutants-list {{ margin: 15px 0; }}
                .pollutant-item {{ padding: 8px; background: white; margin: 5px 0; border-radius: 4px; }}
                .recommendation {{ background: #e3f2fd; padding: 15px; border-radius: 4px; margin: 15px 0; color: #1976d2; }}
                .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="alert-header">
                <h1>⚠️ Air Quality Alert for {city}</h1>
            </div>
            <div class="alert-body">
                <div class="value-box">
                    <h2>Current AQI: <strong>{aqi_value}</strong> ({aqi_category})</h2>
                </div>
    """
    
    # Add pollutants section if available
    if pollutants:
        html_body += """
                <div class="pollutants-list">
                    <h3>📊 Pollutant Levels:</h3>
        """
        for pollutant, level in pollutants.items():
            html_body += f'<div class="pollutant-item"><strong>{pollutant}:</strong> {level}</div>\n'
        html_body += '</div>'
    
    # Add recommendation if available
    if recommendation:
        html_body += f'<div class="recommendation">💡 <strong>Recommendation:</strong><br>{recommendation}</div>'
    
    # Add footer
    html_body += """
                <div class="footer">
                    <p>This is an automated alert from AirPulse Air Quality Monitor</p>
                    <p><a href="https://airpulse-minor-project.onrender.com/">View Live Dashboard</a></p>
                </div>
            </div>
        </body>
    </html>
    """
    
    # Plain text fallback
    text_body = f"""
Air Quality Alert for {city}

Current AQI: {aqi_value} ({aqi_category})
    """
    
    if pollutants:
        text_body += "\nPollutant Levels:\n"
        for pollutant, level in pollutants.items():
            text_body += f"  {pollutant}: {level}\n"
    
    if recommendation:
        text_body += f"\nRecommendation:\n{recommendation}\n"
    
    text_body += "\nView the live dashboard: https://airpulse-minor-project.onrender.com/"
    
    # Send email
    return send_email(
        to_email=to_email,
        subject=f"🚨 AQI Alert: {city} - {aqi_category} (AQI {aqi_value})",
        html_body=html_body,
        text_body=text_body
    )


if __name__ == "__main__":
    # Test the email service
    print("Testing AirPulse Email Service...\n")
    
    # Test 1: Check configuration
    config = EmailConfig()
    is_valid, error = config.validate()
    print(f"Configuration Valid: {is_valid}")
    if error:
        print(f"  Error: {error}")
    print()
    
    # Test 2: Send sample email (requires configured SMTP)
    if is_valid:
        print("Sending test email...")
        result = send_email(
            to_email="test@example.com",
            subject="🧪 AirPulse Test Email",
            html_body="<h1>Test Email</h1><p>This is a test email from AirPulse Email Service.</p>",
            text_body="Test email from AirPulse Email Service."
        )
        print(f"Success: {result['success']}")
        print(f"Message: {result['message']}")
        if result['message_id']:
            print(f"Message ID: {result['message_id']}")
