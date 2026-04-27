import os
import json
import urllib.request
from datetime import date, timedelta
from google.oauth2 import credentials as google_credentials
import google.auth
import gspread

SPREADSHEET_ID = "178QqsiuGulHOEq2wuSIs6efnbyiIqtrFj5qS2vBzU2A"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def get_sheet_data() -> list[dict]:
    """Fetch all rows from the On-Call Schedule sheet using Application Default Credentials."""
    creds, _ = google.auth.default(scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1
    return sheet.get_all_records()


def get_current_monday() -> date:
    today = date.today()
    return today - timedelta(days=today.weekday())


def parse_date(date_str: str) -> date:
    from datetime import datetime
    for fmt in ("%b %d, %Y", "%b %d %Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {date_str!r}")


def find_technicians(records: list[dict], current_monday: date) -> tuple[str, str]:
    previous_monday = current_monday - timedelta(weeks=1)
    outgoing = None
    incoming = None

    for row in records:
        try:
            week_start = parse_date(str(row.get("Week Start", "")))
        except ValueError:
            continue
        if week_start == previous_monday:
            outgoing = row.get("Technician", "").strip()
        if week_start == current_monday:
            incoming = row.get("Technician", "").strip()

    if not outgoing:
        raise ValueError(f"Could not find outgoing technician for week of {previous_monday}")
    if not incoming:
        raise ValueError(f"Could not find incoming technician for week of {current_monday}")

    return outgoing, incoming


def build_message(outgoing: str, incoming: str) -> dict:
    return {
        "text": (
            f":bell: *ON CALL CHANGEOVER REMINDER:*\n"
            f"*{outgoing}* is the outgoing technician and *{incoming}* is to log in as the "
            f"on-call tech for this week. Please confirm on both ends, thank you!"
        )
    }


def send_slack_message(webhook_url: str, message: dict):
    data = json.dumps(message).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as response:
        if response.status != 200:
            raise ValueError(f"Slack returned status {response.status}")


def main():
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        raise EnvironmentError("SLACK_WEBHOOK_URL environment variable is not set.")

    current_monday = get_current_monday()
    print(f"Running for week of {current_monday}")

    records = get_sheet_data()
    outgoing, incoming = find_technicians(records, current_monday)

    print(f"Outgoing: {outgoing}")
    print(f"Incoming: {incoming}")

    message = build_message(outgoing, incoming)
    send_slack_message(webhook_url, message)
    print("Message sent successfully.")


if __name__ == "__main__":
    main()
