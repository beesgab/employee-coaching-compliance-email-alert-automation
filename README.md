# Coaching Compliance

Automated weekly coaching compliance report generator for a coaching team.

## Overview

This project builds and sends a weekly coaching compliance email using Airtable data and a local coaching report CSV file. It formats an HTML report table and sends it through Gmail SMTP.

## Files

- `main.py` - Primary script that loads environment variables, fetches Airtable records, builds the coaching report, and sends HTML email notifications.
- `test.py` - Simple SMTP email test script using Gmail credentials from environment variables.
- `coaching_report.csv` - CSV file attached to the email when `main.py` is run with attachment enabled.
- `rate_limiter/python/package_throttler.py` - Local rate limiting helper used when calling the Airtable API.
- `requirements.txt` - Python dependency list required for this project.

## Requirements

- Python 3.11+ (or compatible)
- The dependencies in `requirements.txt`

Install dependencies with:

```powershell
python -m pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file at the project root with the following values:

```env
AIRTABLE_API_KEY=your_airtable_api_key
EMAIL_FROM_NAME=Your Name
EMAIL_FROM=from@example.com
GMAIL_ADDRESS=your_gmail_address@gmail.com
GMAIL_APP_PASSWORD=your_gmail_app_password
```

## Usage

Run the main script directly:

```powershell
python main.py
```

If you want to test Gmail SMTP connectivity separately, run:

```powershell
python test.py
```

## Notes

- `main.py` uses `pyairtable` to fetch records from Airtable and `emails` to build and send HTML email messages.
- The rate limiter is configured in `rate_limiter/python/package_throttler.py` and used to throttle Airtable API requests.
- The CSV attachment is read from `coaching_report.csv` and is attached when `attachment=True` is passed to `send_email`.

## License

No license is specified. Update this README if you add licensing information.
