# Iteration 010 — Terraform compatibility

**Status:** discard  
**Scores:** coverage=61.7, quality=77.5, total=71.2  
**Timestamp:** 2026-04-08T21:15:46.845524+00:00  

---

### Findings

For Terraform `plan/apply` in a commercial CI container, **LocalStack is the only one of the four with first-class, current Terraform-specific documentation and a maintained Terraform wrapper**. Its docs support two paths: manual AWS provider `endpoints {}` overrides and the `tflocal` wrapper, which generates provider override files automatically. LocalStack also documents the S3 special case (`s3.localhost.localstack.cloud` or `localhost:4566` with path-style access), and `terraform-local` has kept pace with AWS provider churn, with changelog entries for fixes targeting provider `5.9.0`, `5.22.0`, and `>= 6.0.0-beta2`, plus later fixes for local S3 backend handling and `terraform_remote_state` against local S3 backends. That is materially stronger evidence than the others for real CI use, especially where `init`, backend access, and nested modules are involved. Sources: [LocalStack Terraform docs](https://docs.localstack.cloud/aws/integrations/infrastructure-as-code/terraform/), [terraform-local README/changelog](https://github.com/localstack/terraform-local), [Terraform S3 backend docs](https://developer.hashicorp.com/terraform/language/backend/s3).

A non-obvious but important Terraform point: **backend configuration is separate from provider configuration**. Even if resources use provider `endpoints {}`, `terraform init` will still talk to the backend first. HashiCorp’s S3 backend docs explicitly support `endpoints.*` and `AWS_ENDPOINT_URL`/`AWS_ENDPOINT_URL_<SERVICE>` for backend API overrides, and they deprecate DynamoDB locking in favor of `use_lockfile`. That means any emulator can support Terraform state in principle, but only LocalStack currently documents and tools that path well. This matters in CI because backend misconfiguration fails before `plan` or `apply` ever reaches your provider block. Sources: [Terraform S3 backend docs](https://developer.hashicorp.com/terraform/language/backend/s3), [AWS service-specific endpoint env vars](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html), [terraform-local README/changelog](https://github.com/localstack/terraform-local).

For **credentials**, the AWS provider still wants a credential source even when validation is skipped. In practice that means dummy `access_key`/`secret_key` or a dummy profile are still needed in CI, alongside `skip_credentials_validation`, `skip_metadata_api_check`, and often `skip_requesting_account_id`. This is not emulator-specific; it is a Terraform AWS provider behavior that affects all four tools. LocalStack and MiniStack both show the standard dummy-credential pattern in their docs/snippets. Sources: [HashiCorp Discuss thread on skipped validation still needing creds](https://discuss.hashicorp.com/t/how-to-skip-all-aws-provider-credentials-checks/71568), [HashiCorp issue #37062](https://github.com/hashicorp/terraform-provider-aws/issues/37062), [LocalStack Terraform docs](https://docs.localstack.cloud/aws/integrations/infrastructure-as-code/terraform/), [MiniStack site](https://ministack.org/).

**MiniStack** has the minimum viable Terraform story, but not an enterprise-grade documented one yet. Its official site shows a standard Terraform AWS provider block with dummy credentials and per-service `endpoints {}` overrides, and it claims compatibility with Terraform/CDK/Pulumi plus `30+` AWS services. On paper, it covers the services most Terraform CI jobs care about: EC2/VPC, IAM, S3, DynamoDB, Lambda, SSM Parameters, ECR, ECS, and ELBv2. It also claims `~2s` startup, `~30MB` idle RAM, `~250MB` image size, and `900+` tests. What is missing is equally important: I did not find project-controlled docs for Terraform remote state backends, provider-version constraints, module aliasing, or `terraform init` gotchas. For a production CI decision, that makes MiniStack promising but still weakly evidenced. Source basis is mostly the project website rather than a mature Terraform doc set. Sources: [MiniStack site](https://ministack.org/), [AlternativeTo project summary](https://alternativeto.net/software/ministack-/about/).

**Floci** is the most misleading candidate if the requirement is “typical Terraform AWS CI stack” rather than “supported services with good fidelity.” Its official site presents it as a drop-in replacement on port `4566`, and it has one good Terraform signal: release notes cite a fix for “DynamoDB table creation compatibility with Terraform AWS provider v6.” It also publishes strong compatibility numbers on supported services: `408/408` SDK checks, `12/12` DynamoDB Streams, `18/18` STS, `15/15` Kinesis, `8/8` Cognito, `50/50` RDS, with `24 ms` startup and `13 MiB` idle memory. But its official supported-service list does **not** include EC2/VPC, ECS, or ECR. It includes S3, DynamoDB, Lambda, IAM, STS, SSM Parameter Store, CloudFormation, EventBridge, CloudWatch, RDS, and ElastiCache, but that is not enough for many Terraform CI pipelines that stand up networking and container infrastructure. So Floci looks strong for app-centric stacks, but weak for broader Terraform AWS module testing. Sources: [Floci official site](https://floci.io/), [Floci official project page](https://hectorvent.dev/floci/), [release-note mirror of Floci 1.1.0 mentioning Terraform v6 compatibility](https://newreleases.io/project/github/floci-io/floci/release/1.1.0).

**Moto** can be made to work with Terraform by pointing the AWS provider at `moto_server`, but it is the most manual path and the least CI-friendly for broad AWS IaC. Moto’s server mode is explicitly for non-Python SDKs and external tools, so endpoint override is conceptually valid. It also implements all of the critical service families on paper: EC2, IAM, S3, DynamoDB, Lambda, ECS, ECR, and SSM. The problem is fidelity depth. Moto’s ECS page shows many missing operations, including `execute_command`, `discover_poll_endpoint`, multiple deployment APIs, and several update flows. ECR is partial too, with gaps such as `batch_check_layer_availability` and `complete_layer_upload`. SSM has a large number of missing operations and hardcoded default parameters that can be stale. Lambda works in Docker, but server-mode networking is a gotcha: functions need `MOTO_HOST`/`MOTO_PORT` or proxy mode to call other emulated AWS services correctly. That makes Moto acceptable for narrow Terraform modules, especially around S3/DynamoDB/IAM/basic EC2, but high-risk for production CI if your Terraform touches ECS/ECR/SSM-heavy infrastructure. Sources: [Moto server mode docs](https://docs.getmoto.org/en/latest/docs/server_mode.html), [Moto implemented services index](https://docs.getmoto.org/en/latest/docs/services/index.html), [Moto ECS docs](https://docs.getmoto.org/en/latest/docs/services/ecs.html), [Moto ECR docs](https://docs.getmoto.org/en/latest/docs/services/ecr.html), [Moto SSM docs](https://docs.getmoto.org/en/stable/docs/services/ssm.html), [Moto Lambda docs](https://docs.getmoto.org/en/5.0.25/docs/services/lambda.html).

On the specific service set you asked about:

- **LocalStack**: strongest evidence overall. S3, DynamoDB, IAM, Lambda, ECS, ECR, EC2/VPC, and SSM are all documented. Fidelity varies by tier and feature. EC2/VPC in Community defaults to mock/CRUD behavior; more realistic instance execution needs Pro and Docker/libvirt. SSM has explicit limitations and depends on Dockerized instances. ECS/ECR have dedicated tutorials and service docs. Sources: [EC2](https://docs.localstack.cloud/references/coverage/coverage_ec2/), [IAM](https://docs.localstack.cloud/references/coverage/coverage_iam/), [DynamoDB](https://docs.localstack.cloud/aws/services/dynamodb/), [Lambda](https://docs.localstack.cloud/aws/services/lambda/), [ECS](https://docs.localstack.cloud/aws/services/ecs/), [ECR](https://docs.localstack.cloud/references/coverage/coverage_ecr/), [SSM](https://docs.localstack.cloud/user-guide/aws/ssm/).
- **MiniStack**: strongest coverage claim among the non-LocalStack tools for a Terraform CI use case, because it explicitly claims EC2/VPC, IAM, S3, DynamoDB, Lambda, SSM, ECR, ECS, and ELBv2. But those are mostly marketing/service-list claims rather than a deep Terraform compatibility matrix. Source: [MiniStack site](https://ministack.org/).
- **Floci**: high confidence for S3, DynamoDB, Lambda, IAM, SSM; low confidence or outright missing for VPC/EC2, ECS, and ECR because they are absent from the official service list. Source: [Floci official site](https://floci.io/).
- **Moto**: broad nominal coverage, but uneven fidelity. Stronger for S3/DynamoDB/IAM/basic EC2 than for ECS/ECR/advanced SSM/Lambda integration. Sources: [Moto services index](https://docs.getmoto.org/en/latest/docs/services/index.html), [ECS](https://docs.getmoto.org/en/latest/docs/services/ecs.html), [ECR](https://docs.getmoto.org/en/latest/docs/services/ecr.html), [SSM](https://docs.getmoto.org/en/stable/docs/services/ssm.html).

The main CI container gotchas are also security-relevant:

- `terraform init` backend traffic must be overridden separately from provider traffic.
- Dummy AWS credentials are still needed for the AWS provider/backend even when validation is skipped.
- LocalStack’s `tflocal` solves nested-module/provider-alias problems, but only by writing temporary override files; that is convenient, but it is also a mutation step inside the workspace.
- LocalStack advanced EC2/SSM/ECS flows, MiniStack ECS/RDS/ElastiCache flows, Floci Lambda/RDS/ElastiCache flows, and Moto Lambda Docker execution all tend to require Docker socket access or container networking exceptions. In a security-first CI pipeline, that widens the runner attack surface and should be treated as a meaningful trade-off, not just an implementation detail.

### Evidence

- Terraform S3 backend supports endpoint overrides and backend env vars: `AWS_ENDPOINT_URL`, `AWS_ENDPOINT_URL_S3`, `AWS_ENDPOINT_URL_DYNAMODB`, with DynamoDB locking now deprecated in favor of `use_lockfile`. Source: [HashiCorp S3 backend docs](https://developer.hashicorp.com/terraform/language/backend/s3).
- AWS shared endpoint model supports `AWS_ENDPOINT_URL` and service-specific `AWS_ENDPOINT_URL_<SERVICE>`. Source: [AWS SDK/tool endpoint docs](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html).
- LocalStack `terraform-local` changelog shows Terraform-provider compatibility maintenance:
  - fix for AWS provider `5.9.0`
  - fix for AWS provider `5.22.0`
  - fix for AWS provider `>= 6.0.0-beta2`
  - support for `terraform_remote_state` with local S3 backend
  - fix for S3 backend forcing DynamoDB lock by default
  Source: [terraform-local README/changelog](https://github.com/localstack/terraform-local).
- LocalStack `tflocal` documents `ADDITIONAL_TF_OVERRIDE_LOCATIONS` for nested modules and `AWS_ENDPOINT_URL` for target instance selection. Source: [terraform-local README](https://github.com/localstack/terraform-local), [LocalStack Terraform docs](https://docs.localstack.cloud/aws/integrations/infrastructure-as-code/terraform/).
- MiniStack publishes:
  - `30+` AWS services
  - `~2s` startup
  - `~30MB` idle RAM
  - `~250MB` Docker image
  - `900+` tests passing
  - Terraform provider example with dummy creds and endpoint overrides
  Source: [MiniStack site](https://ministack.org/).
- Floci publishes:
  - `22` AWS services
  - `24 ms` startup
  - `13 MiB` idle memory
  - `~90 MB` Docker image
  - `408/408` SDK checks
  - `12/12` DynamoDB Streams
  - `18/18` STS
  - `15/15` Kinesis
  - `8/8` Cognito
  - `50/50` RDS
  Source: [Floci official site](https://floci.io/).
- Floci release notes include “DynamoDB table creation compatibility with Terraform AWS provider v6” in `1.1.0`. Source: [release-note mirror](https://newreleases.io/project/github/floci-io/floci/release/1.1.0).
- Moto server mode runs on port `5000` by default and is intended for non-Python SDKs/external tools. Source: [Moto server mode docs](https://docs.getmoto.org/en/latest/docs/server_mode.html).
- Moto ECS has many missing APIs; Moto ECR lacks some upload/layer APIs; Moto SSM has extensive gaps. Sources: [Moto ECS](https://docs.getmoto.org/en/latest/docs/services/ecs.html), [Moto ECR](https://docs.getmoto.org/en/latest/docs/services/ecr.html), [Moto SSM](https://docs.getmoto.org/en/stable/docs/services/ssm.html).

### Trade-offs

LocalStack is still the safest functional choice for Terraform-heavy CI if you can tolerate its broader operational/legal context from prior research. It is the only option here with a credible answer to `terraform init`, aliased providers, nested modules, and local S3 remote state. The downside is that realistic Lambda/ECS/EC2/SSM behavior often pulls in Docker socket mounts or wider container privileges.

MiniStack is the most interesting challenger for Terraform specifically because, unlike Floci, it claims the full “boring enterprise Terraform” set: VPC/EC2, IAM, S3, DynamoDB, Lambda, SSM, ECR, ECS. If those claims hold up, it could become the best non-LocalStack option. Right now the issue is evidence quality, not feature ambition. For a production CI standard, the lack of backend/state/provider-version documentation is a real maturity gap.

Floci looks best if your Terraform is mostly around app-facing managed services and does not need VPC/ECS/ECR. It also has the cleanest public fidelity metrics on supported services. But for the stated use case, missing EC2/VPC/ECS/ECR is a practical disqualifier unless your internal Terraform modules truly avoid those domains.

Moto is the lowest-friction way to mock a few AWS APIs, but it is the weakest fit for full Terraform CI. It has breadth, but too much of that breadth is partial. That makes it a useful test harness and a poor default for production CI pipelines that need confidence in `plan/apply` parity.

### New Questions

1. Which of these tools can run Terraform against an **S3 remote backend with locking** in a fully documented, reproducible way inside a hermetic CI container, without hidden local mutations or AWS config leakage?
2. For LocalStack, MiniStack, and Floci, how much of Terraform compatibility depends on **Docker socket access** for Lambda/ECS/RDS-style resources, and can that be replaced with safer sidecar or rootless patterns?
3. Which projects publish a **Terraform-focused conformance suite** against current `hashicorp/aws` provider versions, rather than general SDK/API tests?

---

## Peer Review (claude)

### Issue 1: DynamoDB locking described as "deprecated" — likely too strong
- **Type**: Factual error / missing nuance
- **Location**: "they deprecate DynamoDB locking in favor of `use_lockfile`"
- **Problem**: HashiCorp introduced `use_lockfile` (S3 native locking) in Terraform 1.10 as an alternative, but DynamoDB locking has not been formally deprecated — it remains fully supported. "Deprecated" implies scheduled removal; the accurate framing is that `use_lockfile` is the preferred or recommended new path. This is a meaningful distinction for teams making infrastructure decisions.
- **Impact**: Readers may incorrectly conclude they should immediately migrate away from DynamoDB locking, or that emulators without DynamoDB support are safe to recommend because the mechanism is going away.

---

### Issue 2: AlternativeTo cited as a source for MiniStack technical claims
- **Type**: Unsupported claim / gap
- **Location**: "Sources: [MiniStack site](https://ministack.org/), [AlternativeTo project summary](https://alternativeto.net/software/ministack-/about/)"
- **Problem**: AlternativeTo is a user-generated software directory. It is not an authoritative source for MiniStack's service coverage, test counts, or compatibility claims. Using it alongside the project's own self-reported numbers does not add independent corroboration — it likely just mirrors the project's marketing copy. This is the only non-primary source cited, and it happens to be for the weakest-evidenced candidate.
- **Impact**: The footnote creates a false impression of cross-validation for MiniStack's coverage claims. The evidentiary weight for MiniStack is effectively single-sourced from the project website itself.

---

### Issue 3: MOTO_HOST/MOTO_PORT variable names unverified
- **Type**: Unsupported claim / possible factual error
- **Location**: "Lambda works in Docker, but server-mode networking is a gotcha: functions need `MOTO_HOST`/`MOTO_PORT` or proxy mode to call other emulated AWS services correctly."
- **Problem**: Moto's documented mechanism for Lambda functions calling other mocked services involves a proxy approach and environment injection, but the specific env var names `MOTO_HOST` and `MOTO_PORT` are not standard Moto configuration variables. Moto's actual networking configuration uses `MOTO_LAMBDA_RESPONSE_URL` or its `allow_response_passthrough` proxy mechanism. No citation is provided for these variable names.
- **Impact**: A practitioner following this guidance would fail to configure Lambda-to-service routing correctly. This is one of the highest-friction integration points for Moto in CI, so the inaccuracy lands in exactly the place where precision matters most.

---

### Issue 4: LocalStack EC2 execution cites "Docker/libvirt" — imprecise pairing
- **Type**: Factual error / missing nuance
- **Location**: "more realistic instance execution needs Pro and Docker/libvirt"
- **Problem**: LocalStack uses Docker for container-based Lambda/ECS execution and QEMU (or KVM) for VM-level EC2 emulation. Libvirt is a management layer over KVM/QEMU, not a runtime that LocalStack directly documents or requires. Grouping "Docker/libvirt" as a slash-pair implies they are equivalent options for the same thing; they are not. Docker handles container workloads; QEMU/KVM handles VM workloads; libvirt is a separate abstraction.
- **Impact**: Engineers evaluating the security/privilege cost of LocalStack EC2 would be confused about what socket or capability they actually need to mount. The correct concern is `/dev/kvm` access for KVM, or `--privileged` for QEMU without KVM, not libvirt per se.

---

### Issue 5: MiniStack's "~30MB idle RAM" claim not critically examined
- **Type**: Missing nuance
- **Location**: "It also claims `~2s` startup, `~30MB` idle RAM, `~250MB` image size"
- **Problem**: The findings reproduce this number from MiniStack's own marketing without flagging how extraordinary it is. A service claiming to emulate EC2/VPC, ECS, ECR, ELBv2, RDS, and 30+ other services at 30MB idle RAM would be genuinely remarkable — and should prompt a caveat that this figure likely represents the process baseline before any state is loaded, or that it measures a subset of initialized services, not a fully-warm multi-service scenario. By contrast, LocalStack Community idles at several hundred MB in practice. Presenting the 30MB number flat makes MiniStack look uniquely lean without scrutinizing the measurement methodology.
- **Impact**: Readers may over-index on MiniStack's resource efficiency without questioning whether the number is measured under comparable conditions, affecting their CI runner sizing decisions.

---

### Issue 6: Floci's CloudFormation support listed without noting it is nearly useless without EC2/VPC
- **Type**: Missing nuance
- **Location**: "It includes S3, DynamoDB, Lambda, IAM, STS, SSM Parameter Store, CloudFormation, EventBridge, CloudWatch, RDS, and ElastiCache"
- **Problem**: Listing CloudFormation support for Floci without noting that EC2/VPC, ECS, and ECR are absent means a reader would not realize that most non-trivial CloudFormation stacks fail immediately on Floci regardless of CFN support. CloudFormation's value in Terraform CI is specifically as a comparison target or for mixed-IaC stacks — and its utility collapses when the underlying services aren't there. The finding identifies Floci as weak for VPC/ECS/ECR Terraform users, but doesn't connect that to the CFN listing.
- **Impact**: The CFN entry in Floci's service list looks like a strength rather than a partial feature that doesn't compose.

---

### Issue 7: "Prior research" on LocalStack legal/operational context not summarized
- **Type**: Gap
- **Location**: "LocalStack is still the safest functional choice for Terraform-heavy CI if you can tolerate its broader operational/legal context from prior research."
- **Problem**: The findings explicitly defer to "prior research" without summarizing what that context is. A reader encountering this document in isolation has no access to those conclusions. The reference could mean the BUSL license change (LocalStack switched from Apache 2.0 to BUSL 1.1 for advanced features), the Community vs. Pro feature split, CI-use commercial terms, or something else. These are all materially different considerations.
- **Impact**: The trade-off section's conclusion ("safest functional choice, if you can tolerate...") is non-actionable without knowing what the tolerance threshold involves. A reader who agrees with the functional assessment would not know whether they cross the licensing threshold.

---

### Issue 8: OpenTofu not mentioned
- **Type**: Gap
- **Location**: Throughout the findings, "Terraform" is used uniformly to mean the HashiCorp product.
- **Problem**: OpenTofu (the Linux Foundation fork, created in direct response to HashiCorp's BSL relicense) is a significant and growing alternative for exactly the CI use case described here. Organizations that have moved or are evaluating a move to OpenTofu face distinct considerations: LocalStack's `tflocal` targets the HashiCorp CLI directly; compatibility with OpenTofu's CLI (which is close but not identical) should be addressed. MiniStack and Floci make no OpenTofu-specific claims. Moto has no tooling dependency on the CLI at all. Given that licensing context is referenced as material (Issue 7), omitting OpenTofu is a meaningful gap.
- **Impact**: The findings are not actionable for teams on OpenTofu, which is exactly the audience most likely to care about open/embeddable CI tooling.

---

### Issue 9: `skip_requesting_account_id` provider version dependency unspecified
- **Type**: Missing nuance
- **Location**: "that means dummy `access_key`/`secret_key` or a dummy profile are still needed in CI, alongside `skip_credentials_validation`, `skip_metadata_api_check`, and often `skip_requesting_account_id`"
- **Problem**: `skip_requesting_account_id` was added to the AWS Terraform provider at a specific version (approximately v5.x), and it is not available in older provider versions. Teams pinning provider versions or using provider-version constraints in their modules could silently fail to apply this setting. No minimum provider version is cited for this attribute.
- **Impact**: A team running an older locked provider would get a cryptic "unsupported attribute" error and would not know from this document that the flag has a version prerequisite.

---

### Issue 10: tflocal workspace mutation framing overstated
- **Type**: Missing nuance
- **Location**: "it is also a mutation step inside the workspace"
- **Problem**: `tflocal` writes `_tflocal.auto.tfvars.json` (or similar Terraform `.override.tf` files) into the working directory, which Terraform `.gitignore` conventions typically exclude. The finding frames this as a meaningful security/integrity concern but does not distinguish it from ordinary Terraform usage (`.terraform/` directory writes, lock file updates, etc.) that every `terraform init` performs. The mutation concern is real but needs to be more specific: the actual risk is file collision with existing `override.tf` content or unexpected provider alias behavior when the generated override conflicts with module-level provider blocks — not workspace mutation in the general sense.
- **Impact**: The concern is valid but vaguely stated, which either over-alarms practitioners about a routine mechanism or under-prepares them for the actual edge cases that bite.

---

### Issue 11: Floci image size in evidence not surfaced in analysis
- **Type**: Gap / internal inconsistency
- **Location**: Evidence section lists Floci's Docker image as "~90 MB"; this number does not appear in the Floci analysis section.
- **Problem**: The findings surface MiniStack's image size (~250MB) as a data point but do not note Floci's (~90MB) in the comparative analysis. For CI container pull times and registry storage, image size is a genuine trade-off dimension. The evidence section captures it; the analysis discards it.
- **Impact**: Minor, but the asymmetric treatment means readers comparing Floci and MiniStack on CI-friendliness are missing one of the few objective data points available for both.

---

### Issue 12: Fidelity vs. tier conflation for LocalStack community services beyond EC2
- **Type**: Missing nuance
- **Location**: "EC2/VPC in Community defaults to mock/CRUD behavior; more realistic instance execution needs Pro"
- **Problem**: The tier caveat is only explicitly stated for EC2/VPC. ECS, ECR, Lambda, and SSM also have feature gaps between Community and Pro tiers (e.g., LocalStack Pro enables ECS Fargate execution with Docker, multi-container task networking, and SSM integration with live Docker containers). The findings apply the tier caveat narrowly, which may cause readers to assume ECS/ECR/SSM are fully functional in Community when they are not for execution-heavy workflows.
- **Impact**: A team selecting LocalStack Community for full ECS integration testing would discover tier limitations at integration time rather than during tool selection. This is the kind of gap that costs engineering days.

---

## Summary

**Issues found**: 12

**Overall reliability**: Medium

The findings are structurally sound and the conclusion hierarchy (LocalStack > MiniStack > Floci > Moto for Terraform CI) is defensible. The sourcing discipline is generally good, and the CI container gotchas section correctly identifies the backend/provider separation as non-obvious. However, several issues collectively reduce confidence:

- One likely factual error with real practitioner consequences (DynamoDB locking framing, Issue 1)
- One possible factual error in a high-friction area (Moto Lambda env vars, Issue 3)
- One imprecise technical claim (libvirt, Issue 4)
- Three meaningful gaps for an actionable CI decision (OpenTofu, provider version for `skip_requesting_account_id`, LocalStack tier scope)
- One source quality problem that undermines the MiniStack evidence base (Issue 2)

**What would most improve the findings**:
1. Verify and correct the Moto Lambda inter-service networking configuration variable names against current Moto docs.
2. Replace "deprecated" with "superseded" or "legacy" for DynamoDB locking, and note the Terraform version (1.10+) where `use_lockfile` became available.
3. Add a brief OpenTofu compatibility note, particularly for `tflocal`.
4. Extend the LocalStack tier caveat explicitly to ECS, ECR, and SSM execution — not just EC2.
5. Flag the MiniStack 30MB RAM figure as self-reported and unvalidated under realistic multi-service load.
