# LocalStack Alternatives: AWS Local Emulation Evaluation Report
*April 2026 — Prepared for senior AWS cloud architects*

---

## Executive Summary

LocalStack's February–March 2026 commercialization—eliminating Community Edition for commercial use and introducing seat-based pricing ($39–$89/user/month)—has created a genuine need to evaluate open-source alternatives. Three plausible multi-service OSS replacements exist: **MiniStack** (operationally closest to LocalStack, single-endpoint, black-box), **Floci** (lightest CI footprint, strongest published compatibility detail, Java Testcontainers module), and **Moto** (most mature, lowest bus-factor, strongest for Python-first teams). None of these is a proven drop-in replacement. For service-specific needs, **ElasticMQ** (SQS only) and **Adobe S3Mock** or **MinIO** (S3 focus) outperform general emulators on their respective target services. The honest finding is that the OSS ecosystem has not caught up to LocalStack's breadth and fidelity; any migration requires direct validation against your actual workflows before committing.

---

## Comparison Table

| Tool | Services | License | Image (compressed) | Startup | Idle RAM | Stars | Testcontainers | SigV4 Enforcement | CloudFormation |
|---|---|---|---|---|---|---|---|---|---|
| **MiniStack** | 38 claimed | MIT | ~26 MB (Docker Hub) | <2 s | ~30 MB | ~1.8k | Generic container only | No evidence | 12 resource types |
| **Floci** | 28 claimed | MIT | ~69 MB (Docker Hub) | 24 ms (vendor) | 13 MiB (vendor) | ~3.0k | Java module v2.0.0 | Not for S3/SQS/SNS/DDB | 12 resource types |
| **Moto** | All 8 core + more | Apache 2.0 | ~97 MB (Docker Hub) | No benchmark | No benchmark | ~8.4k | Generic (Python-first) | Off by default | Broad but partial |
| **ElasticMQ** | SQS only | Apache 2.0 | ~31 MB native, ~226 MB JVM | Milliseconds (native) | Low | ~2.8k | Rust module; generic elsewhere | No evidence | N/A |
| **Adobe S3Mock** | S3 only | Apache 2.0 | Not benchmarked | Fast | Low | Moderate | Java/JUnit/Testcontainers | No (accepts all presigned) | N/A |
| **MinIO** | S3 only | AGPLv3 + commercial | ~59–63 MB (quay.io) | Fast | Moderate | High | Java, Go, .NET, Python, Node, Rust | Yes (validates SigV4) | N/A |
| **LocalStack (Hobby)** | 80+ | Subscription (not commercial) | Large | Moderate | Moderate | ~56k | Official module | Yes (Pro tier) | Broad (Pro tier) |

**Confidence note:** MiniStack and Floci performance figures are vendor-published and unverified. Moto has no official startup/memory benchmarks in server mode. All figures reflect April 2026 state.

---

## Dimension-by-Dimension Findings

### 1. AWS Service Coverage

The eight services most commonly needed for application-level integration testing are S3, SQS, SNS, DynamoDB, Lambda, API Gateway, IAM/STS, and CloudFormation.

**MiniStack** publicly documents S3, SQS, SNS, DynamoDB, Lambda (Python + Node, Docker-backed runtimes, event source mappings), API Gateway v1/v2, IAM/STS, and CloudFormation. The Lambda coverage is unusually specific for an OSS emulator. The CloudFormation claim of "38 AWS services" is contradicted by explicit documentation showing only 12 supported resource types; resources outside that set fail with `CREATE_FAILED`. Given AWS CloudFormation supports over 1,000 resource types, MiniStack's CloudFormation support is symbolic, not functional.

**Floci** documents 28 services with published per-service operation counts: S3 (30 ops), SQS (17), SNS (13), DynamoDB (22), Lambda (25), API Gateway REST (24), API Gateway v2 (16), IAM (65+), and CloudFormation (12). Suite-level pass counts are detailed: S3 23/23, S3 Object Lock 30/30, S3 Advanced 13/13, DynamoDB Streams 12/12, API Gateway REST 43/43, API Gateway v2 5/5, STS 18/18, IAM 32/32. However, all these numbers are self-published and unverified externally. Known public defects include: S3 responses rejected by the AWS SDK (breaking CDK asset publishing), leading-slash S3 keys being stripped and colliding, and DynamoDB `DescribeTable` for GSIs omitting non-key attributes. CloudFormation support appears equivalent to MiniStack: 12 resource types.

