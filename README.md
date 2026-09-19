# ecfreefood

Scrapes Emmanuel College Engage events and syncs events mentioning free food or prizes into a Google Calendar.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Create a Google Cloud service account with Calendar API access.
3. Share your target Google Calendar with the service account email.
4. Save the service account JSON key locally.

## Usage

```bash
python ecfreefood.py \
  --calendar-id your_calendar_id@group.calendar.google.com \
  --credentials /absolute/path/to/service-account.json
```

Use `--dry-run` to preview matched events without writing to Google Calendar.