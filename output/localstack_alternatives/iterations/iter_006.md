# Iteration 006 — Migration effort from LocalStack (config, SDK compatibility, breaking changes)

**Status:** keep  
**Scores:** coverage=76.2, quality=67.5, total=71.0  
**Timestamp:** 2026-04-08T17:00:45.158815+00:00  

---

### Findings

For migration effort, the cleanest split is:

1. **MiniStack** is the closest to a LocalStack-shaped control plane.
2. **Floci** is close on the main AWS API surface, but less close on LocalStack-specific operational endpoints.
3. **Moto server** is not a LocalStack drop-in; it is a different testing model with materially different endpoints, control APIs, and service limitations.
4. **Robotocore** looks promising as an additional OSS option, but I did not find enough migration-specific documentation yet to treat it as a low-risk replacement.

**What changes when leaving LocalStack itself**

The first migration step is not AWS-service behavior; it is removing LocalStack-specific glue. Current LocalStack usage often depends on:
- auth tokens in Docker/CI since the unified image change on **March 23, 2026** ([LocalStack blog](https://blog.localstack.cloud/localstack-single-image-next-steps/), [Auth Token docs](https://docs.localstack.cloud/aws/getting-started/auth-token/))
- LocalStack-only internal endpoints like `/_localstack/health` and `/_aws/...` ([internal endpoints docs](https://docs.localstack.cloud/references/internal-endpoints/))
- helper wrappers: `awslocal`, `tflocal`, `cdklocal`, `samlocal` ([awscli-local](https://github.com/localstack/awscli-local), [Terraform docs](https://docs.localstack.cloud/aws/integrations/infrastructure-as-code/terraform/), [aws-cdk-local](https://github.com/localstack/aws-cdk-local), [aws-sam-cli-local](https://github.com/localstack/aws-sam-cli-local))
- sometimes Transparent Endpoint Injection / `localhost.localstack.cloud` DNS behavior, especially for CDK custom resources ([Transparent Endpoint Injection docs](https://docs.localstack.cloud/aws/capabilities/networking/transparent-endpoint-injection/), [SDK integration docs](https://docs.localstack.cloud/aws/integrations/aws-sdks/))

That last item is the biggest hidden migration cost. MiniStack, Floci, and Moto all document plain endpoint override workflows; none of the reviewed docs show a LocalStack-equivalent DNS interception feature.

**Endpoint/config migration by target**

**MiniStack**
- Default remains single-edge on `http://localhost:4566`.
- Dummy credentials and region remain the same pattern as LocalStack: `AWS_ACCESS_KEY_ID=test`, `AWS_SECRET_ACCESS_KEY=test`, `AWS_DEFAULT_REGION=us-east-1`, plus `--endpoint-url=http://localhost:4566` or SDK `endpoint_url`/`endpoint` override ([MiniStack README](https://github.com/Nahuel990/ministack), [MiniStack site](https://ministack.org/)).
- It explicitly says it is compatible with LocalStack health probes:
  - `GET /_localstack/health`
  - `GET /health`
  - plus MiniStack-native `GET /_ministack/health` and `POST /_ministack/reset` ([README](https://github.com/Nahuel990/ministack))
- Terraform migration is manual endpoint configuration, not a wrapper. MiniStack documents a full provider `endpoints { ... }` block and sets `s3_use_path_style = true` ([README](https://github.com/Nahuel990/ministack), [site](https://ministack.org/)).
- CDK migration guidance is thin but straightforward: set `process.env.AWS_ENDPOINT_URL = "http://localhost:4566"` ([README](https://github.com/Nahuel990/ministack)).

**Floci**
- Also uses single-edge `http://localhost:4566`.
- Dummy credentials and any region are accepted; docs recommend `AWS_ENDPOINT_URL=http://localhost:4566` plus `AWS_DEFAULT_REGION=us-east-1` ([Floci README](https://github.com/floci-io/floci), [docs](https://fredpena-floci.mintlify.app/introduction)).
- It claims “drop-in replacement” and “zero lines of application code,” but the docs also show two practical caveats:
  - Node S3 example sets `forcePathStyle: true`
  - multi-container use needs `FLOCI_HOSTNAME=floci`, otherwise returned `QueueUrl` values still point to `http://localhost:4566/...` and break from sibling containers ([README](https://github.com/floci-io/floci))
- In the reviewed docs, I did **not** find a documented `/_localstack/health` compatibility path or a documented reset endpoint. That is not proof they do not exist; it does mean LocalStack-style CI probes are not prominently documented.
- Floci does publish compatibility suites for Terraform and CDK (`compat-terraform`, `compat-cdk`), but the public README gives fewer concrete before/after migration snippets than MiniStack ([README](https://github.com/floci-io/floci)).

**Moto server**
- Default server endpoint is **not** `:4566`; it is `http://127.0.0.1:5000/`, though you can change the port or bind host (`moto_server -p3000`, `-H 0.0.0.0`) ([Moto server-mode docs](https://docs.getmoto.org/en/latest/docs/server_mode.html)).
- Credentials can be dummy values; SDK endpoint overrides are required in server mode ([server-mode docs](https://docs.getmoto.org/en/latest/docs/server_mode.html)).
- Control APIs are Moto-specific:
  - dashboard at `/moto-api/`
  - reset API at `/moto-api/reset` ([server-mode docs](https://docs.getmoto.org/en/latest/docs/server_mode.html))
- There is no LocalStack-compatible `/_localstack/health` surface in the reviewed docs.
- Migration is often bigger because many Moto examples assume Python decorators instead of a black-box container. For non-Python or IaC-heavy teams, only server mode is relevant.

**Which tools are actually LocalStack-compatible vs just “AWS-compatible”**

**Closest to LocalStack operational surface:** MiniStack  
It preserves the familiar single port and explicitly supports `/_localstack/health`. That matters for CI jobs and service readiness checks. It is the only reviewed alternative that clearly documents this compatibility.

**Mostly AWS-compatible, not clearly LocalStack-operational-compatible:** Floci  
It preserves `:4566` and the “point SDK at one endpoint” workflow, but I found no documented LocalStack health/reset compatibility. Operationally, it looks closer to “same AWS wire protocol, different emulator control plane.”

**Not LocalStack-compatible:** Moto  
Moto’s API surface is AWS-ish for many services, but its control plane, health/reset endpoints, and testing model are different enough that LocalStack-based harnesses will need edits.

**Known breaking points when migrating real LocalStack-based projects**

**1. LocalStack wrapper removal is real work**
- If a project uses `awslocal`, `tflocal`, `cdklocal`, or `samlocal`, there is no reviewed equivalent from MiniStack, Floci, or Moto.
- That means moving from wrapper-driven magic back to explicit endpoint config.
- This is especially painful for Terraform and CDK because LocalStack’s wrappers patch more than just one URL. `cdklocal` explicitly patches endpoint env vars, strips conflicting AWS env vars, and forces S3/path-style handling for newer CDK versions ([aws-cdk-local README](https://github.com/localstack/aws-cdk-local), [Terraform docs](https://docs.localstack.cloud/aws/integrations/infrastructure-as-code/terraform/)).

**2. CDK bootstrap and asset publishing remain the highest-risk migration area**
- CDK bootstrap depends on S3, ECR, IAM, and CloudFormation working together ([AWS CDK bootstrap docs](https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping.html)).
- LocalStack has special tooling and, in some cases, Transparent Endpoint Injection specifically because CDK custom resources cannot always be retargeted cleanly ([TEI docs](https://docs.localstack.cloud/aws/capabilities/networking/transparent-endpoint-injection/), [aws-cdk-local README](https://github.com/localstack/aws-cdk-local)).
- MiniStack and Floci both say CDK works, but neither documents a replacement for LocalStack’s DNS interception.
- Inference: projects relying on `cdklocal` or LocalStack DNS tricks are likely to need explicit endpoint env vars at minimum, and custom-resource-heavy stacks may still fail.

**3. S3 endpoint style is still a migration trap**
- AWS SDK v3 has a documented problem with virtual-host-style S3 requests when using a single local endpoint such as `AWS_ENDPOINT_URL=http://localhost:4566` ([AWS SDK JS issue #7136](https://github.com/aws/aws-sdk-js-v3/issues/7136)).
- LocalStack’s own ecosystem needed S3-specific handling in wrappers (`AWS_ENDPOINT_URL_S3`, path-style bucket URL patching in `cdklocal`, `--s3-endpoint-url` support in `awslocal`) ([aws-cdk-local README](https://github.com/localstack/aws-cdk-local), [awscli-local README](https://github.com/localstack/awscli-local)).
- MiniStack’s Terraform example sets `s3_use_path_style = true`; Floci’s Node example sets `forcePathStyle: true` ([MiniStack README](https://github.com/Nahuel990/ministack), [Floci README](https://github.com/floci-io/floci)).
- Practical conclusion: if your LocalStack project “worked by accident” with a generic `AWS_ENDPOINT_URL`, migration may expose S3 path-style assumptions rather than remove them.

**4. Returned URL correctness differs by emulator**
- LocalStack has configurable SQS returned URL strategies and uses `localhost.localstack.cloud` subdomains ([SQS docs](https://docs.localstack.cloud/aws/services/sqs/), [networking docs](https://docs.localstack.cloud/aws/capabilities/networking/accessing-endpoint-url/)).
- Floci documents `FLOCI_BASE_URL` and `FLOCI_HOSTNAME` because returned URLs can otherwise point at the wrong host from other containers ([Floci README](https://github.com/floci-io/floci)).
- MiniStack, in the reviewed docs, does not document an equivalent returned-URL hostname control.
- Moto documents server mode generally, but not a LocalStack-like returned-URL strategy; it also notes a host-file caveat for `s3-control` ([Moto server-mode docs](https://docs.getmoto.org/en/latest/docs/server_mode.html)).
- For CI on Docker Compose or service containers, this is a real migration risk.

**5. Moto has the largest semantic break from LocalStack for API Gateway and Lambda-heavy stacks**
- API Gateway: Moto documents that only `HTTP` integrations and `AWS` integrations with DynamoDB are supported; `AWS_PROXY`, `MOCK`, and others are ignored, and mocked public URLs work only in decorator mode, not server mode ([Moto API Gateway docs](https://docs.getmoto.org/en/5.0.24/docs/services/apigateway.html)).
- Lambda: Moto documents Docker execution, but also says Lambdas need MotoServer/MotoProxy reachability to call other mocked AWS services; `PackageType=Image` invocation is not supported ([Moto Lambda docs](https://docs.getmoto.org/en/5.0.25/docs/services/lambda.html), [server-mode docs](https://docs.getmoto.org/en/latest/docs/server_mode.html)).
- So migrating a LocalStack end-to-end black-box integration suite to Moto often means redesigning tests, not just changing the endpoint.

**6. MiniStack appears to have the lowest LocalStack-to-alt migration friction**
- Same `:4566`
- same test creds/region pattern
- explicit `/_localstack/health` compatibility
- explicit Terraform endpoint examples
- CDK guidance via `AWS_ENDPOINT_URL`
- but CloudFormation is still only **12 resource types**, so “easy migration” does not mean “high-fidelity IaC success” ([MiniStack README](https://github.com/Nahuel990/ministack), [site](https://ministack.org/))

**7. Floci looks easy for simple SDK/CLI swaps, riskier for opaque LocalStack-integrated harnesses**
- Best case: swap Docker image, remove auth token, keep `AWS_ENDPOINT_URL=http://localhost:4566`
- Worst case: if you depended on LocalStack internal endpoints, path-style quirks being patched for you, or `localhost.localstack.cloud`/DNS behavior, there is more work than Floci’s marketing copy suggests
- That does not mean Floci is weak; it means the migration docs are thinner than the “drop-in” claim.

**8. Additional OSS alternative: Robotocore**
- I found an official coverage page and third-party launch coverage indicating a single-edge `:4566` model and a `_robotocore/health` endpoint ([coverage page](https://robotocore.github.io/robotocore/coverage.html), [UBOS article](https://ubos.tech/news/introducing-robotocore-open%E2%80%91source-local-aws-twin-revolutionizes-cloud-development/)).
- I did **not** find enough first-party migration docs, wrapper guidance, or community migration failures to rate its migration effort confidently.
- For a senior architect, I would treat it as an emerging candidate, not yet a safe short-list winner for immediate LocalStack replacement.

### Evidence

**Config diffs**

**LocalStack Docker service**
```yaml
# before
services:
  localstack:
    image: localstack/localstack
    ports:
      - "4566:4566"
    environment:
      - LOCALSTACK_AUTH_TOKEN=${LOCALSTACK_AUTH_TOKEN}
```

**MiniStack / Floci**
```yaml
# after: MiniStack
services:
  ministack:
    image: nahuelnucera/ministack
    ports:
      - "4566:4566"

# after: Floci
services:
  floci:
    image: hectorvent/floci:latest
    ports:
      - "4566:4566"
```
Sources: [LocalStack auth-token change](https://blog.localstack.cloud/localstack-single-image-next-steps/), [MiniStack README](https://github.com/Nahuel990/ministack), [Floci README](https://github.com/floci-io/floci)

**Terraform**
```hcl
# LocalStack wrapper style
tflocal apply
```

```hcl
# MiniStack manual provider style
provider "aws" {
  region                      = "us-east-1"
  access_key                  = "test"
  secret_key                  = "test"
  s3_use_path_style           = true
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  endpoints {
    s3       = "http://localhost:4566"
    dynamodb = "http://localhost:4566"
    lambda   = "http://localhost:4566"
  }
}
```
Sources: [LocalStack Terraform docs](https://docs.localstack.cloud/aws/integrations/infrastructure-as-code/terraform/), [MiniStack README](https://github.com/Nahuel990/ministack)

**CDK**
```bash
# LocalStack-specific
cdklocal deploy
```

```bash
# MiniStack/Floci-style explicit env
export AWS_ENDPOINT_URL=http://localhost:4566
cdk deploy
```
Sources: [aws-cdk-local README](https://github.com/localstack/aws-cdk-local), [MiniStack README](https://github.com/Nahuel990/ministack), [Floci README](https://github.com/floci-io/floci)

**Moto server**
```bash
moto_server -p5000
export AWS_ENDPOINT_URL=http://localhost:5000
```
Sources: [Moto server-mode docs](https://docs.getmoto.org/en/latest/docs/server_mode.html)

**Numbers directly relevant to migration**
- LocalStack unified image requiring auth token from **March 23, 2026**: [blog](https://blog.localstack.cloud/localstack-single-image-next-steps/), [auth docs](https://docs.localstack.cloud/aws/getting-started/auth-token/)
- MiniStack: `4566`, `~2s` startup, `~30MB` idle RAM, `~250MB` image, `900+` tests: [site](https://ministack.org/), [README](https://github.com/Nahuel990/ministack)
- Floci: `4566`, `24ms` startup, `13 MiB` idle RAM, `~90MB` image, `408/408` SDK checks, `compat-terraform` and `compat-cdk` suites listed: [README](https://github.com/floci-io/floci), [docs](https://fredpena-floci.mintlify.app/introduction)
- Moto server default port `5000`, random free ports supported via `ThreadedMotoServer(port=0)`: [server-mode docs](https://docs.getmoto.org/en/latest/docs/server_mode.html)
- Moto API Gateway limitations: `AWS_PROXY` and `MOCK` ignored; public URLs only in decorator mode: [API Gateway docs](https://docs.getmoto.org/en/5.0.24/docs/services/apigateway.html)
- Moto Lambda limitation: `PackageType=Image` invocation unsupported: [Lambda docs](https://docs.getmoto.org/en/5.0.25/docs/services/lambda.html)

### Trade-offs

**MiniStack is best when migration cost matters more than published fidelity depth.**  
It keeps the familiar `:4566` model, supports `/_localstack/health`, and documents explicit Terraform and CDK endpoint overrides. The trade-off is that it is still not a full LocalStack replacement for non-trivial IaC; CloudFormation support is narrow, and its “real Postgres/Redis/Docker” architecture changes failure modes.

**Floci is best when the project already uses plain SDK endpoint overrides and little LocalStack-specific tooling.**  
If your code already does `AWS_ENDPOINT_URL=http://localhost:4566`, the migration can be very small. If your pipeline relies on LocalStack wrappers, custom DNS behavior, or CI probes against `/_localstack/health`, migration is less trivial than Floci’s “zero changes” positioning implies. The `forcePathStyle` and `FLOCI_HOSTNAME` knobs are the tell.

**Moto is best when you are willing to migrate away from “LocalStack-style integration environment” toward “test harness under our control.”**  
For Python-first teams, that can be a feature, not a bug. For teams using Terraform, CDK bootstrap, API Gateway proxy integrations, or Lambda image flows, it is the highest migration-effort option here.

**Robotocore is the main additional OSS project worth watching, not yet recommending for low-friction migration.**  
The shape looks attractive, but the migration evidence is not mature enough yet. That is a documentation risk by itself.

### New Questions

1. Which emulator has the lowest failure rate for **CDK asset publishing and bootstrap** under real `cdk deploy` runs, not just README claims?
2. How do MiniStack and Floci behave with **LocalStack-specific helper tools removed** in large repos that currently depend on `cdklocal`, `tflocal`, or `samlocal`?
3. Which emulator gives the most correct behavior for **returned service URLs** in Docker Compose and CI service-container topologies, especially SQS and API Gateway?

---

## Peer Review (claude)

### Issue 1: Moto documentation is cited at stale versioned URLs

- **Type**: Factual error / gap
- **Location**: "Moto API Gateway docs (v5.0.24)" and "Moto Lambda docs (v5.0.25)"
- **Problem**: The findings cite two different pinned Moto release versions (5.0.24 and 5.0.25) for two different service pages. Moto is actively maintained and releases frequently. As of early 2026, Moto would be well past version 5.0.x. The API Gateway limitation list in particular has changed across releases; some previously-unsupported integration types have gained partial support. Citing two different old version pins creates a risk that the stated limitations are already outdated, and using different version numbers for different service pages suggests the researcher was not consistently using the same release.
- **Impact**: The strongest negative claim in the document — that Moto has a "largest semantic break" for API Gateway and Lambda — may be accurate in direction but overstated in degree if the current release has expanded support since 5.0.24/5.0.25.

---

### Issue 2: "Real Postgres/Redis/Docker architecture" claim for MiniStack is unsupported

- **Type**: Unsupported claim
- **Location**: "its 'real Postgres/Redis/Docker' architecture changes failure modes"
- **Problem**: This architectural description appears nowhere in the cited sources (MiniStack README and site). No citation is provided. If MiniStack actually uses real Postgres/Redis internally, that is a significant architectural differentiator worth sourcing directly. If it does not, this claim is fabricated or conflated from another tool.
- **Impact**: This characterization directly affects the trade-off assessment. If MiniStack does use real backing services, it has meaningfully different failure modes than a pure in-memory mock — a claim that should either be verified and cited, or removed.

---

### Issue 3: MiniStack Docker image name inconsistency

- **Type**: Factual error
- **Location**: The Docker Compose "after" example shows `image: nahuelnucera/ministack`; the GitHub URL is `github.com/Nahuel990/ministack`
- **Problem**: The Docker Hub org (`nahuelnucera`) and the GitHub handle (`Nahuel990`) differ. These may resolve to the same person, but a reader following the evidence chain would find the names do not match, and a team pulling the image without independent verification might pull from the wrong registry or a differently-named image. The correct Docker Hub image name was not independently confirmed.
- **Impact**: A practitioner copying the Docker Compose snippet could pull the wrong image. Low impact on analysis quality, but high impact on reproducibility.

---

### Issue 4: Floci "24ms startup" metric lacks definitional context

- **Type**: Missing nuance
- **Location**: "Floci: 4566, 24ms startup, 13 MiB idle RAM, ~90MB image"
- **Problem**: 24ms is almost certainly the time for the HTTP endpoint to become ready after the container process is already running — not the Docker container cold-start time, which would include image pull, layer extraction, and process init. The distinction matters for CI. Comparing "24ms service ready time" to MiniStack's "~2s startup" is not apples-to-apples if they measure different things. Neither metric's measurement methodology is defined.
- **Impact**: The performance comparison between alternatives is unreliable if the underlying metrics measure different things. A reader could overweight Floci on startup performance based on incomparable numbers.

---

### Issue 5: "900+ tests" for MiniStack is cited as a coverage signal without context

- **Type**: Missing nuance
- **Location**: "MiniStack: 4566, ~2s startup, ~30MB idle RAM, ~250MB image, 900+ tests"
- **Problem**: A project's internal test count says nothing definitive about service breadth or fidelity. 900 tests could cover 3 services deeply or 30 services shallowly. This is the only coverage metric offered for MiniStack alongside Floci's "408/408 SDK checks" — and neither metric is explained. The comparison creates a misleading impression of relative coverage without a common denominator.
- **Impact**: Readers cannot use these numbers to make a meaningful fidelity comparison. The omission of actual service coverage lists (which services are supported, at what depth) is a significant analytical gap throughout the findings.

---

### Issue 6: Service coverage comparison is entirely missing

- **Type**: Gap
- **Location**: Throughout the findings
- **Problem**: The entire analysis focuses on operational surface (port, health endpoints, startup, credentials) and does not provide a service-by-service coverage table for any alternative. For a migration decision, the most critical question is: "Does this emulator support the specific AWS services and operations my project uses?" S3, SQS, SNS, DynamoDB, Lambda, API Gateway, Step Functions, EventBridge, Secrets Manager, and IAM are each meaningfully different across MiniStack, Floci, and Moto. The only service-level detail offered is CloudFormation's "12 resource types" for MiniStack and Moto's API Gateway/Lambda caveats.
- **Impact**: A team relying on Step Functions, EventBridge, or Secrets Manager has no guidance at all. This is arguably the most important gap in the findings for a practical migration assessment.

---

### Issue 7: LocalStack Community vs. Pro distinction is absent from the auth token analysis

- **Type**: Missing nuance
- **Location**: "auth tokens in Docker/CI since the unified image change on March 23, 2026"
- **Problem**: Historically, LocalStack's community/free tier did not require auth tokens — that was a Pro-tier gating mechanism. The March 2026 unified image change may mean auth tokens are now required even for the free tier, which would be a significant policy change affecting a much larger user base than just Pro customers. The findings do not clarify whether this change affects free-tier users, Pro users, or both. This matters because the migration urgency differs: a team that was using LocalStack free and had no auth token obligation faces a different situation than a team that was already paying for Pro.
- **Impact**: Overstates or understates migration urgency depending on the reader's LocalStack tier. The cited blog post presumably clarifies this, but the findings do not surface the distinction.

---

### Issue 8: CDK migration via `AWS_ENDPOINT_URL` is oversimplified

- **Type**: Missing nuance
- **Location**: "CDK migration guidance is thin but straightforward: set `process.env.AWS_ENDPOINT_URL = 'http://localhost:4566'`" and the CDK snippet `export AWS_ENDPOINT_URL=http://localhost:4566 && cdk deploy`
- **Problem**: `AWS_ENDPOINT_URL` as a universal CDK override is not straightforward. CDK constructs that invoke Lambda or API Gateway internally, custom resource providers that make SDK calls at deploy time, and constructs that use the AWS SDK v2 (which does not honor `AWS_ENDPOINT_URL` the same way v3 does) all behave differently. CDK version also matters — newer CDK versions changed how asset publishing and bootstrapping call into AWS. The finding acknowledges "custom-resource-heavy stacks may still fail" but frames the env-var approach as the standard fix when it is not reliably sufficient.
- **Impact**: A team with a non-trivial CDK stack may follow this guidance, encounter failures, and conclude the alternative emulator is broken when the real problem is the oversimplified migration path.

---

### Issue 9: Floci's "zero lines of application code" contradiction is identified but not resolved

- **Type**: Contradiction (unresolved)
- **Location**: "It claims 'drop-in replacement' and 'zero lines of application code,' but the docs also show two practical caveats: Node S3 example sets `forcePathStyle: true`; multi-container use needs `FLOCI_HOSTNAME=floci`"
- **Problem**: The findings correctly flag this tension but do not reach a conclusion about it. Setting `forcePathStyle: true` in an S3 client constructor is a code change. If the application previously worked without it (as it might with LocalStack's path-style handling), then the "zero lines of application code" claim is false by the emulator's own documentation. The findings hedge with "not proof they do not exist" phrasing for the health endpoint, but apply no such epistemic humility to whether the code-change caveats actually contradict the marketing claim.
- **Impact**: Floci's trade-off assessment is too favorable. The "best case: swap Docker image" framing should be qualified with "only if you already have forcePathStyle configured and only if you're not in a multi-container topology."

---

### Issue 10: Testcontainers integration is not addressed

- **Type**: Gap
- **Location**: Throughout the "wrapper removal" and migration sections
- **Problem**: Testcontainers is a widely-used integration pattern for LocalStack (the `localstack/testcontainers-go`, `localstack/testcontainers-java`, and `testcontainers-python` integrations are common). None of the alternatives' Testcontainers support is assessed. Teams using Testcontainers with LocalStack have a Java/Go/Python lifecycle management layer that is tightly coupled to the LocalStack container image. Replacing the image silently may break Testcontainers init strategies (wait conditions, health-check probes, module-specific config).
- **Impact**: A material class of LocalStack users — those in JVM or Go ecosystems using Testcontainers — has no migration guidance whatsoever.

---

### Issue 11: MiniStack CloudFormation "12 resource types" — unverified specificity

- **Type**: Unsupported claim (partially)
- **Location**: "CloudFormation is still only 12 resource types"
- **Problem**: This is a very precise number cited to the MiniStack README and site, but CloudFormation resource type counts change with releases. The finding presents this as a current fact without a version or timestamp. More importantly, the 12-type figure is not put in context: LocalStack Community supports a much larger number, and LocalStack Pro supports hundreds. Without knowing *which* 12 types MiniStack supports, the number is not actionable — a team using only those 12 types might be fine; a team using 13 might be blocked entirely.
- **Impact**: The CloudFormation limitation is correctly flagged as important, but the number alone without a list of supported types is not enough for a migration decision.

---

### Issue 12: Moto's server mode limitations for API Gateway are stated categorically from old docs

- **Type**: Factual error (potentially)
- **Location**: "API Gateway: Moto documents that only HTTP integrations and AWS integrations with DynamoDB are supported; AWS_PROXY, MOCK, and others are ignored"
- **Problem**: The `AWS_PROXY` integration type limitation is cited from Moto 5.0.24, which is a significantly old release for an active project. `AWS_PROXY` support in Moto has been a long-standing community request and partial implementations have been contributed over time. Stating categorically that `AWS_PROXY` is "ignored" based on a stale doc version risks being wrong for current Moto. Similarly, "AWS integrations with DynamoDB are supported" is oddly specific — the actual supported list may differ.
- **Impact**: If `AWS_PROXY` has partial or full support in current Moto, the "largest semantic break" and "redesigning tests" conclusions about API Gateway stacks may be overstated.

---

### Issue 13: The hierarchy of migration friction is inconsistent between the summary and the detail

- **Type**: Contradiction (structural)
- **Location**: "The first migration step is not AWS-service behavior; it is removing LocalStack-specific glue" vs. the detailed breakdown, which spends the majority of its analysis on AWS-service behavior differences
- **Problem**: The opening framing argues glue removal is the primary cost. But the "Known breaking points" section spends five of eight items on service-behavior and testing-model differences (CDK bootstrap, S3 path style, returned URLs, API Gateway limitations, Lambda limitations). For teams with complex stacks, service-behavior failures are clearly the harder problem. The glue-first framing is accurate for simple projects but misleading as a general claim.
- **Impact**: A reader who internalizes "the hard part is just removing wrappers" will under-budget migration effort. The document's own evidence contradicts this framing.

---

### Issue 14: No mention of credential/IAM behavior differences

- **Type**: Gap
- **Location**: Throughout
- **Problem**: LocalStack has IAM enforcement that can be toggled (strict mode vs. lenient mode). Some teams rely on LocalStack's IAM simulation to test policies. The findings mention dummy credentials for all alternatives but do not discuss whether MiniStack, Floci, or Moto simulate IAM authorization or simply accept any credentials. This is a meaningful difference for security-testing workflows.
- **Impact**: Teams using LocalStack's IAM enforcement as a policy-testing mechanism have no guidance on whether any alternative supports this pattern.

---

## Summary

**Total issues found**: 14

**Overall reliability assessment**: **Medium**

The findings are directionally sound — MiniStack is plausibly the closest LocalStack analog, Moto is plausibly the furthest, and the identified migration pain points (wrappers, CDK, S3 path-style, returned URLs) are real. The sourcing is generally specific and the hedging on Robotocore and Floci health endpoints is appropriately cautious.

**What would most improve the findings**:

1. **Replace stale Moto version citations** (5.0.24/5.0.25) with current-release docs and re-evaluate the API Gateway/Lambda limitations.
2. **Add a service coverage matrix** — even a partial table of "which services are supported" for each alternative would dramatically increase the document's utility for migration decisions.
3. **Source or remove the MiniStack "real Postgres/Redis/Docker" architectural claim** — it is either the most architecturally interesting fact in the document or an error, and right now it sits unsupported.
4. **Clarify the LocalStack free-vs-Pro auth token impact** of the March 2026 unified image change, since that determines migration urgency for the majority of users.
5. **Address Testcontainers** as a migration surface, especially for JVM and Go teams.
