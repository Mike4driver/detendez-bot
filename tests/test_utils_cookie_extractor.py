import os
import time
import pytest

from utils.cookie_extractor import YouTubeCookieExtractor


def test_basic_cookies_file_write_and_cleanup(tmp_path):
    extractor = YouTubeCookieExtractor()
    extractor.cookies_file = str(tmp_path / "youtube_cookies.txt")

    # Simulate writing basic cookies
    basic = extractor._create_basic_cookies()
    with open(extractor.cookies_file, "w", encoding="utf-8") as f:
        f.write("\n".join(basic))

    assert os.path.exists(extractor.cookies_file)
    content = open(extractor.cookies_file, "r", encoding="utf-8").read()
    assert "Netscape HTTP Cookie File" in content
    assert ".youtube.com" in content

    # Make file old and ensure cleanup removes it
    old_mtime = time.time() - 90000  # > 24h? No, set again below to ensure > 24h
    os.utime(extractor.cookies_file, (old_mtime, old_mtime))
    # Force older than 24h
    very_old = time.time() - 90000 - 100000
    os.utime(extractor.cookies_file, (very_old, very_old))

    # Run cleanup
    import asyncio
    asyncio.run(extractor.cleanup_old_cookies())

    assert not os.path.exists(extractor.cookies_file)


