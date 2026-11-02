import importlib
import unittest
from io import BytesIO
from unittest.mock import Mock, patch

from fastapi import BackgroundTasks
from fastapi.exceptions import HTTPException
from PIL import Image
from pydantic import ValidationError

from app.api.routes.interactions import get_post_or_404
from app.api.routes.media import normalize_image
from app.core import database, security
from app.models.analytics_event import AnalyticsEvent
from app.models.media import MediaAsset
from app.schemas.analytics import AnalyticsEventCreate
from app.schemas.auth import RegisterRequest
from app.schemas.user import ProfileUpdate
from app.services.analytics import record_event
from app.services.notifications import queue_notification


class ApplicationSmokeTests(unittest.TestCase):
    def test_application_modules_import(self) -> None:
        modules = [
            "app.main",
            "app.api.router",
            "app.api.routes.analytics",
            "app.api.routes.auth",
            "app.api.routes.follows",
            "app.api.routes.interactions",
            "app.api.routes.media",
            "app.api.routes.notifications",
            "app.api.routes.posts",
            "app.api.routes.profiles",
            "app.core.config",
            "app.core.database",
            "app.core.feed_cache",
            "app.core.rate_limit",
            "app.core.redis",
            "app.core.security",
            "app.dependencies.auth",
            "app.models",
            "app.models.analytics_event",
            "app.models.comment",
            "app.models.follow",
            "app.models.like",
            "app.models.media",
            "app.models.notification",
            "app.models.post",
            "app.models.user",
            "app.schemas.analytics",
            "app.schemas.auth",
            "app.schemas.comment",
            "app.schemas.media",
            "app.schemas.notification",
            "app.schemas.post",
            "app.schemas.user",
            "app.services.analytics",
            "app.services.notification_worker",
            "app.services.notifications",
        ]

        for module in modules:
            with self.subTest(module=module):
                self.assertIsNotNone(importlib.import_module(module))

    def test_database_dependency_closes_session(self) -> None:
        session = Mock()
        with patch.object(database, "SessionLocal", return_value=session):
            dependency = database.get_db()
            self.assertIs(next(dependency), session)
            dependency.close()

        session.close.assert_called_once_with()

    def test_password_and_access_token_round_trip(self) -> None:
        hashed = security.hash_password("correct horse battery staple")

        self.assertTrue(security.verify_password("correct horse battery staple", hashed))
        self.assertFalse(security.verify_password("wrong password", hashed))
        token_payload = security.decode_access_token(security.create_access_token("42"))
        self.assertEqual(token_payload["sub"], "42")

    def test_schemas_validate_and_reject_invalid_input(self) -> None:
        registration = RegisterRequest(
            email="user@example.com", username="user123", password="password123"
        )
        self.assertEqual(registration.username, "user123")
        self.assertEqual(ProfileUpdate(full_name="Updated").full_name, "Updated")

        with self.assertRaises(ValidationError):
            RegisterRequest(email="not-an-email", username="x", password="short")
        with self.assertRaises(ValidationError):
            ProfileUpdate()

    def test_media_asset_builds_public_url(self) -> None:
        media = MediaAsset(file_name="photo.jpg", post_id=1, content_type="image/jpeg")

        self.assertEqual(media.url, "/media/photo.jpg")

    def test_normalize_image_accepts_png_and_rejects_unknown_type(self) -> None:
        image = Image.new("RGB", (2, 2), "red")

        source = BytesIO()
        image.save(source, format="PNG")
        normalized, content_type, extension = normalize_image(source.getvalue(), "image/png")

        self.assertTrue(normalized)
        self.assertEqual((content_type, extension), ("image/png", ".png"))
        with self.assertRaises(HTTPException):
            normalize_image(source.getvalue(), "image/gif")

    def test_interaction_helper_raises_for_missing_post(self) -> None:
        db = Mock()
        db.get.return_value = None

        with self.assertRaises(HTTPException) as error:
            get_post_or_404(99, db)

        self.assertEqual(error.exception.status_code, 404)

    def test_record_event_persists_payload(self) -> None:
        db = Mock()
        payload = AnalyticsEventCreate(event_name="view_post", entity_type="post", entity_id=7)

        event = record_event(db, user_id=3, payload=payload)

        self.assertIsInstance(event, AnalyticsEvent)
        self.assertEqual((event.user_id, event.event_name, event.entity_id), (3, "view_post", 7))
        db.add.assert_called_once_with(event)
        db.commit.assert_called_once_with()
        db.refresh.assert_called_once_with(event)

    def test_queue_notification_skips_self_notifications(self) -> None:
        background_tasks = BackgroundTasks()

        queue_notification(background_tasks, recipient_id=1, actor_id=1, event_type="like")

        self.assertEqual(background_tasks.tasks, [])

    def test_queue_notification_adds_background_task(self) -> None:
        background_tasks = BackgroundTasks()

        queue_notification(
            background_tasks,
            recipient_id=1,
            actor_id=2,
            event_type="comment",
            post_id=9,
        )

        self.assertEqual(len(background_tasks.tasks), 1)
        self.assertEqual(background_tasks.tasks[0].func.__name__, "enqueue_notification")

    @patch("app.services.notification_worker.redis_client.xautoclaim")
    def test_notification_worker_claims_pending_messages(self, xautoclaim: Mock) -> None:
        xautoclaim.return_value = ["0-0", [], []]

        from app.services.notification_worker import claim_pending_notifications

        result = claim_pending_notifications("worker-1")

        self.assertEqual(result, ["0-0", [], []])
        xautoclaim.assert_called_once()


if __name__ == "__main__":
    unittest.main()
