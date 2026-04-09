Open-source replacements for LocalStack across the eight named AWS services were scarce in April 2026. The only plausible multi-service OSS candidates identified were MiniStack, Floci, and Moto. Everything else was either single-service, such as ElasticMQ for SQS, S3Mock for S3, and Dynalite for DynamoDB, or not clearly recommendable as open source for commercial teams, as with the initially reviewed fake-s3 licensing situation, which later became unresolved because the analysis may have examined the wrong project or a fork. There was also no credible maintained OSS project called `localstack-free`; search results mostly pointed back to LocalStack’s own materials.

A useful early directional read for the core eight services was:
- MiniStack: strong partial support for S3, SQS, Lambda, DynamoDB, API Gateway; weaker partial support for SNS, IAM, CloudFormation.
- Floci: similar breadth, with strong partial support for S3, SQS, Lambda, DynamoDB, API Gateway; moderate-to-strong partial for SNS and IAM; moderate partial for CloudFormation.
- Moto: strongest on S3, SQS, SNS, DynamoDB, IAM; weaker on Lambda and CloudFormation; weakest fit on API Gateway.
- ElasticMQ: SQS only.
- S3Mock: S3 only.
- Dynalite: DynamoDB only and aging.
- fake-s3: S3 only, but licensing conclusions were later challenged.

That first coverage table was criticized because terms like “high partial” and “medium partial” were never defined, which made the ratings look more precise than they were. Reviewers also argued that service coverage and product class were being mixed together. Moto is primarily a Python mocking framework with server mode, while MiniStack and Floci are trying to behave more like LocalStack-style black-box network emulators.

On breadth and operational shape, MiniStack was presented as the broadest OSS “single endpoint on `:4566`” alternative. Its docs claimed 38 AWS services, 900+ tests, startup under 2 seconds, about 30 MB idle RAM, and roughly 200-250 MB image size, while one Docker Hub view showed a 26.02 MB compressed tag. Public docs listed support for S3, SQS, SNS, DynamoDB, Lambda, API Gateway v1/v2, IAM/STS, and CloudFormation. Lambda coverage included Python and Node execution, Docker-backed provided runtimes, and event source mappings. API Gateway coverage included v1 and v2 data-plane routing. It also exposed LocalStack-compatible health endpoints and a reset endpoint, which is useful for CI orchestration. The major limitation was CloudFormation: only 12 resource types were explicitly supported. Peer review argued this was badly underweighted because AWS CloudFormation supports well over a thousand types, so MiniStack is not credible for non-trivial IaC fidelity despite looking attractive for app-level integration flows.

Floci appeared narrower on total service count but stronger on published compatibility detail and CI footprint. Its README cited 28 services, 1,873 automated compatibility tests, 408/408 SDK compatibility tests, 24 ms startup, 13 MiB idle RAM, and about 90 MB image size; Docker Hub showed roughly 69 MB compressed. Floci published unusually explicit operation counts per service: S3 30 ops, SQS 17, SNS 13, DynamoDB 22, Lambda 25, API Gateway REST 24, API Gateway v2 16, IAM 65+, CloudFormation 12. It also published per-suite pass counts like S3 23/23, S3 Object Lock 30/30, S3 Advanced 13/13, DynamoDB Streams 12/12, API Gateway REST 43/43, API Gateway v2 5/5, STS 18/18, IAM 32/32. On paper, that made Floci the strongest candidate for a lightweight single-container CI emulator.

The problem was evidence quality. Reviewers noted that Floci’s strongest evidence was self-published, likely maintainer-authored, so the research effectively rewarded it for publishing the most favorable internal numbers. The meaning of 408/408 versus 1,873 tests was never clearly explained. Passing a vendor-controlled compatibility suite is not the same as independent validation. Public issues already showed operationally important cracks: S3 responses rejected by the AWS SDK, breaking CDK asset publishing; leading-slash S3 keys being stripped and colliding; and DynamoDB `DescribeTable` for GSIs omitting non-key attributes. Those kinds of bugs can break real pipelines even when headline compatibility numbers look excellent.

Moto was consistently the most mature and transparent option. PyPI showed version 5.1.22 released on March 8, 2026; GitHub showed roughly 8.1k-8.4k stars and a long release history. Moto supports all eight core services and explicitly documents implemented versus missing operations. Its strengths were S3, SQS, SNS, DynamoDB, IAM, and a much broader CloudFormation story than MiniStack or Floci. But its fit as a LocalStack replacement is weaker because of product class, not because of breadth. Moto is strongest as a Python mocking library and only secondarily as a server-mode black-box emulator. Its API Gateway limitations were serious for LocalStack-like workflows: for REST APIs, only HTTP integrations and AWS integrations with DynamoDB were documented as supported, while `AWS_PROXY`, `MOCK`, and others were ignored in the cited docs, and mocked public URLs only worked in decorator mode, not server mode. Lambda realism was also limited: Docker-backed invocation exists, but lambdas created under decorators cannot reach Moto state unless MotoServer or MotoProxy is used in a reachable setup. Other documented gaps included no Function URL support, no image-package invocation, partial CloudFormation behavior, missing pagination in some DynamoDB PartiQL and CloudFormation paths, and real divergence bugs such as S3 notifications not URL-encoding keys like AWS and valid DynamoDB update expressions failing.

A key meta-point was that Moto’s flaws are unusually visible because the project is old, honest, and widely used. The research even described Moto as “the most honest source.” Peer review pushed back on treating documented limitations as a weakness while letting younger tools benefit from silence. Moto may look “messier” partly because more users have already found and reported edge cases.

