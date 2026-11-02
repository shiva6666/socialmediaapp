# Insta Clone API

A modular FastAPI starter for a social app. The first feature is account registration,
login, and retrieval of the authenticated user's profile. Users can also follow accounts,
publish text posts, read a ranked feed, interact with posts, and receive in-app notifications.

## Architecture sketch

![Social media backend architecture](docs/images/social-media-backend-architecture.jpg)

The diagram shows the larger system this project is working toward. The current code is a
single FastAPI application; its features are modules in that app rather than separate services.
For a walkthrough of the current Redis feed cache, notification flow, and backend design
choices, see the [Redis backend learning guide](docs/redis-backend-learning-guide.md) and
its [editable Excalidraw architecture diagram](docs/redis-backend-architecture.excalidraw).
For the request-by-request rate-limit flow, see the
[rate-limiting data-flow diagram](docs/rate-limiting-data-flow.excalidraw).

## Run locally with Docker

```bash
cp -n .env.example .env  # creates .env only if it does not already exist
# Replace SECRET_KEY in .env with a long random value before using real accounts.
docker compose up --build
```

Compose starts PostgreSQL, Redis, pgAdmin, and the FastAPI app. It waits for PostgreSQL and
Redis to become healthy, runs `alembic upgrade head`, then starts the API. Open
`http://127.0.0.1:8000/docs` for the interactive API docs. Uploaded media and database
data are stored in Docker volumes.

Local service addresses:

| Service | Address |
|---|---|
| FastAPI docs | `http://127.0.0.1:8000/docs` |
| pgAdmin | `http://127.0.0.1:5050` |
| PostgreSQL | `localhost:5433` |
| Redis | `localhost:6380` |

Useful commands:

```bash
docker compose logs -f app  # follow API logs
docker compose down         # stop services; preserve data volumes
docker compose down -v      # stop services and delete database, Redis, and media data
```

The Compose file uses development database credentials and a development-only fallback
`SECRET_KEY`. Set a strong `SECRET_KEY` in `.env` before using real accounts; do not use
the default credentials for a public deployment.

