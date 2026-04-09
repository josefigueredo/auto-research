# Iteration 010 — SigV4 signing and SDK compatibility under real AWS SDKs

**Status:** keep  
**Scores:** coverage=67.5, quality=72.5, total=70.5  
**Timestamp:** 2026-04-08T17:27:12.004764+00:00  

---

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
