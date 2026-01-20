import smtplib
import socket
import requests
import time
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.message import EmailMessage
from flask import current_app
import logging
from app.sms import send_sms

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
    
    def send_email(self, to_email, subject, message, is_html=False, background=True):
        """Send email notification
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            message: Email message body
            is_html: Whether message is HTML format
            background: If True, send email in background thread (default: True)
        
        Returns:
            If background=True, returns True immediately (email sent asynchronously)
            If background=False, returns True/False based on send result
        """
        if background:
            # Capture app instance from current context before starting thread
            app = None
            try:
                # Try to get the app from current app context
                app = current_app._get_current_object()
            except (RuntimeError, AttributeError):
                # No app context available, will create new one in background thread
                pass
            
            # Send email in background thread to avoid blocking requests
            thread = threading.Thread(
                target=self._send_email_background,
                args=(to_email, subject, message, is_html, app),
                daemon=True  # Daemon thread will not prevent app shutdown
            )
            thread.start()
            return True  # Return immediately, email is being sent in background
        
        # Send email synchronously (original behavior)
        return self._send_email_sync(to_email, subject, message, is_html)
    
    def _send_email_background(self, to_email, subject, message, is_html, app=None):
        """Send email in background thread with app context"""
        # Get the Flask app instance for background thread
        if app is None:
            # If no app instance provided, create a new one
            try:
                from app import create_app
                app = create_app()
            except Exception as e:
                # If we can't create app, log and fail gracefully
                try:
                    logging.error(f"Failed to create app instance for background email: {e}")
                except:
                    pass
                return False
        
        # Run email sending with app context
        try:
            with app.app_context():
                self._send_email_sync(to_email, subject, message, is_html)
        except Exception as e:
            # Log error but don't raise (background thread)
            try:
                logging.error(f"Error sending email in background thread: {e}")
            except:
                pass
            return False
    
    def _send_email_sync(self, to_email, subject, message, is_html):
        """Send email synchronously (internal method)"""
        try:
            # Reload config if not loaded or in app context
            if not self._config_loaded:
                self._load_config()
            
            if not self.smtp_username or not self.smtp_password:
                # Missing credentials – log and fail gracefully
                try:
                    current_app.logger.warning("SMTP credentials not configured. Email not sent.")
                except RuntimeError:
                    # Outside app context – best effort logging
                    logging.warning("SMTP credentials not configured. Email not sent.")
                return False
            
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            if is_html:
                msg.attach(MIMEText(message, 'html'))
            else:
                msg.attach(MIMEText(message, 'plain'))

            # Explicit DNS resolution before SMTP connection
            smtp_host = self.smtp_server
            smtp_ip = None
            try:
                # Resolve hostname to IP address explicitly
                smtp_ip = socket.gethostbyname(self.smtp_server)
                try:
                    current_app.logger.info(f"DNS resolution successful: {self.smtp_server} -> {smtp_ip}")
                except RuntimeError:
                    logging.info(f"DNS resolution successful: {self.smtp_server} -> {smtp_ip}")
            except socket.gaierror as dns_error:
                # DNS resolution failed - this is the actual DNS problem
                error_msg = f"DNS resolution failed for {self.smtp_server}: {dns_error}"
                try:
                    current_app.logger.error(f"Failed to send email to {to_email}: {error_msg}")
                except RuntimeError:
                    logging.error(f"Failed to send email to {to_email}: {error_msg}")
                return False
            except Exception as dns_error:
                # Other DNS-related errors
                error_msg = f"DNS error for {self.smtp_server}: {dns_error}"
                try:
                    current_app.logger.warning(f"DNS resolution issue for {self.smtp_server}, proceeding with hostname: {error_msg}")
                except RuntimeError:
                    logging.warning(f"DNS resolution issue for {self.smtp_server}, proceeding with hostname: {error_msg}")
            
            # Try using IP address directly if DNS resolution succeeded (helps with some network configurations)
            # Note: Using IP may cause TLS certificate validation issues, so we'll fall back to hostname if needed
            use_ip_directly = False
            if smtp_ip:
                try:
                    current_app.logger.info(f"DNS resolved {self.smtp_server} to {smtp_ip}. Will attempt connection with hostname first.")
                except RuntimeError:
                    logging.info(f"DNS resolved {self.smtp_server} to {smtp_ip}. Will attempt connection with hostname first.")
                # Start with hostname (better for TLS), but we can switch to IP if hostname fails
                smtp_host = self.smtp_server

            # Retry mechanism with exponential backoff
            max_retries = 3
            retry_delays = [2, 4]  # 2s, 4s delays
            last_error = None
            connection_timeout = 5  # Reduced timeout for faster failure
            operation_timeout = 10  # Total timeout for SMTP operations
            
            for attempt in range(max_retries):
                server = None
                try:
                    # Use a shorter timeout to prevent worker timeouts
                    # Set socket timeout before creating SMTP connection
                    import socket as socket_module
                    old_timeout = socket_module.getdefaulttimeout()
                    socket_module.setdefaulttimeout(connection_timeout)
                    
                    try:
                        # Use a timeout so Docker/network issues don't hang forever
                        server = smtplib.SMTP(smtp_host, self.smtp_port, timeout=connection_timeout)
                        server.set_debuglevel(0)  # Disable debug output
                        
                        # Set timeout for all operations
                        server.timeout = operation_timeout
                        
                        server.ehlo()
                        server.starttls()
                        server.ehlo()
                        server.login(self.smtp_username, self.smtp_password)
                        
                        text = msg.as_string()
                        email_message = EmailMessage()
                        email_message['From'] = self.from_email
                        email_message['To'] = to_email
                        email_message['Subject'] = subject
                        email_message.set_content(text)
                        server.send_message(email_message)
                        
                        # Success - break out of retry loop
                        break
                    finally:
                        # Restore original socket timeout
                        socket_module.setdefaulttimeout(old_timeout)
                        # Close connection properly
                        if server:
                            try:
                                server.quit()
                            except:
                                try:
                                    server.close()
                                except:
                                    pass
                    
                except socket.gaierror as e:
                    # DNS resolution error during connection
                    error_type = "DNS resolution"
                    last_error = e
                    error_msg = f"{error_type} error connecting to {smtp_host}:{self.smtp_port} - {e}"
                    # Clean up if server was partially created
                    if server:
                        try:
                            server.close()
                        except:
                            pass
                    
                except (socket.timeout, TimeoutError) as e:
                    # Connection timeout
                    error_type = "Connection timeout"
                    last_error = e
                    error_msg = f"{error_type} connecting to {smtp_host}:{self.smtp_port} - {e}"
                    # Clean up if server was partially created
                    if server:
                        try:
                            server.close()
                        except:
                            pass
                    
                except ConnectionRefusedError as e:
                    # Connection refused (port might be blocked)
                    error_type = "Connection refused (port may be blocked)"
                    last_error = e
                    error_msg = f"{error_type} on {smtp_host}:{self.smtp_port} - {e}"
                    # Clean up if server was partially created
                    if server:
                        try:
                            server.close()
                        except:
                            pass
                    
                except OSError as e:
                    # Network errors (including errno -3)
                    # Check for specific errno -3 (EAI_NONAME - Temporary failure in name resolution)
                    if hasattr(e, 'errno') and e.errno == -3:
                        error_type = "DNS resolution failure during SMTP connection (errno -3)"
                        # If we're using hostname and have IP, try IP on next attempt
                        if smtp_ip and smtp_host == self.smtp_server and attempt < max_retries - 1:
                            try:
                                current_app.logger.warning(f"Connection to hostname {self.smtp_server} failed with DNS error (errno -3), will try IP {smtp_ip} on next attempt")
                            except RuntimeError:
                                logging.warning(f"Connection to hostname {self.smtp_server} failed with DNS error (errno -3), will try IP {smtp_ip} on next attempt")
                            smtp_host = smtp_ip  # Switch to IP for next retry
                            error_msg = f"{error_type} on {self.smtp_server}, will retry with IP {smtp_ip}"
                        else:
                            error_msg = f"{error_type} connecting to {smtp_host}:{self.smtp_port} - {e}"
                    else:
                        error_type = "Network/OS error"
                        error_msg = f"{error_type} connecting to {smtp_host}:{self.smtp_port} - {e}"
                    last_error = e
                    
                except smtplib.SMTPAuthenticationError as e:
                    # Authentication error - don't retry
                    error_type = "SMTP authentication"
                    last_error = e
                    error_msg = f"{error_type} error: {e}"
                    # Clean up if server was partially created
                    if server:
                        try:
                            server.close()
                        except:
                            pass
                    try:
                        current_app.logger.error(f"Failed to send email to {to_email}: {error_msg}")
                    except RuntimeError:
                        logging.error(f"Failed to send email to {to_email}: {error_msg}")
                    return False
                    
                except (smtplib.SMTPException, Exception) as e:
                    # Other SMTP errors
                    error_type = "SMTP error"
                    last_error = e
                    error_msg = f"{error_type}: {e}"
                    # Clean up if server was partially created
                    if server:
                        try:
                            server.close()
                        except:
                            pass
                    
                # If we get here, the attempt failed
                if attempt < max_retries - 1:
                    # Wait before retrying (exponential backoff)
                    delay = retry_delays[attempt] if attempt < len(retry_delays) else retry_delays[-1]
                    try:
                        current_app.logger.warning(f"Email send attempt {attempt + 1}/{max_retries} failed: {error_msg}. Retrying in {delay}s...")
                    except RuntimeError:
                        logging.warning(f"Email send attempt {attempt + 1}/{max_retries} failed: {error_msg}. Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    # Last attempt failed
                    try:
                        current_app.logger.error(f"Failed to send email to {to_email} after {max_retries} attempts. Last error: {error_msg}")
                    except RuntimeError:
                        logging.error(f"Failed to send email to {to_email} after {max_retries} attempts. Last error: {error_msg}")
                    return False
            
            # If we get here, email was sent successfully (we broke out of the retry loop)
            try:
                current_app.logger.info(f"Email sent successfully to {to_email}")
            except RuntimeError:
                logging.info(f"Email sent successfully to {to_email}")
            return True

        except Exception as e:
            # Catch-all to ensure no unhandled exceptions escape
            try:
                current_app.logger.error(f"Unexpected error in send_email for {to_email}: {e}")
            except RuntimeError:
                logging.error(f"Unexpected error in send_email for {to_email}: {e}")
            return False
    
    def send_sms(self, phone_number, message):
        """Send SMS notification using Twilio"""
        if phone_number[0] == '0':
            phone_number = '+255' + phone_number[1:]
        elif phone_number[0] == '+':
            phone_number = phone_number[1:]
        try:
           current_app.logger.info(send_sms(phone_number, message))
        except Exception as e:
            print(f"Failed to send SMS to {phone_number}: {str(e)}")
            try:
                current_app.logger.error(f"Failed to send SMS to {phone_number}: {str(e)}")
            except RuntimeError:
                logging.error(f"Failed to send SMS to {phone_number}: {str(e)}")
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
            try:
                current_app.logger.error(f"Failed to send RSVP notification: {str(e)}")
            except RuntimeError:
                logging.error(f"Failed to send RSVP notification: {str(e)}")
            return {
                'email_sent': False,
                'sms_sent': False,
                'error': str(e)
            }

    def send_user_approval_email(self, user):
        """Notify a user that their account has been approved"""
        try:
            if not user.email:
                try:
                    current_app.logger.warning("Approved user is missing email address")
                except RuntimeError:
                    logging.warning("Approved user is missing email address")
                return False
            
            # Get base URL safely
            try:
                base_url = current_app.config.get('BASE_URL', 'https://digitalclub.kiut.ac.tz')
            except RuntimeError:
                base_url = 'https://digitalclub.kiut.ac.tz'
            
            subject = "Your Digital Club account is approved"
            message = f"""
Hello {user.member.full_name if user.member else user.email},

Great news! Your Digital Club account has been approved. You can now log in and explore events, projects, and community resources.

Login email: {user.email}
Dashboard: {base_url}/login

If you did not request this approval, please contact the club leadership.

See you inside!
Digital Club Team
            """.strip()
            
            return self.send_email(user.email, subject, message)
        
        except Exception as exc:
            try:
                current_app.logger.error(f"Failed to send approval email: {exc}")
            except RuntimeError:
                logging.error(f"Failed to send approval email: {exc}")
            return False

    def send_admin_promotion_email(self, user, promoted_by):
        """Notify a member they have been promoted to admin"""
        try:
            if not user.email:
                try:
                    current_app.logger.warning("Promoted user is missing email address")
                except RuntimeError:
                    logging.warning("Promoted user is missing email address")
                return False
            
            # Get base URL safely
            try:
                base_url = current_app.config.get('BASE_URL', 'https://digitalclub.kiut.ac.tz')
            except RuntimeError:
                base_url = 'https://digitalclub.kiut.ac.tz'
            
            subject = "You have been promoted to Digital Club admin"
            promoter = promoted_by.member.full_name if promoted_by and promoted_by.member else promoted_by.email if promoted_by else "System"
            message = f"""
Hello {user.member.full_name if user.member else user.email},

Congratulations! You have been granted admin access to the Digital Club platform by {promoter}.

You can now manage members, events, content, and system settings. Please log in and review the admin dashboard to get started.

Dashboard: {base_url}/admin

If you believe this was a mistake, contact a super admin immediately.

Thank you for helping lead the community,
Digital Club Team
            """.strip()
            
            return self.send_email(user.email, subject, message)
        
        except Exception as exc:
            try:
                current_app.logger.error(f"Failed to send admin promotion email: {exc}")
            except RuntimeError:
                logging.error(f"Failed to send admin promotion email: {exc}")
            return False

# Global notification service instance (will be created when needed)
notification_service = None

def get_notification_service():
    """Get or create notification service instance"""
    global notification_service
    if notification_service is None:
        notification_service = NotificationService()
    return notification_service
