import json
import unittest

from lambda_function import handler


class LambdaHandlerTests(unittest.TestCase):
    def test_processes_document_request(self):
        response = handler(
            {
                "httpMethod": "POST",
                "body": json.dumps({"fileName": "notes.md", "content": "# Hi"}),
            },
            None,
        )

        self.assertEqual(response["statusCode"], 200)
        result = json.loads(response["body"])
        self.assertEqual(result["format"], "markdown")
        self.assertIn("<h1>Hi</h1>", result["previewHtml"])

    def test_rejects_unsupported_document_type(self):
        response = handler(
            {
                "httpMethod": "POST",
                "body": json.dumps({"fileName": "archive.zip", "content": "data"}),
            },
            None,
        )

        self.assertEqual(response["statusCode"], 415)
        self.assertEqual(json.loads(response["body"])["error"], "Unsupported document type.")


if __name__ == "__main__":
    unittest.main()