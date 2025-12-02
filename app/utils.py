import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app
import logging

class NotificationService:
    """Service for sending email and SMS notifications"""
    
    def __init__(self):
        # Configuration will be loaded when needed
        self._config_loaded = False
        self._load_config()
    
    def _load_config(self):
        """Load configuration from Flask app context"""
        try:
            self.smtp_server = "smtp.gmail.com" #current_app.config.get('SMTP_SERVER', 'smtp.gmail.com')
            self.smtp_port = 587#current_app.config.get('SMTP_PORT', 587)
            self.smtp_username = "kiutdigitalclubs@gmail.com" #current_app.config.get('SMTP_USERNAME')
            self.smtp_password = "rkxw rvsh waap tuqo" #current_app.config.get('SMTP_PASSWORD')
            self.from_email = "kiutdigitalclubs@gmail.com"#current_app.config.get('FROM_EMAIL', 'noreply@digitalclub.kiut.ac.tz')
            
            # SMS configuration (using Twilio as example)
            self.twilio_account_sid = current_app.config.get('TWILIO_ACCOUNT_SID')
            self.twilio_auth_token = current_app.config.get('TWILIO_AUTH_TOKEN')
            self.twilio_phone_number = current_app.config.get('TWILIO_PHONE_NUMBER')
            
            self._config_loaded = True
        except RuntimeError:
            # Working outside of application context
            self.smtp_server = 'smtp.gmail.com'
            self.smtp_port = 587
            self.smtp_username = None
            self.smtp_password = None
            self.from_email = 'noreply@digitalclub.kiut.ac.tz'
            self.twilio_account_sid = None
            self.twilio_auth_token = None
            self.twilio_phone_number = None
            self._config_loaded = False
    
    def send_email(self, to_email, subject, message, is_html=False):
        """Send email notification"""
        try:
            # Reload config if not loaded or in app context
            if not self._config_loaded:
                self._load_config()
            
            if not self.smtp_username or not self.smtp_password:
                current_app.logger.warning("SMTP credentials not configured. Email not sent.")
                return False
            
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            if is_html:
                msg.attach(MIMEText(message, 'html'))
            else:
                msg.attach(MIMEText(message, 'plain'))
            
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            text = msg.as_string()
            server.sendmail(self.from_email, to_email, text)
            server.quit()
            
            current_app.logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            current_app.logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    def send_sms(self, phone_number, message):
        """Send SMS notification using Twilio"""
        try:
            # Reload config if not loaded or in app context
            if not self._config_loaded:
                self._load_config()
            
            if not all([self.twilio_account_sid, self.twilio_auth_token, self.twilio_phone_number]):
                current_app.logger.warning("Twilio credentials not configured. SMS not sent.")
                return False
            
            # Remove any non-digit characters from phone number
            phone_number = ''.join(filter(str.isdigit, phone_number))
            
            # Add country code if not present (assuming Tanzania +255)
            if not phone_number.startswith('255'):
                phone_number = '255' + phone_number.lstrip('0')
            
            url = f"https://api.twilio.com/2010-04-01/Accounts/{self.twilio_account_sid}/Messages.json"
            
            data = {
                'From': self.twilio_phone_number,
                'To': f'+{phone_number}',
                'Body': message
            }
            
            response = requests.post(url, data=data, auth=(self.twilio_account_sid, self.twilio_auth_token))
            
            if response.status_code == 201:
                current_app.logger.info(f"SMS sent successfully to {phone_number}")
                return True
            else:
                current_app.logger.error(f"Failed to send SMS to {phone_number}: {response.text}")
                return False
                
        except Exception as e:
            current_app.logger.error(f"Failed to send SMS to {phone_number}: {str(e)}")
            return False
    
    def send_rsvp_notification(self, rsvp, status):
        """Send RSVP status notification via email and SMS"""
        try:
            if status == 'approved':
                subject = f"RSVP Approved - {rsvp.event.title}"
                email_message = f"""
Dear {rsvp.full_name},

Your RSVP for "{rsvp.event.title}" has been approved!

Event Details:
- Date: {rsvp.event.event_date.strftime('%B %d, %Y at %I:%M %p')}
- Location: {rsvp.event.location or 'TBA'}

Your Acceptance Code: {rsvp.acceptance_code}

Please bring this code with you to the event for verification.

Best regards,
Digital Club Team
                """
                
                sms_message = f"RSVP Approved! Event: {rsvp.event.title} on {rsvp.event.event_date.strftime('%B %d, %Y')}. Your code: {rsvp.acceptance_code}. Bring this code to the event."
                
            else:  # rejected
                subject = f"RSVP Update - {rsvp.event.title}"
                email_message = f"""
Dear {rsvp.full_name},

Thank you for your interest in "{rsvp.event.title}".

Unfortunately, we are unable to accommodate your RSVP at this time due to capacity limitations.

We appreciate your understanding and hope to see you at future events.

Best regards,
Digital Club Team
                """
                
                sms_message = f"RSVP Update: Unfortunately, we cannot accommodate your RSVP for {rsvp.event.title} due to capacity limitations. We hope to see you at future events!"
            
            # Send email
            email_sent = self.send_email(rsvp.email, subject, email_message)
            
            # Send SMS if phone number is available
            sms_sent = False
            if rsvp.phone:
                sms_sent = self.send_sms(rsvp.phone, sms_message)
            
            return {
                'email_sent': email_sent,
                'sms_sent': sms_sent,
                'email_address': rsvp.email,
                'phone_number': rsvp.phone
            }
            
        except Exception as e:
            current_app.logger.error(f"Failed to send RSVP notification: {str(e)}")
            return {
                'email_sent': False,
                'sms_sent': False,
                'error': str(e)
            }

    def send_user_approval_email(self, user):
        """Notify a user that their account has been approved"""
        try:
            if not user.email:
                current_app.logger.warning("Approved user is missing email address")
                return False
            
            subject = "Your Digital Club account is approved"
            message = f"""
Hello {user.member.full_name if user.member else user.email},

Great news! Your Digital Club account has been approved. You can now log in and explore events, projects, and community resources.

Login email: {user.email}
Dashboard: {current_app.config.get('BASE_URL', 'https://digitalclub.kiut.ac.tz')}/login

If you did not request this approval, please contact the club leadership.

See you inside!
Digital Club Team
            """.strip()
            
            return self.send_email(user.email, subject, message)
        
        except Exception as exc:
            current_app.logger.error(f"Failed to send approval email: {exc}")
            return False

    def send_admin_promotion_email(self, user, promoted_by):
        """Notify a member they have been promoted to admin"""
        try:
            if not user.email:
                current_app.logger.warning("Promoted user is missing email address")
                return False
            
            subject = "You have been promoted to Digital Club admin"
            promoter = promoted_by.member.full_name if promoted_by and promoted_by.member else promoted_by.email if promoted_by else "System"
            message = f"""
Hello {user.member.full_name if user.member else user.email},

Congratulations! You have been granted admin access to the Digital Club platform by {promoter}.

You can now manage members, events, content, and system settings. Please log in and review the admin dashboard to get started.

Dashboard: {current_app.config.get('BASE_URL', 'https://digitalclub.kiut.ac.tz')}/admin

If you believe this was a mistake, contact a super admin immediately.

Thank you for helping lead the community,
Digital Club Team
            """.strip()
            
            return self.send_email(user.email, subject, message)
        
        except Exception as exc:
            current_app.logger.error(f"Failed to send admin promotion email: {exc}")
            return False

# Global notification service instance (will be created when needed)
notification_service = None

def get_notification_service():
    """Get or create notification service instance"""
    global notification_service
    if notification_service is None:
        notification_service = NotificationService()
    return notification_service