### Run the API directly (without Docker)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp -n .env.example .env  # preserve an existing .env file
docker compose up -d db redis
uvicorn app.main:app --reload
```

For this mode, configure `DATABASE_URL` in `.env` with `localhost:5433` and `REDIS_URL`
with `localhost:6380`. Compose publishes its Redis on port 6380 to avoid conflicting with
a Redis server already listening on the default port. Local development creates missing
tables automatically by default.

### Run tests

The test suite uses Python's standard-library `unittest` runner and does not require live
database or Redis services. Run all tests with:

```bash
python -m unittest discover -s tests -v
```

The smoke tests cover application module imports and core behaviors, while
`tests/test_feed_cache.py` covers versioned feed-cache keys and Redis failure handling.

The home feed ranks posts by engagement and recency: likes contribute 2 points each,
comments 3 points each, posts from the last 24 hours get a 10-point bonus, and posts older
than 24 hours but within the last 7 days get a 5-point bonus. These bonuses are not
stacked. Ties are ordered newest first, then by post ID. This is a shared, non-personalized
score; it does not yet use a viewer's interests or analytics events. Redis caches each
user's paginated feed for `FEED_CACHE_TTL_SECONDS` (60 seconds by default). Feed cache keys
include version counters for the viewer's followed authors and follow membership. Author content, profile,
media, like, or comment changes increment that author's counter; follow changes increment
the viewer's membership counter. This avoids deleting cache keys for every follower when an
author changes. Feed reads resolve the followed-author list and fetch its counters in one
Redis `MGET`, shifting work from writes to reads. If Redis is unavailable, the feed falls
back to SQL; if a version increment fails, an old cache entry can remain visible until its
TTL expires.
Notification events are added to a Redis Stream after the API response and persisted by a
background consumer; if Redis is unavailable while enqueueing, the task logs the failure
and attempts to write the notification directly to the database. Configure Redis with
`REDIS_URL`. Stream delivery is at-least-once: the consumer acknowledges events after the
database commit, so an interruption between those steps can result in a duplicate notification.
API requests are rate limited per client IP using Redis: the default is 100 requests per
minute, login is limited to 5 per minute, and registration to 3 per hour. Exceeding a
limit returns HTTP `429`; responses include rate-limit headers. Invalid login and
registration attempts count toward their limits. Configure the limits with
`DEFAULT_RATE_LIMIT`, `LOGIN_RATE_LIMIT`, and `REGISTER_RATE_LIMIT`. Since counters are
stored in Redis, requests fail closed with `503 Service Unavailable` if Redis cannot be
reached.

Feed pages are not deleted when content changes. A changed author or membership version
produces a different cache key, and unused pages expire through the TTL. If Redis cannot
provide version counters, the request skips feed caching and reads from SQL. If Redis loses
its version counters while old feed entries remain, those entries can become addressable
again until they expire.

## API endpoints

- `POST /api/v1/auth/register` — create an account
- `POST /api/v1/auth/login` — exchange email and password for a bearer token
- `GET /api/v1/auth/me` — return the current user's profile (send `Authorization: Bearer <token>`)
- `PATCH /api/v1/users/me` — update your username or display name (authentication required)
- `POST /api/v1/posts` — publish a text post (authentication required)
- `PATCH /api/v1/posts/{post_id}` — edit your post text (authentication required)
- `DELETE /api/v1/posts/{post_id}` — delete your post (authentication required)
- `POST /api/v1/posts/{post_id}/media` — upload an image to your post (authentication required; JPEG, PNG, or WebP, up to 10 MB)
- `DELETE /api/v1/posts/{post_id}/media/{media_id}` — remove an image from your post (authentication required)
- `GET /api/v1/notifications` — list your notifications (authentication required; supports `unread_only`, `limit`, and `offset`)
- `PATCH /api/v1/notifications/{notification_id}/read` — mark one notification as read (authentication required)
- `POST /api/v1/analytics/events` — record an authenticated user event such as `post_viewed`
- `GET /api/v1/posts/feed` — list ranked posts from you and accounts you follow (authentication required)
- `GET /api/v1/posts/users/{username}` — list a user's public posts
- `POST /api/v1/users/{username}/follow` — follow a user (authentication required)
- `DELETE /api/v1/users/{username}/follow` — unfollow a user (authentication required)
- `POST /api/v1/posts/{post_id}/likes` — like a post (authentication required)
- `DELETE /api/v1/posts/{post_id}/likes` — remove your like (authentication required)
- `GET /api/v1/posts/{post_id}/likes/count` — get a post's like count
- `POST /api/v1/posts/{post_id}/comments` — add a comment (authentication required)
- `GET /api/v1/posts/{post_id}/comments` — list a post's comments
- `DELETE /api/v1/posts/{post_id}/comments/{comment_id}` — delete your comment (authentication required)
- `GET /health` — health check

The default database is a local SQLite file. Set `DATABASE_URL` to use PostgreSQL. For
local development, `AUTO_CREATE_TABLES=true` creates missing tables on startup. For a
deployment, set `AUTO_CREATE_TABLES=false` and apply schema changes with Alembic before
starting the app:

```bash
alembic upgrade head
```

When a model changes, create a migration, review the generated file, and then apply it:

```bash
alembic revision --autogenerate -m "describe the schema change"
alembic upgrade head
```

The initial schema migration is already in `alembic/versions/`. Alembic reads
`DATABASE_URL` from the same settings as the app. Uploaded images are stored in `MEDIA_DIR`
(default `uploads/`) and served from `/media/`. Uploads accept JPEG, PNG, and WebP images up
to 10 MB; dimensions are limited to 25 million pixels and animated images are rejected.
Images are normalized before they are written to local storage.