**Moto** has the broadest and most transparently documented coverage. It explicitly maps implemented vs. missing operations per service. IAM and S3 coverage is deep. CloudFormation is materially broader than MiniStack or Floci, with a large documented resource matrix spanning many services. Lambda has Docker-backed invocation but semantic limitations: lambdas under decorators cannot reach Moto state unless MotoServer or MotoProxy is used correctly. API Gateway is the weakest: only HTTP integrations and AWS-DynamoDB integrations are documented as supported for REST APIs; `AWS_PROXY`, `MOCK`, and others are not. There is no Function URL support and no image-package Lambda invocation.

**Trade-off:** If CloudFormation is in scope, Moto is the only credible OSS option. If it is not, MiniStack and Floci cover the common app-level integration set (S3 + SQS + Lambda + DynamoDB + API Gateway) at comparable breadth. API Gateway `AWS_PROXY` support is where all three are weakest.

---

### 2. Maintenance, Sustainability, and Bus Factor

| Tool | Stars | Contributors | Backer | Release cadence |
|---|---|---|---|---|
| MiniStack | ~1.8k | ~9 | Individual | v1.1.46–v1.1.51 (Apr 7–8, 2026) |
| Floci | ~3.0k | ~1 effective | Individual (hectorvent) | 1.3.0 Apr 6, 1.4.0 Apr 8, 2026 |
| Moto | ~8.4k | ~1,150 | Community + OpenCollective | v5.1.20 Jan 17, v5.1.21 Feb 8, v5.1.22 Mar 8, 2026 |
| ElasticMQ | ~2.8k | ~15 PR authors | SoftwareMill (commercial support available) | v1.6.16 Feb 16, 2026 |

MiniStack and Floci both live in personal Docker Hub namespaces (`nahuelnucera/ministack`, `hectorvent/floci`), have no disclosed institutional backing, and exhibit release cadences that suggest one primary author driving rapid iteration. High velocity is encouraging but high bus factor is a real operational risk for infrastructure tooling used in CI pipelines.

Moto is the lowest-risk maintenance bet by a wide margin: 1,150+ contributors, years of production use, documented limitations, active issue tracking, and multiple funding channels. Its flaws look numerous partly because it has the most public scrutiny—that is a feature of maturity, not a weakness.

ElasticMQ benefits from SoftwareMill institutional backing and offers commercial support options, which is unusual in this space. It has a narrower contributor base than Moto but a more realistic governance model than MiniStack or Floci.

---

### 3. Docker Image, Startup, and Resource Footprint

| Tool | Docker Hub compressed | Docs claim | Startup | Notes |
|---|---|---|---|---|
| MiniStack | 26.02 MB | 200–250 MB | <2 s, or <1 s | Internal inconsistency; CI examples use `sleep 2` |
| Floci | 69 MB | ~90 MB | 24 ms (vendor) | CI examples also use `sleep 2`; vendor numbers are unverified |
| Moto server | 96.69 MB | — | No official benchmark | No solid idle RAM figure |
| ElasticMQ JVM | 226 MB | ~240 MB | Seconds | Larger footprint |
| ElasticMQ native | 31 MB | ~30 MB | Milliseconds | Best startup in this set |
| MinIO | 59–63 MB (quay.io) | — | Fast | `minio/minio` Docker Hub is archived; use `quay.io/minio/minio` |

**Important caveat:** "startup" in vendor docs means binary process start, not Docker cold-start including image pull, container creation, and readiness. The CI examples for both MiniStack and Floci use `sleep 2` despite sub-second startup claims, which suggests actual Docker-in-CI readiness is on the order of 2+ seconds regardless. For most CI pipelines, a 2-second service container startup is operationally fine; the gap between the marketing figure and practical figure matters mostly for how you should interpret benchmarks.

For parallel test suites with many short-lived service containers, Floci's claimed 13 MiB idle RAM is attractive if accurate. Moto server is unknown territory here and requires empirical measurement in your environment.

