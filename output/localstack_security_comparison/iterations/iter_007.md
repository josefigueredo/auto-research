# Iteration 007 — CVE and vulnerability history

**Status:** keep  
**Scores:** coverage=73.3, quality=67.5, total=69.8  
**Timestamp:** 2026-04-08T20:53:12.335195+00:00  

---

### Findings

For **public vulnerability history and response process**, **LocalStack is the only one of the four with a meaningful public CVE trail**. I found three public CVEs tied to LocalStack: **CVE-2021-32090** (critical OS command injection), **CVE-2021-32091** (medium XSS), and **CVE-2023-48054** (high improper certificate validation). The weakest part of LocalStack’s record is not the raw CVE count by itself, but the **2021 disclosure handling**: SonarSource says it reported the issues in **October 2020**, followed up again, and that LocalStack later said the threats were not a key concern because LocalStack runs locally. That is a materially weaker signal than a documented private disclosure workflow with coordinated remediation. LocalStack’s current docs now say it responds to emergency vulnerabilities “as soon as possible” and scans images with Dependabot, Trivy, and Snyk, but its GitHub repo still shows **no `SECURITY.md` and no published GitHub advisories**. Net: LocalStack has the most evidence of security work, but also the clearest evidence of **historically imperfect disclosure handling**. Sources: [GitHub security page](https://github.com/localstack/localstack/security), [LocalStack FAQ](https://docs.localstack.cloud/aws/getting-started/faq/), [SonarSource disclosure writeup](https://www.sonarsource.com/blog/hack-the-stack-with-localstack), [OSV CVE-2021-32090](https://osv.dev/vulnerability/CVE-2021-32090), [OSV CVE-2021-32091](https://osv.dev/vulnerability/CVE-2021-32091), [NVD CVE-2023-48054](https://nvd.nist.gov/vuln/detail/CVE-2023-48054).

**MiniStack** has a better explicit policy document than LocalStack, but a weaker process. Its GitHub security page renders a `SECURITY.md` that is unusually candid: it says MiniStack is for **local development/CI only**, has **no authentication**, ignores AWS credentials, keeps data in memory without encryption, and warns that Docker socket mounts can expose the host. That honesty is useful. The problem is the disclosure channel: it tells reporters to **open a public GitHub issue tagged `security`**. For a commercial CI/CD standard, that is not a mature vulnerability disclosure process; it is effectively public issue reporting, not coordinated private disclosure. I found **no published GitHub advisories** and **no public CVEs** for MiniStack in the sources I checked. That does **not** prove it is safer; it mostly means the project is new/smaller and has little public security-history data. Sources: [GitHub security page](https://github.com/Nahuel990/ministack/security), [Docker Hub tags](https://hub.docker.com/r/nahuelnucera/ministack/tags).

**Floci** has the thinnest public security governance. GitHub shows **no `SECURITY.md`**, **no published advisories**, and I found **no public CVEs**. GitHub does expose a generic “Report a vulnerability” link, but that is not the same as a documented project policy with scope, SLA, or disclosure instructions. For a senior architect, the main point is not “no CVEs”; it is **lack of visible process and lack of public remediation history**. In a commercial CI context, that is a transparency risk. Sources: [GitHub security page](https://github.com/floci-io/floci/security), [Docker Hub image page](https://hub.docker.com/r/hectorvent/floci), [project site](https://floci.io/).

**Moto** lands between LocalStack and the newer projects. GitHub shows **no `SECURITY.md` and no GitHub advisories**, but the repo README does provide a **private disclosure route via Tidelift security contact**, which is stronger than MiniStack’s “open a public issue” and stronger than Floci’s lack of documented process. I did not find public Moto CVEs in NVD/OSV/GitHub advisory sources for the project itself. That means Moto’s public security history is quieter than LocalStack’s, but the disclosure posture is still only moderate because the process lives in the README rather than a first-class GitHub security policy. Sources: [Moto GitHub security page](https://github.com/getmoto/moto/security), [Moto repo README/search page](https://github.com/getmoto/moto), [Moto docs](https://docs.getmoto.org/).

For **container image vulnerability data**, I could verify the **latest public image tags/digests** from Docker Hub for all four, but I could only obtain a **public third-party image scan result for LocalStack**. In this environment, `trivy` is not installed, and Docker Scout is installed but requires Docker authentication, so I could not independently run the requested Trivy/Grype scans. Public unauthenticated scan results were not discoverable for MiniStack, Floci, or Moto. That transparency gap is itself relevant: if a vendor or project does not publish scan artifacts or at least a repeatable SBOM+scan workflow, a buyer has to do all image assurance themselves.

The one concrete public image-scan result I found was for **`localstack/localstack:latest-amd64`** on Snyk. At capture time it showed **1 critical, 2 high, 6 medium, and 155 low vulnerabilities** across **167 dependencies** on **Debian 13**. The critical item was in **`libnss3`**; the high items were both in **Node.js 22.22.0**. Cached Snyk summaries for the same image fluctuated between **138** and **164** total vulns, which is normal for continuously updated advisory backends, so the safest reading is: **LocalStack latest public image currently has at least one critical and multiple high findings in public scan data**. Sources: [Snyk detailed image report](https://snyk.io/test/docker/localstack%2Flocalstack%3Alatest-amd64), [Docker Hub LocalStack tags](https://hub.docker.com/r/localstack/localstack/tags), [Docker Hub LocalStack overview](https://hub.docker.com/r/localstack/localstack).

By contrast, for **MiniStack**, **Floci**, and **Moto**, I could confirm current image references but **not public scan counts**:
- MiniStack latest tag on Docker Hub showed **amd64 digest `b30718993e9c`**, **55.78 MB**.
- Floci latest showed **digest prefix `sha256:11a6cbf73…`**, **69.8 MB**.
- Moto latest showed **amd64 digest `661c6253b244`**, **96.69 MB**; pinned `5.1.22` showed **amd64 digest `117238c6e7e3`**, **96.58 MB**.
- LocalStack latest showed **amd64 digest `1d206fbb2283`**, **476.49 MB**.

That means the strongest evidence-based statement here is: **LocalStack has the most visible current image exposure because it is the only one with a public current scan result I could verify; the other three have insufficient public scan transparency, not proven cleanliness.** Sources: [MiniStack tags](https://hub.docker.com/r/nahuelnucera/ministack/tags), [Floci Docker Hub](https://hub.docker.com/r/hectorvent/floci), [Moto tags](https://hub.docker.com/r/motoserver/moto/tags), [LocalStack tags](https://hub.docker.com/r/localstack/localstack/tags).

### Evidence

- **LocalStack public CVEs**
  - **CVE-2021-32090**, published **2021-05-07**, CVSS **9.8 critical** in OSV. Source: [OSV](https://osv.dev/vulnerability/CVE-2021-32090)
  - **CVE-2021-32091**, published **2021-05-07**, CVSS **6.1 medium** in OSV. Source: [OSV](https://osv.dev/vulnerability/CVE-2021-32091)
  - **CVE-2023-48054**, published **2023-11-16**, CVSS **7.4 high** in NVD/OSV. Sources: [NVD](https://nvd.nist.gov/vuln/detail/CVE-2023-48054), [OSV/GHSA alias](https://osv.dev/vulnerability/GHSA-8633-g3ph-97rp)
- **LocalStack response-process evidence**
  - SonarSource says it reported the 2021 issues in **October 2020** and that the vendor later considered them not a key concern because LocalStack runs locally. Source: [SonarSource](https://www.sonarsource.com/blog/hack-the-stack-with-localstack)
  - LocalStack docs now say it responds to emergency vulnerabilities “as soon as possible” and uses **Dependabot, Trivy, and Snyk** to scan repos/images. Source: [LocalStack FAQ](https://docs.localstack.cloud/aws/getting-started/faq/)
  - GitHub still shows **no security policy detected** and **no published advisories**. Source: [GitHub security page](https://github.com/localstack/localstack/security)
- **LocalStack current image**
  - Docker Hub latest amd64 digest shown as **`1d206fbb2283`**, compressed size **476.49 MB**. Source: [Docker Hub tags](https://hub.docker.com/r/localstack/localstack/tags)
  - Public Snyk image report for `latest-amd64`: **1 critical / 2 high / 6 medium / 155 low**, **167 dependencies**, target OS **Debian 13**. Source: [Snyk image report](https://snyk.io/test/docker/localstack%2Flocalstack%3Alatest-amd64)
- **MiniStack process**
  - GitHub security page renders a `SECURITY.md`; it warns of **no auth**, credentials ignored, unencrypted in-memory data, and Docker socket host access. Source: [GitHub security page](https://github.com/Nahuel990/ministack/security)
  - Disclosure path is **public GitHub issue tagged `security`**; GitHub shows **no published advisories**. Same source.
  - Latest image amd64 digest shown as **`b30718993e9c`**, size **55.78 MB**. Source: [Docker Hub tags](https://hub.docker.com/r/nahuelnucera/ministack/tags)
- **Floci process**
  - GitHub shows **no security policy detected** and **no published advisories**. Source: [GitHub security page](https://github.com/floci-io/floci/security)
  - Latest image digest prefix shown as **`sha256:11a6cbf73…`**, size **69.8 MB**. Source: [Docker Hub image page](https://hub.docker.com/r/hectorvent/floci)
- **Moto process**
  - GitHub security page shows **no security policy detected** and **no published advisories**. Source: [GitHub security page](https://github.com/getmoto/moto/security)
  - Repo README says to report security issues via **Tidelift security contact**. Source: [Moto repo](https://github.com/getmoto/moto)
  - Latest image amd64 digest shown as **`661c6253b244`**; pinned **`5.1.22`** amd64 digest **`117238c6e7e3`**. Source: [Docker Hub tags](https://hub.docker.com/r/motoserver/moto/tags)

### Trade-offs

**If you weight public security governance highest, Moto currently looks better than Floci and MiniStack, but not because of richer CVE history.** It is because Moto at least exposes a **private disclosure path**. That is still weaker than a formal `SECURITY.md` with timelines, but it is materially better than Floci’s no-policy posture and MiniStack’s public-issue reporting.

**If you weight observable remediation activity highest, LocalStack is paradoxical.** It has the richest evidence of active security work and scanning, but also the worst documented public history in this comparison because the 2021 Sonar case shows a vendor that at least once appears to have **down-prioritized reported vulnerabilities** based on deployment assumptions. For a hardened CI pipeline, that matters because “it only runs locally” is exactly the kind of reasoning platform teams try to avoid.

**If you need auditable image-risk numbers today, only LocalStack gave me a verified public current-image result.** That is not a clean result, but it is still more transparent than the others. MiniStack, Floci, and Moto are not disqualified by public scan silence, but they also do not earn trust from it. In procurement terms, that means you would need to **internally mirror and scan all three yourself** before approval.

**Counter-intuitive point:** “no CVEs found” is a weak positive for MiniStack and Floci. For small or young projects, it often means **low disclosure volume**, not low vulnerability density. For a commercial CI/CD standard, **absence of a mature disclosure process is itself a security signal**.

### New Questions

1. Do any of the four publish or support **machine-verifiable SBOMs and signed provenance** for the exact image digests used in CI, so vulnerability triage can be tied to immutable artifacts rather than mutable tags?
2. Which of the four can be **rebuilt reproducibly in-house** from source onto a company-approved base image without breaking Terraform `plan`/`apply` behavior?
3. How much of each tool’s practical security risk comes from the emulator itself versus **Docker-socket-mediated secondary containers** it launches for Lambda, ECS, RDS, or similar services?

I could not independently execute Trivy/Grype scans for all four images in this environment because `trivy` is not installed and Docker Scout requires Docker authentication; public scan evidence was only verifiable for LocalStack. That limitation is why I treated the scan section conservatively and emphasized transparency gaps rather than inventing counts.

---

## Peer Review (claude)

## Critical Peer Review

---

### Issue 1: MiniStack repository identity is unverified
- **Type**: unsupported claim / gap
- **Location**: `Sources: [GitHub security page](https://github.com/Nahuel990/ministack/security)`
- **Problem**: The entire MiniStack security analysis is built on a repo under the personal GitHub account `Nahuel990`, not an organization account. The findings never establish that this is the canonical, authoritative, or commercially supported repository for "MiniStack." If this is a personal fork or a minor side project with low adoption, the comparison is structurally flawed — you'd be grading a hobby repo against production-grade tools.
- **Impact**: High. All MiniStack conclusions (SECURITY.md candor, public-issue disclosure, no CVEs) depend on the reader trusting this is the right repo. The findings never make that case.

---

### Issue 2: Floci Docker Hub publisher mismatch not addressed
- **Type**: gap / missing nuance
- **Location**: `[Docker Hub image page](https://hub.docker.com/r/hectorvent/floci)` versus `[GitHub security page](https://github.com/floci-io/floci/security)`
- **Problem**: The GitHub org is `floci-io` but the Docker Hub image is published under `hectorvent` — a personal account. This discrepancy is never acknowledged. It raises a legitimate supply chain question: is the Docker image built and pushed by the same team that maintains the source code? An image published from a personal account without a verifiable CI pipeline to the org repo is a distinct trust concern from an org-published image.
- **Impact**: Medium. Weakens the claim that Floci's image provenance is comparable to LocalStack's organization-owned registry artifacts.

---

### Issue 3: Tidelift security contact is materially undersold for Moto
- **Type**: missing nuance
- **Location**: `the process lives in the README rather than a first-class GitHub security policy`
- **Problem**: Tidelift is not just a README link — it is a structured, third-party-operated vulnerability disclosure service with defined intake, triage, and notification workflows specifically built for open source maintainers. Describing it as inferior to a `SECURITY.md` file (which is just a text file with no enforcement) inverts the actual process maturity. A Tidelift disclosure goes to a professional intermediary; a `SECURITY.md` is only as good as the maintainer who reads the email.
- **Impact**: Medium. Moto's security posture is ranked below what the evidence supports. A reader comparing projects could incorrectly deprioritize Moto on this basis.

---

### Issue 4: "No public CVEs" analysis applies incorrect logic to Moto
- **Type**: missing nuance / unsupported claim
- **Location**: `That does not prove it is safer; it mostly means the project is new/smaller and has little public security-history data.` (applied equally to all three non-LocalStack projects)
- **Problem**: This "small/young project" caveat is explicitly applied to MiniStack and Floci, but Moto is neither small nor young. Moto has been active since approximately 2012, has millions of PyPI downloads, and is used in production test suites at major enterprises. For a project of that age and adoption with no public CVEs, "low disclosure volume" is a weaker explanation than it would be for a 2-year-old hobby project. The absence of CVEs for Moto is a moderately positive signal, not a neutral one, and the findings treat them identically.
- **Impact**: Medium. Misrepresents Moto's relative security maturity.

---

### Issue 5: LocalStack vendor response rests on a single adversarial source
- **Type**: unsupported claim / missing nuance
- **Location**: `SonarSource says it reported the issues in October 2020, followed up again, and that LocalStack later said the threats were not a key concern because LocalStack runs locally.`
- **Problem**: The characterization of LocalStack's response — specifically the "not a key concern" quote and the implied negligence — is sourced exclusively from SonarSource's own blog post, written by the party that discovered and disclosed the vulnerabilities. SonarSource has a publication incentive to frame vendor responses unfavorably. No LocalStack official response, issue tracker evidence, or neutral third-party account is cited to corroborate or contextualize their characterization. The findings treat this as established fact rather than one party's account.
- **Impact**: High. The "materially weaker signal" conclusion about LocalStack's disclosure handling drives significant downstream ranking in the trade-offs section, and it rests on unverified, source-biased testimony.

---

### Issue 6: Moto's primary use case as a Python library is absent
- **Type**: gap
- **Location**: The entire Moto section, including container image analysis
- **Problem**: Moto is fundamentally a Python library imported directly into test code (`@mock_aws` decorators), not a Docker service. The `motoserver/moto` container is a secondary deployment mode. The dominant security risk for Moto users is the **Python package supply chain** (PyPI, dependencies, import-time code execution), not the container image. Evaluating Moto's security posture almost entirely through the lens of its Docker image misrepresents how most users encounter it and where its actual attack surface lives.
- **Impact**: High. A security assessment that ignores the primary consumption vector (Python package) for a tool primarily consumed as a Python package is structurally incomplete.

---

### Issue 7: "No SECURITY.md" claims presented as current fact without staleness caveat
- **Type**: missing nuance
- **Location**: `its GitHub repo still shows no SECURITY.md and no published GitHub advisories` (LocalStack); similar for Moto and Floci
- **Problem**: GitHub security policies can be added or updated at any time. The findings acknowledge data staleness generally but present these specific absences as definitive current fact rather than point-in-time observations. LocalStack in particular is an actively maintained commercial project with dedicated engineering staff. The lack of a staleness caveat on these specific claims makes them feel more authoritative than they are.
- **Impact**: Low-medium. Could lead to incorrect remediation recommendations if any of these repos have since added a security policy.

---

### Issue 8: LocalStack Community vs. Pro security posture distinction is missing
- **Type**: gap
- **Location**: Throughout the LocalStack analysis
- **Problem**: LocalStack has two meaningfully different products: the open-source Community edition and the commercial LocalStack Pro. Pro includes additional services, a different image, and presumably different security assurance commitments given its enterprise positioning. The findings analyze `localstack/localstack:latest` but never acknowledge that a commercial buyer of LocalStack Pro would have a different contract surface, different SLA expectations for vulnerability response, and potentially different scan profiles. Conflating Community and Pro security posture is a gap for a "senior architect" audience evaluating CI/CD standardization.
- **Impact**: Medium. Relevant to the stated use case (commercial CI/CD standard).

---

### Issue 9: "Paradox" framing for LocalStack is logically misleading
- **Type**: missing nuance
- **Location**: `If you weight observable remediation activity highest, LocalStack is paradoxical.`
- **Problem**: This is not a paradox — it is the expected pattern for any large, mature, widely-adopted project. Older projects with more users accumulate more CVEs *and* build more security infrastructure in response. Framing this as paradoxical implies the combination is unusual or suspicious, when it is the normal trajectory of software security maturity. The framing could cause readers to discount LocalStack's positive security signals inappropriately.
- **Impact**: Low. Rhetorical issue more than factual, but it shapes the trade-off section's tone.

---

### Issue 10: Runtime container security controls not addressed
- **Type**: gap
- **Location**: Trade-offs and New Questions sections
- **Problem**: The findings cover CVE history, disclosure processes, and image vulnerability counts, but never address runtime security posture: Does each tool require `--privileged` mode? What Linux capabilities are needed? Do they use user namespaces? What network ports are exposed and to what interfaces? For a "hardened CI pipeline" audience, these runtime controls are often more immediately actionable than CVE counts on base image packages.
- **Impact**: Medium. The New Questions section gestures at Docker socket risk but does not capture the full runtime security surface, which is partially addressable without vendor cooperation.

---

### Issue 11: Image size is implicitly equated with vulnerability surface without stating this assumption
- **Type**: missing nuance
- **Location**: Size comparisons (LocalStack 476.49 MB vs. Moto 96.69 MB vs. MiniStack 55.78 MB)
- **Problem**: The findings present image sizes alongside CVE data in a way that implies a correlation without stating it explicitly. Image size is a weak proxy for vulnerability surface — a small image can have a vulnerable base layer while a large image can use a hardened distroless base. The findings never make clear whether they are treating size as a proxy for attack surface, and if so, why that assumption holds here.
- **Impact**: Low. Could mislead readers who interpret the size comparison as a security ranking.

---

## Summary

| # | Type | Severity |
|---|------|----------|
| 1 | Unsupported claim / gap (MiniStack repo identity) | High |
| 2 | Gap (Floci publisher mismatch) | Medium |
| 3 | Missing nuance (Tidelift undersold) | Medium |
| 4 | Missing nuance / unsupported claim (Moto CVE logic) | Medium |
| 5 | Unsupported claim (single adversarial source for LocalStack response) | High |
| 6 | Gap (Moto as Python library) | High |
| 7 | Missing nuance (staleness caveat on policy absences) | Low–Medium |
| 8 | Gap (LocalStack Community vs. Pro) | Medium |
| 9 | Missing nuance ("paradox" framing) | Low |
| 10 | Gap (runtime security controls) | Medium |
| 11 | Missing nuance (size as surface proxy) | Low |

**Total issues: 11**

**Overall reliability: Medium**

The findings are methodologically honest about what the researcher could and could not verify (scan limitations, single-source constraints), and the vulnerability count data for LocalStack is well-sourced. The analysis degrades most in three places: (1) the MiniStack section is built on an unverified repository identity, which undermines that entire comparison leg; (2) the LocalStack disclosure handling verdict rests on one party's self-interested account with no corroboration; and (3) Moto's security profile is assessed almost entirely through its container image when its Python package is how most engineers actually consume it.

**What would most improve the findings:**
1. Establish MiniStack's canonical repository and adoption level before drawing conclusions from it.
2. Corroborate the LocalStack vendor response characterization with a second source or note explicitly that it is SonarSource's unverified account.
3. Add a Moto PyPI/package security analysis (dependency tree, PyPI provenance, import-time surface) alongside the container analysis.