Among point tools, ElasticMQ stood out as a strong SQS-only option. It supports FIFO, DLQs, delays, visibility timeout, tags, persistence, Docker images, and a `/health` endpoint. Docker Hub showed 10M+ pulls. The JVM image was around 226 MB compressed or ~240 MB in docs, while the native image was about 31 MB compressed or ~30 MB in docs. Official documentation described native startup in milliseconds. For queue-heavy pipelines that only need SQS semantics, ElasticMQ looked simpler and likely more stable than running a full AWS emulator.

For S3-only testing, Adobe S3Mock was initially treated as the best OSS option. It supports Docker, Testcontainers, and JUnit, and documents supported versus unsupported operations clearly. Important caveats: it only supports path-style addressing and accepts presigned URLs without fully validating them, so it is fine for integration testing but not for exact security-behavior validation. Peer review flagged a major omission here: MinIO was missing entirely, which was a serious gap because MinIO is widely deployed, Apache 2.0 licensed, and one of the most important S3-compatible systems in practice.

On fake-s3, the original analysis concluded it was no longer a clean OSS recommendation for commercial teams because the reviewed project required a license key and priced organization use from $25/year to $1,250/year. Peer review argued the research probably analyzed the wrong project, conflating another repo or fork with the canonical Ruby fake-s3. That means the negative conclusion on fake-s3 remains unresolved.

LocalStack’s business context mattered. LocalStack announced on February 27, 2026 that Community support would end, and on March 23, 2026 it moved to a unified image requiring an auth token. Current pricing was Base at $39/user/month billed annually and Ultimate at $89/user/month billed annually, with temporary promotions lowering Base to $23 annually or $27 monthly through April 30, 2026. The free tier was now labeled Hobby, remained technically usable for CI, but was not valid for commercial software development. CI credits were removed from pricing, so cost is now primarily seat-based, not runner-based. However, there was still ambiguity around whether CI runners require their own seats or operate under shared service-account assumptions, which could materially change cost.

For a 5-10 developer team, published LocalStack costs worked out roughly as:
- Base annual list: $195/month for 5 devs, $390/month for 10.
- Base annual promo: $115/month for 5, $230/month for 10.
- Base monthly promo: $135/month for 5, $270/month for 10.
- Base monthly non-promo: $225/month for 5, $450/month for 10.
- Ultimate annual: $445/month for 5, $890/month for 10.
- Ultimate monthly via AWS Marketplace: $535/month for 5, $1,070/month for 10.

By contrast, MiniStack, Floci, Moto, ElasticMQ, and S3Mock were permissively licensed OSS tools with effectively $0 software licensing cost for developers and CI runners. Their cost is operational: compute, RAM, CI minutes, and engineering effort to validate fidelity or combine specialized tools.

The research’s workload prioritization for most teams was:
1. S3 + SQS + Lambda + DynamoDB first.
2. SNS next.
3. API Gateway for full HTTP flows.
4. IAM/STS for auth-sensitive code.
5. CloudFormation only if you are directly testing IaC.

Against that profile, the first practical recommendation was:
- MiniStack covers the common integration set in one tool.
- Floci also covers it and appears better on CI footprint.
- Moto covers it but is better for framework-led mocking than “run local AWS and hit it like AWS.”
- ElasticMQ + S3Mock + Dynalite can cover many storage/queue/table-heavy pipelines if you do not need Lambda, API Gateway, or IAM realism.

That recommendation was later softened heavily. Reviewers noted that MiniStack and Floci lacked independent adoption evidence relative to how strongly they were being recommended, both appeared founder-led and high bus-factor, their strongest claims were project-controlled, and important baselines were missing from the analysis: LocalStack Community Edition as a direct baseline, AWS SAM CLI, MinIO, and Testcontainers integration. Most importantly, cross-service fidelity under real failure modes remained largely unverified.

On maintenance and sustainability, the strongest conclusion was that Moto is the lowest-risk maintenance choice, ElasticMQ has decent institutional backing but narrow staffing, and MiniStack/Floci are high-velocity but high bus-factor bets. Reported activity signals were:
- MiniStack: about 1.8k stars, around 9 contributors, apparently individual-led.
- Floci: about 3.0k stars, effectively single-founder despite org branding.
- Moto: about 8.4k stars, about 1,150 contributors, plus OpenCollective and GitHub Sponsors.
- ElasticMQ: about 2.8k stars, 15 PR authors, backed by SoftwareMill, which offers commercial support.

Release cadence reflected that split:
- MiniStack released v1.1.46 through v1.1.51 between April 7 and April 8, 2026.
- Floci released 1.3.0 on April 6 and 1.4.0 on April 8, 2026.
- Moto released 5.1.20 on January 17, 5.1.21 on February 8, and 5.1.22 on March 8, 2026.
- ElasticMQ released v1.6.16 on February 16, 2026 after v1.6.15 on September 22, 2025.

The original interpretation was that MiniStack and Floci were impressively responsive but still in rapid formation; Moto looked mature and predictable; ElasticMQ looked active but maintenance-oriented. Peer review agreed directionally but flagged some issue-tracker metrics as non-comparable or stale.

On footprint and runtime characteristics, Floci had the strongest published story for a full multi-service emulator, MiniStack looked lightweight but internally inconsistent, Moto server lacked good official benchmarks, and ElasticMQ native was the clear efficiency winner if SQS alone was enough. Published figures were:
- MiniStack: 26.02 MB compressed on Docker Hub vs ~200-250 MB in docs; startup under 2s or elsewhere <1s; ~30-40 MB idle RAM.
- Floci: 69 MB compressed vs ~90 MB in docs; ~24 ms startup; ~13 MiB idle RAM; 289 Lambda req/s and 2 ms warm latency.
- Moto server: 96.69 MB compressed, with no solid official startup or memory figures.
- ElasticMQ JVM: 226.08 MB compressed or ~240 MB in docs; startup in seconds.
- ElasticMQ native: 31.08 MB compressed or ~30 MB in docs; startup in milliseconds.

