import os
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import main
from app.auth import hash_password
from app.database import get_db
from app.models import Base, User


class AuthenticationAndComplaintFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.session_factory = sessionmaker(
            bind=self.engine, autoflush=False, expire_on_commit=False
        )
        self.engine_patch = patch.object(main, "engine", self.engine)
        self.session_patch = patch.object(main, "SessionLocal", self.session_factory)
        self.engine_patch.start()
        self.session_patch.start()
        self.secret_patch = patch.dict(
            os.environ,
            {"ECOSORT_AUTH_SECRET": "test-only-secret-with-at-least-32-bytes"},
        )
        self.secret_patch.start()

        def override_db():
            with self.session_factory() as db:
                yield db

        main.app.dependency_overrides[get_db] = override_db
        self.client = TestClient(main.app)
        self.client.__enter__()
        self.client_started = True
        self.uploaded_paths: list[Path] = []
        with self.session_factory.begin() as db:
            db.add(
                User(
                    email="authority@example.test",
                    full_name="Test Authority",
                    role="authority",
                    password_hash=hash_password("authority-password-123"),
                )
            )
        image = Image.new("RGB", (128, 128), (89, 145, 92))
        ImageDraw.Draw(image).rectangle((25, 30, 105, 108), fill=(212, 151, 74))
        image_buffer = BytesIO()
        image.save(image_buffer, format="JPEG")
        self.image_bytes = image_buffer.getvalue()

    def tearDown(self) -> None:
        if self.client_started:
            self.client.__exit__(None, None, None)
        main.app.dependency_overrides.clear()
        for image_path in self.uploaded_paths:
            image_path.unlink(missing_ok=True)
        self.secret_patch.stop()
        self.session_patch.stop()
        self.engine_patch.stop()
        self.engine.dispose()

    def register_and_submit(self, client: TestClient, email: str, key: str) -> dict:
        registration = client.post(
            "/api/auth/register",
            json={
                "full_name": email.split("@")[0],
                "email": email,
                "password": "citizen-password-123",
                "role": "authority",
            },
        )
        self.assertEqual(registration.status_code, 201, registration.text)
        self.assertEqual(registration.json()["role"], "citizen")

        response = client.post(
            "/api/reports",
            headers={"Idempotency-Key": key},
            data={
                "description": f"Overflowing waste near {email}",
                "location": "Central Park",
            },
            files={
                "photo": (
                    "report.jpg",
                    self.image_bytes,
                    "image/jpeg",
                )
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.uploaded_paths.append(
            main.BACKEND_DIR / response.json()["photo_path"]
        )
        return response.json()

    def test_citizen_ownership_authority_workflow_and_restart(self) -> None:
        self.assertEqual(self.client.get("/api/complaints").status_code, 401)
        citizen_report = self.register_and_submit(
            self.client, "first@example.test", "first-report-key-01"
        )
        self.assertIn(citizen_report["predicted_category"], {"Wet Waste", "Dry Waste"})
        self.assertIsNotNone(citizen_report["prediction_confidence"])
        self.assertEqual(
            self.client.get("/api/auth/me").json()["email"], "first@example.test"
        )
        self.assertEqual(
            self.client.post(
                "/api/auth/login",
                json={
                    "email": "first@example.test",
                    "password": "citizen-password-123",
                    "role": "authority",
                },
            ).status_code,
            401,
        )
        profile = self.client.put(
            "/api/auth/me",
            json={"full_name": "Updated Citizen", "email": "first@example.test"},
        )
        self.assertEqual(profile.status_code, 200, profile.text)
        self.assertEqual(profile.json()["full_name"], "Updated Citizen")

        second_client = TestClient(main.app)
        second_report = self.register_and_submit(
            second_client, "second@example.test", "second-report-key-01"
        )
        self.assertNotEqual(citizen_report["complaint_id"], second_report["complaint_id"])

        own_complaints = self.client.get("/api/complaints")
        self.assertEqual(own_complaints.status_code, 200, own_complaints.text)
        self.assertEqual(
            [item["id"] for item in own_complaints.json()],
            [citizen_report["complaint_id"]],
        )
        filtered = self.client.get(
            "/api/complaints",
            params={"category": citizen_report["predicted_category"]},
        )
        self.assertEqual(filtered.status_code, 200, filtered.text)
        self.assertEqual(len(filtered.json()), 1)
        other_complaint_id = second_report["complaint_id"]
        self.assertEqual(
            self.client.get(f"/api/complaints/{other_complaint_id}").status_code, 404
        )
        own_photo_name = Path(citizen_report["photo_path"]).name
        other_photo_name = Path(second_report["photo_path"]).name
        self.assertEqual(self.client.get(f"/uploads/{own_photo_name}").status_code, 200)
        self.assertEqual(
            self.client.get(f"/uploads/{other_photo_name}").status_code, 404
        )
        self.assertEqual(
            self.client.put(
                f"/api/complaints/{citizen_report['complaint_id']}/status",
                json={"status": "Assigned"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.put(
                f"/api/complaints/{citizen_report['complaint_id']}/assignment",
                json={"assigned_department": "Unauthorized team"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.put(
                f"/api/complaints/{citizen_report['complaint_id']}/resolve",
                files={
                    "after_cleaning_photo": (
                        "after.jpg",
                        self.image_bytes,
                        "image/jpeg",
                    )
                },
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get("/api/reports").json()[0]["id"], citizen_report["id"]
        )

        authority = TestClient(main.app)
        login = authority.post(
            "/api/auth/login",
            json={
                "email": "authority@example.test",
                "password": "authority-password-123",
                "role": "authority",
            },
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.assertEqual(len(authority.get("/api/complaints").json()), 2)

        complaint_id = citizen_report["complaint_id"]
        assignment = authority.put(
            f"/api/complaints/{complaint_id}/assignment",
            json={"assigned_department": "Sanitation Team Alpha"},
        )
        self.assertEqual(assignment.status_code, 200, assignment.text)
        self.assertEqual(assignment.json()["assigned_department"], "Sanitation Team Alpha")
        self.assertEqual(assignment.json()["status_history"][-1]["event_type"], "assignment")

        for next_status in ("Assigned", "In Progress"):
            updated = authority.put(
                f"/api/complaints/{complaint_id}/status",
                json={"status": next_status, "staff_note": "Work reviewed."},
            )
            self.assertEqual(updated.status_code, 200, updated.text)

        resolved = authority.put(
            f"/api/complaints/{complaint_id}/resolve",
            data={"staff_note": "Cleanup confirmed."},
            files={
                "after_cleaning_photo": (
                    "after.jpg",
                    self.image_bytes,
                    "image/jpeg",
                )
            },
        )
        self.assertEqual(resolved.status_code, 200, resolved.text)
        self.assertEqual(resolved.json()["status"], "Resolved")
        self.uploaded_paths.append(
            main.BACKEND_DIR / resolved.json()["after_cleaning_photo_path"]
        )
        after_photo_name = Path(resolved.json()["after_cleaning_photo_path"]).name
        self.assertEqual(
            self.client.get(f"/uploads/{after_photo_name}").status_code, 200
        )
        self.assertEqual(
            second_client.get(f"/uploads/{after_photo_name}").status_code, 404
        )
        self.assertEqual(
            resolved.json()["status_history"][-1]["changed_by"], "Test Authority"
        )
        self.assertEqual(authority.post("/api/auth/logout").status_code, 204)
        self.assertEqual(authority.get("/api/complaints").status_code, 401)
        self.assertEqual(self.client.post("/api/auth/logout").status_code, 204)
        self.assertEqual(self.client.get("/api/reports").status_code, 401)

        self.client.__exit__(None, None, None)
        self.client_started = False
        restarted_client = TestClient(main.app)
        with restarted_client:
            auth = restarted_client.post(
                "/api/auth/login",
                json={
                    "email": "authority@example.test",
                    "password": "authority-password-123",
                    "role": "authority",
                },
            )
            self.assertEqual(auth.status_code, 200, auth.text)
            saved = restarted_client.get(f"/api/complaints/{complaint_id}")
            self.assertEqual(saved.status_code, 200, saved.text)
            self.assertTrue(
                (main.BACKEND_DIR / saved.json()["before_cleaning_photo_path"]).exists()
            )
            self.assertTrue(
                (main.BACKEND_DIR / saved.json()["after_cleaning_photo_path"]).exists()
            )
        second_client.close()
        authority.close()


if __name__ == "__main__":
    unittest.main()
