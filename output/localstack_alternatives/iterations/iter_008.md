# Iteration 008 — Terraform / CDK / SAM / CloudFormation support

**Status:** keep  
**Scores:** coverage=58.8, quality=67.5, total=64.0  
**Timestamp:** 2026-04-08T17:13:23.584470+00:00  

---

### Findings

For **Terraform AWS provider workflows**, the picture is uneven.

**MiniStack** is the strongest on paper for Terraform among the three OSS alternatives, but almost all evidence is self-published. Its README says it works with **AWS provider v5 and v6**, exposes explicit endpoint overrides for many services, and claims the `terraform-aws-modules/vpc/aws` module `v6.6.0` is “fully supported,” including **23 VPC-related resources** such as subnets, NAT, route tables, associations, and default resources. Its site separately says MiniStack works with Terraform, CDK, Pulumi, and any AWS API-speaking tool. MiniStack also exposes a reset endpoint and advertises **900+** or **955** passing tests, which helps CI hygiene. What I did **not** find was an independently reported end-to-end Terraform suite, issue-thread validation, or public CRUD drift reports comparable to Moto’s long-tail issue history. Practical conclusion: MiniStack is plausible for local Terraform CRUD against the services it implements, but the public evidence is still closer to “maintainer claim + examples” than “battle-tested provider fidelity.” Sources: [MiniStack README](https://github.com/Nahuel990/ministack), [MiniStack site](https://ministack.org/)

**Floci** has the cleanest published Terraform-specific evidence. Its README publishes a dedicated compatibility suite with **`compat-terraform` = 14 tests** and **`compat-cdk` = 5 tests**, and says this is the recommended way to validate “real SDK and client workflows” end to end. A release note for `1.1.0` also explicitly mentions a fix for **“DynamoDB table creation compatibility with Terraform AWS provider v6”**, which is a useful signal: Terraform compatibility is real enough to have already broken and been patched. Floci also supports persistent and hybrid storage modes, which matters for CI jobs that need state to survive container restarts during a pipeline stage. The problem is maturity and counter-evidence: the same public ecosystem also reports recent compatibility gaps around CDK/Lambda/S3 behavior, and I could not fully retrieve the underlying GitHub issues in this pass. Practical conclusion: Floci currently has the best **published** Terraform compatibility story of the OSS LocalStack alternatives, but it still looks beta for broad IaC use. Sources: [Floci README](https://github.com/floci-io/floci), [Floci site](https://floci.io/), [Floci 1.1.0 release summary](https://newreleases.io/project/github/floci-io/floci/release/1.1.0), [community roundup noting CDK/S3 gaps](https://dev.to/peytongreen_dev/localstack-now-requires-an-account-heres-how-to-test-aws-in-python-without-one-in-2026-2153)

**Moto** supports Terraform in the narrow sense that its **server mode** can be targeted by the Terraform AWS provider; the docs even include a provider example. But Moto does **not** publish Terraform compatibility suites, and its model is still fundamentally “mock AWS services” rather than “drop-in black-box IaC target.” In practice, Terraform state management is external anyway, so the real question is CRUD fidelity. There the answer is mixed: strong for implemented resources, weak where service semantics are partial or diverge. Moto’s own docs are unusually explicit about those gaps, and its issue tracker shows real divergence bugs even on mature services. Practical conclusion: Moto can support Terraform workflows for constrained stacks, but it is the least convincing choice for “end-to-end provider workflow parity” in CI. Sources: [Moto server mode docs](https://docs.getmoto.org/en/latest/docs/server_mode.html), [Moto implemented services](https://moto.readthedocs.io/en/4.2.12/docs/services/index.html), [Moto issue example: DynamoDB UpdateExpression regression](https://github.com/getmoto/moto/issues/8740), [Moto issue example: S3 notification encoding divergence](https://github.com/getmoto/moto/issues/9054)

For **CDK bootstrap and asset publishing**, none of the OSS options is yet a clean LocalStack replacement.

**MiniStack** documents CDK only as `AWS_ENDPOINT_URL=http://localhost:4566` plus a generic claim that CDK and Amplify Gen 2 deployments are supported. I did not find any published MiniStack CDK bootstrap suite, asset publishing test matrix, or issue history around bootstrap buckets, ECR assets, or modern synthesizer behavior. That absence matters because CDK bootstrap depends on multiple services at once: CloudFormation, S3, IAM, sometimes ECR, and often Lambda packaging. So MiniStack’s CDK story is currently “claimed compatibility,” not “demonstrated bootstrap fidelity.” Sources: [MiniStack README](https://github.com/Nahuel990/ministack), [MiniStack site](https://ministack.org/)

**Floci** is slightly better documented: it publishes **5 CDK compatibility tests**, which is at least evidence that the maintainer is testing CDK as a first-class scenario. But that number is small, and public community reporting still flags **CDK Lambda encoding / S3 asset issues**. Given the known S3 compatibility sensitivity in CDK bootstrap and asset publishing, I would treat Floci as viable only for very narrow CDK stacks until those issue threads are easier to verify and clearly closed. The surprising part is that Floci can look excellent on raw SDK counts yet still be fragile for CDK, because CDK is especially sensitive to subtle S3 response semantics and multipart/upload edge cases. Sources: [Floci README](https://github.com/floci-io/floci), [Floci site](https://floci.io/), [community roundup noting CDK/S3 gaps](https://dev.to/peytongreen_dev/localstack-now-requires-an-account-heres-how-to-test-aws-in-python-without-one-in-2026-2153)

**Moto** is the weakest fit for CDK bootstrap. It has no published CDK compatibility suite, and bootstrap depends heavily on CloudFormation plus S3 behavior. Moto’s CloudFormation docs show broad API support, but still list many unimplemented operations and caveats. More importantly, Moto’s Lambda and API Gateway docs have server-mode caveats that make “realistic CDK app deployment then invoke” much less reliable than raw CRUD. Sources: [Moto CloudFormation docs](https://docs.getmoto.org/en/latest/docs/services/cloudformation.html), [Moto server mode docs](https://docs.getmoto.org/en/latest/docs/server_mode.html)

For **SAM / CloudFormation**, the most important finding is that **MiniStack and Floci do not currently show public evidence of CloudFormation coverage beyond their documented 12 resource types**.

**MiniStack** is explicit here. The README enumerates exactly **12 supported CloudFormation resource types**:
`AWS::S3::Bucket`, `AWS::SQS::Queue`, `AWS::SNS::Topic`, `AWS::SNS::Subscription`, `AWS::DynamoDB::Table`, `AWS::Lambda::Function`, `AWS::IAM::Role`, `AWS::IAM::Policy`, `AWS::IAM::InstanceProfile`, `AWS::SSM::Parameter`, `AWS::Logs::LogGroup`, and `AWS::Events::Rule`. It also states that unsupported resource types fail with `CREATE_FAILED` rather than silently succeeding. I found no primary-source evidence that MiniStack handles more than those 12 today. Sources: [MiniStack README](https://github.com/Nahuel990/ministack), [MiniStack site](https://ministack.org/)

**Floci** repeatedly says **“CloudFormation 12”** in its README, site, and launch post, but unlike MiniStack it does **not** publicly enumerate the 12 resource types in the material I found. That makes the situation worse from an architect’s perspective: the ceiling is documented, but the exact boundary is harder to audit. I did not find evidence that Floci handles materially more than those 12 via CloudFormation in practice. Sources: [Floci README](https://github.com/floci-io/floci), [Floci site](https://floci.io/), [launch post](https://hectorvent.dev/posts/introducing-floci/)

**Moto** is in a different class on CloudFormation breadth. Its docs include:
- a CloudFormation API feature matrix,
- support for **CustomResources in server mode**,
- and a long **supported resource matrix** covering far more than 12 resource types.

The supported-resource page visibly includes resources across API Gateway, Auto Scaling, Batch, DynamoDB, EC2, ECR, ECS, EFS, EMR, EventBridge, IAM, IoT, KMS, Kinesis, Lambda, Logs, RDS, Redshift, Route53, S3, SNS, SQS, SSM, SageMaker, and Step Functions. That is not proof of full semantic parity, but it is a much broader, more auditable CloudFormation story than MiniStack or Floci. I did **not** find a current primary-source claim that Moto’s coverage is literally “cfn-lint-validated”; what I found is a documented resource-support matrix plus explicit caveats. Sources: [Moto CloudFormation docs](https://docs.getmoto.org/en/latest/docs/services/cloudformation.html), [Moto supported CloudFormation resources](https://docs.getmoto.org/en/5.1.14/docs/services/cf.html), [SAM `cfn-lint` docs for contrast](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/validate-cfn-lint.html)

On **SAM specifically**, I found no first-party MiniStack or Floci documentation showing `sam deploy` or SAM transform workflows against their endpoints. For **Moto**, a community answer says plain SAM CLI does not directly target Moto server, and suggests `aws-sam-cli-local`; a follow-up comment questions whether `AWS::Serverless` transform resources are actually handled. That is weak evidence, but directionally it suggests SAM remains awkward across all three and still rides on underlying CloudFormation coverage. Source: [Stack Overflow discussion](https://stackoverflow.com/questions/76555026/deploying-sam-template-to-moto-server)

### Evidence

- MiniStack claims **Terraform AWS Provider v5 and v6** support and a fully supported `terraform-aws-modules/vpc/aws` module `v6.6.0` with **23 resources**. Sources: [README](https://github.com/Nahuel990/ministack), [site](https://ministack.org/)
- MiniStack publishes **955 tests** in README and **900+ tests** on the site. Sources: [README](https://github.com/Nahuel990/ministack), [site](https://ministack.org/)
- MiniStack documents exactly **12 CloudFormation resource types** and says unsupported types fail with `CREATE_FAILED`. Sources: [README](https://github.com/Nahuel990/ministack), [site](https://ministack.org/)
- Floci publishes **`compat-terraform` 14 tests**, **`compat-opentofu` 14 tests**, and **`compat-cdk` 5 tests**. Sources: [README](https://github.com/floci-io/floci), [site](https://floci.io/)
- Floci release `1.1.0` lists **“DynamoDB table creation compatibility with Terraform AWS provider v6”** as a bug fix. Source: [release summary](https://newreleases.io/project/github/floci-io/floci/release/1.1.0)
- Floci documents **24 ms startup**, **13 MiB idle memory**, **~90 MB image**, and **408/408 SDK compatibility tests**. Sources: [README](https://github.com/floci-io/floci), [site](https://floci.io/), [launch post](https://hectorvent.dev/posts/introducing-floci/)
- Floci documents **CloudFormation 12** but I did not find a public list of the exact 12 resource types. Sources: [README](https://github.com/floci-io/floci), [site](https://floci.io/)
- Moto server mode docs include a Terraform provider example using endpoint overrides. Source: [server mode docs](https://docs.getmoto.org/en/latest/docs/server_mode.html)
- Moto CloudFormation docs support **CustomResources in server mode** but require the server to be reachable externally, typically via Docker or `-h 0.0.0.0`. Source: [CloudFormation docs](https://docs.getmoto.org/en/latest/docs/services/cloudformation.html)
- Moto’s supported CloudFormation resource page visibly includes many more resource families than 12, including S3, SQS, SNS, IAM, Lambda, EC2, ECS, RDS, Route53, Step Functions, SageMaker, and more. Source: [supported resources matrix](https://docs.getmoto.org/en/5.1.14/docs/services/cf.html)

### Trade-offs

If the decision axis is **Terraform in CI**, **Floci currently has the best published evidence**, because it at least ships named Terraform compatibility suites and has already patched a Terraform AWS provider v6 break. The trade-off is maturity: the same project is new enough that a handful of subtle SDK or S3 bugs can still derail CDK or larger IaC flows.

If the decision axis is **black-box CloudFormation/CDK realism**, **none of the OSS alternatives is yet strong**. MiniStack and Floci both cap out at **12 documented CloudFormation resource types**, which is too small for most serious CDK bootstrap or SAM deploy scenarios. Floci’s extra CDK test suite is encouraging, but **5 tests** is not enough to treat bootstrap and asset publishing as reliable.

If the decision axis is **CloudFormation breadth and auditability**, **Moto wins clearly**. Its model is less LocalStack-like, but its CloudFormation resource matrix is vastly broader and much more inspectable. The trade-off is that Moto is not really optimized as a turnkey IaC emulator appliance, so Terraform/CDK/SAM workflows require more care and have more service-specific caveats.

The counter-intuitive result is that the tool with the **best Terraform story today may not be the best CDK story**. Floci’s published compatibility numbers are impressive, but CDK bootstrap is sensitive to a narrower set of S3 and CloudFormation correctness details than generic SDK smoke tests. That is why “408/408 SDK tests” does not automatically translate into “safe for CDK assets.”

### New Questions

1. Which of these emulators can reliably support **modern CDK bootstrap v2**, including S3 file assets, Docker/ECR image assets, and IAM bootstrap roles, in a repeatable CI run?
2. How much of each project’s IaC story is backed by **independent consumer issue reports** versus maintainer-authored compatibility suites?
3. For teams using Terraform, is the bigger risk **resource creation failures**, or **post-apply drift/read semantics** such as `Describe*`, `Get*`, tagging, and attribute projection mismatches?

I did not find a primary-source MiniStack or Floci SAM deployment guide, nor a primary-source confirmation of the exact Floci CDK/S3 bug thread in this pass; the community references were sufficient to flag risk, but not to fully verify issue status.

---

## Peer Review (claude)

### Issue 1: compat-opentofu Tests Omitted from Findings

- **Type**: gap / internal contradiction
- **Location**: Evidence section lists "Floci publishes `compat-terraform` 14 tests, `compat-opentofu` 14 tests, and `compat-cdk` 5 tests." The Floci Terraform finding only mentions `compat-terraform` and `compat-cdk`.
- **Problem**: The `compat-opentofu` suite is captured in the evidence but never analyzed in the findings. OpenTofu is the main open-source Terraform fork and is increasingly used in CI pipelines. Its omission creates a false impression that Floci's compatibility story is limited to HashiCorp Terraform, and the trade-offs section gives no guidance for teams already on OpenTofu.
- **Impact**: Medium. Anyone evaluating Floci for OpenTofu workflows gets no signal from this document despite the data being available.

---

### Issue 2: Weak Source Used to Assert CDK/S3 Gaps in Floci as Near-Fact

- **Type**: unsupported claim / missing nuance
- **Location**: "A release note for `1.1.0` also explicitly mentions a fix... the same public ecosystem also reports recent compatibility gaps around CDK/Lambda/S3 behavior, and I could not fully retrieve the underlying GitHub issues in this pass." And: "I would treat Floci as viable only for very narrow CDK stacks until those issue threads are easier to verify and clearly closed."
- **Problem**: The CDK/S3 gap claim rests on a single dev.to community blog post, cited by URL title as "localstack-now-requires-an-account-heres-how-to-test-aws-in-python-without-one-in-2026." This is a secondary, third-party opinion piece, not a primary issue report. The findings admit the underlying GitHub threads were not retrieved, yet the practical conclusion—"viable only for very narrow CDK stacks"—is stated as if the gaps are verified. The confidence of the conclusion is not calibrated to the weakness of the source.
- **Impact**: High. The recommendation against Floci for CDK use is the most actionable output for a reader. If the underlying issues are already closed or were minor, this conclusion materially misinforms the decision.

---

### Issue 3: Moto CloudFormation Documentation Cited at Version 5.1.14, Not Current

- **Type**: factual error (potential)
- **Location**: "Source: [supported resources matrix](https://docs.getmoto.org/en/5.1.14/docs/services/cf.html)"
- **Problem**: The CloudFormation resource matrix is pinned to version `5.1.14` while the server-mode docs use `/en/latest/`. Moto's version numbering is active; the current release as of early 2026 is likely higher. The supported-resource list in `5.1.14` may be materially out of date in either direction—resources added or removed since then. Using a frozen version to argue Moto has "vastly broader" coverage is defensible only if the version is identified as likely representative, which it is not.
- **Impact**: Medium. Weakens the Moto CloudFormation breadth argument; a reviewer comparing against the current release could find the matrix has changed.

---

### Issue 4: MiniStack's 12 and Floci's "CloudFormation 12" Are Never Compared for Overlap

- **Type**: gap
- **Location**: MiniStack section lists all 12 types explicitly. Floci section says "CloudFormation 12" but exact types are not enumerated. The findings treat these as equivalent ceilings without addressing whether the two sets match.
- **Problem**: If Floci's 12 types partially differ from MiniStack's 12 (e.g., Floci covers `AWS::ApiGateway::RestApi` but MiniStack does not, or vice versa), the practical ceiling for each tool is different. The finding's framing—"both cap out at 12 documented CloudFormation resource types"—implies equivalence that is not demonstrated.
- **Impact**: Medium. The conclusion "both are too limited for most serious CDK or SAM scenarios" may still hold, but the nuance matters for teams whose specific stack happens to fall within one tool's 12 but not the other's.

---

### Issue 5: "Terraform State Management Is External Anyway" Oversimplifies Moto's Persistence Problem

- **Type**: missing nuance
- **Location**: "Terraform state management is external anyway, so the real question is CRUD fidelity."
- **Problem**: This framing conflates the Terraform `.tfstate` file (which is indeed external) with the emulator's own in-memory resource state. When Moto runs in server mode, all simulated resources live in memory and are lost on restart. Terraform workflows that span multiple pipeline stages—plan in one container, apply in another—will fail silently if the emulator restarts between steps. This is not a CRUD fidelity issue; it is a session-persistence issue. Floci's persistent and hybrid storage modes directly address this gap. The finding mentions Floci's persistence advantage but does not name Moto's in-memory-only server mode as a concrete counterpoint.
- **Impact**: Medium. For CI architectures where apply and verification run in separate containers, this is a first-order concern, not a footnote.

---

### Issue 6: 14 Terraform Tests Presented as "Best Published Evidence" Without Adequately Flagging Coverage Limitations

- **Type**: missing nuance
- **Location**: "Floci currently has the best **published** Terraform compatibility story of the OSS LocalStack alternatives."
- **Problem**: 14 tests is an extremely thin compatibility suite for Terraform. The `terraform-aws-modules/vpc/aws` module alone exercises 23 resource types. If the 14 `compat-terraform` tests cover a narrow slice—such as table creation and basic S3 operations—they may not catch drift in resource reads, tag propagation, cross-resource references, or the lifecycle transitions that trip up real pipelines. The finding's own trade-offs section flags this indirectly ("CDK is especially sensitive to subtle S3 response semantics") but never applies the same skepticism to Terraform. Winning "best published evidence" when the bar is 14 named tests is a low bar that deserves explicit acknowledgment.
- **Impact**: High. A team reading the trade-offs section could reasonably interpret "best Terraform story" as "safe for Terraform in CI," which 14 tests does not guarantee.

---

### Issue 7: MiniStack Test Count Discrepancy (955 vs. 900+) Is Flagged but Not Resolved

- **Type**: factual ambiguity
- **Location**: "advertises **900+** or **955** passing tests"
- **Problem**: The finding correctly notes the discrepancy but does not attempt to explain it—for example, whether the README and site are at different release points, or whether the two counts reflect different test categories. The evidence section compounds this by listing both numbers side by side as if equivalent. A 55-test gap (~6%) in a 900-count suite is not trivial; it may reflect a stale README, a different test runner scope, or tests that are passing/failing depending on configuration.
- **Impact**: Low-medium. Primarily a credibility signal for MiniStack's testing claims. Leaving it unresolved understates the uncertainty in MiniStack's quality assurance story.

---

### Issue 8: MiniStack Hosted Under Personal GitHub Account—Maturity Signal Not Discussed

- **Type**: gap
- **Location**: "Sources: [MiniStack README](https://github.com/Nahuel990/ministack)"
- **Problem**: The README URL is a personal GitHub account (`Nahuel990`), not a GitHub organization or foundation-backed repository. For a tool being evaluated for enterprise CI use, the bus-factor and governance implications of a personal-account project are a meaningful maturity signal. The finding correctly notes that evidence is "self-published," but never draws the obvious inference: a solo-maintainer personal repo has different long-term support expectations than an organization-backed project. This is especially relevant alongside the test-count discrepancy.
- **Impact**: Medium. Missing this context leaves the "plausible for local Terraform CRUD" conclusion under-qualified.

---

### Issue 9: Moto Issue Tracker Used Simultaneously as Positive and Negative Evidence Without Acknowledging the Tension

- **Type**: contradiction / missing nuance
- **Location**: "What I did **not** find was... issue-thread validation... comparable to Moto's long-tail issue history" (Moto's history implied as a positive credibility signal), versus "its issue tracker shows real divergence bugs even on mature services" (used as a negative signal in the Moto section).
- **Problem**: The same attribute—a large public issue history—is used to argue Moto is more credible than MiniStack (community scrutiny) and also to argue Moto is unreliable (divergence bugs). Both inferences are valid, but presenting them in separate sections without acknowledging the tension makes the analysis feel inconsistent. A reader could reasonably ask: does Moto's large issue history make it more or less trustworthy than MiniStack's absent issue history?
- **Impact**: Low-medium. Does not change the practical recommendations but reduces analytical coherence.

---

### Issue 10: CDK Bootstrap v2 Service Dependency List Is Incomplete

- **Type**: missing nuance
- **Location**: "CDK bootstrap depends on multiple services at once: CloudFormation, S3, IAM, sometimes ECR, and often Lambda packaging."
- **Problem**: CDK bootstrap v2 (the modern bootstrapper) also writes a version parameter to **SSM Parameter Store** (`/cdk-bootstrap/<qualifier>/version`) and optionally uses **KMS** for asset encryption. Omitting SSM means a tool that partially implements SSM could silently fail bootstrap without it being obvious from this analysis. SSM is actually listed among MiniStack's 12 supported CloudFormation types, which makes this gap more consequential—SSM fidelity at the direct-API level does not guarantee SSM works correctly when driven through the CDK bootstrap script.
- **Impact**: Medium. Anyone using this analysis to assess CDK bootstrap readiness may miss the SSM and KMS dependency vectors.

---

### Issue 11: SAM Section Relies on a Single Stack Overflow Thread Without Noting Its Age or Vote Count

- **Type**: missing nuance
- **Location**: "a community answer says plain SAM CLI does not directly target Moto server, and suggests `aws-sam-cli-local`; a follow-up comment questions whether `AWS::Serverless` transform resources are actually handled."
- **Problem**: The Stack Overflow thread is the sole source for the SAM section's practical conclusions. The findings do not note the question date, accepted-answer status, or vote count, all of which would indicate whether this reflects current SAM CLI behavior or an outdated workaround. SAM CLI and Moto's server mode have both evolved; a thread from 2023 may be describing behavior that has since changed in either direction.
- **Impact**: Medium. The SAM section's conclusion ("SAM remains awkward across all three") may be correct, but it rests on insufficiently documented community evidence.

---

## Summary

**Total issues found**: 11

**Overall reliability**: **Medium**

The findings are well-structured and appropriately hedge most conclusions with "maintainer claim" or "beta" qualifiers. The core directional assessments—Floci leads on published Terraform evidence, Moto leads on CloudFormation breadth, all three are weak for CDK bootstrap—are defensible. However, several problems meaningfully degrade the findings' utility as a decision document:

**What would most improve the findings:**

1. **Retrieve the Floci GitHub issue threads** cited via the dev.to post before publishing any CDK recommendation. The current CDK/Floci conclusion is the most consequential and the least evidenced.
2. **Contextualize "14 Terraform tests" explicitly** — name what the tests cover, not just that they exist. Coverage topology matters more than test count.
3. **Add a version-current Moto CloudFormation matrix** (use `/latest/` not `5.1.14`) and acknowledge partial implementation within listed resource families.
4. **Compare MiniStack and Floci's 12 CloudFormation types directly** — or explicitly flag that the overlap is unknown.
5. **Add an OpenTofu paragraph** to the Floci Terraform section; the data is already in the evidence.
