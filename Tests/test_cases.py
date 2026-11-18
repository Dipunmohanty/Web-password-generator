"""Repeatable tests using varied synthetic users and an isolated SQLite database."""

import os
import random
import argparse
import json
import unittest
import traceback
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys
from unittest.mock import patch

from cryptography.fernet import Fernet
import pymysql
from sqlalchemy.engine import make_url


original_database_url = os.environ.get("DATABASE_URL")
os.environ["DATABASE_URL"] = "sqlite://"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import app as backend  # noqa: E402

if original_database_url is not None:
    os.environ["DATABASE_URL"] = original_database_url


SUCCESSFUL_TEST_PASSWORD = "River!Sky6Breeze"


class UserAndPasswordTestCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        backend.app.config.update(TESTING=True)
        cls.random = random.Random(20261118)

    def setUp(self):
        with backend.app.app_context():
            backend.db.drop_all()
            backend.db.create_all()
        os.environ["PASSWORD_FERNET_KEY"] = Fernet.generate_key().decode()
        self.client = backend.app.test_client()
        self.test_user_data = None
        self.test_generated_password = None
        self.test_logs = None

    def make_registration(self, index):
        rng = self.random
        questions = rng.sample(backend.QUESTIONS, 10)
        answers = {
            str(question["id"]): rng.choice(question["options"])
            for question in questions
        }
        birth_date = date(1975, 1, 1) + timedelta(days=rng.randrange(16000))
        names = ["Avery Morgan", "Samira Chen", "Jordan Rivera", "Noah Patel", "Mina Okafor", "Leo Silva"]
        places = ["Osaka", "Lagos", "Toronto", "Reykjavik", "Lima", "Wellington"]
        data = {
            "username": f"test_user_{index}_{rng.randrange(100000)}",
            "password": f"Password{index}!",
            "name": names[index % len(names)],
            "dateOfBirth": birth_date.isoformat(),
            "placeOfBirth": places[index % len(places)],
            "answers": answers,
        }
        self.test_user_data = data
        return data

    def register(self, data):
        return self.client.post("/api/register", json=data)

    def test_registers_varied_users_and_saves_profile_details(self):
        registrations = [self.make_registration(index) for index in range(6)]
        for data in registrations:
            response = self.register(data)
            self.assertEqual(response.status_code, 200, response.get_json())

        with backend.app.app_context():
            profiles = backend.UserProfile.query.order_by(backend.UserProfile.id).all()
            self.assertEqual(len(profiles), len(registrations))
            for profile, data in zip(profiles, registrations):
                self.assertEqual(profile.name, data["name"])
                self.assertEqual(profile.date_of_birth.isoformat(), data["dateOfBirth"])
                self.assertEqual(profile.place_of_birth, data["placeOfBirth"])
                self.assertEqual(profile.answers, data["answers"])
                self.assertIsNotNone(profile.created_at)
            self.assertGreater(len({profile.place_of_birth for profile in profiles}), 1)
            self.assertGreater(len({profile.date_of_birth for profile in profiles}), 1)

    def test_registration_requires_complete_personality_answers(self):
        data = self.make_registration(0)
        data["answers"] = {"1": "Ocean"}
        response = self.register(data)
        self.assertEqual(response.status_code, 400)
        self.assertIn("10 account personality questions", response.get_json()["error"])

    def test_password_generation_uses_and_saves_ai_result(self):
        data = self.make_registration(1)
        self.assertEqual(self.register(data).status_code, 200)
        constraints = {
            "101": "16 characters",
            "102": "Mixed case and digits",
            "103": "Ocean",
            "104": "Short memorable words",
            "105": "Very strong",
            "106": "No preference",
            "107": "A phrase",
            "108": "Calm",
            "109": "Proper capitalization",
            "110": "Common symbols",
        }
        generated = SUCCESSFUL_TEST_PASSWORD
        received = {}

        def fake_generate(profile, received_constraints, password_name):
            received["profile"] = {
                "name": profile.name,
                "date_of_birth": profile.date_of_birth.isoformat(),
                "place_of_birth": profile.place_of_birth,
                "answers": profile.answers,
            }
            received["constraints"] = received_constraints
            received["name"] = password_name
            return generated

        with patch("app.generate_ai_password", side_effect=fake_generate):
            response = self.client.post(
                "/api/generate",
                json={"name": "Travel", "answers": constraints},
            )

        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["password"], generated)
        self.test_generated_password = generated
        self.assertEqual(received["profile"]["name"], data["name"])
        self.assertEqual(received["profile"]["date_of_birth"], data["dateOfBirth"])
        self.assertEqual(received["profile"]["place_of_birth"], data["placeOfBirth"])
        self.assertEqual(received["profile"]["answers"], data["answers"])
        self.assertEqual(received["constraints"], constraints)
        self.assertEqual(received["name"], "Travel")

        saved = self.client.get("/api/passwords").get_json()["passwords"]
        self.assertEqual(saved, [{"name": "Travel", "password": generated}])

    def test_rejects_ai_password_that_violates_requested_length(self):
        data = self.make_registration(2)
        self.assertEqual(self.register(data).status_code, 200)
        constraints = {str(question_id): "test" for question_id in range(101, 111)}
        constraints["101"] = "20 characters"
        constraints["102"] = "Maximum variety"
        with patch("app.generate_ai_password", return_value="River!Sky6Breeze"):
            response = self.client.post(
                "/api/generate",
                json={"name": "Too short", "answers": constraints},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("requested password length", response.get_json()["error"])
        self.test_logs = response.get_json()["error"]

    def test_account_question_pool_has_fifty_unique_questions(self):
        response = self.client.get("/api/questions?kind=account")
        self.assertEqual(response.status_code, 200)
        questions = response.get_json()["questions"]
        self.assertEqual(len(questions), 10)
        self.assertEqual(len({question["id"] for question in questions}), 10)
        self.assertEqual(len(backend.QUESTIONS), 50)

    def test_registration_rejects_invalid_date(self):
        data = self.make_registration(3)
        data["dateOfBirth"] = "not-a-date"
        response = self.register(data)
        self.assertEqual(response.status_code, 400)
        self.test_logs = response.get_json()["error"]

    def test_registration_rejects_duplicate_username(self):
        data = self.make_registration(4)
        self.assertEqual(self.register(data).status_code, 200)
        response = self.register(dict(data, name="Another Person"))
        self.assertEqual(response.status_code, 409)
        self.test_logs = response.get_json()["error"]

    def test_generation_requires_login(self):
        response = self.client.post("/api/generate", json={"name": "Test", "answers": {}})
        self.assertEqual(response.status_code, 401)
        self.test_logs = response.get_json()["error"]

    def test_generation_logs_ai_provider_failure(self):
        data = self.make_registration(5)
        self.assertEqual(self.register(data).status_code, 200)
        constraints = {str(question_id): "test" for question_id in range(101, 111)}
        with patch("app.generate_ai_password", side_effect=RuntimeError("AI provider unavailable")):
            response = self.client.post(
                "/api/generate",
                json={"name": "Provider failure", "answers": constraints},
            )
        self.assertEqual(response.status_code, 503)
        self.test_logs = response.get_json()["error"]

    def test_generation_rejects_empty_ai_response(self):
        data = self.make_registration(6)
        self.assertEqual(self.register(data).status_code, 200)
        constraints = {str(question_id): "test" for question_id in range(101, 111)}
        with patch("app.generate_ai_password", return_value=""):
            response = self.client.post(
                "/api/generate",
                json={"name": "Empty response", "answers": constraints},
            )
        self.assertEqual(response.status_code, 400)
        self.test_logs = response.get_json()["error"]

    def test_generation_rejects_password_missing_required_symbols(self):
        data = self.make_registration(7)
        self.assertEqual(self.register(data).status_code, 200)
        constraints = {
            "101": "16 characters",
            "102": "Mixed case, digits and symbols",
            "103": "Forest",
            "104": "Short memorable words",
            "105": "Very strong",
            "106": "No preference",
            "107": "A phrase",
            "108": "Calm",
            "109": "Proper capitalization",
            "110": "Common symbols",
        }
        with patch("app.generate_ai_password", return_value="RiverSky6Breeze"):
            response = self.client.post(
                "/api/generate",
                json={"name": "Missing symbol", "answers": constraints},
            )
        self.assertEqual(response.status_code, 400)
        self.test_logs = response.get_json()["error"]


def _mysql_connection():
    database_url = os.getenv("TEST_RESULTS_DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "Set TEST_RESULTS_DATABASE_URL to the MySQL database URL before using --persist-results."
        )
    parsed = make_url(database_url)
    if parsed.get_backend_name() != "mysql":
        raise RuntimeError("TEST_RESULTS_DATABASE_URL must point to the MySQL database.")
    return pymysql.connect(
        host=parsed.host or "127.0.0.1",
        port=parsed.port or 3306,
        user=parsed.username,
        password=parsed.password,
        database=parsed.database,
        charset="utf8mb4",
        autocommit=False,
    )


def _create_result_tables(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS test_case_users (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            run_id CHAR(32) NOT NULL,
            username VARCHAR(100) NOT NULL,
            name VARCHAR(120) NOT NULL,
            date_of_birth DATE NOT NULL,
            place_of_birth VARCHAR(160) NOT NULL,
            answers JSON NOT NULL,
            logs LONGTEXT NULL,
            created_at DATETIME NOT NULL,
            UNIQUE KEY uq_test_case_run_username (run_id, username)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS test_case_results (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            test_user_id BIGINT UNSIGNED NOT NULL,
            case_name VARCHAR(160) NOT NULL,
            status VARCHAR(16) NOT NULL,
            generated_password TEXT NULL,
            ai_status VARCHAR(24) NOT NULL,
            failure_log LONGTEXT NULL,
            created_at DATETIME NOT NULL,
            CONSTRAINT fk_test_result_user FOREIGN KEY (test_user_id)
                REFERENCES test_case_users (id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )


def _test_outcomes(result):
    outcomes = {}
    for test, details in result.failures:
        outcomes[test] = ("failed", details)
    for test, details in result.errors:
        outcomes[test] = ("error", details)
    for test, reason in result.skipped:
        outcomes[test] = ("skipped", reason)
    return outcomes


def persist_results(result):
    """Persist synthetic tests into tables isolated from the application tables."""
    run_id = uuid.uuid4().hex
    outcomes = _test_outcomes(result)
    connection = _mysql_connection()
    try:
        with connection.cursor() as cursor:
            _create_result_tables(cursor)
            for index, test in enumerate(result.executed_tests):
                status, traceback_text = outcomes.get(test, ("passed", ""))
                data = getattr(test, "test_user_data", None) or {}
                answers = data.get("answers") or {
                    str(question["id"]): question["options"][0]
                    for question in backend.QUESTIONS[:10]
                }
                username = "case_%s_%02d" % (run_id[:10], index + 1)
                name = data.get("name") or "Synthetic Test User %02d" % (index + 1)
                date_of_birth = data.get("dateOfBirth") or "1990-01-01"
                try:
                    date.fromisoformat(date_of_birth)
                except ValueError:
                    date_of_birth = "1990-01-01"
                place_of_birth = data.get("placeOfBirth") or "Test City"
                test_log = getattr(test, "test_logs", None)
                if traceback_text:
                    test_log = (test_log + "\n" if test_log else "") + traceback_text
                generated_password = getattr(test, "test_generated_password", None)
                ai_status = (
                    "generated" if generated_password else
                    "failed" if test_log and ("AI" in test_log or "password" in test_log.lower()) else
                    "not_requested"
                )
                created_at = datetime.now(timezone.utc).replace(tzinfo=None)
                cursor.execute(
                    """
                    INSERT INTO test_case_users
                        (run_id, username, name, date_of_birth, place_of_birth, answers, logs, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        run_id,
                        username,
                        name,
                        date_of_birth,
                        place_of_birth,
                        json.dumps(answers, ensure_ascii=False),
                        test_log,
                        created_at,
                    ),
                )
                test_user_id = cursor.lastrowid
                cursor.execute(
                    """
                    INSERT INTO test_case_results
                        (test_user_id, case_name, status, generated_password, ai_status, failure_log, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        test_user_id,
                        test.id(),
                        status,
                        generated_password,
                        ai_status,
                        test_log,
                        created_at,
                    ),
                )
        connection.commit()
        return run_id
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--persist-results",
        action="store_true",
        help="Save test users, outcomes, passwords, and failure logs to separate MySQL tables.",
    )
    args = parser.parse_args()

    class RecordingTestResult(unittest.TextTestResult):
        def __init__(self, *result_args, **result_kwargs):
            super().__init__(*result_args, **result_kwargs)
            self.executed_tests = []

        def startTest(self, test):
            self.executed_tests.append(test)
            super().startTest(test)

    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2, resultclass=RecordingTestResult)
    test_result = runner.run(suite)
    if args.persist_results:
        saved_run_id = persist_results(test_result)
        print("Saved test results under run ID %s" % saved_run_id)
    sys.exit(0 if test_result.wasSuccessful() else 1)
