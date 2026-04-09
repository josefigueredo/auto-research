# Iteration 004 — API compatibility and fidelity vs real AWS

**Status:** keep  
**Scores:** coverage=58.8, quality=67.5, total=64.0  
**Timestamp:** 2026-04-08T16:46:44.993183+00:00  

---

### Findings

For **API fidelity versus real AWS**, the practical ranking is:

1. **Floci** has the strongest published compatibility evidence for a LocalStack-like black-box emulator, but almost all of that evidence is still **self-published**.
2. **MiniStack** advertises broad operation coverage for the core 8 services, but its public evidence on **failure modes and edge-case drift is thin**.
3. **Moto** has the most transparent documentation of what is and is not implemented, but it is still the weakest fit for “acts like AWS end-to-end in CI” once you need API Gateway data plane realism, Lambda networking realism, or CloudFormation fidelity.

A key negative finding: I did **not** find evidence that **MiniStack**, **Floci**, or **Moto** pass any **official AWS-owned SDK integration suite** published by AWS itself. What exists instead is:
- **Floci**: a repo-hosted compatibility suite and vendor-published results.
- **MiniStack**: a generic “900+ tests” claim, but no public per-service SDK pass matrix.
- **Moto**: implemented-operation docs, unit/integration coverage inside Moto itself, and issue tracker evidence, but no “AWS SDK suite pass rate” disclosure.

For the core 8 services, the **best-documented fidelity gaps** are concentrated in **Moto**:

- **API Gateway**: Moto explicitly says REST API integrations only support **HTTP** and **AWS integrations with DynamoDB**; other integration types such as **`AWS_PROXY`** and **`MOCK`** are ignored, and mocked public URLs only work in decorator mode, **not server mode**. That is a major divergence from real AWS for black-box CI.  
  Sources: [Moto API Gateway docs](https://docs.getmoto.org/en/5.0.24/docs/services/apigateway.html)

- **Lambda**: Moto runs functions in Docker, but warns that when invoked via decorators the Lambda container cannot reach Moto state; AWS SDK calls from inside the Lambda will try to hit real AWS unless you run MotoServer or MotoProxy in a Docker-reachable setup. Moto also says **Function URLs are not mocked**, the **Qualifier** parameter is not implemented there, and **`PackageType=Image` invocation is not supported**.  
  Sources: [Moto Lambda docs](https://docs.getmoto.org/en/5.1.9/docs/services/lambda.html)

- **CloudFormation**: Moto supports many stack APIs, but multiple behaviors differ materially from AWS: `EnableTerminationProtection` is not implemented; `set_stack_policy` is persisted but **not enforced**; `list_stack_instances` has **no pagination**; `update_stack_instances` updates parameters but **does not update actual resources**.  
  Sources: [Moto CloudFormation docs](https://docs.getmoto.org/en/latest/docs/services/cloudformation.html)

- **DynamoDB**: Moto’s PartiQL `execute_statement` support explicitly says **pagination is not implemented** and parsing is “highly experimental.” Separately, real-world bug reports show valid `UpdateItem` expressions failing in Moto while succeeding on real DynamoDB.  
  Sources: [Moto DynamoDB docs](https://docs.getmoto.org/en/latest/docs/services/dynamodb.html), [Issue #8740](https://github.com/getmoto/moto/issues/8740)

- **S3 notifications / event payload fidelity**: Moto had a confirmed gap where S3 notification object keys were **not URL-encoded** like AWS, which breaks production decoding logic; it also has an open issue showing EventBridge-style S3 notifications are incomplete and that support historically focused on object-created events first.  
  Sources: [Issue #9054](https://github.com/getmoto/moto/issues/9054), [Issue #7363](https://github.com/getmoto/moto/issues/7363)

- **S3 response fidelity**: Moto has an open bug where `StreamingBody` for files larger than 1 MB includes **raw chunked transfer encoding**, which differs from normal SDK expectations.  
  Source: [Moto issues list](https://github.com/getmoto/moto/issues)

For **Floci**, the picture is better on paper:

- Floci publishes **408/408 AWS SDK compatibility checks** on its site and a repo with compatibility modules for Java v2, JS v3, boto3, Go v2, AWS CLI, Rust, Terraform, OpenTofu, and CDK.  
  Sources: [Floci site](https://floci.io/), [Floci GitHub README](https://github.com/floci-io/floci)

- Floci’s own breakdown includes relevant edge-case-heavy areas:
  - **S3** `23/23`
  - **S3 Object Lock** `30/30`
  - **S3 Advanced** `13/13`
  - **DynamoDB Streams** `12/12`
  - **API Gateway REST** `43/43`
  - **API Gateway v2** `5/5`
  - **S3 Event Notifications** `11/11`
  - **STS** `18/18`
  - **IAM** `32/32`  
  Source: [Introducing Floci](https://hectorvent.dev/posts/introducing-floci/)

But Floci is not bug-free, and the public issues already show concrete fidelity cracks:
- **S3**: open issue says **S3 responses are rejected by the AWS SDK** and break CDK asset publishing.
- **S3**: open issue says keys with a **leading slash are stripped and collide** with non-slash keys.
- **DynamoDB**: open issue says `DescribeTable` for a GSI is **missing non-key attributes**.  
  Source: [Floci issues](https://github.com/floci-io/floci/issues)

Those are meaningful because they hit exactly the kind of things that break real pipelines: CDK asset upload flows, schema discovery, and object-key edge cases.

For **MiniStack**, the public story is mixed:

- MiniStack documents a broad operation surface for all core 8 services:
  - S3 supports multipart, versioning, notifications, Object Lock, replication.
  - DynamoDB supports transactions, TTL, streams.
  - Lambda supports SQS/Kinesis/DynamoDB Streams event source mappings, layers, aliases, concurrency, Function URLs, and image/package modes.
  - API Gateway v1/v2 support includes Lambda proxy, HTTP proxy, and MOCK integrations.
  - CloudFormation supports stack lifecycle, change sets, exports, intrinsic functions, and only **12 resource types**.  
  Sources: [MiniStack GitHub README](https://github.com/Nahuel990/ministack), [MiniStack site](https://ministack.org/)

- MiniStack also exposes a CI-friendly reset endpoint and LocalStack-compatible health endpoints, which is good operationally but says nothing about semantic parity.  
  Source: [MiniStack GitHub README](https://github.com/Nahuel990/ministack)

- The main problem is evidence quality: MiniStack claims **900+ tests**, but I did not find a public SDK-suite breakdown comparable to Floci’s.  
  Sources: [MiniStack site](https://ministack.org/), [MiniStack GitHub README](https://github.com/Nahuel990/ministack)

- The public issue tracker is small, but the few visible issues are concerning because they touch runtime behavior:
  - open bug: **“SQS not returning all messages”**
  - open request: **support for Go apps provided as a Docker image in Lambda**  
  Source: [MiniStack issues](https://github.com/Nahuel990/ministack/issues)

That does **not** prove MiniStack is worse than Floci; it means MiniStack currently provides **less auditable evidence** of API fidelity.

#### Edge cases

**Presigned URLs**
- **Floci** explicitly claims S3 presigned URL support and includes S3/S3 Advanced tests, but public issue evidence already shows at least one **AWS SDK/CDK S3 response compatibility problem** affecting asset publishing.  
  Sources: [Floci README](https://github.com/floci-io/floci), [Floci issues](https://github.com/floci-io/floci/issues)
- **MiniStack** documents broad S3 support but I did not find a public presigned-URL compatibility disclosure or test breakdown.
- **Moto** has strong S3 breadth, but public issues show notification payload mismatches and response-format drift; I did not find a current explicit Moto claim that presigned URL verification matches AWS end-to-end.

**Pagination tokens**
- **Moto** is the clearest risk here. Pagination is explicitly missing for parts of **CloudFormation** and **DynamoDB PartiQL**; API Gateway docs also note pagination gaps.  
  Sources: [Moto CloudFormation docs](https://docs.getmoto.org/en/latest/docs/services/cloudformation.html), [Moto DynamoDB docs](https://docs.getmoto.org/en/latest/docs/services/dynamodb.html), [Moto API Gateway docs](https://docs.getmoto.org/en/5.0.24/docs/services/apigateway.html)
- **Floci** and **MiniStack** both expose many list APIs, but I found very little public disclosure of token edge-case failures. For an architect, that is a verification gap, not a clean bill of health.

**Conditional writes**
- **MiniStack** advertises DynamoDB transactions and update APIs, but no public evidence of conditional-expression fidelity.
- **Floci** publishes full DynamoDB suite passes but also has a live `DescribeTable` metadata bug; I did not find public conditional-write failures.
- **Moto** has concrete evidence of DynamoDB expression mismatches versus real AWS in at least one valid `UpdateItem` case.  
  Source: [Issue #8740](https://github.com/getmoto/moto/issues/8740)

**Event source mappings**
- **Floci** explicitly claims SQS, Kinesis, and DynamoDB Streams Lambda ESM support and publishes passing ESM-related suites.  
  Sources: [Floci site](https://floci.io/), [Introducing Floci](https://hectorvent.dev/posts/introducing-floci/)
- **MiniStack** also explicitly claims SQS, Kinesis, and DynamoDB Streams event source mappings.  
  Source: [MiniStack GitHub README](https://github.com/Nahuel990/ministack)
- **Moto** implements `create_event_source_mapping`, but its broader Lambda/server-mode limitations make this less trustworthy for full black-box emulation. Discussion history also suggests users ask about simulating parameters such as `max_concurrency` and batch behavior, which is a signal that this area is not straightforward.  
  Sources: [Moto Lambda docs](https://docs.getmoto.org/en/5.1.9/docs/services/lambda.html), [Moto discussions](https://github.com/getmoto/moto/discussions)

### Evidence

Concrete data points relevant to this dimension:

- **Floci**
  - Claims **408/408 SDK compatibility checks** and **1,873 automated compatibility tests**.  
    Sources: [floci.io](https://floci.io/), [Floci GitHub README](https://github.com/floci-io/floci)
  - Compatibility modules listed publicly:
    - Java v2: **889**
    - JS v3: **360**
    - boto3: **264**
    - Go v2: **120**
    - AWS CLI v2: **138**
    - Rust: **69**
    - Terraform: **14**
    - OpenTofu: **14**
    - CDK: **5**  
    Source: [Floci GitHub README](https://github.com/floci-io/floci)
  - Published selected-suite results:
    - S3 **23/23**
    - S3 Object Lock **30/30**
    - S3 Advanced **13/13**
    - DynamoDB **18/18**
    - DynamoDB Advanced **18/18**
    - DynamoDB Streams **12/12**
    - API Gateway REST **43/43**
    - API Gateway v2 **5/5**
    - IAM **32/32**
    - STS **18/18**
    - S3 Event Notifications **11/11**  
    Source: [Introducing Floci](https://hectorvent.dev/posts/introducing-floci/)
  - Current visible open bugs touching fidelity:
    - `#293` CDK asset publishing broken, S3 responses rejected by AWS SDK
    - `#292` DynamoDB `DescribeTable` GSI missing non-key attributes
    - `#282` S3 leading-slash keys collide after stripping  
    Source: [Floci issues](https://github.com/floci-io/floci/issues)

- **MiniStack**
  - Claims **38 AWS services** and **900+ tests**.  
    Sources: [MiniStack site](https://ministack.org/), [MiniStack GitHub README](https://github.com/Nahuel990/ministack)
  - Core 8 operation depth is documented, including:
    - S3: multipart, notifications, replication, Object Lock
    - DynamoDB: transactions, streams, TTL
    - Lambda: ESMs, layers, Function URLs, image/package modes
    - API Gateway v1/v2: Lambda proxy, HTTP proxy, MOCK
    - CloudFormation: only **12 resource types**  
    Source: [MiniStack GitHub README](https://github.com/Nahuel990/ministack)
  - Current visible open bugs/features touching fidelity:
    - `#185` SQS not returning all messages
    - `#67` support for Go apps as Docker image in Lambda  
    Source: [MiniStack issues](https://github.com/Nahuel990/ministack/issues)

- **Moto**
  - API Gateway limitations:
    - only HTTP integrations and AWS integrations with DynamoDB
    - `AWS_PROXY`, `MOCK`, etc. ignored
    - BasePath ignored
    - request/response TemplateMapping unsupported
    - public URL behavior only in decorators, **not ServerMode**  
    Source: [Moto API Gateway docs](https://docs.getmoto.org/en/5.0.24/docs/services/apigateway.html)
  - Lambda limitations:
    - decorator-invoked Lambdas cannot reach Moto state
    - Function URLs not mocked
    - `Qualifier` unsupported there
    - `PackageType=Image` invocation unsupported  
    Source: [Moto Lambda docs](https://docs.getmoto.org/en/5.1.9/docs/services/lambda.html)
  - CloudFormation limitations:
    - `EnableTerminationProtection` not implemented
    - `list_stack_instances` pagination not implemented
    - `set_stack_policy` not enforced
    - `update_stack_instances` does not update actual resources  
    Source: [Moto CloudFormation docs](https://docs.getmoto.org/en/latest/docs/services/cloudformation.html)
  - DynamoDB limitations:
    - `execute_statement` pagination not implemented
    - parser marked “highly experimental”  
    Source: [Moto DynamoDB docs](https://docs.getmoto.org/en/latest/docs/services/dynamodb.html)
  - Real-world divergence reports:
    - S3 notification keys not URL-encoded like AWS: [Issue #9054](https://github.com/getmoto/moto/issues/9054)
    - S3 EventBridge notifications incomplete: [Issue #7363](https://github.com/getmoto/moto/issues/7363)
    - valid DynamoDB `UpdateItem` expression failed in Moto, worked on real AWS: [Issue #8740](https://github.com/getmoto/moto/issues/8740)

### Trade-offs

**Floci**
- Better when you need a **single-container, LocalStack-like emulator** and want the strongest published evidence for SDK/API fidelity.
- Worse when you need independently replicated proof. Its best numbers and pass rates are still **vendor-run**, not AWS-run.
- Practical read: strongest current OSS option for CI if you are willing to validate a few workflow-critical edges yourself, especially **S3 asset upload** and **DynamoDB metadata**.

**MiniStack**
- Better when you want broad service coverage and a LocalStack-like operating model, including richer documented support for API Gateway and Lambda than Moto.
- Worse when you need auditable compatibility evidence. MiniStack currently publishes **breadth** much better than it publishes **fidelity**.
- Practical read: plausible for dev/CI, but riskier than Floci for teams that need documented proof of wire-level behavior.

**Moto**
- Better when your team values transparency about what is implemented, and when tests are more **framework-driven mocks** than black-box “local AWS”.
- Worse when your pipeline depends on realistic API Gateway routing, Lambda-to-AWS networking inside the emulated environment, Function URLs, or CloudFormation parity.
- Practical read: still excellent for many unit/integration tests, but weakest as a LocalStack replacement for end-to-end local cloud behavior.

The surprising result is that **Moto is the most honest source** here: its docs state many limitations plainly. **Floci and MiniStack look stronger operationally**, but their real-world fidelity is harder to audit because they disclose less negative detail publicly.

### New Questions

1. How well do Floci and MiniStack preserve **HTTP-level fidelity** under real client stacks like CDK bootstrap, Terraform apply, SAM CLI, and presigned-upload browser flows, beyond their own SDK suites?
2. Which emulator has the fewest failures in **stateful retries and idempotency paths**: duplicate SQS deliveries, Lambda retry policies, CloudFormation rollback, and DynamoDB conditional retry behavior?
3. How much of the remaining compatibility risk can be reduced by using a **hybrid stack**: Moto for unit tests, plus Floci or MiniStack only for black-box CI stages?

I did not find public evidence of AWS-official integration-suite certification for any of these tools, and MiniStack in particular lacks a public per-SDK failure matrix. That limits how confidently I can name exact per-operation failures for MiniStack beyond what its docs and issue titles disclose.

---

## Peer Review (claude)

### Issue 1: Circular reasoning in the Floci #1 ranking
- **Type**: Missing nuance / logical gap
- **Location**: "Floci has the strongest published compatibility evidence for a LocalStack-like black-box emulator, but almost all of that evidence is still self-published."
- **Problem**: The research ranks Floci first based on quantity of published evidence, then immediately concedes that evidence is self-published. The conclusion ("strongest current OSS option for CI") does not logically follow if the evidentiary basis is vendor-controlled. Self-published pass rates can reflect what the vendor chose to test, not what the tool actually handles. The ranking conflates "most evidence published" with "highest fidelity."
- **Impact**: High. This is the central claim of the findings. A reader may adopt Floci based on a ranking whose supporting evidence the research itself flags as unreliable.

---

### Issue 2: Undisclosed vendor authorship of the Floci suite results
- **Type**: Unsupported claim / missing nuance
- **Location**: Suite results (S3 23/23, API Gateway REST 43/43, etc.) are sourced from `hectorvent.dev/posts/introducing-floci/`
- **Problem**: The research never discloses whether hectorvent.dev is the author or maintainer of Floci. If it is, this is marketing content, not independent verification — yet the results are presented alongside raw numbers as if they carry evidentiary weight. The research should state explicitly who authored this post and their relationship to the project.
- **Impact**: High. Per-suite pass rates are the primary positive evidence for Floci. If the source is the project's own author, those numbers deserve the same skepticism applied to MiniStack's "900+ tests" claim — but they are not treated that way.

---

### Issue 3: The 408-check and 1,873-test figures are never reconciled
- **Type**: Factual gap / unclear claim
- **Location**: "Claims 408/408 AWS SDK compatibility checks and 1,873 automated compatibility tests." The per-SDK breakdown (Java v2: 889, JS v3: 360, etc.) sums to 1,873 — but 408 is never explained.
- **Problem**: These are two different metrics with no explanation of what "408 checks" means versus "1,873 tests." The 408 figure likely refers to distinct API operations covered, while 1,873 refers to individual test cases, but the research never clarifies. A reader citing "408/408" may misunderstand what is actually measured. Critically, 408 passing checks do not imply edge-case correctness — the open Floci bugs (CDK asset upload broken, GSI metadata wrong) would presumably occur in operations already counted as "passing" in a basic operability check.
- **Impact**: Medium-high. The headline "408/408" is the single most cited positive data point for Floci and its meaning is ambiguous.

---

### Issue 4: Missing LocalStack baseline
- **Type**: Gap
- **Location**: Throughout the findings; no mention of LocalStack Community or LocalStack Pro.
- **Problem**: The research evaluates three "LocalStack alternatives" without ever establishing what LocalStack itself offers as a baseline. Any claim that Floci or MiniStack is a credible replacement requires knowing what gap exists relative to LocalStack. LocalStack Community and Pro are the dominant tools in this space; they have independent real-world usage data, known fidelity gaps, and broader community validation. Omitting them makes the comparative ranking unanchored.
- **Impact**: High. The findings cannot meaningfully advise an architect choosing between these tools and LocalStack without this context.

---

### Issue 5: MiniStack's CloudFormation limitation is severely underweighted
- **Type**: Missing nuance
- **Location**: "CloudFormation supports stack lifecycle, change sets, exports, intrinsic functions, and only 12 resource types."
- **Problem**: AWS CloudFormation supports over 1,200 resource types. Twelve is not a minor caveat — it means any stack using RDS, ECS, SNS, ElastiCache, Kinesis, or dozens of other common services will simply fail. This is listed as one bullet among several positive features, but it should be called out as a disqualifying limitation for any team using CloudFormation with non-trivial stacks. The trade-offs section for MiniStack does not mention it at all.
- **Impact**: Medium-high. A reader scanning the MiniStack section for CloudFormation suitability will miss this.

---

### Issue 6: Moto is a different product class; the comparison is a category error
- **Type**: Missing nuance
- **Location**: "Moto is... the weakest fit for 'acts like AWS end-to-end in CI'"
- **Problem**: Moto is a Python mocking library designed for in-process unit and integration tests, not a black-box HTTP emulator. Floci and MiniStack are black-box container services analogous to LocalStack. Ranking Moto as "weakest" on a black-box CI criterion is like ranking a compiler as a poor text editor. The research acknowledges ("your tests are more framework-driven mocks than black-box 'local AWS'") but buries this in the trade-offs section rather than flagging it upfront as a fundamental architectural difference. For its intended use case, Moto may be the strongest of the three tools.
- **Impact**: Medium. Readers unfamiliar with Moto's design may walk away with an inaccurate picture of its fitness.

---

### Issue 7: Open/closed status of Floci and MiniStack issues is not stated
- **Type**: Factual gap
- **Location**: Floci issues #293, #292, #282; MiniStack issues #185, #67
- **Problem**: The research cites these as active fidelity concerns but never confirms whether they are open or recently closed. If issue #293 (CDK asset publishing broken) was closed last week with a fix, the negative weight it carries in the analysis is unwarranted. Conversely, if they have been open for months, that signals slow maintenance velocity — also relevant. The findings treat issue existence as equivalent to issue persistence without verifying the state.
- **Impact**: Medium. The Floci and MiniStack negative findings rest partly on these issues; their validity depends on current status.

---

### Issue 8: Moto version inconsistency across cited docs
- **Type**: Factual gap
- **Location**: API Gateway cited from 5.0.24; Lambda from 5.1.9; CloudFormation and DynamoDB from "latest."
- **Problem**: Moto is actively developed. Citing docs from three different version snapshots means some limitations described may have been fixed in the interim. A finding like "Function URLs are not mocked" may be accurate for 5.1.9 but not for the current release. The research should either pin all citations to a single version or note that these were verified against the same release.
- **Impact**: Medium. Moto's negative findings carry disproportionate weight in the comparison, and stale citations weaken their reliability.

---

### Issue 9: "Core 8 services" is never explicitly defined
- **Type**: Gap
- **Location**: "MiniStack advertises broad operation coverage for the core 8 services"; "For the core 8 services, the best-documented fidelity gaps..."
- **Problem**: The eight services are never listed as a group. From context the reader can infer S3, DynamoDB, Lambda, API Gateway, CloudFormation, SQS, STS, and IAM — but this is never confirmed. If MiniStack's "38 services" include services outside this inferred list, the coverage comparison may be understating or mischaracterizing MiniStack's scope. The implicit definition also makes the research harder to reuse.
- **Impact**: Low-medium. Creates ambiguity but does not invalidate the analysis if the inference is correct.

---

### Issue 10: No analysis of what Floci's test methodology actually measures
- **Type**: Gap
- **Location**: Throughout the Floci evidence section
- **Problem**: The research never asks what "passing" means in Floci's compatibility suite. Does a passing test verify full response-body fidelity, HTTP header parity, error message format, pagination token shape, or just that the operation returns a 200? The open bug where S3 responses are "rejected by the AWS SDK" (issue #293) suggests at least one operation was counted as covered while its response format was wrong. Without understanding the test assertions, the 408/408 figure is uninterpretable as a fidelity metric.
- **Impact**: High. This is foundational to whether the Floci evidence justifies the #1 ranking.

---

### Issue 11: MiniStack SQS message-delivery bug is underweighted
- **Type**: Missing nuance
- **Location**: "open bug: 'SQS not returning all messages'"
- **Problem**: SQS message delivery is a core guarantee of the SQS protocol. A bug where not all messages are returned is not a minor edge case — it breaks any consumer doing standard long-poll receives and would silently corrupt test results that depend on message counts. This is at least as severe as Moto's listed DynamoDB expression bug, but the research treats it as one of two brief bullet points under MiniStack with no commentary on its implications for event-driven CI pipelines.
- **Impact**: Medium. The trade-off section for MiniStack should mention this explicitly.

---

### Issue 12: Moto's maturity and community size are not factored into the trade-offs
- **Type**: Missing nuance
- **Location**: Moto trade-offs section
- **Problem**: Moto has been in production use for roughly a decade, has thousands of real-world integrations, and is maintained by a substantial open-source community. The findings present Moto's documented limitations as weaknesses without acknowledging that its longevity means many corner cases have already been discovered and fixed, its issue tracker is a reliable signal precisely because users report problems, and its stability risk is lower than two newer tools with smaller communities. This context is missing from the trade-offs comparison.
- **Impact**: Medium. The overall framing ("weakest") does not reflect risk-adjusted fitness for the majority of Moto's actual use cases.

---

### Issue 13: Presigned URL analysis is asymmetric and incomplete for Moto
- **Type**: Missing nuance / gap
- **Location**: "Moto has strong S3 breadth, but... I did not find a current explicit Moto claim that presigned URL verification matches AWS end-to-end."
- **Problem**: Moto does implement presigned URL generation, but presigned URLs generated by Moto point to Moto's own server endpoint, not to AWS — meaning they work only within the mocked context and will not replicate AWS's actual URL signature scheme. This is a known, documented architectural characteristic of Moto, not just an undisclosed gap. The research treats this as equivalent to "no evidence found" rather than acknowledging this structural difference, which is more informative than "no claim found."
- **Impact**: Low-medium. Affects the accuracy of the presigned URL section specifically.

---

### Issue 14: The "surprising result" framing inverts the interpretation of transparency
- **Type**: Missing nuance
- **Location**: "The surprising result is that Moto is the most honest source here: its docs state many limitations plainly. Floci and MiniStack look stronger operationally, but their real-world fidelity is harder to audit because they disclose less negative detail publicly."
- **Problem**: This is not a surprising result — it is expected behavior from a mature open-source project with community contributors who document limitations as they discover them. Framing it as "surprising" subtly implies that Floci and MiniStack's lack of disclosed limitations reflects genuine fewer limitations rather than less documentation. The research acknowledges this immediately after ("that is a verification gap, not a clean bill of health") but the "surprising" framing primes the reader to interpret silence as strength.
- **Impact**: Low-medium. The clarifying sentence is present, but the framing may still mislead a reader who skims.

---

## Summary

**Total issues found**: 14

**Overall reliability**: Medium

The findings are honest about their evidentiary limits, the Moto section is well-supported and accurate, and the concluding new questions are appropriately scoped. However, the Floci ranking — the central actionable conclusion — rests on self-published evidence whose authorship is not disclosed, a headline metric (408/408) whose meaning is not defined, and a test methodology that is never examined. The MiniStack analysis is the thinnest of the three tools, as acknowledged.

**What would most improve the findings**:
1. Establish the identity of the `hectorvent.dev` author relative to the Floci project and reweight the evidence accordingly.
2. Define what Floci's "passing" assertion checks (response body? status code? header fidelity?) before treating 408/408 as a fidelity score.
3. Add LocalStack as a baseline comparator so the rankings are anchored.
4. Verify current open/closed status of all cited issues before using them as negative evidence.
5. Explicitly name the core 8 services and reframe the Moto comparison to acknowledge it is a different product class.