Community examples complicated these claims. MiniStack CI examples used `sleep 2` before health checks. A Floci migration article also used `sleep 2` despite the 24 ms startup claim. Moto community examples used `sleep 5`, though reviewers noted those were service-specific and should not be generalized. ElasticMQ native was described as fast but without comparably rigorous CI benchmarks. Peer review warned that several of these comparisons were apples-to-oranges: binary startup versus full Docker cold-start, compressed image size versus installed size, and workload-specific throughput numbers.

On CI/CD integration, the broad pattern across MiniStack, Floci, Moto server, and ElasticMQ was still “start a container, wait until ready, then seed resources or run tests.” The tools differed in readiness, reset, persistence, and isolation support.

MiniStack had the most CI-oriented control surface among the multi-service newcomers. It documented health endpoints at `/_ministack/health`, `/_localstack/health`, and `/health`, plus a reset endpoint at `/_ministack/reset`, explicitly positioned for CI and test suites. A maintainer-authored GitHub Actions example used `docker run -d -p 4566:4566`, `sleep 2`, and a health probe. That made MiniStack operationally attractive for CI, especially because state can be reset without restarting the container. The weakness was documentation maturity: no strong first-party GitHub Actions, GitLab, or Jenkins cookbook beyond simple examples.

Floci looked strong on persistence and networking controls but weaker on published CI workflows. It documented storage modes (`memory`, `persistent`, `hybrid`, `wal`), a persistent path, and `FLOCI_HOSTNAME` for correct returned URLs in multi-container setups. Those are directly relevant to CI service-container topologies. But the reviewed material did not clearly surface a documented health endpoint or reset endpoint, and no strong first-party GitHub Actions, GitLab, or Jenkins guidance was found. Community examples still relied on `sleep 2`.

Moto had the clearest documented mechanics for deterministic testing, but mostly in Python/test-harness terms rather than platform-branded CI recipes. Server-mode docs covered Docker, `ThreadedMotoServer(port=0)` for random free ports, teardown, reset API, and a `TEST_SERVER_MODE` pattern. Moto’s own contributing docs also warned that parallel tests can leak shared-state effects unless resource names are unique. That is useful evidence about operational behavior, but peer review correctly noted it is contributor guidance, not directly end-user CI documentation.

ElasticMQ had the strongest operational docs among point tools: `/health`, queue pre-creation via config, auto-create-on-demand, persisted metadata, full message persistence via H2, and URL-generation controls for containerized deployments. If you need SQS only, ElasticMQ had the cleanest pre-seeding and restart-persistence story.

Across all tools, the main CI failure modes were startup races, port conflicts, shared-state leakage, incorrect returned hostnames, and resource limits. MiniStack and Floci examples both leaned on fixed sleeps. Moto explicitly documented random-port allocation. ElasticMQ documented node-address tuning. MiniStack had a reset endpoint for wiping state between test suites. Moto documented reset patterns and name-collision caveats. Floci’s main mitigation was storage-mode control and hostname configuration. ElasticMQ isolated cleanly through separate containers or persisted state paths.

For migration away from LocalStack, the first real cost was removing LocalStack-specific glue rather than just swapping service behavior. Existing LocalStack setups often depend on auth tokens, internal endpoints like `/_localstack/health` and `/_aws/...`, wrappers such as `awslocal`, `tflocal`, `cdklocal`, and `samlocal`, and sometimes Transparent Endpoint Injection or `localhost.localstack.cloud` DNS behavior. None of MiniStack, Floci, or Moto showed an equivalent to LocalStack’s DNS interception in the reviewed material.

MiniStack appeared closest to LocalStack operationally:
- same `http://localhost:4566`
- same dummy credentials and region pattern
- explicit support for `/_localstack/health`
- explicit Terraform endpoint examples
- simple CDK guidance via `AWS_ENDPOINT_URL`
This likely makes MiniStack the lowest-friction migration target at the control-plane level, though not necessarily at the fidelity level.

Floci also uses `:4566`, accepts dummy creds, and positions itself as a drop-in replacement, but practical caveats included `forcePathStyle: true` in S3 examples and `FLOCI_HOSTNAME` for correct multi-container URLs. That means migration can be tiny if a project already uses plain endpoint overrides, but less trivial if it relied on LocalStack wrappers or DNS behavior. The “zero lines of application code” marketing claim looked overstated in light of those caveats.

Moto is not a LocalStack drop-in. Its default port is 5000, control APIs live under `/moto-api/`, and its testing model is different enough that many LocalStack-based harnesses would need real edits. For Python-first teams that may be acceptable or even preferable; for CDK, Terraform-heavy, or non-Python black-box flows, migration effort is much higher.

For Terraform, Floci had the best published evidence because it explicitly ships named compatibility suites (`compat-terraform` 14 tests, `compat-opentofu` 14 tests, `compat-cdk` 5 tests) and had already fixed a real Terraform AWS provider v6 compatibility issue. But 14 tests is a very low bar for Terraform confidence. MiniStack also made strong Terraform claims, including AWS provider v5/v6 support and a fully supported `terraform-aws-modules/vpc/aws` module v6.6.0 with 23 resources, but almost all of that evidence was maintainer-authored. Moto can work with Terraform through endpoint overrides, but it has no published compatibility suite and remains weaker for end-to-end provider-parity claims.

