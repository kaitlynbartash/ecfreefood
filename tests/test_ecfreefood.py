from datetime import datetime, timezone
import unittest

from ecfreefood import filter_events, parse_events_from_html


SAMPLE_HTML = """
<html><head>
<script type="application/ld+json">
[
  {
    "@context": "https://schema.org",
    "@type": "Event",
    "name": "Club Fair",
    "description": "Meet student organizations.",
    "startDate": "2026-09-20T15:00:00-04:00",
    "endDate": "2026-09-20T17:00:00-04:00",
    "location": {"name": "Dining Hall"},
    "url": "/engage/event/111"
  },
  {
    "@context": "https://schema.org",
    "@type": "Event",
    "name": "Game Night",
    "description": "Free food and prizes for attendees.",
    "startDate": "2026-09-21T18:00:00-04:00",
    "location": {"name": "Library"},
    "url": "/engage/event/222"
  }
]
</script>
</head><body></body></html>
"""


class EcFreeFoodTests(unittest.TestCase):
    def test_parse_events_from_json_ld(self):
        events = parse_events_from_html(SAMPLE_HTML)
        self.assertEqual(2, len(events))
        self.assertEqual("Club Fair", events[0].title)
        self.assertEqual("https://emmanuel.campuslabs.com/engage/event/111", events[0].url)

    def test_filter_events_by_food_or_prizes(self):
        events = parse_events_from_html(SAMPLE_HTML)
        matches = filter_events(events)
        self.assertEqual(1, len(matches))
        self.assertEqual("Game Night", matches[0].title)

    def test_parse_naive_datetime_defaults_to_utc(self):
        html = """
        <script type="application/ld+json">
        {"@type":"Event","name":"Prize Wheel","description":"Win a prize!","startDate":"2026-09-22T12:00:00","url":"/engage/event/333"}
        </script>
        """
        events = parse_events_from_html(html)
        self.assertEqual(datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc), events[0].start)


if __name__ == "__main__":
    unittest.main()
