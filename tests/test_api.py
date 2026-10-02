import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app, raise_server_exceptions=False)

    def test_returns_actionable_document_error(self):
        response = self.client.post(
            "/documents/process",
            json={"fileName": "settings.json", "content": "{"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Invalid json document.")
        self.assertEqual(response.json()["code"], "INVALID_REQUEST")

    def test_returns_structured_validation_errors(self):
        response = self.client.post("/utilities/jwt/decode", json={})

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["code"], "VALIDATION_ERROR")
        self.assertEqual(response.json()["details"][0]["field"], "token")

    def test_does_not_expose_unexpected_exception_details(self):
        with self.assertLogs("app", level="ERROR"), patch(
            "app.handler", side_effect=RuntimeError("private failure detail")
        ):
            response = self.client.post(
                "/documents/process",
                json={"fileName": "notes.md", "content": "# Hello"},
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["code"], "INTERNAL_ERROR")
        self.assertNotIn("private failure detail", response.text)

    def test_decodes_jwt_without_claiming_it_is_verified(self):
        response = self.client.post(
            "/utilities/jwt/decode",
            json={"token": "eyJhbGciOiJub25lIn0.eyJzdWIiOiIxMjMifQ."},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["header"], {"alg": "none"})
        self.assertEqual(response.json()["payload"], {"sub": "123"})
        self.assertFalse(response.json()["verified"])

    def test_rejects_invalid_jwt(self):
        response = self.client.post(
            "/utilities/jwt/decode", json={"token": "not-a-jwt"}
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "INVALID_JWT")

    def test_url_base64_round_trips_unicode_text(self):
        original = "Hello, 🌐"
        encoded_response = self.client.post(
            "/utilities/base64/url/encode", json={"text": original}
        )
        self.assertEqual(encoded_response.status_code, 200)

        decoded_response = self.client.post(
            "/utilities/base64/url/decode",
            json={"encoded": encoded_response.json()["encoded"]},
        )

        self.assertEqual(decoded_response.status_code, 200)
        self.assertEqual(decoded_response.json()["decoded"], original)

    def test_rejects_invalid_url_base64(self):
        response = self.client.post(
            "/utilities/base64/url/decode", json={"encoded": "%%%"}
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "INVALID_BASE64")


if __name__ == "__main__":
    unittest.main()