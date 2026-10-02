# dev-utils

An AWS Lambda API that formats JSON, HTML, and XML documents and renders Markdown. It returns normalized source plus an HTML preview that is sanitized for display in a React client. Documents are sent in the request body; uploaded files are not stored or hosted.

## API

`POST /documents/process` accepts:

```json
{
	"fileName": "example.json",
	"content": "{\"hello\":\"world\"}",
	"contentType": "application/json"
}
```

`contentType` is optional when the filename has a supported extension. The response includes `fileName`, `format`, `formattedContent`, `previewHtml`, and `characterCount`. Formats are `json`, `html`, `xml`, and `markdown`. HTML and Markdown previews are sanitized; JSON and XML previews display escaped source. Requests are limited to 1 MiB. Unsupported types return HTTP 415, invalid requests or documents return HTTP 400, and oversized requests return HTTP 413.

React clients can display `formattedContent` in a code viewer and use the sanitized `previewHtml` for the preview pane:

```jsx
<article dangerouslySetInnerHTML={{ __html: result.previewHtml }} />
```

## Local development

Requires Python 3.12 or newer.

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

## Deploy with AWS SAM

Requires AWS SAM CLI and configured AWS credentials.

```sh
sam build
sam deploy --guided
```

The template allows any CORS origin by default. Set the `ALLOWED_ORIGIN` Lambda environment variable to the React app's origin before exposing the endpoint publicly.