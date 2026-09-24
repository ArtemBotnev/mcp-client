import unittest
from datetime import datetime, timedelta, timezone

from mcp_client.agent.time_normalization import find_time_interval, with_normalized_time_context


MSK = timezone(timedelta(hours=3))


class TimeNormalizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 9, 24, 15, 30, 45, tzinfo=MSK)

    def test_today_interval_ends_now(self) -> None:
        interval = find_time_interval("Создай отчет за сегодня", now=self.now)

        self.assertIsNotNone(interval)
        self.assertEqual(interval.start_iso, "2026-09-24T00:00:00+03:00")
        self.assertEqual(interval.end_iso, "2026-09-24T15:30:45+03:00")

    def test_yesterday_interval_ends_at_today_start(self) -> None:
        interval = find_time_interval("Нужен отчёт за вчера", now=self.now)

        self.assertIsNotNone(interval)
        self.assertEqual(interval.start_iso, "2026-09-23T00:00:00+03:00")
        self.assertEqual(interval.end_iso, "2026-09-24T00:00:00+03:00")

    def test_day_before_yesterday_does_not_match_yesterday(self) -> None:
        interval = find_time_interval("Нужен отчёт за позавчера", now=self.now)

        self.assertIsNotNone(interval)
        self.assertEqual(interval.start_iso, "2026-09-22T00:00:00+03:00")
        self.assertEqual(interval.end_iso, "2026-09-23T00:00:00+03:00")

    def test_previous_week_uses_calendar_week(self) -> None:
        interval = find_time_interval("Сделай сводку за прошлую неделю", now=self.now)

        self.assertIsNotNone(interval)
        self.assertEqual(interval.start_iso, "2026-09-14T00:00:00+03:00")
        self.assertEqual(interval.end_iso, "2026-09-21T00:00:00+03:00")

    def test_last_week_uses_rolling_seven_days(self) -> None:
        interval = find_time_interval("Сделай отчет за последнюю неделю", now=self.now)

        self.assertIsNotNone(interval)
        self.assertEqual(interval.start_iso, "2026-09-17T15:30:45+03:00")
        self.assertEqual(interval.end_iso, "2026-09-24T15:30:45+03:00")

    def test_last_numbered_month_clamps_day(self) -> None:
        now = datetime(2026, 3, 31, 10, 0, 0, tzinfo=MSK)
        interval = find_time_interval("Построй график за последние 1 месяц", now=now)

        self.assertIsNotNone(interval)
        self.assertEqual(interval.start_iso, "2026-02-28T10:00:00+03:00")
        self.assertEqual(interval.end_iso, "2026-03-31T10:00:00+03:00")

    def test_message_gets_client_context(self) -> None:
        result = with_normalized_time_context("Сохрани отчет за месяц", now=self.now)

        self.assertIn("[Контекст клиента]", result)
        self.assertIn("from=2026-08-24T15:30:45+03:00", result)
        self.assertIn("to=2026-09-24T15:30:45+03:00", result)

    def test_message_without_interval_is_unchanged(self) -> None:
        result = with_normalized_time_context("Какие инструменты доступны?", now=self.now)

        self.assertEqual(result, "Какие инструменты доступны?")


if __name__ == "__main__":
    unittest.main()
