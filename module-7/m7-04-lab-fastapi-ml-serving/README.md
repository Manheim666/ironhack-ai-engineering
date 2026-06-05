# Example payloads

Each file is a valid instance of the matching schema in `../openapi.yaml`:

| File | Schema |
|------|--------|
| `predict-request.json` | `PredictRequest` |
| `predict-response.json` | `PredictResponse` |
| `predict-error-413.json` | `Error` |
| `batch-request.json` | `BatchPredictRequest` |
| `batch-response.json` | `BatchPredictResponse` |

## Image size assumption

The `image_base64` fields use a short placeholder string (e.g.
`/9j/4AAQSkZJRgABAQEAYABgAAD...`) instead of a real encoded image, to keep the
files readable. In production the decoded image bytes must not exceed **5 MB**
(5242880 bytes). Base64 inflates size by ~33%, so the encoded string for a
maxed-out 5 MB image would be roughly **6.99 MB** of text. Anything larger is
rejected with `413 payload_too_large` (see `predict-error-413.json`).
