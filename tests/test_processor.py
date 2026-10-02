import unittest

from document_viewer.processor import DocumentError, process_document


class ProcessDocumentTests(unittest.TestCase):
    def test_formats_json_and_creates_escaped_preview(self):
        result = process_document("settings.json", '{"name":"<script>"}')

        self.assertEqual(result["format"], "json")
        self.assertIn('\n  "name": "<script>"', result["formattedContent"])
        self.assertIn("&lt;script&gt;", result["previewHtml"])

    def test_formats_html_and_removes_scripts_from_preview(self):
        result = process_document(
            "page.html", "<h1>Title</h1><script>alert(1)</script><p>Text</p>"
        )

        self.assertIn("<h1>", result["formattedContent"])
        self.assertIn("<h1>", result["previewHtml"])
        self.assertIn("Title", result["previewHtml"])
        self.assertNotIn("<script>", result["previewHtml"])

    def test_formats_xml(self):
        result = process_document("feed.xml", "<feed><item>One</item></feed>")

        self.assertIn("\n  <item>One</item>", result["formattedContent"])
        self.assertIn("&lt;feed&gt;", result["previewHtml"])

    def test_renders_markdown_and_sanitizes_unsafe_links(self):
        result = process_document("notes.md", "# Notes\n\n[bad](javascript:alert(1))")

        self.assertEqual(result["formattedContent"], "# Notes\n\n[bad](javascript:alert(1))")
        self.assertIn("<h1>Notes</h1>", result["previewHtml"])
        self.assertNotIn("javascript:", result["previewHtml"])

    def test_rejects_invalid_json(self):
        with self.assertRaisesRegex(DocumentError, "Invalid json document"):
            process_document("settings.json", "{")

    def test_rejects_unsupported_file_type(self):
        with self.assertRaisesRegex(DocumentError, "Unsupported document type"):
            process_document("archive.zip", "contents")


if __name__ == "__main__":
    unittest.main()