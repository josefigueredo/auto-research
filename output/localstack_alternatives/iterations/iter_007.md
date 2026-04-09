# Iteration 007 — Licensing and pricing (LocalStack free vs Pro vs alternatives)

**Status:** keep  
**Scores:** coverage=67.5, quality=75.0, total=72.0  
**Timestamp:** 2026-04-08T17:05:51.723168+00:00  

---

### Findings

The March 23, 2026 LocalStack unified-image change applies to free users too, not only paid tiers. LocalStack’s March 5 migration post says the latest releases require “a LocalStack for AWS account” and “an auth token (including for CI usage),” while also saying a Free plan will remain for hobbyists and individual developers. Their pricing page now brands that free tier as `Hobby`, and the current FAQ says the Hobby plan is free for non-commercial use, supports CI/CD, but still requires authentication and is not valid for commercial software development. In practice: a commercial team cannot stay compliant on current LocalStack releases with the free tier, even though CI itself is no longer separately metered.  
Sources: [LocalStack March 5 post](https://blog.localstack.cloud/localstack-single-image-next-steps/), [LocalStack pricing](https://www.localstack.cloud/pricing)

For licensing, the main open-source alternatives in scope are permissive and do not restrict commercial use based on the license itself. `MiniStack` and `Floci` both present themselves as MIT-licensed on their GitHub repos/readmes. `Moto`, `ElasticMQ`, and `Adobe S3Mock` are Apache-2.0 licensed on GitHub. MIT and Apache-2.0 are permissive licenses that allow commercial use, with the usual notice/preservation conditions. I did not find a commercial-use restriction in the project licenses for any of those five tools.  
Sources: [MiniStack GitHub](https://github.com/Nahuel990/ministack), [MiniStack site](https://ministack.org/), [Floci GitHub](https://github.com/floci-io/floci), [Floci site](https://floci.io/), [Moto GitHub](https://github.com/getmoto/moto), [ElasticMQ GitHub](https://github.com/softwaremill/elasticmq), [Adobe S3Mock GitHub](https://github.com/adobe/S3Mock), [MIT on ChooseALicense](https://choosealicense.com/licenses/mit/), [Apache-2.0 on ChooseALicense](https://choosealicense.com/licenses/apache-2.0/)

For a team of 5-10 developers with 2-3 CI runners, LocalStack pricing is now primarily seat-based, not runner-based. The current pricing page says Base is `$39/user/month billed annually`, with a time-limited promo showing `$23/user/month billed annually` or `$27/user/month billed monthly` for Base credit-card purchases through April 30, 2026. Ultimate is `$89/user/month billed annually`; the pricing FAQ says Ultimate monthly is via AWS Marketplace, and the Marketplace page shows `$107/user/month` on a 1-month contract. LocalStack also says licenses are assigned to a single individual and cannot be pooled across multiple developers concurrently. Their current pricing FAQ says CI credits are gone; CI is available across plans, subject to fair use and plan terms. So published marginal cost per extra CI runner is currently `$0`, but there is no published concurrency entitlement, only fair-use language.  
Sources: [LocalStack pricing](https://www.localstack.cloud/pricing), [LocalStack pricing FAQ](https://www.localstack.cloud/pricing), [AWS Marketplace LocalStack Cloud Emulator](https://aws.amazon.com/marketplace/pp/prodview-lllzw3ywntoxg), [AWS Marketplace LocalStack Ultimate](https://aws.amazon.com/marketplace/pp/prodview-toez36gqeoa6a)

That yields these practical commercial costs:

- LocalStack Hobby: `$0`, but not valid for commercial use.
- LocalStack Base annual list: 5 devs = `$195/month` effective, 10 devs = `$390/month`.
- LocalStack Base current promo annual: 5 devs = `$115/month`, 10 devs = `$230/month`, first 12 months only, promo stated through April 30, 2026.
- LocalStack Base monthly current promo: 5 devs = `$135/month`, 10 devs = `$270/month`, first 12 months only.
- LocalStack Base monthly non-promo: 5 devs = `$225/month`, 10 devs = `$450/month`.
- LocalStack Ultimate annual: 5 devs = `$445/month`, 10 devs = `$890/month`.
- LocalStack Ultimate monthly via AWS Marketplace: 5 devs = `$535/month`, 10 devs = `$1,070/month`.

For the OSS alternatives in scope, published software licensing cost is effectively `$0` for both developers and CI runners. None of MiniStack, Floci, Moto, ElasticMQ, or Adobe S3Mock publishes a per-seat or per-runner charge on the cited sources. The real cost is operational: CI minutes, Docker host RAM/CPU, and the engineering time needed to assemble single-service tools if one emulator is insufficient. That makes the open-source alternatives economically compelling for small commercial teams, but only if service coverage and fidelity are adequate for the workloads.  
Sources: [MiniStack site](https://ministack.org/), [Floci site](https://floci.io/), [Moto GitHub](https://github.com/getmoto/moto), [ElasticMQ GitHub](https://github.com/softwaremill/elasticmq), [Adobe S3Mock GitHub](https://github.com/adobe/S3Mock)

One surprising point: some search snippets and older cached pricing pages still mention `300` or `1000` monthly CI credits on Base/Ultimate, but the current live pricing FAQ says LocalStack “no longer differentiates plans using CI credits.” For architectural decisions, the live pricing page is the safer source than search-result snippets.  
Sources: [LocalStack pricing](https://www.localstack.cloud/pricing), [LocalStack Feb. 27 pricing update](https://blog.localstack.cloud/2026-upcoming-pricing-changes/)

### Evidence

LocalStack auth/pricing facts:

- March 23, 2026 unified image requires account + auth token, including CI: [March 5 migration post](https://blog.localstack.cloud/localstack-single-image-next-steps/)
- Free plan remains, but for hobbyists/individual developers: [March 5 migration post](https://blog.localstack.cloud/localstack-single-image-next-steps/)
- Free tier “will not permit usage for commercial purposes”: [Feb. 27 pricing update](https://blog.localstack.cloud/2026-upcoming-pricing-changes/)
- Current pricing labels free tier as `Hobby`: [pricing page](https://www.localstack.cloud/pricing)
- Hobby plan includes “Run tests in CI”: [pricing page](https://www.localstack.cloud/pricing)
- Current FAQ: CI available across plans; CI credits removed; usage subject to fair use: [pricing page](https://www.localstack.cloud/pricing)
- Current FAQ: licenses are single-user, not pooled: [pricing page](https://www.localstack.cloud/pricing)

Current LocalStack published prices as of April 8, 2026:

- Base annual: `$39/user/month`; promo shows `$23/user/month`; promo note says through `April 30, 2026`: [pricing page](https://www.localstack.cloud/pricing)
- Base monthly: `$45/user/month`; promo shows `$27/user/month`: [pricing page](https://www.localstack.cloud/pricing)
- Ultimate annual: `$89/user/month`: [pricing page](https://www.localstack.cloud/pricing)
- Ultimate monthly via AWS Marketplace: `$107/user/month`: [AWS Marketplace Ultimate](https://aws.amazon.com/marketplace/pp/prodview-toez36gqeoa6a)
- Marketplace “Cloud Emulator” monthly team-seat product: `$100/user/month`: [AWS Marketplace Cloud Emulator](https://aws.amazon.com/marketplace/pp/prodview-lllzw3ywntoxg)

License baselines:

- MiniStack: MIT on repo/readme; site also says MIT-licensed: [GitHub](https://github.com/Nahuel990/ministack), [site](https://ministack.org/)
- Floci: MIT on repo/readme; site says MIT licensed: [GitHub](https://github.com/floci-io/floci), [site](https://floci.io/)
- Moto: Apache-2.0 on GitHub: [GitHub](https://github.com/getmoto/moto)
- ElasticMQ: Apache-2.0 on GitHub: [GitHub](https://github.com/softwaremill/elasticmq)
- Adobe S3Mock: Apache-2.0 on GitHub/readme: [GitHub](https://github.com/adobe/S3Mock)

Commercial-use meaning of those licenses:

- MIT permits commercial use: [ChooseALicense MIT](https://choosealicense.com/licenses/mit/)
- Apache-2.0 permits commercial use: [ChooseALicense Apache-2.0](https://choosealicense.com/licenses/apache-2.0/)

### Trade-offs

LocalStack’s commercial case is now cleaner than it looked during the initial announcement, but not cheaper. The important nuance is that CI is no longer priced per build credit in the current live pricing; the cost center is seats. For a 5-10 person team, that makes budgeting predictable, and 2-3 CI runners do not appear to add direct published cost. The catch is that the free tier is not a lawful option for commercial use, and the “fair use” boundary for CI is not quantified publicly.

The open-source alternatives have the opposite profile. Licensing is straightforward: MIT or Apache-2.0, no auth token, no seat tax, no CI concurrency tax. That is materially better for small commercial teams and for ephemeral CI fleets. The trade-off is that your bill moves from vendor subscription to integration risk and maintenance risk. With Floci and MiniStack, that risk is mainly emulator fidelity and project maturity; with Moto, ElasticMQ, and S3Mock, it is scope mismatch because they are library/server or single-service tools rather than a full LocalStack-style platform.

MiniStack and Floci are the strongest “replace LocalStack without asking procurement” candidates on licensing grounds. Both are MIT, both market themselves as permanently free, and neither imposes auth-token gating. MiniStack is notable because it explicitly markets itself as a commercial-safe counterposition to LocalStack’s change and documents real Docker-backed infra for some services. Floci is even more aggressive in positioning: “No auth token. Ever.” The edge case is sustainability: permissive license does not guarantee project longevity, support responsiveness, or governance stability.

Moto, ElasticMQ, and S3Mock are legally safe for commercial use, but they are usually cheaper only when your architecture is narrower. If your project only needs SQS, ElasticMQ is likely the lowest-cost serious choice. If it only needs S3, S3Mock is similar. If you already structure tests around Python mocks or server mode, Moto can be effectively free. But once you need a single black-box emulator across multiple services and SDK/IaC flows, those tools stop being direct LocalStack pricing alternatives and start becoming assembly work.

### New Questions

1. What are the actual fair-use and enforcement mechanics behind LocalStack’s now-unmetered CI policy, especially for 2-3 always-on runners or bursty monorepo pipelines?
2. Which OSS alternatives have enough maintainer depth, release cadence, and issue-response quality to be acceptable for commercial CI dependencies?
3. Do any of the OSS alternatives offer a credible paid-support path or corporate sponsorship model that reduces vendor-risk without reintroducing LocalStack-level seat pricing?

---

## Peer Review (claude)

## Peer Review: LocalStack Pricing & OSS Alternatives Research

---

### Issue 1: Narrative conflates promo and standard monthly Base pricing
- **Type**: Missing nuance / presentation error
- **Location**: "Base is `$39/user/month billed annually`... or `$27/user/month billed monthly` for Base credit-card purchases through April 30, 2026"
- **Problem**: The narrative lists the promo monthly ($27) as the apparent alternative to the annual rate ($39), without first establishing that the *standard* non-promo monthly is $45/user/month. A reader scanning the prose — rather than the cost table — would not know a $45 option exists. The cost table correctly shows "Base monthly non-promo: $225/$450" but the narrative never states the $45 rate explicitly.
- **Impact**: Medium. A decision-maker relying on the prose summary could budget against $27/month and be surprised after April 30 when the rate reverts to $45, a 67% increase. This matters especially given the promo expires in 22 days from the review date (April 8, 2026).

---

### Issue 2: Promo expiry urgency is not flagged
- **Type**: Missing nuance
- **Location**: "promo stated through April 30, 2026" (cost table); the trade-offs section does not reference the deadline at all
- **Problem**: As of April 8, 2026, the promotional pricing window closes in 22 days. Any team using these figures for a procurement decision is operating under a time constraint that the findings treat as a footnote in the cost table. The trade-offs and new questions sections make no mention of it. A reader who reaches "New Questions" without the cost table in hand has no idea there is an imminent price cliff.
- **Impact**: Medium-high. For a 10-person team, the difference between annual promo ($230/month) and annual list ($390/month) is $1,920/year. Omitting the urgency from the analytical sections is a material gap for a decision-support document.

---

### Issue 3: AWS Marketplace "Cloud Emulator" ($100/user/month) appears in evidence but is absent from findings
- **Type**: Gap / internal inconsistency
- **Location**: Evidence section lists "Marketplace 'Cloud Emulator' monthly team-seat product: `$100/user/month`" but the findings narrative and cost table do not reference it
- **Problem**: The evidence records two distinct AWS Marketplace products — "Cloud Emulator" ($100/user/month) and "Ultimate" ($107/user/month) — but the findings only discuss Ultimate via Marketplace. The Cloud Emulator product presumably corresponds to a lower tier than Ultimate. Omitting it leaves readers without a complete Marketplace pricing picture and may understate available options.
- **Impact**: Low-medium. If Cloud Emulator maps to Base-tier features, it represents a viable purchasing path that bypasses direct LocalStack billing. If it is a legacy or deprecated listing, that should be stated. Either way, the evidence was collected and then not used.

---

### Issue 4: "No auth token. Ever." treated as a verified quote without a specific citation
- **Type**: Unsupported claim
- **Location**: Trade-offs section: "Floci is even more aggressive in positioning: 'No auth token. Ever.'"
- **Problem**: This is formatted as a direct quotation but no URL, page section, or timestamp is provided in either the findings or evidence sections. The evidence only cites the Floci GitHub and site generically. If this slogan is on a landing page it should carry a URL; if it is from README text, a commit SHA or date would help, since marketing copy on early-stage projects changes frequently.
- **Impact**: Low-medium. This is a key differentiating claim used to favor Floci in the trade-off analysis. An unanchored marketing quote is weak evidence, particularly for a project whose longevity is acknowledged to be uncertain.

---

### Issue 5: MiniStack's single-developer GitHub origin is not explicitly flagged as a commercial risk
- **Type**: Missing nuance
- **Location**: Trade-offs: "MiniStack is notable because it explicitly markets itself as a commercial-safe counterposition to LocalStack's change and documents real Docker-backed infra for some services."
- **Problem**: The GitHub URL in the evidence (`github.com/Nahuel990/ministack`) is a personal account, not an organization. The findings mention sustainability as a generic concern but never state that MiniStack appears to be a solo-developer project. For a team evaluating it as a commercial CI dependency, this is a first-order concern — not a philosophical caveat about "project longevity." The recommendation that MiniStack is among "the strongest 'replace LocalStack without asking procurement' candidates" should carry a much stronger warning about project maturity.
- **Impact**: High. A commercial team that adopts MiniStack based on this analysis and then finds the project abandoned or the maintainer unresponsive has no support path. The framing ("strongest candidate") overstates confidence relative to the evidence.

---

### Issue 6: "Documents real Docker-backed infra for some services" is vague and unverified
- **Type**: Unsupported claim / missing nuance
- **Location**: Trade-offs: "MiniStack is notable because it... documents real Docker-backed infra for some services"
- **Problem**: "Some services" is doing significant work here. Which services? Does MiniStack cover the services the hypothetical 5-10 person team actually uses? Without a service coverage list, this claim is analytically inert. It cannot support the recommendation that MiniStack is a strong LocalStack replacement candidate.
- **Impact**: Medium. Service coverage is the primary functional criterion for replacing LocalStack. Leaving it as "some services" means readers cannot evaluate fit without doing independent research — which defeats the purpose of the findings.

---

### Issue 7: No service coverage data is provided for any alternative
- **Type**: Gap
- **Location**: Entire findings; trade-offs section acknowledges the problem abstractly: "only if service coverage and fidelity are adequate"
- **Problem**: The findings explicitly say service coverage matters but provide zero coverage data for MiniStack, Floci, Moto, ElasticMQ, or S3Mock. Moto is described as a "library/server or single-service tool" in one sentence, but Moto actually covers over 300 AWS services — this is a significant understatement. ElasticMQ is SQS-only, S3Mock is S3-only, but Moto is multi-service. Conflating Moto with ElasticMQ and S3Mock as "single-service tools" is factually imprecise.
- **Impact**: High. The entire cost comparison is conditional on coverage adequacy. Without coverage data, a reader cannot determine whether any open-source alternative is a viable substitute for their specific stack.

---

### Issue 8: Moto is mischaracterized as a "single-service tool"
- **Type**: Factual error
- **Location**: Trade-offs: "with Moto, ElasticMQ, and S3Mock, it is scope mismatch because they are library/server or single-service tools rather than a full LocalStack-style platform"
- **Problem**: Moto is not a single-service tool. It mocks a large and growing portion of the AWS service catalog (S3, EC2, Lambda, DynamoDB, SQS, IAM, CloudFormation, and many others). Grouping it with ElasticMQ (SQS-only) and S3Mock (S3-only) misrepresents its scope. The distinction the findings are trying to draw — between "in-process library mock" and "black-box Docker emulator" — is valid, but the "single-service" label is not.
- **Impact**: Medium-high. Readers considering Moto may dismiss it prematurely based on a mischaracterized scope. Moto in server mode is actually a plausible multi-service emulator for Python-centric teams, a nuance the findings omit entirely.

---

### Issue 9: CI runner seat requirements are not clarified
- **Type**: Gap
- **Location**: "2-3 CI runners do not appear to add direct published cost" and "licenses are assigned to a single individual and cannot be pooled"
- **Problem**: The findings state that seats are per-individual and that CI runners add no published marginal cost, but do not resolve a critical ambiguity: do CI runners require their own seat licenses, or do they operate under a shared service account? If each CI runner needs a seat, a team of 5 developers with 3 runners needs 8 seats ($312/month at list annual pricing for Base), not 5. If runners operate under a single service account, that may violate the "single individual" policy. Neither interpretation is ruled out by the evidence cited.
- **Impact**: High. This ambiguity can produce a 40-60% underestimate of actual cost for teams with active CI fleets. The findings should flag this as an open question requiring direct confirmation from LocalStack, not treat it as resolved.

---

### Issue 10: No maturity or activity metrics for any OSS alternative
- **Type**: Gap
- **Location**: Trade-offs section; New Questions #2 partially acknowledges this
- **Problem**: The findings cite licenses and websites but provide no signal on release cadence, GitHub star count, open issue count, last commit date, or number of active maintainers for any of the five alternatives. New Question #2 asks about "maintainer depth, release cadence, and issue-response quality" — but these are answerable from public data that should have been part of the findings, not deferred to future research. For a commercial CI dependency decision, a project with 12 stars and no release in 18 months is categorically different from one with 8,000 stars and weekly releases.
- **Impact**: High. Sustainability risk is the primary trade-off acknowledged for OSS alternatives. Without any maturity data, the trade-off analysis rests on assertions rather than evidence.

---

### Issue 11: "CI is available across plans, subject to fair use and plan terms" — "fair use" is left unexamined
- **Type**: Gap
- **Location**: "there is no published concurrency entitlement, only fair-use language"
- **Problem**: The findings correctly identify that LocalStack's CI policy is vague, but treat this as a known unknown and move on. This deserves deeper treatment: Has LocalStack published any guidance on what triggers "fair use" enforcement? Do their support docs or community forums give practical parameters (e.g., X builds/day, Y concurrent runners)? The Feb 27 blog post citation could contain relevant language that was not extracted. Leaving this as purely open is appropriate for New Questions, but the trade-offs section should more forcefully flag it as a commercial risk — not merely a curiosity.
- **Impact**: Medium. A team that signs a Base contract expecting unlimited CI and then gets throttled or invoiced retroactively has a real business problem. The findings understate this risk.

---

### Issue 12: Hobby plan CI support creates an apparent contradiction that is not fully resolved
- **Type**: Missing nuance / potential contradiction
- **Location**: "Hobby plan includes 'Run tests in CI'" and "commercial team cannot stay compliant on current LocalStack releases with the free tier"
- **Problem**: The findings note both that Hobby supports CI and that commercial use is prohibited on Hobby. This is logically consistent but creates a surface contradiction that the findings do not fully explain: a commercial team *can* technically use Hobby in CI but is *contractually prohibited* from doing so. The distinction between technical capability and license compliance deserves an explicit sentence, since a developer reading the pricing page might see "CI: included" and assume it applies to their commercial project.
- **Impact**: Low-medium. A developer could make a wrong compliance decision based on the pricing page feature list without the commercial-use exclusion being front of mind.

---

## Summary

**Issues found**: 12

**Overall reliability**: **Medium**

The findings are accurate on the core pricing arithmetic, the licensing status of OSS alternatives, and the high-level commercial/non-commercial distinction for LocalStack's Hobby tier. The math checks out, the license characterizations are correct (with the Moto exception), and the structural framing is sound.

The reliability drops to medium because of three categories of weakness:

1. **Moto's scope is materially mischaracterized** (Issue 8), which could lead readers to dismiss the strongest multi-service OSS option.
2. **CI runner seat ambiguity is unresolved** (Issue 9), which can produce a significant cost underestimate — the most consequential factual gap.
3. **MiniStack is recommended without adequate scrutiny** (Issues 5, 6) despite appearing to be a solo-developer project with no maturity data.

**What would most improve the findings**:
- Add a service-coverage table for all five OSS alternatives (resolves Issues 6, 7, 8).
- Add maturity signals: last release date, star count, maintainer count (resolves Issue 10).
- Seek written clarification from LocalStack on whether CI runners require individual seats (resolves Issue 9).
- Verify and anchor the Floci "No auth token. Ever." quote (resolves Issue 4).
- Flag the April 30 promo cliff prominently in the trade-offs section (resolves Issues 1, 2).
