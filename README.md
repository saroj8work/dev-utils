# dev-utils

A FastAPI API for formatting JSON, HTML, and XML documents and rendering Markdown. It returns normalized source plus an HTML preview that is sanitized for display in a React client. Documents are sent in the request body; they are not stored or hosted.

The same FastAPI app runs locally with Uvicorn and on AWS Lambda through Mangum. `lambda_function.py` contains the request validation and document-processing handler used by the FastAPI routes. The SAM template points Lambda at `app.lambda_handler`.

## API

`POST /documents/process` accepts a JSON object:

```json
{
	"fileName": "notes.md",
	"content": "# Hello",
	"contentType": "text/markdown"
}
```

`contentType` is optional when the filename has a supported extension. Supported formats are `json`, `html`, `xml`, and `markdown`. The response includes `fileName`, `format`, `formattedContent`, `previewHtml`, and `characterCount`. HTML and Markdown previews are sanitized; JSON and XML previews display escaped source. Requests are limited to 1 MiB. Unsupported types return HTTP 415, invalid requests or documents return HTTP 400, and oversized requests return HTTP 413.

An example response for the request above:

```json
{
	"fileName": "notes.md",
	"format": "markdown",
	"formattedContent": "# Hello",
	"previewHtml": "<h1>Hello</h1>",
	"characterCount": 7
}
```

React clients can display `formattedContent` in a code viewer and use the sanitized `previewHtml` for the preview pane:

```jsx
<article dangerouslySetInnerHTML={{ __html: result.previewHtml }} />
```

### Utility endpoints

`POST /utilities/jwt/decode` accepts `{"token":"header.payload.signature"}` and returns decoded `header`, `payload`, and `signature` fields. It does not verify the signature or validate claims; the response includes `"verified": false`. Do not use decoded claims for authentication or authorization.

`POST /utilities/base64/url/encode` accepts `{"text":"Hello, 🌐"}` and returns a URL-safe Base64 string in `encoded`. `POST /utilities/base64/url/decode` accepts `{"encoded":"SGVsbG8sIPCfjI0"}` and returns the UTF-8 result in `decoded`. The encoded field may include or omit padding.

### Error responses

Errors are JSON so clients can display the `error` message and optionally branch on the stable `code`. For example, an invalid document returns:

```json
{
	"error": "Invalid json document.",
	"code": "INVALID_REQUEST"
}
```

Request validation errors return HTTP 422 and include per-field `details` with `field`, `message`, and `type`. Malformed JWT and Base64 inputs return HTTP 400 with `INVALID_JWT` or `INVALID_BASE64`. Unexpected server failures return HTTP 500 with `INTERNAL_ERROR`; implementation details are logged on the server and are not exposed to clients.

## Run locally

Requires Python 3.12 or newer and `uv`. From the repository root:

```powershell
uv sync
uv run uvicorn app:app --reload
```

Uvicorn serves the API at `http://127.0.0.1:8000`. Open `http://127.0.0.1:8000/docs` for the interactive FastAPI documentation. This local run does not require Docker or AWS credentials. Stop the server with Ctrl+C.

Additional tools are available through `POST /utilities/jwt/decode`, `POST /utilities/base64/url/encode`, and `POST /utilities/base64/url/decode`. JWT decoding only displays the token's header, payload, and signature segment; it does not verify the signature or validate claims. URL-safe Base64 decoding expects UTF-8 text and accepts input with or without padding.

Errors use JSON with an `error` message and a machine-readable `code`. Request validation errors also include a `details` array containing field names and messages. Unexpected server errors are logged server-side and return a generic message without exposing internal exception details.

In a second PowerShell terminal, send a test request:

```powershell
$body = @{
	fileName = "notes.md"
	content = "# Hello"
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
	-Uri http://127.0.0.1:8000/documents/process `
	-ContentType "application/json" `
	-Body $body
```

Run the automated tests with:

```powershell
uv run python -m unittest discover -s tests -v
```

The same tests cover document errors, validation responses, JWT decoding, URL-safe Base64 round trips, and invalid utility inputs.

Uvicorn is a development dependency. `uv sync` installs it locally; it is not listed in `requirements.txt`, which contains the runtime dependencies packaged by AWS SAM.

## Deploy to AWS Lambda

The AWS deployment uses Python 3.12, API Gateway, and the Mangum adapter. Install the AWS SAM CLI and configure AWS credentials with permission to create or update the CloudFormation stack, Lambda function, API Gateway API, and required IAM role. The AWS CLI is one way to configure credentials and region.

From the repository root, build and deploy:

```powershell
sam build
sam deploy --guided
```

During the guided deployment, choose a stack name and AWS region, confirm the deployment settings, and allow SAM to create the Lambda execution role. The guided settings are saved for later deployments. For subsequent updates, run:

```powershell
sam build
sam deploy
```

The API URL has this form:

```text
https://<api-id>.execute-api.<region>.amazonaws.com/Prod/documents/process
```

Find the API ID in the API Gateway console under the API created for this stack. To test the deployed API, use that URL in place of the local URL in the PowerShell request above.

The template currently sets `ALLOWED_ORIGIN` to `*`, allowing requests from any origin. Before exposing the API publicly to a browser client, change it to that client's origin and redeploy. Docker is only needed if you choose to use `sam local`; it is not required for the Uvicorn local run or the standard SAM build and deploy commands above.