---

### 4. SigV4 Signing and SDK Compatibility

This dimension is where the OSS field most clearly differs from LocalStack Pro.

**By default, none of MiniStack, Floci, or Moto validates SigV4 requests meaningfully.**

- **Moto** documents this explicitly: if `INITIAL_NO_AUTH_ACTION_COUNT` is unset, auth "defaults to infinity"—meaning Moto never authenticates requests at all. Auth can be enabled, but the docs describe it as "very basic" without specifying whether it means credential presence, HMAC verification, or expiry checking. This is a material ambiguity.
- **MiniStack** has no public documentation or issue evidence of SigV4 enforcement. Its getting-started guides use `skip_credentials_validation = true` in Terraform examples. Low public issue count is not validation of correctness; it is evidence of low external scrutiny.
- **Floci** explicitly claims "full IAM authentication and SigV4 validation" for Lambda, ElastiCache, and RDS—but notably does not make the same claim for S3, SQS, SNS, or DynamoDB. The 408/408 SDK compatibility claims are vendor-published. Known fixed bugs include missing AWS request-id headers, wrong SQS error-code mapping, broken pagination tokens, and missing `versionId` in `CompleteMultipartUpload`—all of which break real SDK behavior even when CRUD operations look correct.

**MinIO** is the only tool in this set that genuinely validates SigV4 for its service (S3). Its docs state clients must authenticate with AWS Signature Version 4, and presigned URL expiry is enforced. The evidence for this is indirect: public issues show MinIO *rejecting* AWS SDK-generated presigned URLs with `SignatureDoesNotMatch`, which demonstrates real cryptographic enforcement but also demonstrates false positives when SDKs or endpoint resolution change (e.g., `aws-sdk-java-v2` post-2.21.16 behavior change). MinIO enforces something cryptographically real; whether it enforces SigV4 *correctly* in all edge cases is a different question.

**S3Mock** documents its position honestly: presigned URLs are accepted but not validated—expiry, signature, and HTTP verb are not checked. This is a deliberate design decision for a test-only fake, but it means S3Mock cannot serve as a CI gate for auth regressions.

**ElasticMQ** shows no public evidence of SigV4 enforcement. Treat it as authoritative for SQS queue semantics, not for auth behavior.

**Practical implication:** If your code depends on AWS rejecting malformed signatures, expired presigned URLs, or invalid credentials, every OSS emulator in this set except MinIO (for S3 only) will silently accept those requests. Bugs of this class will pass locally and fail on AWS.

---

### 5. CI/CD Integration

All tools share the basic CI integration pattern: start container, wait for readiness, seed resources, run tests, tear down. They differ on readiness signaling, state reset, persistence, and language-native ergonomics.

**MiniStack** has the most CI-oriented control surface among multi-service newcomers. It exposes health endpoints at `/_ministack/health`, `/_localstack/health`, and `/health` (LocalStack-compatible), plus a reset endpoint at `/_ministack/reset` for wiping state between test suites without restarting the container. This is operationally valuable: container restart in CI costs 2–10 seconds; state reset is much faster. The documentation includes a GitHub Actions example but no GitLab or Jenkins cookbook.

**Floci** documents storage modes (`memory`, `persistent`, `hybrid`, `wal`) and `FLOCI_HOSTNAME` for correct returned URLs in multi-container topologies—directly relevant to CI service containers with bridge networking. A reset endpoint and explicit health endpoint were not clearly documented in reviewed materials. No first-party GitHub Actions, GitLab, or Jenkins guidance found. Community CI examples use `sleep 2`.

**Moto** in server mode exposes `ThreadedMotoServer(port=0)` for random free-port allocation, a reset API, and a `TEST_SERVER_MODE` pattern for deterministic test isolation. Its own contributing docs explicitly warn that parallel tests can leak shared-state effects unless resource names are unique—which is useful operational guidance that most emulators do not document at all. The reset API is analogous to MiniStack's, making Moto viable for sequential test suites.

**ElasticMQ** has the strongest operational docs among point tools: `/health` endpoint, queue pre-creation via config file, auto-create-on-demand, full message persistence via H2, URL-generation control via `node-address` for containerized deployments. If SQS is your only need, ElasticMQ has the cleanest seeding and restart-persistence story of any tool in this set.

