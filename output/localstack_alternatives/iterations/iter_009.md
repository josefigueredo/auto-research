# Iteration 009 — MinIO as S3-compatible replacement and Testcontainers integration patterns across all candidates

**Status:** keep  
**Scores:** coverage=73.8, quality=77.5, total=76.0  
**Timestamp:** 2026-04-08T17:21:27.621648+00:00  

---

### Findings

MinIO is the strongest open-source S3-focused replacement in this set for dev/CI, but it is not a pure “mock” in the S3Mock sense and it is not operationally identical to LocalStack.

On licensing, MinIO’s source is AGPLv3, and MinIO’s own compliance page says network hosting/distribution triggers AGPL obligations for combined or derivative works; it also offers a commercial license for proprietary/commercial use. Its GitHub README now adds an important 2026 wrinkle: the current community edition is “source code only,” with MinIO recommending `go install` or building your own image, while legacy prebuilt binaries remain available but unmaintained. Separately, Docker Hub still shows the historical `minio/minio` image, but marks that repository as archived, while the Docker Hub README points users to `quay.io/minio/minio` for the stable container path. For a commercial team that wants a clean permissive-license story, this is materially different from MIT tools like Floci or MiniStack. Sources: [MinIO GitHub README](https://github.com/minio/minio), [MinIO compliance/licensing](https://www.min.io/compliance), [Docker Hub](https://hub.docker.com/r/minio/minio).

Operationally, MinIO is an object store first, not an AWS emulator. Its own container docs say standalone mode is best for early development/evaluation, and call out that some features such as versioning, object locking, and bucket replication require distributed deployment with erasure coding. That is a subtle but important difference from S3Mock and LocalStack: MinIO can be much closer to a real S3-compatible storage system, but some semantics depend on how you deploy it. Sources: [Docker Hub README](https://hub.docker.com/r/minio/minio), [MinIO GitHub README](https://github.com/minio/minio).

On S3 API coverage, MinIO’s published position is far broader than S3Mock’s and generally more storage-realistic than LocalStack’s S3-only image. MinIO’s docs enumerate object APIs, multipart upload APIs, bucket versioning/CORS/analytics/notifications/policies, and document only a limited unsupported set such as object ACL calls; the product page explicitly claims full API coverage, path-style and virtual-host-style access, versioning, lifecycle, multipart uploads, event notifications, object lock, legal hold, and presigned URLs. By contrast, S3Mock explicitly says it implements only parts of S3, supports path-style only, accepts presigned URLs without validating signature/expiry/verb, and is not for production. LocalStack’s S3 docs are in the middle: they support both path and virtual-host style and expose an API-coverage matrix, but the docs also call out gaps such as the `s3-latest` image having no persistence and SSE-C doing parameter validation without actual encryption/decryption. Sources: [MinIO S3 API docs](https://docs.min.io/enterprise/aistor-object-store/developers/s3-api-compatibility/), [MinIO S3 API page](https://www.min.io/product/aistor/s3-api), [S3Mock README](https://github.com/adobe/S3Mock), [LocalStack S3 docs](https://docs.localstack.cloud/aws/services/s3/).

For Testcontainers support, the picture is more uneven than expected:
- MinIO has the best support surface of the candidates. The Testcontainers module catalog lists MinIO for Java, Go, .NET, Python, Node.js, and Rust. The modules expose higher-level helpers instead of just a port: Java exposes `getS3URL()`, `getUserName()`, `getPassword()`, and credential overrides; Go exposes `ConnectionString()` plus normal container customizers; Node and Python expose client/config helpers. Sources: [Testcontainers module catalog](https://testcontainers.com/modules/), [MinIO module page](https://testcontainers.com/modules/minio/), [Java docs](https://java.testcontainers.org/modules/minio/), [Go docs](https://golang.testcontainers.org/modules/minio/), [Python docs](https://testcontainers-python.readthedocs.io/en/latest/modules/minio/README.html).
- Floci now has a real Testcontainers module, but only for Java. The registry lists Floci as a Java cloud module, and the module repo exposes `FlociContainer`, `withRegion`, plus getters for endpoint, region, access key, and secret key. The repo also notes a gap: the helper library does not yet fully support Floci’s ElastiCache and RDS services even though Floci itself emulates them. This is the most surprising finding in this iteration because it materially improves Floci’s CI story versus the earlier assumption that it was Docker-only. Sources: [module catalog](https://testcontainers.com/modules/), [Floci module page](https://testcontainers.com/modules/floci/), [Floci module repo](https://github.com/floci-io/testcontainers-floci).
- MiniStack does not appear in the Testcontainers module catalog, while Floci does. I also found MiniStack’s published materials centered on `docker run` and `docker-compose`, not a registry-listed Testcontainers wrapper. Inference: for MiniStack today, the practical path is a plain `GenericContainer`/equivalent wrapper around `nahuelnucera/ministack` rather than a first-class module with typed helpers. Sources: [module catalog](https://testcontainers.com/modules/), [MiniStack Docker Hub](https://hub.docker.com/r/nahuelnucera/ministack).
- Moto does not have a mainstream registry-listed Testcontainers module. Moto itself supports Docker/server mode well, including a reset API and a threaded in-process server, and there is at least one niche Python package (`tomodachi-testcontainers`) with a Moto fixture, but I did not find a broadly adopted official catalog module. Inference: most teams will either use Moto directly in Python tests or wrap the official `motoserver/moto` image with a generic container. Sources: [Moto server-mode docs](https://docs.getmoto.org/en/latest/docs/server_mode.html), [Testcontainers module catalog](https://testcontainers.com/modules/), [tomodachi-testcontainers](https://pypi.org/project/tomodachi-testcontainers/0.13.1/).
- ElasticMQ has a maintained Rust module in `testcontainers-modules`, exposing the default SQS port `9324`, host/port lookup, image/tag overrides, startup timeout, and other standard container request controls. I did not find equivalent first-class modules in the main Java/Go/.NET/Node/Python catalogs, so outside Rust the usual pattern is again generic containers. Sources: [Rust ElasticMQ module docs](https://docs.rs/testcontainers-modules/latest/testcontainers_modules/elasticmq/struct.ElasticMq.html), [module source docs](https://docs.rs/testcontainers-modules/latest/src/testcontainers_modules/elasticmq/mod.rs.html), [module catalog](https://testcontainers.com/modules/).

Testcontainers-based integration patterns are operationally better than `docker-compose` or ad hoc `docker run` for test isolation and determinism, especially in polyglot CI, but only when the candidate has a decent module or you build a careful generic wrapper.

Why: Testcontainers defines dependencies as code, starts them for the test run, and tears them down automatically after tests, even on failure. Its module abstraction also bakes in technology-specific waits, endpoint discovery, and helper methods. Docker’s own Testcontainers docs stress that Java and Go are Docker-sponsored implementations and the ecosystem spans Java, Go, .NET, Node.js, Python, Rust and more. Sources: [Testcontainers homepage](https://testcontainers.com/), [introducing Testcontainers](https://testcontainers.com/guides/introducing-testcontainers), [Docker Testcontainers docs](https://docs.docker.com/testcontainers/), [Getting Started](https://testcontainers.com/getting-started/).

By contrast, `docker-compose` is good for shared local environments but weaker for per-test isolation. Docker’s docs are explicit that `depends_on` controls start order, not readiness, unless you add health checks and `service_healthy`; otherwise you still own race conditions. GitHub Actions service containers improve CI ergonomics by creating fresh containers per job and isolating them on a job-scoped Docker network, but they are still workflow-level plumbing, not test-level lifecycle. Raw `docker run` gives maximum portability and mirrors what many of these emulator projects document first, but it pushes cleanup, random port allocation, wait logic, and parallelism safety onto your test harness. Sources: [Docker Compose startup order](https://docs.docker.com/compose/how-tos/startup-order/), [GitHub Actions service containers](https://docs.github.com/actions/guides/about-service-containers), [GitHub Actions service containers tutorial](https://docs.github.com/actions/tutorials/use-containerized-services/use-docker-service-containers).

### Evidence

- MinIO license: AGPLv3 source plus commercial license option; MinIO says AGPL obligations apply when hosting/distributing over a network. Sources: [GitHub](https://github.com/minio/minio), [compliance page](https://www.min.io/compliance).
- MinIO community distribution: source-only now; legacy binaries remain but are unmaintained. Source: [GitHub README](https://github.com/minio/minio).
- MinIO Docker image state: Docker Hub `minio/minio` shows `Archived`; recent amd64 compressed tag sizes are about 59.35 MB to 63.09 MB. Source: [Docker Hub tags](https://hub.docker.com/r/minio/minio/tags).
- MinIO standalone ports/creds: `9000` plus console `9001`, default `minioadmin:minioadmin`. Source: [Docker Hub README](https://hub.docker.com/r/minio/minio).
- MinIO object size: Testcontainers module page describes current maximum supported object size as `5 TB`. Source: [MinIO module page](https://testcontainers.com/modules/minio/).
- Floci published runtime numbers: `24 ms` startup, `13 MiB` idle RAM, `289/s` Lambda throughput, `69 MB` Docker Hub compressed image, Java Testcontainers module version `2.0.0`. Sources: [floci.io](https://floci.io/), [Docker Hub](https://hub.docker.com/r/hectorvent/floci), [Floci module page](https://testcontainers.com/modules/floci/).
- S3Mock limitations: path-style only, presigned URLs accepted but not validated, HTTP `9090`, HTTPS `9191`. Source: [S3Mock README](https://github.com/adobe/S3Mock).
- LocalStack S3-only image: supports only S3 APIs; no persistence in that image; SSE-C validation only, no actual encryption. Source: [LocalStack S3 docs](https://docs.localstack.cloud/aws/services/s3/).
- GitHub Actions service containers: fresh service container per job, destroyed at job end; Linux runner requirement for service containers. Sources: [guide](https://docs.github.com/actions/guides/about-service-containers), [tutorial](https://docs.github.com/actions/tutorials/use-containerized-services/use-docker-service-containers).

### Trade-offs

MinIO is best when the real question is “do we need a durable, realistic S3-compatible object store in tests?” not “do we need an AWS emulator.” It is stronger than S3Mock on API surface and realism, and likely better than LocalStack/S3Mock for object-storage-heavy CI flows. But its AGPL/commercial posture is a real policy constraint, and some S3 features depend on distributed deployment rather than the easiest single-container mode.

S3Mock remains simpler and more obviously test-only. If you want a permissive-license, lightweight, intentionally incomplete S3 fake and you do not care about virtual-host style or presigned URL validation, it is still easier to reason about than MinIO. If you do care about those edges, MinIO is the better fit.

Floci now looks materially stronger for Java shops than it did in the earlier iteration because it has a dedicated Testcontainers module. That improves startup determinism and reduces custom boilerplate. The catch is language scope: today it is Java-only, and even there the helper library lags Floci’s full service set for RDS/ElastiCache.

MiniStack is still weaker on Testcontainers ergonomics. The lack of a registry-listed module does not make it unusable, but it means every team has to invent and maintain its own container wrapper, waits, endpoint plumbing, and possibly reset/seed utilities. That increases adoption friction relative to Floci in Java and MinIO across multiple languages.

Moto is still attractive for Python-first teams because its own server mode, reset API, and in-process server controls are strong. But as a black-box CI dependency for non-Python teams, it has less turnkey Testcontainers support than MinIO or even Floci Java. The niche Python fixture ecosystem does not change that much.

ElasticMQ remains excellent if your scope is only SQS, but its Testcontainers support is fragmented by language. Rust gets a typed module; other stacks generally fall back to generic container patterns.

For CI architecture, Testcontainers wins when you need per-test or per-suite isolation, random ports, deterministic cleanup, and language-local ergonomics. `docker-compose` wins when you want one shared environment for humans or for an entire job. Raw Docker wins when you need maximal portability or the emulator’s docs assume it, but it has the highest maintenance tax.

### New Questions

- How much do these tools differ on virtual-hosted S3 behavior, presigned URL validation, and SigV4 edge cases under real SDKs and CDK asset publishing?
- Which emulators support deterministic state reset and seeding well enough for parallel test sharding, not just single-run CI jobs?
- For Java specifically, does Floci’s Testcontainers module plus Spring Boot `@ServiceConnection` meaningfully reduce migration effort compared with LocalStack’s module in real multi-service test suites?

---

## Peer Review (claude)

## Critical Peer Review

---

### Issue 1: MinIO versioning and object locking do NOT require distributed deployment
- **Type**: Factual error
- **Location**: "some features such as versioning, object locking, and bucket replication require distributed deployment with erasure coding"
- **Problem**: This conflates three distinct features. MinIO has supported object versioning and object locking in single-node (SNSD and SNMD) deployments since at least 2021. Only *bucket replication* requires a multi-site setup. Citing all three as requiring distributed erasure-coded deployment is incorrect and may have been sourced from outdated MinIO documentation or misread.
- **Impact**: High. A reader evaluating MinIO for a single-container dev/CI workflow may incorrectly conclude they cannot use versioning or object locking in that mode, which is false.

---

### Issue 2: MinIO AIStor enterprise page conflated with open-source community edition
- **Type**: Factual error / missing nuance
- **Location**: "the product page explicitly claims full API coverage...Sources: [MinIO S3 API page](https://www.min.io/product/aistor/s3-api)"
- **Problem**: The cited URL is the MinIO AIStor product page, which is the enterprise/commercial offering. Full API coverage claims from that page do not necessarily apply to the open-source AGPLv3 community edition. The research never flags this distinction, meaning the strongest API coverage claim is borrowed from enterprise marketing materials and applied to the open-source tool.
- **Impact**: High. This is a category error. Feature parity between AIStor and the community edition is not established anywhere in the findings.

---

### Issue 3: MinIO ACL incompatibility understated
- **Type**: Missing nuance
- **Location**: "document only a limited unsupported set such as object ACL calls"
- **Problem**: MinIO has removed support for both object ACLs *and* bucket ACLs entirely, requiring IAM policies as the replacement. This is not a minor edge case — ACL-based access control is common in CDN configurations, cross-account object sharing, and public-read bucket patterns. Applications using `PutObjectAcl`, `GetObjectAcl`, `PutBucketAcl`, or `GetBucketAcl` will fail silently or with errors against MinIO. "A limited unsupported set such as object ACL calls" significantly undersells this gap.
- **Impact**: Medium-high. Any team testing ACL-dependent code against MinIO will encounter failures not predicted by the findings.

---

### Issue 4: "Source code only" characterization for MinIO community edition is overstated or unverified
- **Type**: Unsupported claim / potentially factual error
- **Location**: "the current community edition is 'source code only,' with MinIO recommending `go install` or building your own image, while legacy prebuilt binaries remain available but unmaintained"
- **Problem**: The canonical published image for MinIO has been `quay.io/minio/minio` for some time, and it continues to receive updates. The research separately notes this is the "stable container path" recommended by the Docker Hub README. The claim that the community edition is now "source code only" directly contradicts the parallel claim that `quay.io/minio/minio` is the stable container path. If `quay.io/minio/minio` is actively maintained, the community edition is *not* source-code-only — it has a maintained container image.
- **Impact**: High. This creates an internal contradiction (see also Issue 5) and may significantly overstate the distribution friction for MinIO.

---

### Issue 5: Internal contradiction — "archived" Docker Hub repo but "recent" tag sizes cited
- **Type**: Contradiction
- **Location**: Evidence section: "Docker Hub `minio/minio` shows `Archived`; recent amd64 compressed tag sizes are about 59.35 MB to 63.09 MB"
- **Problem**: If the `minio/minio` Docker Hub repository is archived, there are no *recent* tags — only historical ones. Calling these sizes "recent" implies active publication when the repo is simultaneously described as archived. The sizes would reflect the state at archival time, not current releases.
- **Impact**: Medium. The ambiguity erodes trust in the evidence section's precision and may mislead readers about the current Docker Hub artifact state.

---

### Issue 6: Floci performance metrics presented as facts, sourced exclusively from vendor marketing
- **Type**: Unsupported claim
- **Location**: "Floci published runtime numbers: `24 ms` startup, `13 MiB` idle RAM, `289/s` Lambda throughput, `69 MB` Docker Hub compressed image" and the trade-offs section treating Floci as materially stronger based partly on these numbers
- **Problem**: Every performance figure for Floci comes from `floci.io` — the vendor's own homepage. These are marketing claims, not independently benchmarked results. The research presents them as factual data points without any caveat that they are vendor-reported and unverified. Startup time, memory usage, and throughput figures on a product's homepage are notoriously optimistic.
- **Impact**: Medium-high. The conclusion that Floci "looks materially stronger for Java shops" is partly predicated on these unverified numbers. Readers may make tool selection decisions based on marketing figures they believe to be measured results.

---

### Issue 7: Floci's Docker Hub namespace raises unaddressed provenance concern
- **Type**: Gap
- **Location**: Evidence: "Docker Hub `hectorvent/floci`"; trade-offs: "Floci now looks materially stronger for Java shops"
- **Problem**: The Docker Hub image is under a personal namespace (`hectorvent/`) rather than an organization or verified publisher namespace. The research does not address Floci's institutional backing, project maturity, community size, or governance. For a tool being recommended as a production-test dependency, the difference between a well-funded project and an individual's side project is material. The Testcontainers module version `2.0.0` is cited but without context on release cadence or adoption.
- **Impact**: Medium. A practitioner reading this would have no basis to assess Floci's long-term reliability.

---

### Issue 8: Moto's Docker server mode utility for non-Python teams underrepresented
- **Type**: Missing nuance
- **Location**: "as a black-box CI dependency for non-Python teams, it has less turnkey Testcontainers support than MinIO or even Floci Java"
- **Problem**: This is true for *Testcontainers-specific ergonomics* but the broader framing positions Moto as weak for non-Python teams generally. Moto's server mode (`motoserver/moto`) runs as a standalone HTTP server callable by any SDK in any language. It supports an extensive reset API and per-test state isolation. The finding accurately notes this, then fails to carry it into the trade-offs comparison. The section ends up damning Moto with a narrow Testcontainers criterion when its language-agnostic server mode is a genuine differentiator.
- **Impact**: Medium. The trade-offs section may lead non-Python teams to discount Moto more than the full evidence warrants.

---

### Issue 9: "Floci's ElastiCache and RDS services" — claim lacks a direct quote or evidence
- **Type**: Unsupported claim
- **Location**: "The repo also notes a gap: the helper library does not yet fully support Floci's ElastiCache and RDS services even though Floci itself emulates them"
- **Problem**: This specific claim about the Testcontainers module's ElastiCache/RDS gap is attributed to "the repo" but no direct quote, issue link, or README excerpt is provided. The citation is just `[Floci module repo](https://github.com/floci-io/testcontainers-floci)`. Without a direct quote, readers cannot verify whether this is accurately characterized, how recently it was noted, or whether it has since been resolved.
- **Impact**: Low-medium. The gap may be real, but the lack of a verifiable citation weakens the finding.

---

### Issue 10: Docker Compose `depends_on` analysis missing `condition: service_healthy` nuance
- **Type**: Missing nuance
- **Location**: "Docker's docs are explicit that `depends_on` controls start order, not readiness, unless you add health checks and `service_healthy`; otherwise you still own race conditions"
- **Problem**: The caveat is technically present but then dropped. The finding leaves the impression that `docker-compose` is inherently racy, when in fact `depends_on: condition: service_healthy` fully resolves readiness ordering. A reader skimming the trade-offs section may conclude `docker-compose` has a fundamental race-condition problem when the solution is well-documented and widely used.
- **Impact**: Low-medium. Creates a slightly misleading impression of `docker-compose` reliability.

---

### Issue 11: Gap — no coverage of MinIO's IAM/policy model and its S3 compatibility surface
- **Type**: Gap
- **Location**: S3 API coverage section and trade-offs section for MinIO
- **Problem**: MinIO's access control model diverges significantly from S3: it uses its own IAM system (MinIO Identity and Access Management) rather than AWS IAM, does not support resource-based S3 bucket policies in the same way, and has its own admin API. Applications that test IAM policies, assume S3 bucket policy semantics, or use STS assume-role flows may encounter compatibility gaps that the research does not surface at all. This is distinct from the ACL issue in Issue 3.
- **Impact**: Medium. Teams using IAM-policy-dependent code paths have no signal from this research.

---

### Issue 12: Gap — SigV4 signing and SDK compatibility not assessed for any tool
- **Type**: Gap
- **Location**: "New Questions" section acknowledges this but it also belongs in the gap section of the main findings
- **Problem**: The research notes SigV4 edge cases as a new question but treats this purely as future work. For dev/CI use, SigV4 compatibility under real AWS SDKs (e.g., `boto3`, AWS SDK for Java, AWS SDK for Go) is a day-one concern when evaluating emulators — not a deferred question. S3Mock explicitly does not validate presigned URL signatures; MinIO validates SigV4 but may diverge on edge cases. The research should at minimum characterize this as a known gap with practical implications rather than deferring it entirely.
- **Impact**: Medium. This is one of the most common sources of "tests pass on emulator, fail on AWS" bugs.

---

## Summary

**Issues found**: 12 (4 high-impact, 6 medium, 2 low-medium)

**Overall reliability**: **Medium**

The research is well-structured, internally consistent in most places, and contains genuinely useful comparative detail. The Testcontainers module survey in particular is thorough and adds value. However, it has two significant factual errors (standalone MinIO capabilities; AIStor/community conflation) and a recurring pattern of presenting vendor-sourced claims without flagging them as such. The internal contradiction around MinIO's distribution state (source-only vs. maintained quay.io image) needs resolution before the findings can be trusted as a decision input.

**What would most improve the findings:**

1. Resolve the MinIO distribution contradiction: verify whether `quay.io/minio/minio` is actively published, and if so, drop or heavily qualify the "source code only" framing.
2. Correct the versioning/object-locking claim to apply only to bucket replication.
3. Clearly separate MinIO Community Edition capabilities from MinIO AIStor claims throughout.
4. Flag all Floci performance numbers as vendor-reported and unverified.
5. Add a paragraph on MinIO ACL incompatibility and IAM model divergence as practical compatibility risks.