For CDK bootstrap and asset publishing, none of the OSS options looked proven. MiniStack mostly had claims plus a generic endpoint override. Floci at least had 5 CDK compatibility tests, but public reports still suggested CDK/S3 asset issues. Moto looked weakest for CDK bootstrap because CloudFormation, S3 semantics, and server-mode caveats make “realistic deploy and invoke” workflows fragile.

CloudFormation was weak almost everywhere. MiniStack explicitly supports only 12 resource types and fails unsupported ones with `CREATE_FAILED`. Floci also repeatedly states “CloudFormation 12” but, in the reviewed material, did not clearly enumerate which 12 types. Moto is in a different class on CloudFormation breadth, with a much larger documented resource-support matrix spanning far more services, though still without full semantic parity. So the trade-off is stark: MiniStack and Floci look more LocalStack-like operationally, but Moto has the broader and more auditable CloudFormation story.

The most defensible bottom line was not that Floci or MiniStack are proven LocalStack replacements. It was:
- There are only a few plausible OSS multi-service alternatives: MiniStack, Floci, and Moto.
- MiniStack and Floci are operationally closer to LocalStack because they expose a single endpoint and target black-box local-cloud workflows.
- Moto is the most mature, transparent, and lowest bus-factor option, but its best fit is still as a Python mocking framework or carefully used server target, not as a direct LocalStack substitute.
- ElasticMQ is the best OSS answer if SQS alone solves the problem.
- S3Mock is a credible S3-only testing tool, but MinIO should have been in the comparison.
- CloudFormation remains weak in MiniStack and Floci and partial in Moto.
- IAM support across tools is probably sufficient for happy-path auth but not exact security validation.
- Evidence quality is asymmetric: Moto’s flaws are documented because it has years of public usage; MiniStack and Floci may look cleaner partly because they are newer and less independently audited.
- Major omissions remain: MinIO, AWS SAM CLI, LocalStack Community as a baseline, Testcontainers patterns, and direct validation of cross-service failure-mode fidelity.

So the practical recommendation is cautious:
- For black-box multi-service local AWS in dev/CI, evaluate Floci and MiniStack first.
- For lower maintenance risk and explicit limitations, use Moto if your test style fits it.
- For service-specific needs, point tools such as ElasticMQ, S3Mock, and likely MinIO may be better engineering choices than any all-in-one emulator.
- Any adoption of Floci or MiniStack should include direct validation of the exact flows that matter to you: S3/CDK uploads, SQS delivery semantics, Lambda event-source behavior, API Gateway integration types, returned URL correctness in containerized CI, and CloudFormation template/resource coverage.

## MinIO as S3-compatible replacement and Testcontainers integration patterns across all candidates

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

## SigV4 signing and SDK compatibility under real AWS SDKs

### Findings

Across this dimension, the field splits into two classes.

First, the broad multi-service emulators, especially **MiniStack**, **Floci**, and **Moto**, appear to prioritize “accept real AWS SDK calls” over “enforce AWS-like SigV4 failures.” Second, the point tools that only emulate one service, especially **MinIO** for S3, are materially stronger on real signature validation.

For the four target services under real SDKs:

