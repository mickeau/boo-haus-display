#!/usr/bin/env python3
"""
Fixture-style tests for the positive news ingestion pipeline.

Run with:
    python3 test_news_pipeline.py
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from bs4 import BeautifulSoup

from date_handler import DateHandler
from digest_detector import DigestDetectorFactory
from digest_parsers import DigestParserFactory
from news_summariser import HeadlineSummarizer, load_articles_from_json
from news_config import SITES_CONFIG
from news_models import extract_display_stories, normalize_story
from news_scraper import CombinedNewsRSSScraper
from screens.news_screen import NewsScreen


class FakeResponse:
    def __init__(self, content, url="https://example.test/"):
        self.content = content.encode("utf-8")
        self.url = url

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, responses):
        self.responses = responses
        self.headers = {}
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=30):
        self.calls.append({
            "url": url,
            "params": params,
            "headers": headers,
            "timeout": timeout,
        })
        return FakeResponse(self.responses[url], url=url)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def test_positive_news_digest_parser():
    url = "https://positive.news/society/good-news-from-week-40-of-2026/"
    html = """
    <html><body>
      <span class="article__date">September 7, 2026</span>
      <div class="half-and-half--item">
        <div class="half-and-half__content">
          <span class="half-and-half__title h5">Cleaner Rivers Return</span>
          <p>Image: River Trust</p>
          <p>Local volunteers restored wetland channels and helped native plants return across the catchment.</p>
          <p>The project is now being copied by schools and community groups nearby.</p>
        </div>
      </div>
      <div class="half-and-half--item">
        <div class="half-and-half__content">
          <span class="half-and-half__title h5">Solar Kitchens Expand</span>
          <p>Community kitchens installed shared solar batteries and cut evening energy costs for families.</p>
        </div>
      </div>
    </body></html>
    """
    parser = DigestParserFactory.create(
        "positive_news",
        FakeSession({url: html}),
        SITES_CONFIG["positive_news"],
        DateHandler(recent_days=30, cleanup_days=30),
    )

    stories = parser.extract_digest_stories(url)

    assert_true(len(stories) == 2, "Positive News digest should split into two stories")
    assert_true(stories[0]["title"] == "Cleaner Rivers Return", "first story title should be extracted")
    assert_true("Image:" not in stories[0]["content"], "image credits should be excluded")
    assert_true(stories[0]["source_type"] == "digest_story", "digest stories should be typed")
    assert_true(stories[0]["digest_url"] == url, "digest URL should be retained")


def test_ogn_digest_detection_and_date():
    url = "https://www.onlygoodnewsdaily.com/post/global-good-news-7-sept-2026"
    detector = DigestDetectorFactory.create(
        "only_good_news_daily",
        SITES_CONFIG["only_good_news_daily"],
    )
    parser = DigestParserFactory.create(
        "only_good_news_daily",
        FakeSession({}),
        SITES_CONFIG["only_good_news_daily"],
        DateHandler(recent_days=30, cleanup_days=30),
    )

    assert_true(detector.is_digest("A neutral RSS title", url), "OGN URL pattern should identify digests")
    assert_true(
        parser.extract_article_date(url).startswith("2026-09-07"),
        "OGN digest date should come from URL",
    )


def test_rss_fallback_parser_and_regular_article_normalization():
    scraper = CombinedNewsRSSScraper()
    rss_url = "https://example.test/feed.xml"
    article_url = "https://example.test/story"
    rss = f"""
    <rss><channel>
      <item>
        <title>Community Garden Opens</title>
        <link>{article_url}</link>
        <pubDate>Mon, 07 Sep 2026 10:04:14 +0000</pubDate>
        <description><![CDATA[<p>Short RSS summary</p>]]></description>
      </item>
    </channel></rss>
    """
    scraper.session = FakeSession({rss_url: rss})

    feed = scraper.fetch_rss_feed_without_feedparser(rss_url)
    entry = feed.entries[0]
    published = scraper.article_scraper.extract_publish_date_from_rss(entry)
    article = scraper.normalize_article({
        "title": entry.title,
        "url": entry.link,
        "content": "  A community garden opened with new accessible plots, shared tools, and produce donations.  " * 3,
        "publish_date": published,
        "source_type": "regular_article",
        "source_site": "positive_news",
    })

    required_fields = {
        "story_id",
        "source_url",
        "url",
        "published_at",
        "publish_date",
        "scraped_at",
        "quality_score",
        "status",
        "source_type",
        "source_site",
        "title",
        "content",
    }
    assert_true(required_fields.issubset(article), "normalized story should include canonical fields")
    assert_true(article["published_at"].startswith("2026-09-07"), "RSS date should be parsed")
    assert_true(article["status"] == "needs_summary", "good article should be ready for summarisation")
    assert_true(article["source_url"] == article_url, "source URL should be canonical")


def test_merge_articles_dedupes_by_story_id():
    scraper = CombinedNewsRSSScraper()
    article = scraper.normalize_article({
        "title": "Reusable Cups Cut Waste",
        "url": "https://example.test/reuse",
        "content": "A reusable cup project cut waste at local events and helped charities save money. " * 4,
        "publish_date": datetime(2026, 9, 7, tzinfo=timezone.utc).isoformat(),
        "source_type": "regular_article",
        "source_site": "positive_news",
    })

    merged = scraper.merge_articles([article], [article.copy()])

    assert_true(len(merged) == 1, "merge should not duplicate an existing story id")


def test_normalization_preserves_ready_status_and_sorts_newest_first():
    scraper = CombinedNewsRSSScraper()
    older = scraper.normalize_article({
        "title": "Older Story",
        "url": "https://example.test/older",
        "content": "An older story has enough useful detail to be displayed by the screen. " * 4,
        "publish_date": datetime(2026, 9, 6, tzinfo=timezone.utc).isoformat(),
        "source_type": "regular_article",
        "source_site": "positive_news",
        "summary": "Older story summary",
        "status": "ready",
    })
    newer = scraper.normalize_article({
        "title": "Newer Story",
        "url": "https://example.test/newer",
        "content": "A newer story has enough useful detail to be displayed by the screen. " * 4,
        "publish_date": datetime(2026, 9, 7, tzinfo=timezone.utc).isoformat(),
        "source_type": "regular_article",
        "source_site": "positive_news",
    })

    merged = scraper.merge_articles([older], [newer])

    assert_true(older["status"] == "ready", "normalization should preserve ready summaries")
    assert_true(merged[0]["title"] == "Newer Story", "merged articles should be newest first")


def test_news_screen_reads_raw_story_database():
    story = {
        "story_id": "story-1",
        "title": "Libraries Launch Tool Share",
        "content": "Libraries launched a useful tool-sharing service for residents. It is already reducing waste.",
        "published_at": datetime.now(timezone.utc).isoformat(),
        "source_site": "positive_news",
        "source_type": "regular_article",
        "status": "needs_summary",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "stories.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"stories": [story]}, f)

        screen = NewsScreen()
        with open(path, "r", encoding="utf-8") as f:
            extracted = screen._extract_stories(json.load(f))
        filtered = screen._filter_recent_stories(extracted)

    assert_true(len(filtered) == 1, "news screen should read raw story database records")
    assert_true(filtered[0]["summary"], "raw story database records should get a fallback summary")


def test_news_rss_fetch_obeys_offline_mode():
    old_offline = os.environ.get("BOO_HAUS_OFFLINE")
    os.environ["BOO_HAUS_OFFLINE"] = "1"

    try:
        scraper = CombinedNewsRSSScraper()
        fake_session = FakeSession({"https://example.test/feed.xml": "<rss></rss>"})
        scraper.session = fake_session

        feed = scraper.fetch_rss_feed("https://example.test/feed.xml")

        assert_true(feed is None, "offline RSS fetch should not return live feed data")
        assert_true(fake_session.calls == [], "offline RSS fetch should not call the session")
    finally:
        if old_offline is None:
            os.environ.pop("BOO_HAUS_OFFLINE", None)
        else:
            os.environ["BOO_HAUS_OFFLINE"] = old_offline


def test_news_model_keeps_summary_only_records_displayable():
    record = normalize_story({
        "title": "Community Repair Cafe Expands",
        "summary": "Volunteers opened more repair sessions after demand increased across town.",
        "publish_date": datetime.now(timezone.utc).isoformat(),
        "source_site": "positive_news",
    })
    stories = extract_display_stories({"stories": [record]})

    assert_true(record["status"] == "ready", "summary-only records should remain displayable")
    assert_true(len(stories) == 1, "display extraction should keep summary-only records")
    assert_true(stories[0]["headline"] == "Community Repair Cafe Expands", "headline should be preserved")


def test_summariser_loads_list_shaped_raw_database():
    story = {
        "title": "Library Bikes Expand",
        "content": "A library bike scheme expanded after a successful pilot.",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "combined_news_recent.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump([story], f)

        loaded = load_articles_from_json(path)

    assert_true(loaded == [story], "summariser should load list-shaped raw story databases")


def test_summariser_cache_validation_and_atomic_output_without_api():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = os.path.join(tmpdir, "cache.json")
        output_file = os.path.join(tmpdir, "news_stories.json")
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"summaries": []}, f)

        summarizer = HeadlineSummarizer.__new__(HeadlineSummarizer)
        summarizer.cache_file = cache_file
        summarizer.cleanup_threshold = datetime.now()
        summarizer.cache_data = summarizer._load_cache()

        assert_true(summarizer.cache_data["summaries"] == {}, "malformed cache summaries should reset cache")

        article = normalize_story({
            "title": "Community Repair Cafe Expands",
            "summary": "Volunteers opened more repair sessions after demand increased across town.",
            "publish_date": datetime.now(timezone.utc).isoformat(),
            "source_site": "positive_news",
        })
        summarizer.save_summaries_json([article], output_file)

        with open(output_file, "r", encoding="utf-8") as f:
            saved = json.load(f)

    assert_true(len(saved["stories"]) == 1, "summariser should write output JSON")
    assert_true(not Path(output_file + ".tmp").exists(), "summariser should not leave temp files")


def main():
    tests = [
        test_positive_news_digest_parser,
        test_ogn_digest_detection_and_date,
        test_rss_fallback_parser_and_regular_article_normalization,
        test_merge_articles_dedupes_by_story_id,
        test_normalization_preserves_ready_status_and_sorts_newest_first,
        test_news_screen_reads_raw_story_database,
        test_news_rss_fetch_obeys_offline_mode,
        test_news_model_keeps_summary_only_records_displayable,
        test_summariser_loads_list_shaped_raw_database,
        test_summariser_cache_validation_and_atomic_output_without_api,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print(f"\nPASS {len(tests)} news pipeline tests")


if __name__ == "__main__":
    main()
