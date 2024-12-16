# Standard library imports
import os
import json
import datetime
import smtplib
import logging
from email.mime.text import MIMEText

# Third-party imports
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables from .env file if running locally
# GitHub Actions will use repository secrets instead
load_dotenv()

# Verify required environment variables are present
required_env_vars = [
    'GOOGLE_SERVICE_ACCOUNT',
    'SMTP_SERVER',
    'SMTP_PORT',
    'EMAIL_USER',
    'EMAIL_PASSWORD',
    'EMAIL_RECIPIENT',
    'PRIMARY_CALENDAR_ID',
    'SECONDARY_CALENDAR_ID'
]

for var in required_env_vars:
    if var not in os.environ:
        raise EnvironmentError(f"Missing required environment variable: {var}")

# Set up Google Calendar API with read-only scope
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
try:
    SERVICE_ACCOUNT_INFO = json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT'])
    credentials = service_account.Credentials.from_service_account_info(
        SERVICE_ACCOUNT_INFO, scopes=SCOPES)
    service = build('calendar', 'v3', credentials=credentials)
except Exception as e:
    logging.error(f"Failed to initialize Google Calendar API: {e}")
    raise

# Calendar IDs for both accounts to monitor
# These should be replaced with actual calendar IDs from Google Calendar settings
CALENDAR_IDS = [
    os.environ['PRIMARY_CALENDAR_ID'],
    os.environ['SECONDARY_CALENDAR_ID']
]

# Keywords used for matching snowboarding-related events
# Add or modify keywords as needed for better matching
KEYWORDS = ['snowboarding', 'snow', 'board', 'snow trip']

def get_upcoming_snowboarding_weekends():
    """
    Fetch upcoming snowboarding events from specified Google Calendars.
    
    Returns:
        list: List of datetime objects representing snowboarding weekend dates
    """
    weekends = []
    # Get current time in UTC for filtering future events
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    for calendar_id in CALENDAR_IDS:
        try:
            # Fetch next 50 events from each calendar
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=now,
                maxResults=50,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            logging.info(f"Found {len(events)} events in calendar {calendar_id}")
            
            # Filter events based on keywords and weekend dates
            for event in events:
                summary = event.get('summary', '').lower()
                if any(keyword in summary for keyword in KEYWORDS):
                    # Handle both all-day and timed events
                    start = event['start'].get('date') or event['start'].get('dateTime')
                    if start:
                        # Parse different date formats
                        if 'T' in start:  # Timed event
                            start_date = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
                        else:  # All-day event
                            start_date = datetime.datetime.strptime(start, '%Y-%m-%d')
                        
                        if start_date.weekday() in [5, 6]:  # Saturday or Sunday
                            weekends.append(start_date)
                            logging.info(f"Found snowboarding event: {summary} on {start}")
                            
        except Exception as e:
            logging.error(f"Error fetching events from calendar {calendar_id}: {e}")
            
    return weekends

def send_email_reminder():
    """
    Send email reminder about parking for snowboarding weekend.
    Uses SMTP with TLS for secure email transmission.
    """
    try:
        smtp_server = os.environ['SMTP_SERVER']
        smtp_port = int(os.environ['SMTP_PORT'])
        email_user = os.environ['EMAIL_USER']
        email_password = os.environ['EMAIL_PASSWORD']
        recipient = os.environ['EMAIL_RECIPIENT']

        msg = MIMEText('Reminder to get parking for the upcoming snowboarding weekend.')
        msg['Subject'] = 'Snowboarding Parking Reminder'
        msg['From'] = email_user
        msg['To'] = recipient

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()  # Enable TLS encryption
            server.login(email_user, email_password)
            server.send_message(msg)
            logging.info("Reminder email sent successfully")
            
    except Exception as e:
        logging.error(f"Failed to send email reminder: {e}")
        raise

def is_upcoming_weekend(event_date, today):
    """
    Check if the event date is for the upcoming weekend.
    
    Args:
        event_date: datetime object of the event
        today: datetime object of today
    
    Returns:
        bool: True if event is this upcoming weekend
    """
    days_until_event = (event_date.date() - today).days
    return 0 <= days_until_event <= 6  # Within the next week

def main():
    """
    Main function to check for upcoming snowboarding weekends and send reminders.
    Sends reminder if event is this upcoming weekend.
    """
    try:
        weekends = get_upcoming_snowboarding_weekends()
        today = datetime.datetime.now(datetime.timezone.utc).date()
        
        for weekend in weekends:
            if is_upcoming_weekend(weekend, today):
                send_email_reminder()
                
    except Exception as e:
        logging.error(f"Error in main execution: {e}")
        raise

if __name__ == '__main__':
    main()