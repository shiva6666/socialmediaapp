"""
Seed script — populates the database with realistic fake data.

Usage:
    python scripts/seed.py

Make sure your DATABASE_URL in .env points to the Postgres instance
and that you have run `alembic upgrade head` first.
"""

import random
import sys
from pathlib import Path

# Allow running from the project root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from pwdlib import PasswordHash  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models import Comment, Follow, Like, Notification, Post, User  # noqa: E402

password_hash = PasswordHash.recommended()
DEFAULT_PASSWORD = "Password123!"

# ---------------------------------------------------------------------------
# Fake data
# ---------------------------------------------------------------------------

USERS = [
    {"username": "shiva_dev",    "email": "shiva@example.com",   "full_name": "Shiva Kumar"},
    {"username": "priya_photos", "email": "priya@example.com",   "full_name": "Priya Sharma"},
    {"username": "rahul_codes",  "email": "rahul@example.com",   "full_name": "Rahul Verma"},
    {"username": "ananya_art",   "email": "ananya@example.com",  "full_name": "Ananya Iyer"},
    {"username": "karan_travel", "email": "karan@example.com",   "full_name": "Karan Mehta"},
    {"username": "neha_fitness", "email": "neha@example.com",    "full_name": "Neha Gupta"},
    {"username": "arjun_music",  "email": "arjun@example.com",   "full_name": "Arjun Nair"},
    {"username": "divya_food",   "email": "divya@example.com",   "full_name": "Divya Pillai"},
]

POST_BODIES = [
    "Just shipped a new feature! 🚀 The backend is finally talking to the frontend.",
    "Golden hour at Marine Drive. Some places just never get old. 🌅",
    "Three months into learning backend dev. SQLAlchemy is clicking now!",
    "Homemade masala chai on a rainy day ☕ — nothing beats it.",
    "Caught the sunrise at 5 AM. Worth every minute of lost sleep. 🏔️",
    "New personal best at the gym today 💪 Consistency is everything.",
    "Playing around with Redis pub/sub. Async patterns are wild.",
    "Street food tour of Old Delhi done! 10/10 would eat again. 🍛",
    "Finally understood SQLAlchemy relationships. It just clicked!",
    "Late night debugging session. The bug was a missing comma. Classic. 😅",
    "Weekend hike complete. My legs hate me but my soul is happy. 🥾",
    "Just finished a 3-hour jam session. Music is therapy. 🎸",
    "Tried making sourdough for the first time. It... sort of worked? 🍞",
    "REST vs GraphQL debate in the team today. We still haven't decided.",
    "Postman is open. The API is lying to me. Sending thoughts and prayers.",
]

COMMENTS = [
    "This is amazing! 🔥",
    "Great work, keep it up!",
    "Love this so much ❤️",
    "Where is this?? Looks stunning.",
    "How long did this take you?",
    "Same! I felt this deeply 😄",
    "Goals honestly.",
    "Drop the recipe please!",
    "The vibes here are immaculate.",
    "This made my day 😊",
]


def seed() -> None:
    db = SessionLocal()
    try:
        # Guard: don't re-seed if data already exists
        if db.query(User).count() > 0:
            print("⚠️  Database already has users — skipping seed to avoid duplicates.")
            print("    Drop and recreate the DB, then run `alembic upgrade head` to start fresh.")
            return

        print("🌱  Seeding users...")
        hashed_pw = password_hash.hash(DEFAULT_PASSWORD)
        users = [
            User(**u, password_hash=hashed_pw)
            for u in USERS
        ]
        db.add_all(users)
        db.flush()  # get IDs without committing

        print("🌱  Seeding posts...")
        posts = []
        for i, body in enumerate(POST_BODIES):
            author = users[i % len(users)]
            posts.append(Post(body=body, author_id=author.id))
        db.add_all(posts)
        db.flush()

        print("🌱  Seeding follows...")
        follow_pairs: set[tuple[int, int]] = set()
        for user in users:
            # Each user follows 3–5 random others
            others = [u for u in users if u.id != user.id]
            for target in random.sample(others, k=random.randint(3, 5)):
                pair = (user.id, target.id)
                if pair not in follow_pairs:
                    follow_pairs.add(pair)
                    db.add(Follow(follower_id=user.id, following_id=target.id))
                    # Notification for the followed user
                    db.add(Notification(
                        recipient_id=target.id,
                        actor_id=user.id,
                        event_type="follow",
                    ))
        db.flush()

        print("🌱  Seeding likes & comments...")
        for post in posts:
            # Each post gets liked by 2–6 random users
            likers = random.sample(users, k=random.randint(2, 6))
            for liker in likers:
                if liker.id != post.author_id:
                    db.add(Like(post_id=post.id, user_id=liker.id))
                    db.add(Notification(
                        recipient_id=post.author_id,
                        actor_id=liker.id,
                        event_type="like",
                        post_id=post.id,
                    ))

            # Each post gets 1–3 comments
            commenters = random.sample(users, k=random.randint(1, 3))
            for commenter in commenters:
                body = random.choice(COMMENTS)
                db.add(Comment(post_id=post.id, user_id=commenter.id, body=body))
                if commenter.id != post.author_id:
                    db.add(Notification(
                        recipient_id=post.author_id,
                        actor_id=commenter.id,
                        event_type="comment",
                        post_id=post.id,
                    ))

        db.commit()
        print("\n✅  Seed complete!")
        print(f"    👤  {len(users)} users created")
        print(f"    📝  {len(posts)} posts created")
        print(f"    🔗  {len(follow_pairs)} follow relationships")
        print(f"\n    🔑  All accounts use password: {DEFAULT_PASSWORD}")
        print("    📧  Emails: shiva@example.com, priya@example.com, etc.")

    except Exception as e:
        db.rollback()
        print(f"\n❌  Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
