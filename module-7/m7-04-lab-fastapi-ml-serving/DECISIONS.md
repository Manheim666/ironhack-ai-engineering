# Design Decisions

## 1. Versioning

I picked path-based versioning (`/v1/`) because it is visible in logs, dashboards, and curl commands without inspecting headers, which makes routing and debugging trivial. Header-based versioning is invisible to caches and proxies and is easy for partner integrators to forget to set, so a wrong default silently breaks them.

## 2. Batch ordering and partial failures

When `predict-batch` is called with 32 items and one image is corrupt, the call still returns `200` and a `results` array keyed by the caller-supplied `id`, where the good items carry `status: "ok"` with labels and the corrupt item carries `status: "error"` with the shared `Error` envelope. I chose per-item partial failure over failing the whole batch so one bad image cannot waste 31 good predictions the caller already paid for. Results are matched by `id`, never by array position, so the caller never has to assume order is preserved.

## 3. Async lifecycle

A job moves through `queued → running → done`, or `queued → running → failed` if the model rejects the image. `POST /v1/predict-async` returns `202` with a `job_id` in `queued`; the client polls `GET /v1/predictions/{job_id}` until `status` is `done` (result populated) or `failed` (error populated). Results are retained for 24 hours after completion; after that the `job_id` returns `404 not_found`, so clients must fetch results within the retention window.