- **MiniStack**
  - I found no public documentation or issue evidence that MiniStack validates SigV4 for **S3, SQS, SNS, or DynamoDB**.
  - Its docs consistently show dummy credentials (`test` / `test`) and Terraform with `skip_credentials_validation = true`, while marketing says “works with boto3, AWS CLI, Terraform, CDK, Pulumi.” That is evidence of **SDK interoperability**, not of signature enforcement. This is an inference, but a strong one: MiniStack likely accepts signed SDK requests without meaningfully validating SigV4 on these core services. Sources: [MiniStack homepage](https://ministack.org/), [MiniStack getting started](https://www.ministack.org/getting-started.html), [Docker Hub](https://hub.docker.com/r/nahuelnucera/ministack).
  - I also found essentially no public issue trail about SigV4, presigned URLs, or SDK incompatibilities. For an architect, that is not reassuring evidence of correctness; it is mostly evidence of **low external scrutiny**.

- **Floci**
  - Floci publishes strong compatibility claims, but its public SigV4 claim is narrow: it explicitly says **Lambda, ElastiCache, and RDS** support “full IAM authentication and SigV4 validation.” It does **not** make the same explicit claim for **S3, SQS, SNS, or DynamoDB**. That matters. Sources: [floci.io](https://floci.io/), [Hector Ventura project page](https://hectorvent.dev/projects/).
  - For S3/SQS/SNS/DynamoDB, the available evidence supports “real SDK happy-path compatibility” more than “strict auth validation.” Floci advertises **408/408 SDK compatibility checks**, but that is vendor-published and unverified externally. Source: [floci.io](https://floci.io/).
  - There is already public evidence of SDK-compatibility defects even in this young project: recent releases fixed missing AWS request-id headers “for sdk compatibility,” fixed missing `versionId` in `CompleteMultipartUpload`, fixed SQS Query-to-JSON error translation, and fixed DynamoDB expression behavior. These are exactly the sorts of bugs that break real applications even when basic CRUD works. Sources: [floci 1.2.0 release notes](https://newreleases.io/project/github/floci-io/floci/release/1.2.0), [floci 1.1.0 release notes](https://newreleases.io/project/github/floci-io/floci/release/1.1.0), [floci 1.0.10 release notes](https://newreleases.io/project/github/floci-io/floci/release/1.0.10).
  - On current public evidence, I would not assume Floci rejects invalid or expired S3 presigned URLs the way AWS does. I did not find documentation saying it does.

- **Moto**
  - Moto is the clearest case of a broad emulator that is **not auth-realistic by default**. Moto documents that IAM-like auth is optional, “very basic,” and if `INITIAL_NO_AUTH_ACTION_COUNT` is unset, it “defaults to infinity,” meaning Moto will **never perform any authentication at all**. Sources: [Moto IAM docs](https://docs.getmoto.org/en/5.0.21/docs/iam.html), [Moto server mode docs](https://docs.getmoto.org/en/latest/docs/server_mode.html).
  - So for **S3, SQS, SNS, and DynamoDB under boto3 / Java / Go**, Moto is generally good for black-box SDK traffic, but by default it is **not validating SigV4**. Invalid signatures and expired presigned URLs are therefore a real local-vs-AWS risk unless you explicitly add auth checks elsewhere.
  - Moto also has documented behavior mismatches that can break real code:
    - S3 notifications were emitting object keys without AWS’s required URL encoding. Source: [moto issue #9054](https://github.com/getmoto/moto/issues/9054)
    - DynamoDB `UpdateItem` had a regression where valid AWS expressions failed locally with `ValidationException`. Source: [moto issue #8740](https://github.com/getmoto/moto/issues/8740)

- **MinIO**
  - MinIO is the strongest open-source option here for **real S3 SigV4 behavior**. Its docs say clients must authenticate each operation using **AWS Signature Version 4**, and presigned URLs are a first-class feature with explicit expiry. Sources: [MinIO IAM docs](https://min.io/docs/minio/macos/administration/identity-access-management.html), [MinIO concepts docs](https://min.io/docs/minio/container/administration/concepts.html), [MinIO `mc share`](https://min.io/docs/minio/linux/reference/minio-mc/mc-share.html).
  - Unlike S3Mock, MinIO does reject bad signatures in practice. There are multiple historical compatibility bugs where AWS SDK-generated presigned URLs were rejected with `SignatureDoesNotMatch`, including boto3-based examples and AWS SDK for Java endpoint/presigner combinations. Sources: [minio issue #9564](https://github.com/minio/minio/issues/9564), [minio issue #10361](https://github.com/minio/minio/issues/10361), [aws-sdk-java-v2 issue #4697](https://github.com/aws/aws-sdk-java-v2/issues/4697), [aws-sdk-java-v2 issue #6123](https://github.com/aws/aws-sdk-java-v2/issues/6123).
  - That means MinIO is better than most emulators for catching auth bugs, but it is still not perfect: SDK or endpoint-resolution changes can create **MinIO-only failures** that do not reproduce on AWS.

- **S3Mock**
  - S3Mock is explicit: presigned URLs are **accepted but not validated**. It does not check expiration, signature, or HTTP verb. It is also **path-style only**. Source: [S3Mock README](https://github.com/adobe/S3Mock).
  - This is the clearest example of a local tool that can produce **false confidence**: invalid or expired presigned URLs can pass locally and fail on AWS.
  - The project supports AWS SDK for Java v2 and publishes examples, but that is transport compatibility, not security fidelity. Source: [S3Mock README](https://github.com/adobe/S3Mock).

- **ElasticMQ**
  - ElasticMQ is SQS-only. Its docs show use with dummy credentials and focus on SQS semantics, not auth validation. I found no public evidence that it performs meaningful SigV4 validation. Sources: [ElasticMQ README](https://github.com/softwaremill/elasticmq), [Rust Testcontainers module docs](https://docs.rs/testcontainers-modules/latest/testcontainers_modules/elasticmq/struct.ElasticMq.html).
  - In practice, the safest assumption is that ElasticMQ is good for queue semantics and SDK wiring, but **not** for validating AWS-style auth failures.

#### Direct answers to the key questions

- **Does each emulator correctly handle SigV4 request-signing validation for S3, SQS, SNS, and DynamoDB under boto3, Java v2, and Go v2?**
  - **MinIO**: yes for **S3 only**, with real validation; no relevance for SQS/SNS/DynamoDB.
  - **S3Mock**: no for S3 presigned URL validation.
  - **Moto**: not by default; auth is off unless configured, and even then it is “very basic.”
  - **ElasticMQ**: no public evidence of strict SigV4 validation.
  - **MiniStack**: no public evidence of strict SigV4 validation.
  - **Floci**: no public evidence of strict SigV4 validation for S3/SQS/SNS/DynamoDB specifically; explicit SigV4 claims are for other services.

- **Which emulators accept or reject invalid/expired presigned URLs?**
  - **S3Mock**: explicitly accepts them.
  - **Moto**: likely accepts many cases by default because auth is off; this is an inference from its auth model.
  - **MinIO**: designed to reject invalid signatures and expired URLs; public issues show real rejection on mismatch cases.
  - **MiniStack / Floci**: I did not find authoritative evidence either way; this is a material gap.
  - **ElasticMQ**: not applicable; SQS presigned URL usage is not the normal concern here.

- **Are there documented SDK compatibility bugs that break real code even when the happy path works?**
  - **Yes** for Floci, Moto, and MinIO.
  - **S3Mock** documents its biggest divergence openly.
  - **MiniStack** has too little public issue history to conclude much; that is a risk in itself, not a strength.

### Evidence

Concrete data points most relevant to this dimension:

- **Moto auth default**
  - If `INITIAL_NO_AUTH_ACTION_COUNT` is unset, Moto auth “defaults to infinity,” so it never authenticates requests. Source: [Moto IAM docs](https://docs.getmoto.org/en/5.0.21/docs/iam.html)
- **S3Mock presigned URL behavior**
  - “Presigned URLs: Accepted but not validated (expiration, signature, HTTP verb not checked).” Source: [S3Mock README](https://github.com/adobe/S3Mock)
- **S3Mock endpoint shape**
  - HTTP `9090`, HTTPS `9191`, path-style only. Source: [S3Mock README](https://github.com/adobe/S3Mock)
- **Floci compatibility claims**
  - Vendor-reported **408/408 SDK compatibility tests**, **24 ms** startup, **13 MiB** idle memory, **~90 MB** image. Source: [floci.io](https://floci.io/)
- **MiniStack compatibility claims**
  - Vendor-reported **900+ tests**, **~2 s** startup, **~30 MB** idle RAM, Docker Hub tag size about **25.1 MB compressed** at crawl time. Sources: [MiniStack homepage](https://ministack.org/), [Docker Hub](https://hub.docker.com/r/nahuelnucera/ministack)
- **ElasticMQ throughput**
  - Historical self-published REST-interface throughput around **2,540-2,600 msg/s** on a 2012 MBP; this is old and should be treated as dated. Source: [ElasticMQ README](https://github.com/softwaremill/elasticmq)
- **Floci documented compatibility fixes**
  - `core: globally inject aws request-id headers for sdk compatibility`
  - `sqs: translate Query-protocol error codes to JSON __type equivalents`
  - `return stable cursor tokens in GetLogEvents to fix SDK pagination loop`
  - `return versionId in CompleteMultipartUpload response`
  Sources: [1.2.0](https://newreleases.io/project/github/floci-io/floci/release/1.2.0), [1.0.10](https://newreleases.io/project/github/floci-io/floci/release/1.0.10)
- **Moto documented divergences**
  - S3 notification keys not URL-encoded like AWS. Source: [moto issue #9054](https://github.com/getmoto/moto/issues/9054)
  - Valid DynamoDB `UpdateItem` expression rejected locally. Source: [moto issue #8740](https://github.com/getmoto/moto/issues/8740)
- **MinIO documented/reported S3 signing issues**
  - Presigned upload with boto3 example rejected with `SignatureDoesNotMatch`. Source: [minio issue #9564](https://github.com/minio/minio/issues/9564)
  - AWS iOS presigned URL issue fixed later. Source: [minio issue #10361](https://github.com/minio/minio/issues/10361)
  - AWS SDK for Java v2 `S3Presigner` behavior change after 2.21.16 caused MinIO rejection. Source: [aws-sdk-java-v2 issue #4697](https://github.com/aws/aws-sdk-java-v2/issues/4697)

### Trade-offs

If your main risk is **“tests pass locally but fail on AWS because of signing or presigned URL behavior,”** then **MinIO** is the best OSS choice in this set, but only for S3. It validates signatures seriously enough to catch real auth mistakes, and that is exactly why it also exposes incompatibilities when SDKs or endpoint handling change.

If you need a **single-container AWS emulator** for app-level integration tests, **Floci** currently looks stronger than MiniStack on published interoperability detail, but not on proven auth realism for S3/SQS/SNS/DynamoDB. Its release notes already show the familiar emulator pattern: good happy-path SDK support, ongoing fixes for response headers, error-code mapping, pagination tokens, and multipart details. That is usable for CI, but it is not the same thing as AWS-grade request validation.

**MiniStack** is currently the hardest to recommend for this dimension. Not because I found damning evidence, but because I found almost none. For a senior architect, sparse issue history is ambiguous: it may mean fewer users, less adversarial testing, or simply that signing fidelity has not been exercised much in public.

**Moto** remains a very practical choice for Python-heavy teams and for broad service coverage, especially when the objective is deterministic black-box integration testing. But for auth realism it is weak by default. If your code depends on AWS rejecting malformed signatures, expired presigned URLs, or subtle S3 notification formatting, Moto can absolutely let bugs through.

**S3Mock** is honest and useful, but only if you treat it as a functional S3 fake, not as a security-behavior validator. Its explicit decision to accept presigned URLs without checking expiry or signature makes it inappropriate for any CI gate that is supposed to catch auth regressions.

**ElasticMQ** is still a strong SQS semantic emulator. But on this dimension, it is closer to Moto than to MinIO: good for queue behavior, weakly evidenced for real SigV4 enforcement.

### New Questions

1. How do these emulators behave under newer AWS SDK defaults, especially S3 checksum headers, `aws-chunked` uploads, and virtual-host/path-style endpoint auto-detection?
2. Which tools can be configured to run in a “strict auth mode” that actually rejects unsigned or malformed requests, and how complete is that strictness per service?
3. For multi-language teams, which emulator has the best externally validated compatibility suite, rather than only maintainer-published numbers?

Sources used: [MiniStack](https://ministack.org/), [MiniStack getting started](https://www.ministack.org/getting-started.html), [MiniStack Docker Hub](https://hub.docker.com/r/nahuelnucera/ministack), [Floci](https://floci.io/), [Floci project page](https://hectorvent.dev/projects/), [Floci 1.2.0](https://newreleases.io/project/github/floci-io/floci/release/1.2.0), [Floci 1.1.0](https://newreleases.io/project/github/floci-io/floci/release/1.1.0), [Floci 1.0.10](https://newreleases.io/project/github/floci-io/floci/release/1.0.10), [Moto server mode](https://docs.getmoto.org/en/latest/docs/server_mode.html), [Moto IAM](https://docs.getmoto.org/en/5.0.21/docs/iam.html), [Moto issue #9054](https://github.com/getmoto/moto/issues/9054), [Moto issue #8740](https://github.com/getmoto/moto/issues/8740), [S3Mock README](https://github.com/adobe/S3Mock), [MinIO IAM docs](https://min.io/docs/minio/macos/administration/identity-access-management.html), [MinIO concepts](https://min.io/docs/minio/container/administration/concepts.html), [MinIO mc share](https://min.io/docs/minio/linux/reference/minio-mc/mc-share.html), [MinIO issue #9564](https://github.com/minio/minio/issues/9564), [MinIO issue #10361](https://github.com/minio/minio/issues/10361), [AWS SDK Java v2 issue #4697](https://github.com/aws/aws-sdk-java-v2/issues/4697), [AWS SDK Java v2 issue #6123](https://github.com/aws/aws-sdk-java-v2/issues/6123), [ElasticMQ README](https://github.com/softwaremill/elasticmq), [ElasticMQ Rust module docs](https://docs.rs/testcontainers-modules/latest/testcontainers_modules/elasticmq/struct.ElasticMq.html).

---

## Peer Review (claude)

## Critical Peer Review

---

### Issue 1: Two-class taxonomy breaks on its own example
- **Type**: Missing nuance / internal inconsistency
- **Location**: "the field splits into two classes. First, the broad multi-service emulators...prioritize 'accept real AWS SDK calls' over 'enforce AWS-like SigV4 failures.' Second, the point tools...especially MinIO...are materially stronger on real signature validation."
- **Problem**: S3Mock is also a point tool (S3-only), yet it is explicitly weaker on SigV4 than MinIO. The taxonomy predicts point tools are stronger on auth fidelity, but S3Mock directly contradicts this. The actual axis is design philosophy (functional fake vs. protocol-faithful server), not service breadth.
- **Impact**: The framing misleads readers into thinking narrowing service scope implies better auth realism. It doesn't — S3Mock proves the opposite.

---

### Issue 2: MinIO evidence supports false positives, not correct rejection
- **Type**: Missing nuance / unsupported claim
- **Location**: "Unlike S3Mock, MinIO does reject bad signatures in practice. There are multiple historical compatibility bugs where AWS SDK-generated presigned URLs were rejected with `SignatureDoesNotMatch`..."
- **Problem**: Every cited issue (minio/minio#9564, #10361, aws-sdk-java-v2#4697, #6123) documents MinIO *incorrectly rejecting valid AWS-generated signatures*, not correctly rejecting bad ones. These are false positives. They demonstrate MinIO enforces *something*, but they do not demonstrate it enforces SigV4 *correctly*. A tool that rejects valid signatures is not the same as one that correctly validates them.
- **Impact**: The cornerstone claim that MinIO is the best choice for catching auth bugs rests on evidence of MinIO misbehaving, not behaving correctly. The research partly acknowledges this ("MinIO-only failures that do not reproduce on AWS") but does not flag the logical problem with using false-positive evidence to support a true-positive claim.

---

### Issue 3: Moto version-pinned citation for a key claim
- **Type**: Factual risk / gap
- **Location**: "Moto documents that IAM-like auth is optional, 'very basic,' and if `INITIAL_NO_AUTH_ACTION_COUNT` is unset, it 'defaults to infinity'... Sources: [Moto IAM docs](https://docs.getmoto.org/en/5.0.21/docs/iam.html)"
- **Problem**: The citation pins to version 5.0.21. The current Moto release as of early 2026 is substantially later in the 5.x series. Auth behavior is exactly the kind of thing that gets updated between releases. Using a frozen doc URL for a central claim without noting this risk is a methodological gap. The `/en/latest/` URL is also cited in the server mode source but not for this specific claim.
- **Impact**: If this behavior changed in a later release, the most damning claim in the Moto section would be stale.

---

### Issue 4: "Very basic" Moto auth is unexplained
- **Type**: Missing nuance / gap
- **Location**: "its IAM-like auth is optional, 'very basic,' and if `INITIAL_NO_AUTH_ACTION_COUNT` is unset..."
- **Problem**: The research never explains what "very basic" means in practice when auth *is* enabled. Does it check that a credential is present? Does it verify the HMAC? Does it check expiry? Does it validate the signed headers list? Readers making an architectural decision need this distinction. Presence-checking and cryptographic validation are categorically different guarantees.
- **Impact**: A team that enables auth in Moto might believe they have signature validation when they only have credential-presence checking.

---

### Issue 5: Floci's SigV4 claim for ElastiCache and RDS is conflated with request signing
- **Type**: Missing nuance / potential factual error
- **Location**: "its public SigV4 claim is narrow: it explicitly says Lambda, ElastiCache, and RDS support 'full IAM authentication and SigV4 validation.'"
- **Problem**: ElastiCache and RDS do not typically use SigV4 for SDK API calls in the same sense S3/SQS/SNS/DynamoDB do. RDS and ElastiCache use IAM *database authentication tokens* (which are a form of pre-signed credential), not SigV4-signed HTTP requests to a service control plane. If Floci is claiming "SigV4 validation" for ElastiCache/RDS, that is an unusual and potentially inaccurate claim that deserves scrutiny — but the research accepts it without comment. The conflation of IAM db-auth with SigV4 HTTP request signing is a meaningful technical distinction.
- **Impact**: The inference that Floci's SigV4 support is "narrow" is built on a claim that may itself be technically confused.

---

### Issue 6: aws-sdk-java-v2 issue #6123 cited in sources but never referenced in body
- **Type**: Gap / inconsistency
- **Location**: Sources list includes `[AWS SDK Java v2 issue #6123]` but it is never cited inline in the MinIO section or anywhere else.
- **Problem**: An issue is included in the evidence set but its content is never reported. The reader cannot assess what it contributes. Either it supports an existing claim (and should be cited) or it was included by mistake.
- **Impact**: Minor credibility issue; suggests the source list may not be fully reconciled with the body.

---

### Issue 7: MiniStack appears to be a single-maintainer personal project; this is not disclosed
- **Type**: Missing nuance / gap
- **Location**: "I also found essentially no public issue trail...For an architect, that is not reassuring evidence of correctness; it is mostly evidence of low external scrutiny."
- **Problem**: The Docker Hub source URL is `hub.docker.com/r/nahuelnucera/ministack` — a personal namespace, not an organization. This suggests MiniStack may be a solo side project, not a maintained open-source product. That is a substantially different risk profile than Moto or MinIO (both with large contributor bases). The "low external scrutiny" observation is correct but stops short of the more direct conclusion: MiniStack may have essentially no production-scale user base.
- **Impact**: The risk framing for MiniStack is understated. Recommending it without noting it appears to be a personal project is a meaningful omission for an architect audience.

---

### Issue 8: ElasticMQ throughput figure adds noise without value
- **Type**: Missing nuance
- **Location**: "Historical self-published REST-interface throughput around 2,540-2,600 msg/s on a 2012 MBP; this is old and should be treated as dated."
- **Problem**: The research correctly warns this is old, but includes it anyway. A benchmark from a 2012 MacBook Pro, from what appears to be the original ElasticMQ README benchmark section (likely 10+ years old), is not just dated — it is meaningless for any modern infrastructure decision. Including it with a caveat still anchors readers on a number that tells them nothing.
- **Impact**: Low analytical impact, but it pads the evidence section with a data point the research itself says cannot be trusted. It should be omitted or replaced.

---

### Issue 9: LocalStack is entirely absent
- **Type**: Gap
- **Location**: The entire findings document.
- **Problem**: LocalStack is the most widely deployed multi-service AWS emulator in CI pipelines, with both a Community tier (MIT-licensed) and a Pro tier. Its SigV4 behavior, IAM enforcement modes, and SDK compatibility are directly on-topic for every question this research addresses. The Community tier has known gaps in auth enforcement; the Pro tier has more complete IAM simulation. Omitting it entirely leaves the most common real-world alternative unreviewed.
- **Impact**: High. An architect reading this to decide on a local AWS emulation strategy will immediately ask "what about LocalStack?" and the research cannot answer. The comparison set is materially incomplete.

---

### Issue 10: S3Mock "path-style only" claim may be outdated
- **Type**: Factual risk
- **Location**: "It is also path-style only."
- **Problem**: S3Mock's README has historically documented path-style-only support, but the project is actively maintained (Adobe-backed). Virtual-hosted style support has been requested and partially addressed in more recent releases. The research cites the README but does not note the version or date checked. If virtual-hosted style has been added since, this is a factual error.
- **Impact**: Moderate. Path-style vs. virtual-hosted-style is a real configuration concern, especially since AWS SDK v3+ defaults to virtual-hosted style. If the limitation has been resolved, the critique of S3Mock in this dimension is overstated.

---

### Issue 11: "Best OSS choice" claim is not scoped to the comparison set
- **Type**: Unsupported claim / missing nuance
- **Location**: "MinIO is the best OSS choice in this set for real S3 SigV4 behavior"
- **Problem**: The phrase "in this set" appears in the trade-offs section but is phrased loosely as "the best OSS choice here." A reader who skims this could take it as a general recommendation, when it is only a conclusion within a deliberately narrow comparison group that excludes LocalStack, DynamoDB Local, AWS SAM Local, and others. "Best in an incomplete set" is a qualified claim, and the qualification needs to be more prominent.
- **Impact**: Moderate risk of over-recommendation if the reader does not notice the scope constraint.

---

### Issue 12: Floci compatibility bug evidence is used ambiguously
- **Type**: Missing nuance
- **Location**: "recent releases fixed missing AWS request-id headers 'for sdk compatibility,' fixed missing `versionId` in `CompleteMultipartUpload`...These are exactly the sorts of bugs that break real applications even when basic CRUD works."
- **Problem**: The research presents these fixes as evidence of current risk, but they are actually evidence of *resolved* defects. Fixed bugs in a changelog are not the same as current divergences. The correct inference is that the project actively ships compatibility fixes, which is a positive signal about intent and velocity — but is also evidence that pre-fix versions had real gaps. The research slides between these two interpretations without distinguishing them.
- **Impact**: The characterization of Floci's reliability is slightly unfair. The correct framing is: "the kinds of bugs that *were* caught and fixed suggest more may exist unfound" — which is a valid concern, but different from implying the listed bugs are still present.

---

## Summary

| | Count |
|---|---|
| Factual errors or material factual risks | 3 (Issues 3, 5, 10) |
| Unsupported or poorly-supported claims | 3 (Issues 2, 9, 11) |
| Missing nuance | 5 (Issues 1, 4, 7, 8, 12) |
| Gaps | 3 (Issues 6, 7, 9) |
| Internal contradictions | 1 (Issue 1) |

**Overall reliability: Medium.**

The research is methodologically honest — it consistently flags inferences as inferences and cites sources for direct claims. The Moto and S3Mock sections are the strongest: the claims are specific, sourced, and well-reasoned. The MinIO section is the weakest analytically: its evidence is systematically misread (false positives cited as validation fidelity). The entire comparison is undermined by the absence of LocalStack.

**What would most improve the findings:**

1. Add LocalStack — it is the dominant tool in this space and its omission is the single largest gap.
2. Reframe the MinIO evidence section: distinguish between "MinIO enforces *something* cryptographic" and "MinIO enforces SigV4 *correctly*." These are different claims.
3. Verify the Moto auth behavior against the current `latest` docs, not a pinned old version.
4. Clarify the Floci/ElastiCache/RDS SigV4 claim — IAM db-auth tokens and SigV4 HTTP request signing are not the same thing.
5. Remove or replace the ElasticMQ throughput figure; it adds nothing reliable.