**Testcontainers integration summary:**

| Tool | Testcontainers support |
|---|---|
| MinIO | Java, Go, .NET, Python, Node.js, Rust — typed modules with `getS3URL()`, credentials helpers |
| Floci | Java only — `FlociContainer`, typed endpoint/region/credential getters; RDS/ElastiCache gap noted in module |
| MiniStack | No catalog-listed module — generic container required in all languages |
| Moto | No mainstream catalog module — Docker server or in-process server; Python fixtures via niche packages |
| ElasticMQ | Rust typed module; generic containers elsewhere |
| S3Mock | JUnit 5 extension, Java Testcontainers integration built in |

Testcontainers integration materially affects test determinism and cleanup reliability. MinIO has the broadest polyglot support. Floci's Java module is a concrete improvement over MiniStack for Java shops. MiniStack requires every team to build and maintain their own container wrapper.

---

### 6. Migration Effort from LocalStack

Migration cost has two components: removing LocalStack-specific glue, and validating that the replacement produces equivalent behavior.

**LocalStack-specific dependencies to identify before migration:**
- Auth token (required in new unified image)
- Internal endpoints: `/_localstack/health`, `/_aws/...`
- Wrapper CLIs: `awslocal`, `tflocal`, `cdklocal`, `samlocal`
- DNS behavior: `localhost.localstack.cloud` or Transparent Endpoint Injection
- LocalStack-specific Docker Compose service definitions

**MiniStack** is the lowest-friction migration target at the control-plane level:
- Same `http://localhost:4566` default endpoint
- Same dummy credentials and region pattern
- Explicit `/_localstack/health` support
- Explicit Terraform endpoint examples (AWS provider v5/v6)
- CDK guidance via `AWS_ENDPOINT_URL`
- Claims compatibility with `terraform-aws-modules/vpc/aws` v6.6.0 (23 resources)—maintainer-authored claim

DNS interception is not available. LocalStack wrapper CLIs (`awslocal`, etc.) will not work as-is.

**Floci** also uses `:4566` and accepts dummy credentials. Migration is mechanically simple for setups using plain endpoint overrides. However, `forcePathStyle: true` is required in S3 examples, and `FLOCI_HOSTNAME` must be set correctly for multi-container topologies. Floci publishes compatibility suites: `compat-terraform` (14 tests), `compat-opentofu` (14 tests), `compat-cdk` (5 tests). A Terraform AWS provider v6 compatibility issue was already fixed. These test counts are low bars—14 tests cannot validate a complex Terraform module—but they establish an explicit compatibility intent that MiniStack lacks.

**Moto** is not a LocalStack drop-in. Default port is 5000, not 4566. Control APIs live under `/moto-api/` rather than `/_localstack/`. The testing model is Python-decorator-first, not black-box server-first. For CDK, Terraform-heavy, or non-Python workflows, migration effort is substantially higher than MiniStack or Floci.

**CDK and CloudFormation:** No OSS option is proven for CDK bootstrap and asset publishing. Floci has 5 CDK compatibility tests, but public reports show CDK/S3 asset publishing failures. MiniStack has a generic `AWS_ENDPOINT_URL` guidance but no specific CDK bootstrap validation. Moto's server-mode caveats for CloudFormation and S3 make realistic CDK deploy-and-invoke workflows fragile. If CDK bootstrap is a hard requirement, this is the highest-risk area across all OSS alternatives.

---

### 7. Licensing and Commercial Cost

| Tool | License | Commercial use cost |
|---|---|---|
| MiniStack | MIT | $0 |
| Floci | MIT | $0 |
| Moto | Apache 2.0 | $0 |
| ElasticMQ | Apache 2.0 | $0; commercial support available from SoftwareMill |
| Adobe S3Mock | Apache 2.0 | $0 |
| MinIO | AGPLv3 + commercial license | $0 for internal use; commercial license required if distributing/hosting as a service for others; AGPL obligations apply when hosting over a network |
| LocalStack Hobby | Subscription (non-commercial) | $0, but not valid for commercial software development |
| LocalStack Base (annual promo, through Apr 30) | Subscription | ~$23/user/month → $115/month for 5 devs, $230/month for 10 |
| LocalStack Base (annual list) | Subscription | $39/user/month → $195/month for 5 devs, $390/month for 10 |
| LocalStack Ultimate (annual) | Subscription | $89/user/month → $445/month for 5 devs, $890/month for 10 |

