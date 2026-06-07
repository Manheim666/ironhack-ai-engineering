# Container plan

The serving image for the `ranker`. Reviewable, not built in this assessment.

## Bake vs mount — and why baked

Decided in [ADR-0001](../architecture/adr/0001-bake-model-into-image.md): the model is **baked into
the image**. The short reasons, since this is the question a reviewer will ask first:

- One image tag = one model version = one known state. Rollback is "deploy the previous tag."
- No runtime dependency on the registry/object store for a pod to start.
- The image tag, registry entry, and `X-Model-Version` header all agree by construction.

The cost we accept: a model update means an image rebuild + redeploy, and ~180 MB of weights ride
inside each image. For our daily-ish model cadence that's a fine trade. (If we pushed many models per
hour, mounting would win — but we don't.)

This is consistent with the [capacity plan](../serving/capacity-plan.md), which assumes pods are
self-contained and interchangeable — no shared model volume to coordinate.

## Base image

`python:3.12-slim`. Pinned by digest in CI (shown un-pinned here for readability). `slim` over the
full image because we don't need the extra system libs; over `alpine` because the musl/manylinux
wheel story for ML libs (LightGBM, numpy) is a headache on alpine and not worth it for the few MB.

## Multi-stage layout

| Stage | Has | Ships to final image? |
|---|---|---|
| `builder` | build-essential, pip, venv, model artifact | only the venv + model are copied out |
| `runtime` | slim base, venv, model, app code, non-root user | this is the image |

Build tooling (`build-essential`) lives only in the builder stage, so compilers and the apt cache
never reach the runtime image. That's the main thing keeping the size down and the attack surface
small.

## Size estimate

Rough, but defensible:

| Layer | Size |
|---|---|
| `python:3.12-slim` base | ~130 MB |
| Python deps in venv (fastapi, gunicorn, uvicorn, numpy, lightgbm) | ~150 MB |
| Baked model artifact (`ranker.bin`) | ~180 MB |
| App code | ~5 MB |
| **Final image (approx.)** | **~480 MB** |

If that ever feels heavy, the model weights are the biggest single chunk — but they're the whole point
of baking, so they stay. Trimming would come from the deps (e.g. dropping anything pulled in only for
training but not inference).

## Security / hygiene choices

- **Non-root user** (`uid 10001`). The process can't write outside what it needs.
- **No build tooling in the final image** — nothing to compile with if someone gets in.
- **`HEALTHCHECK`** wired to `/readyz`, which fails if the baked model won't load — a broken image
  fails readiness instead of silently serving errors.
- **Pinned base by digest in CI**, and the image is **scanned** in the pipeline (Trivy step in
  [deploy-model.yml](../cicd/.github/workflows/deploy-model.yml)) — a high/critical CVE fails the
  build before anything ships.
- **`MODEL_VERSION` env** is the single source the app reads to emit `X-Model-Version`, and it matches
  the baked artifact — so the header can't drift from what's actually running.

## How the tag is built

CI builds `ranker:{semver}-{git_sha8}` (e.g. `ranker:1.4.2-9f3a1c2d`) — the same scheme the
[registry](../lifecycle/model-registry.yaml) records and the [pipeline](../cicd/.github/workflows/deploy-model.yml)
pushes. The `MODEL_VERSION` build arg ties the baked artifact to that version so they can't disagree.
