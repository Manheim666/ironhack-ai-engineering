# ADR-0001: Bake the ranking model into the container image

- **Status:** Accepted
- **Date:** 2026-06-05
- **Deciders:** Asif Habilov

## Context

The `ranker` model artifact is \~180 MB. We need every serving pod to run a known, exact version of it, and we A/B test models continuously — so "which model served this request" has to be unambiguous and auditable. The two realistic options:

- **Bake** the model into the image at build time. The image *is* the release.
- **Mount** the model at runtime — pull from the registry / object store on pod start, or mount a volume, and hot-swap without rebuilding.

This is the most consequential decision in the dossier because it dictates the CI/CD shape, the rollback procedure, the registry tagging, and how the version header behaves.

## Decision

**Bake the model into the image.** A deployable artifact = one image tag = one model version. The tag scheme is `{semver}-{git_sha8}` (e.g. `1.4.2-9f3a1c2d`) and the running model reports itself as `X-Model-Version: ranker-1.4.2`.

## Consequences

**What we gain**

- **Atomic, trustworthy rollback.** Rolling back the model is rolling back the image — one `kubectl`apply of the previous tag. No "which model is mounted on which pod" drift. The [rollback runbook](../../runbooks/rollback.md) is short *because* of this.
- **Reproducibility.** Pull the image tag a year from now, get the exact same model + serving code. Nothing to fetch, nothing to go missing.
- **Simple version truth.** The image tag, the registry entry, and the `X-Model-Version` header all line up by construction. That's what makes the [version-mismatch alert](../../monitoring/alerts.yaml)meaningful — a mismatch is a real bug, not an expected race.
- **No runtime dependency on the registry/object store** for a pod to come up. One less thing that can break a scale-up at 3am.

**What it costs**

- **Slower model updates.** A new model = a new image build + redeploy (minutes, through CI), not a hot swap. For a daily-ish model cadence this is fine; if we needed many model pushes per hour, mount would win.
- **Bigger images / more registry storage.** \~180 MB per image of model weights. Mitigated by multi-stage builds and shared base layers (see [container/README.md](../../container/README.md)).
- **Coupling code and model releases.** A pure-code hotfix still ships the model with it. Acceptable — it keeps "one tag = one known state" intact.

## Alternatives rejected

- **Mount from object store on pod start.** Faster model swaps, but reintroduces version drift across pods, adds a startup dependency, and makes rollback "change a pointer somewhere" instead of "deploy the old tag." For a continuously A/B-tested system, the auditability loss isn't worth the speed.
- **Sidecar model server.** More moving parts, another network hop inside the latency budget, and the same version-drift problem. No.

## Revisit if

Model update frequency climbs to the point where image build/redeploy latency is the bottleneck for experimentation, or the model grows large enough that baking it bloats images unacceptably.