**MinIO licensing nuance:** AGPLv3 means if you are distributing software that includes MinIO or offering it as a hosted service, AGPL obligations apply to the combined work. For internal dev/CI usage where MinIO runs on your own infrastructure and is not distributed to third parties, the practical exposure is lower—but legal review is warranted for any commercial team. MinIO's distribution state is also in transition: the `minio/minio` Docker Hub repository is archived; use `quay.io/minio/minio` for the maintained image.

**CI runner cost:** LocalStack's new pricing appears seat-based, not runner-based. CI credits were removed. Whether CI runners require their own seats or operate under a shared service-account model was not definitively resolved in reviewed materials. This ambiguity could materially change cost projections for teams with high CI parallelism.

---

### 8. CloudFormation, Terraform, and CDK Coverage

CloudFormation support is weak across the entire OSS field.

- **MiniStack:** 12 explicitly supported resource types, documented failures for others with `CREATE_FAILED`. Covers basic Lambda, DynamoDB, S3, SQS resources. Terraform claims (including full VPC module support) are maintainer-authored with limited external validation.
- **Floci:** Also states "CloudFormation 12" resource types. Ships `compat-terraform` (14 tests) and `compat-opentofu` (14 tests). Fixed at least one real Terraform AWS provider v6 compatibility issue. The compatibility test counts are too low to provide strong confidence for non-trivial Terraform modules, but the intent and mechanism are more explicit than MiniStack.
- **Moto:** Materially broader CloudFormation resource support than either of the above, with a documented resource matrix spanning many service categories. Still partial—not full semantic parity with AWS CloudFormation—but in a different class than MiniStack and Floci's 12-type lists.

**For teams directly testing IaC (CloudFormation templates, complex Terraform modules), Moto is the only OSS option with a credible story, and even Moto is not a complete solution.** For app-level tests that use CloudFormation only to provision test fixtures (a Lambda function, an SQS queue), MiniStack or Floci may be adequate given their 12-type coverage includes the most common primitives.

---

## Decision Framework

### Use MiniStack when:
- You are migrating from LocalStack and want minimum friction at the endpoint and credential level
- Your service needs are S3 + SQS + Lambda + DynamoDB + API Gateway (no CloudFormation templates)
- You need multi-service emulation in a single container with state reset between test suites
- You are not in Java (no first-class Testcontainers module) and will build your own container wrapper
- You have bandwidth to validate MiniStack's claims against your actual workflows before committing

**Do not use MiniStack when:** CloudFormation is in scope; you need high confidence in vendor sustainability (personal project, ~9 contributors); you need verified SigV4 enforcement; or you need Testcontainers modules in any language.

---

### Use Floci when:
- You are a Java shop and the Testcontainers module materially reduces your migration effort
- You need the lowest CI resource footprint of any multi-service emulator (13 MiB idle, 24 ms startup—if those vendor numbers hold)
- You need explicit Terraform/CDK compatibility tests as a starting point
- You are comfortable that vendor-published compatibility numbers are unverified and will run your own validation

**Do not use Floci when:** You need non-Java Testcontainers support; you need institutional backing guarantees (effectively single-founder project in a personal namespace); you need SigV4 enforcement for S3/SQS/SNS/DynamoDB; or CDK asset publishing is critical and you cannot absorb the known SDK rejection issues.

---

