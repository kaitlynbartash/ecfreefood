#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from typing import Iterable
from urllib.parse import urljoin
from urllib.request import Request, urlopen


DEFAULT_EVENTS_URL = "https://emmanuel.campuslabs.com/engage/events"
DEFAULT_KEYWORDS = ("free food", "prize", "prizes")
JSON_LD_EVENT_PATTERN = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class Event:
    title: str
    description: str
    start: datetime
    end: datetime | None
    location: str
    url: str


def fetch_events_page(url: str) -> str:
    request = Request(url, headers={"User-Agent": "ecfreefood/1.0"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    clean = value.strip()
    if clean.endswith("Z"):
        clean = clean[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(clean)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _iter_json_ld_objects(html: str) -> Iterable[dict]:
    for raw_blob in JSON_LD_EVENT_PATTERN.findall(html):
        blob = unescape(raw_blob).strip()
        if not blob:
            continue
        try:
            parsed = json.loads(blob)
        except json.JSONDecodeError:
            continue
        items = parsed if isinstance(parsed, list) else [parsed]
        for item in items:
            if isinstance(item, dict):
                yield item


def parse_events_from_html(html: str, *, page_url: str = DEFAULT_EVENTS_URL) -> list[Event]:
    events: list[Event] = []
    for item in _iter_json_ld_objects(html):
        if item.get("@type") != "Event":
            continue
        title = (item.get("name") or "").strip()
        start = _parse_datetime(item.get("startDate"))
        if not title or not start:
            continue
        end = _parse_datetime(item.get("endDate"))
        description = (item.get("description") or "").strip()
        location_data = item.get("location")
        if isinstance(location_data, dict):
            location = (location_data.get("name") or "").strip()
        else:
            location = str(location_data or "").strip()
        event_url = urljoin(page_url, (item.get("url") or "").strip())
        events.append(
            Event(
                title=title,
                description=description,
                start=start,
                end=end,
                location=location,
                url=event_url,
            )
        )
    return events


def filter_events(events: Iterable[Event], keywords: Iterable[str] = DEFAULT_KEYWORDS) -> list[Event]:
    needles = [keyword.lower() for keyword in keywords if keyword.strip()]
    if not needles:
        return list(events)
    filtered: list[Event] = []
    for event in events:
        haystack = f"{event.title}\n{event.description}".lower()
        if any(needle in haystack for needle in needles):
            filtered.append(event)
    return filtered


def _build_event_id(event: Event) -> str:
    stable = f"{event.url}|{event.start.isoformat()}|{event.title}".encode("utf-8")
    return f"ecfreefood-{hashlib.sha1(stable).hexdigest()[:30]}"


def sync_to_google_calendar(
    events: Iterable[Event],
    *,
    calendar_id: str,
    credentials_path: str,
    dry_run: bool = False,
) -> int:
    selected = list(events)
    if dry_run:
        for event in selected:
            print(f"[DRY RUN] {event.start.isoformat()} - {event.title} ({event.url})")
        return len(selected)

    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    creds = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=["https://www.googleapis.com/auth/calendar"]
    )
    service = build("calendar", "v3", credentials=creds)

    synced = 0
    for event in selected:
        body = {
            "id": _build_event_id(event),
            "summary": event.title,
            "description": f"{event.description}\n\nSource: {event.url}".strip(),
            "location": event.location,
            "start": {"dateTime": event.start.isoformat()},
            "end": {"dateTime": (event.end or event.start).isoformat()},
        }
        try:
            service.events().insert(calendarId=calendar_id, body=body).execute()
        except HttpError as error:
            if getattr(error, "status_code", None) == 409:
                service.events().update(calendarId=calendar_id, eventId=body["id"], body=body).execute()
            else:
                raise
        synced += 1
    return synced


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape Emmanuel Engage events mentioning free food/prizes and sync to Google Calendar."
    )
    parser.add_argument("--events-url", default=DEFAULT_EVENTS_URL)
    parser.add_argument("--calendar-id", required=True)
    parser.add_argument("--credentials", help="Path to service-account credentials JSON")
    parser.add_argument("--keyword", action="append", default=list(DEFAULT_KEYWORDS))
    parser.add_argument("--dry-run", action="store_true", help="Print matching events but skip Calendar writes")
    args = parser.parse_args()

    html = fetch_events_page(args.events_url)
    all_events = parse_events_from_html(html, page_url=args.events_url)
    matches = filter_events(all_events, keywords=args.keyword)

    if not args.dry_run and not args.credentials:
        parser.error("--credentials is required unless --dry-run is set")

    synced_count = sync_to_google_calendar(
        matches,
        calendar_id=args.calendar_id,
        credentials_path=args.credentials or "",
        dry_run=args.dry_run,
    )
    print(f"Found {len(all_events)} total events; synced {synced_count} events matching keywords.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
