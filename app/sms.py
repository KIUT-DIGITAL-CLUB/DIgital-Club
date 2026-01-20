import requests
import json
import base64
import os
import dotenv
from flask import current_app

dotenv.load_dotenv()

api_key = os.getenv('BEEM_API_KEY')
secret_key = os.getenv('BEEM_SECRET_KEY')
print(api_key, secret_key)
api_key = '18a71d5ee2a9676e'
secret_key = 'MGU4OGZlYzY4NWNlNTMwNGJlZWM5N2I0ODZlYjE5NTE1ZWY2MDNlMDA1YmNiYjk0MzdkYTk2MTVlOTQ4YzJhNg=='
# Official Beem SMS API endpoint
URL = 'https://apisms.beem.africa/v1/send'

# Replace these with your actual Beem API credentials
content_type = 'application/json'

def send_sms(phone_number, message):
    """
    Sends an SMS using the Beem SMS gateway API v1 with certificate verification enabled.
    """
    response = None  # ensure defined for logging in finally
    print("phone numbers " + phone_number + "And Message " + message)
    payload = {
        "source_addr": "KIUTCLUBS",
        "encoding": 0,
        "schedule_time": "",
        "message": message,
        "recipients": [
            {"recipient_id": "1", "dest_addr": phone_number}
        ]
    }
    # Beem requires HTTP Basic Authentication with api_key:secret_key as the credentials
    auth_value = base64.b64encode(f"{api_key}:{secret_key}".encode("utf-8")).decode("utf-8")
    headers = {
        "Content-Type": content_type,
        "Authorization": f"Basic {auth_value}",
    }
    try:
        response = requests.post(
            url=URL,
            data=json.dumps(payload),
            headers=headers,
            timeout=10  # Reasonable timeout to avoid hanging
        )
        response.raise_for_status()  # Will raise for 4xx/5xx responses
        return response.status_code
    except requests.exceptions.SSLError as ssl_err:
        current_app.logger.error(f"SSL Error: {ssl_err}. Please ensure your system has up-to-date CA certificates.")
        return f"SSL Error: {ssl_err}. Please ensure your system has up-to-date CA certificates."
    except requests.exceptions.RequestException as e:
        return f"Error sending SMS: {e}"
    except Exception as e:
        return f"Error sending SMS: {e}"
    finally:
        # Only log status if a response was obtained
        if response is not None:
            current_app.logger.info("SMS sent successfully: " + str(response.status_code))
            print("SMS sent successfully: " + str(response.status_code))

if __name__ == "__main__":
    print(send_sms("+255749300606", "Message We received a request to reset your password. Use the link below to set a new one: http://digitalclub.kiut.ac.tz/auth/reset-password/eyJ1c2VyX2lkIjo4LCJlbWFpbCI6InNuYXZpZHV4Lm9mZmljaWFsQGdtYWlsLmNvbSJ9.aW6Fkg.9q4VOSCKSitj2AvKaiUduVWwpEE"))