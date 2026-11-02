import unittest
from unittest.mock import Mock, patch

from redis.exceptions import RedisError

from app.core import feed_cache


class FeedCacheTests(unittest.TestCase):
    @patch.object(feed_cache.redis_client, "mget")
    def test_feed_cache_key_sorts_and_deduplicates_authors(self, mget: Mock) -> None:
        mget.return_value = ["4", "9", "2"]

        first_key = feed_cache.feed_cache_key(42, [7, 3, 7], 20, 0)
        second_key = feed_cache.feed_cache_key(42, [3, 7], 20, 0)

        expected_keys = [
            "posts:feed:membership-version:42",
            "posts:feed:author-version:3",
            "posts:feed:author-version:7",
        ]
        mget.assert_any_call(expected_keys)
        self.assertEqual(first_key, second_key)
        self.assertTrue(first_key.startswith("posts:feed:v3:42:20:0:"))

    @patch.object(feed_cache.redis_client, "mget")
    def test_feed_cache_key_changes_when_a_version_changes(self, mget: Mock) -> None:
        mget.side_effect = [["1", "2"], ["1", "3"]]

        first_key = feed_cache.feed_cache_key(42, [7], 20, 0)
        second_key = feed_cache.feed_cache_key(42, [7], 20, 0)

        self.assertNotEqual(first_key, second_key)

    @patch.object(feed_cache.redis_client, "mget", side_effect=RedisError("Redis down"))
    def test_feed_cache_key_skips_caching_when_versions_are_unavailable(
        self, mget: Mock
    ) -> None:
        self.assertIsNone(feed_cache.feed_cache_key(42, [7], 20, 0))
        mget.assert_called_once()

    @patch.object(feed_cache.redis_client, "get")
    def test_get_cached_feed_returns_redis_value(self, get: Mock) -> None:
        get.return_value = '{"posts": []}'

        result = feed_cache.get_cached_feed("feed-key")

        self.assertEqual(result, '{"posts": []}')
        get.assert_called_once_with("feed-key")

    @patch.object(feed_cache.redis_client, "get", side_effect=RedisError("Redis down"))
    def test_get_cached_feed_returns_none_on_redis_error(self, get: Mock) -> None:
        self.assertIsNone(feed_cache.get_cached_feed("feed-key"))
        get.assert_called_once_with("feed-key")

    @patch.object(feed_cache.redis_client, "setex")
    def test_cache_feed_sets_value_with_ttl(self, setex: Mock) -> None:
        feed_cache.cache_feed("feed-key", '{"posts": []}', 60)

        setex.assert_called_once_with("feed-key", 60, '{"posts": []}')

    @patch.object(feed_cache.redis_client, "delete")
    def test_discard_cached_feed_deletes_key(self, delete: Mock) -> None:
        feed_cache.discard_cached_feed("feed-key")

        delete.assert_called_once_with("feed-key")

    @patch.object(feed_cache.redis_client, "incr")
    def test_bump_author_feed_version_increments_author_key(self, incr: Mock) -> None:
        feed_cache.bump_author_feed_version(42)

        incr.assert_called_once_with("posts:feed:author-version:42")

    @patch.object(feed_cache.redis_client, "incr")
    def test_bump_membership_feed_version_increments_membership_key(self, incr: Mock) -> None:
        feed_cache.bump_membership_feed_version(42)

        incr.assert_called_once_with("posts:feed:membership-version:42")

    @patch.object(feed_cache.redis_client, "incr", side_effect=RedisError("Redis down"))
    def test_version_bump_failures_are_non_fatal(self, incr: Mock) -> None:
        feed_cache.bump_author_feed_version(42)
        feed_cache.bump_membership_feed_version(42)

        self.assertEqual(incr.call_count, 2)


if __name__ == "__main__":
    unittest.main()
