#!/usr/bin/env python3
"""
Test script for digest detection
Run this to verify digest detection logic is working correctly
"""

from config import SITES_CONFIG
from digest_detector import DigestDetectorFactory


def test_ogn_digest_detection():
    """Test Only Good News Daily digest detection"""
    print("\n" + "="*60)
    print("Testing OGN Digest Detection")
    print("="*60)
    
    ogn_config = SITES_CONFIG['only_good_news_daily']
    detector = DigestDetectorFactory.create('only_good_news_daily', ogn_config)
    
    # Test cases that SHOULD be detected as digests
    digest_titles = [
        "Today's Good News Monday 30 Sept 2025",
        "Today's Good News Friday 27 September 2025",
        "today's good news tuesday 1 oct 2025",  # lowercase
        "Today's Good News - Wednesday Edition",
        "Today's Good News Saturday Special",
    ]
    
    print("\nThese SHOULD be detected as DIGESTS:")
    all_passed = True
    for title in digest_titles:
        result = detector.is_digest(title)
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: '{title}' → {result}")
        if not result:
            all_passed = False
    
    # Test cases that should NOT be detected as digests
    regular_titles = [
        "5 Inspiring Stories from Monday's Rally",
        "Tuesday's Breakthrough in Cancer Research",
        "Wednesday Market Update",
        "Scientists Make Discovery on Thursday",
        "Friday Feature: Community Heroes",
        "A Beautiful Story About Hope",
        "The Power of Kindness",
        "Good news for renewable energy sector",
    ]
    
    print("\nThese should be REGULAR ARTICLES:")
    for title in regular_titles:
        result = detector.is_digest(title)
        status = "✓ PASS" if not result else "✗ FAIL"
        print(f"  {status}: '{title}' → {result}")
        if result:
            all_passed = False
    
    return all_passed


def test_positive_news_digest_detection():
    """Test Positive News digest detection"""
    print("\n" + "="*60)
    print("Testing Positive News Digest Detection")
    print("="*60)
    
    pn_config = SITES_CONFIG['positive_news']
    detector = DigestDetectorFactory.create('positive_news', pn_config)
    
    # Test cases that SHOULD be detected as digests
    digest_cases = [
        ("What went right this week: the good news that matters", 
         "https://positive.news/good-news-stories-from-week-39-of-2025"),
        ("What went right this week: good news that matters",  # slight variation
         "https://positive.news/society/good-news-from-week-38-of-2025"),
        ("What went right this week the good news",  # missing colon
         "https://positive.news/some-other-path/good-news-from-the-week-40-of-2025"),
        ("Regular Article Title",  # URL match only
         "https://positive.news/good-news-from-week-37-of-2025"),
    ]
    
    print("\nThese SHOULD be detected as DIGESTS:")
    all_passed = True
    for title, url in digest_cases:
        result = detector.is_digest(title, url)
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: '{title}'")
        print(f"         URL: {url}")
        print(f"         Result: {result}\n")
        if not result:
            all_passed = False
    
    # Test cases that should NOT be detected as digests
    regular_cases = [
        ("Scientists Discover New Renewable Energy Source",
         "https://positive.news/environment/renewable-energy-breakthrough"),
        ("Community Comes Together to Build Park",
         "https://positive.news/society/community-park-project"),
        ("Climate Action Success Story",
         "https://positive.news/environment/climate-action-2025"),
        ("Weekly roundup of positive stories",  # Similar but not exact
         "https://positive.news/society/roundup-2025"),
    ]
    
    print("\nThese should be REGULAR ARTICLES:")
    for title, url in regular_cases:
        result = detector.is_digest(title, url)
        status = "✓ PASS" if not result else "✗ FAIL"
        print(f"  {status}: '{title}'")
        print(f"         URL: {url}")
        print(f"         Result: {result}\n")
        if result:
            all_passed = False
    
    return all_passed


def test_edge_cases():
    """Test edge cases and special scenarios"""
    print("\n" + "="*60)
    print("Testing Edge Cases")
    print("="*60)
    
    ogn_config = SITES_CONFIG['only_good_news_daily']
    ogn_detector = DigestDetectorFactory.create('only_good_news_daily', ogn_config)
    
    edge_cases = [
        # Title with day name but not digest format
        ("Monday Morning Motivation", False, "Day name without digest keywords"),
        
        # Title with "good news" but not digest format
        ("Good News for Cancer Patients", False, "Has 'good news' but not digest"),
        
        # Mixed case variations
        ("TODAY'S GOOD NEWS MONDAY", True, "All caps"),
        ("Today's good news sunday", True, "Lowercase day"),
        
        # Extra whitespace
        ("Today's  Good  News   Friday", True, "Extra spaces"),
        
        # Day abbreviation (should not match)
        ("Today's Good News Mon", False, "Day abbreviation"),
    ]
    
    print("\nEdge case tests:")
    all_passed = True
    for title, expected, description in edge_cases:
        result = ogn_detector.is_digest(title)
        status = "✓ PASS" if result == expected else "✗ FAIL"
        print(f"  {status}: {description}")
        print(f"         Title: '{title}'")
        print(f"         Expected: {expected}, Got: {result}\n")
        if result != expected:
            all_passed = False
    
    return all_passed


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print(" DIGEST DETECTION TEST SUITE")
    print("="*70)
    
    results = []
    
    # Run OGN tests
    try:
        ogn_passed = test_ogn_digest_detection()
        results.append(("OGN Detection", ogn_passed))
    except Exception as e:
        print(f"\n✗ OGN tests failed with error: {e}")
        results.append(("OGN Detection", False))
    
    # Run Positive News tests
    try:
        pn_passed = test_positive_news_digest_detection()
        results.append(("Positive News Detection", pn_passed))
    except Exception as e:
        print(f"\n✗ Positive News tests failed with error: {e}")
        results.append(("Positive News Detection", False))
    
    # Run edge case tests
    try:
        edge_passed = test_edge_cases()
        results.append(("Edge Cases", edge_passed))
    except Exception as e:
        print(f"\n✗ Edge case tests failed with error: {e}")
        results.append(("Edge Cases", False))
    
    # Print summary
    print("\n" + "="*70)
    print(" TEST SUMMARY")
    print("="*70)
    
    all_passed = True
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False
    
    print("="*70)
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED! 🎉")
        print("\nDigest detection is working correctly.")
        print("You can now run the main scraper with confidence.\n")
        return 0
    else:
        print("\n⚠️  SOME TESTS FAILED ⚠️")
        print("\nPlease review the failed tests above.")
        print("Check the patterns in config.py and adjust as needed.\n")
        return 1


if __name__ == "__main__":
    exit(main())