### Use Moto when:
- Your tests are primarily Python and you can use the decorator-based or in-process server model
- You need the broadest CloudFormation resource support in OSS
- You need low bus-factor and maximum community transparency about limitations
- You need IAM-breadth testing (Moto's IAM coverage is strong, though auth is off by default)
- You want documented, honest limitation maps rather than optimistic compatibility claims

**Do not use Moto when:** You need a black-box LocalStack-style endpoint for non-Python infrastructure (CDK, Terraform workflows, language-agnostic CI); you need API Gateway `AWS_PROXY` support; or you need auth realism without significant configuration.

---

### Use ElasticMQ when:
- Your bottleneck is SQS semantics only (FIFO, DLQs, visibility timeout, delays, message persistence)
- You want the simplest, most stable option for queue-heavy pipelines
- You need institutional backing (SoftwareMill) or commercial support availability
- You are using Rust (typed Testcontainers module available)

**Do not use ElasticMQ when:** You need any other AWS service alongside SQS.

---

### Use MinIO when:
- S3 is your primary concern and you need real SigV4 enforcement (catching auth regressions, presigned URL expiry)
- You need virtual-host-style S3 addressing (S3Mock does not support this)
- You need multipart uploads, bucket versioning, object lock, or lifecycle policies in single-container mode
- Your team is comfortable with AGPLv3 (or has a commercial license for distribution scenarios)

**Do not use MinIO when:** You need IAM policy semantics—MinIO's IAM model is its own system, not AWS IAM; it has removed ACL support entirely (`PutObjectAcl`, `GetObjectAcl`, `PutBucketAcl`, `GetBucketAcl` all fail); or you need any service other than S3.

---

### Use Adobe S3Mock when:
- You need a simple, honest, test-only S3 fake with no intent to validate auth behavior
- Your SDK uses path-style addressing and you do not need virtual-host style
- You want JUnit 5 native integration and a permissive Apache 2.0 license with clear documented limitations

**Do not use S3Mock when:** You need to catch presigned URL or signature bugs (it explicitly does not validate them); you need virtual-host-style addressing; or you need S3 versioning, object lock, or multipart behavior.

---

### Consider staying on LocalStack when:
- Your team needs CloudFormation fidelity (LocalStack Pro has meaningfully broader coverage)
- You depend on CDK bootstrap, `cdklocal`, or `samlocal` wrappers
- You need Transparent Endpoint Injection or `localhost.localstack.cloud` DNS behavior
- Your team uses LocalStack's official Testcontainers module and non-Python stacks
- The seat cost ($39/user/month Base) is acceptable relative to migration engineering cost and validation risk

---

## Recommendations, Ranked by Confidence

### Confidence: High

**1. For SQS-only pipelines, use ElasticMQ.**
It is the most stable, operationally complete, and best-documented OSS SQS emulator. Apache 2.0 licensed, backed by SoftwareMill, native image starts in milliseconds at ~31 MB. No multi-service ambition, no CloudFormation claims, no marketing inflation.

**2. For S3-focused pipelines where auth fidelity matters, use MinIO.**
`quay.io/minio/minio` is the maintained image. MinIO validates SigV4 in ways that can catch real auth bugs. It has the broadest Testcontainers support (Java, Go, .NET, Python, Node.js, Rust). Clarify AGPLv3 obligations with legal before adoption in commercial distribution scenarios. Note: ACL APIs are not supported; use IAM policies instead.

**3. Do not use S3Mock as an auth-validation gate.**
Its explicit non-validation of presigned URL expiry and signatures means auth regressions pass locally and fail on AWS. It remains a valid functional fake for CRUD-focused integration tests.

---

### Confidence: Medium

**4. For Python-first teams needing broad multi-service coverage, use Moto.**
It is the most mature OSS option by every governance metric, has the most honest limitation documentation, and its CloudFormation coverage is the only credible OSS option for non-trivial IaC testing. Disable auth by default means SigV4 bugs will not be caught. Explicitly document this limitation in your test suite runbooks.

**5. For Java shops migrating away from LocalStack, pilot Floci first over MiniStack.**
The Java Testcontainers module (`FlociContainer`, v2.0.0) meaningfully reduces boilerplate versus MiniStack's generic-container requirement. The published compatibility suite (Terraform 14 tests, CDK 5 tests) establishes a baseline to extend. Validate the specific S3 behaviors (CDK asset publishing, path-style vs. virtual-host) and DynamoDB GSI attribute returns against your actual test code before promoting to production CI.

---

### Confidence: Low

**6. For non-Java, non-Python teams needing a multi-service black-box emulator, evaluate MiniStack.**
It is operationally closest to LocalStack (same port, same credential pattern, same health endpoint), has a reset endpoint useful for CI state management, and covers the common service set. But: it appears to be a solo personal project, has minimal external validation, and all performance claims are vendor-published. **Treat it as a provisional choice pending direct validation of your specific workflows.** Do not adopt it for production CI without running your own integration tests against the failure modes you care about.

**7. Avoid any OSS option for CDK bootstrap in production CI without hands-on validation.**
No tool in this set has publicly demonstrated reliable CDK bootstrap and asset publishing. Floci has 5 CDK compatibility tests and a known S3 asset-publishing defect in public issues. MiniStack has endpoint guidance but no CDK-specific test suite. Moto's server-mode CloudFormation is partial. This is the highest-risk migration path in the OSS alternatives.

---

## Known Gaps and Areas for Further Investigation

The following questions were identified but not resolved in this research. Each represents a material unknown for production adoption decisions.

**1. LocalStack Community Edition as a baseline**
LocalStack's Hobby tier remains technically usable for CI (not for commercial software development per their terms). The comparative behavior of LocalStack Community Edition vs. MiniStack/Floci on identical test suites was never directly measured. Without this baseline, it is impossible to quantify the fidelity regression from migration.

**2. S3 virtual-host-style behavior and presigned URL validation across emulators**
AWS SDK v3+ defaults to virtual-host-style S3 addressing. S3Mock does not support it. Floci and MiniStack's virtual-host behavior is undocumented in reviewed materials. This is a day-one compatibility concern for teams with modern SDK defaults.

**3. Chunked uploads, checksum headers, and SDK v3+ defaults**
AWS SDKs have progressively added `x-amz-checksum-*` headers, `aws-chunked` transfer encoding, and S3 Express One Zone semantics. None of the OSS tools' compatibility with these newer SDK defaults was evaluated.

**4. MinIO's "source code only" vs. `quay.io/minio/minio` contradiction**
The research reviewed conflicting signals: MinIO's GitHub README describing the community edition as "source code only" while separately documenting `quay.io/minio/minio` as the stable container path. Verify directly which statement reflects current distribution policy before making a final MinIO recommendation.

**5. Moto's current auth behavior against latest docs**
The Moto auth behavior (auth defaults to infinity) was cited from docs pinned to v5.0.21. Verify this behavior against the current v5.1.x release before presenting it as current fact. Auth behavior is exactly the kind of thing that changes between releases.

**6. Parallel test sharding and state isolation**
No tool's behavior under concurrent test sharding was systematically evaluated. Moto explicitly warns about shared-state leakage between parallel tests. ElasticMQ isolates cleanly by separate container or persisted path. Floci's storage modes may provide isolation paths. MiniStack's reset endpoint is sequential by design. For teams running parallel CI jobs against a shared emulator container, this is a first-order operational concern.

**7. MinIO ACL and IAM model divergence**
MinIO has removed bucket and object ACL support entirely. Applications using `PutObjectAcl`, `GetObjectAcl`, `PutBucketAcl`, or `GetBucketAcl` will fail against MinIO. Additionally, MinIO's IAM model is its own system, not AWS IAM, and STS assume-role flows may behave differently. Evaluate against your specific access control patterns before committing.

**8. AWS SAM CLI and Testcontainers as complementary approaches**
AWS SAM CLI (`sam local`) was not evaluated. For Lambda-heavy workflows where local invocation fidelity matters more than multi-service breadth, SAM CLI may outperform any emulator in this set. Similarly, Testcontainers' composability (running real AWS service Docker images, or combining point tools per service) as an architecture was not evaluated against the all-in-one emulator approach.

**9. Floci's ElastiCache and RDS Testcontainers module gap**
The Floci Java Testcontainers module is noted to not fully support Floci's ElastiCache and RDS services. This was inferred from the module repository but not verified with a direct quote or issue link. Verify current module state before relying on ElastiCache/RDS through the Floci Testcontainers integration.

**10. fake-s3 licensing status**
The original analysis concluded fake-s3 required a commercial license, but peer review argued the wrong project or fork may have been analyzed. The Ruby `fake-s3` gem's canonical licensing status was not definitively resolved.

---

*Research completed April 8, 2026. Tool versions, pricing, and licensing terms change frequently; verify all figures against current sources before making adoption decisions.*