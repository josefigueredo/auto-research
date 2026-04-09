# Iteration 005 — CVE and vulnerability history

**Status:** keep  
**Scores:** coverage=76.7, quality=65.0, total=69.7  
**Timestamp:** 2026-04-08T20:37:31.043924+00:00  

---

### Findings

As of **April 8, 2026**, the only clearly disclosed **project-level CVEs** I could verify for these four emulators are against **LocalStack**. I found **no published GitHub Security Advisories** for any of the four repos’ security tabs, and only **LocalStack** surfaced public CVE records tied directly to the repo/package in OSV/NVD: **CVE-2021-32090** (critical command injection in the dashboard) and **CVE-2021-32091** (medium XSS), both affecting **0.12.6** and earlier ([OSV 32090](https://osv.dev/vulnerability/CVE-2021-32090), [OSV 32091](https://osv.dev/vulnerability/CVE-2021-32091), [NVD 32091](https://nvd.nist.gov/vuln/detail/CVE-2021-32091), [MITRE 32090](https://cve.mitre.org/cgi-bin/cvename.cgi?name=2021-32090)). SonarSource says it reported the issues in **October 2020**, got a response in **January 2021** that they were not treated as a key concern, and then published on **March 2, 2021** ([Sonar](https://www.sonarsource.com/blog/hack-the-stack-with-localstack/)). That is not the behavior of a mature security response program.

LocalStack’s public advisory hygiene is weak. GitHub’s security page for the archived repo says **“No security policy detected”** and **“There aren’t any published security advisories”** ([GitHub security](https://github.com/localstack/localstack/security)). OSV does reference a fix commit for CVE-2021-32090, and release feeds show **v0.12.7** existed shortly after the 0.12.6 disclosures ([OSV GHSA ref](https://osv.dev/vulnerability/GHSA-hpr6-f4vq-mxch), [release feed](https://newreleases.io/project/github/localstack/localstack/release/v0.12.7)), but the public record is inconsistent enough that I would not score LocalStack highly on transparent remediation or advisory publication. More bluntly: it appears to have fixed at least part of the issue path, but not through a documented, high-trust security-advisory workflow.

For **Moto**, **MiniStack**, and **Floci**, I found **no repo-level published advisories** on GitHub and no directly attributable repo/package CVEs in the searches I ran. That is not the same as “secure”; it mostly means their **public vulnerability history is sparse or untested**. The difference is process:
- **MiniStack** has a `SECURITY.md`, explicitly warns it is for local/CI use only, and tells researchers to open a GitHub issue tagged `security` ([GitHub security](https://github.com/Nahuel990/ministack/security)).
- **Moto** has **no `SECURITY.md`** on the repo security tab, but its README gives a private disclosure path through **Tidelift** ([README](https://github.com/getmoto/moto), [GitHub security](https://github.com/getmoto/moto/security)).
- **Floci** has **no `SECURITY.md`** and no published advisories on the repo security page ([GitHub security](https://github.com/floci-io/floci/security)).

On **container/base-image CVE burden**, the inheritance risk currently matters more than project-level CVEs for three of the four tools. The public Dockerfiles show:
- **LocalStack**: `python:3.13.12-slim-trixie@sha256:...` ([Dockerfile](https://raw.githubusercontent.com/localstack/localstack/master/Dockerfile))
- **MiniStack**: prior research points to `python:3.12-alpine`; I could confirm the repo is Docker-based and releases rapidly, but I could not re-open the raw Dockerfile in this session, so I treat this base-image mapping as inherited from your prior validated notes plus current repo/Docker Hub state ([repo](https://github.com/Nahuel990/ministack), [Docker Hub](https://hub.docker.com/r/nahuelnucera/ministack))
- **Moto**: `python:3.13-alpine` ([Dockerfile](https://raw.githubusercontent.com/getmoto/moto/master/Dockerfile))
- **Floci** current root Dockerfile: `eclipse-temurin:25-jre-alpine` for runtime ([Dockerfile](https://raw.githubusercontent.com/floci-io/floci/main/Dockerfile)); Quarkus docs show native builds commonly default to `quay.io/quarkus/ubi9-quarkus-micro-image:2.0` ([Quarkus docs](https://quarkus.io/guides/quarkus-runtime-base-image), [container-image docs](https://es.quarkus.io/guides/container-image)).

For the bases I could scan from public Docker-Scout-backed pages, the current burden is materially different:
- `python:3.13-slim-trixie`: **21 vulns** total, **0 critical / 0 high / 1 medium / 20 low** ([scan](https://sliplane.io/tools/cve/library/python%3A3.13-slim-trixie), official tag mapping on Docker Hub shows `3.13-slim-trixie` is current official tag family [Docker Hub](https://hub.docker.com/_/python))
- `python:3.13-alpine`: **3 vulns** total, **0 critical / 0 high / 1 medium / 2 low** ([scan](https://sliplane.io/tools/cve/library/python%3A3.13-alpine), [Docker Hub](https://hub.docker.com/_/python))
- `eclipse-temurin:25-jre-alpine`: **11 vulns** total, **1 critical / 4 high / 4 medium / 2 low** in the scan snapshot I found ([scan](https://sliplane.io/tools/cve/library/eclipse-temurin%3A25-jre-alpine))

That creates a surprising inversion: **Moto’s Alpine Python base currently looks materially cleaner than LocalStack’s Debian slim base**, while **Floci’s JVM Alpine runtime currently looks worst of the three scanned bases**. I could not verify a current public scanner result for **`python:3.12-alpine`** or **`quarkus-micro-image:2.0`** in this session, so I will not invent exact counts for those two. The best-supported statement is narrower: `python:3.12-alpine` currently resolves to the **3.12.13-alpine3.23** family on Docker Hub ([Docker Hub](https://hub.docker.com/_/python?name=3-alpine&page=1&tab=description)), and Quarkus native images are based on **UBI micro**, not Alpine ([Quarkus docs](https://quarkus.io/guides/quarkus-runtime-base-image)).

On **patched-image release frequency**, the projects split into two groups:
- **MiniStack** and **Floci** are shipping extremely fast right now. MiniStack shows **62 releases**, latest **v1.1.52 on April 8, 2026**, and Docker Hub tags updated **within hours** ([GitHub](https://github.com/Nahuel990/ministack), [Docker tags](https://hub.docker.com/r/nahuelnucera/ministack/tags)). Floci shows **20 releases**, latest **1.4.0 on April 8, 2026**, and Docker Hub updated **3 days ago** ([GitHub](https://github.com/floci-io/floci), [Docker Hub](https://hub.docker.com/r/hectorvent/floci)).
- **Moto** is active but less frenetic: **67 releases**, latest **5.1.22 on March 8, 2026** ([GitHub](https://github.com/getmoto/moto)).
- **LocalStack public OSS** is effectively frozen: repo archived **March 23, 2026** and latest public OSS release is **v4.14.0 from February 26, 2026** ([GitHub repo](https://github.com/localstack/localstack), [security tab](https://github.com/localstack/localstack/security)).

For a commercial CI/CD risk review, that matters more than it first appears. A project with no historical CVEs but also **no tested disclosure machinery** is a process risk. A project with disclosed CVEs and a poor historical response is also a process risk. On this dimension alone:
- **LocalStack** has the worst verified historical incident record.
- **Moto** has the best documented disclosure channel, but not via GitHub advisory infrastructure.
- **MiniStack** has the best explicit repo-level security policy of the three smaller alternatives.
- **Floci** is operationally fast-moving but process-light from a security-governance standpoint.

### Evidence

- **LocalStack disclosed CVEs**
  - **CVE-2021-32090**: critical command injection in dashboard, affects **0.12.6** and earlier ([OSV](https://osv.dev/vulnerability/CVE-2021-32090), [MITRE](https://cve.mitre.org/cgi-bin/cvename.cgi?name=2021-32090))
  - **CVE-2021-32091**: medium XSS, affects **0.12.6** and earlier ([OSV](https://osv.dev/vulnerability/CVE-2021-32091), [NVD](https://nvd.nist.gov/vuln/detail/CVE-2021-32091))
  - Sonar says report sent **October 2020**, vendor response in **January 2021**, public write-up **March 2, 2021** ([Sonar](https://www.sonarsource.com/blog/hack-the-stack-with-localstack/))
  - GitHub security page: **no `SECURITY.md`**, **no published advisories** ([GitHub](https://github.com/localstack/localstack/security))

- **Moto security process**
  - GitHub security page: **no `SECURITY.md`**, **no published advisories** ([GitHub](https://github.com/getmoto/moto/security))
  - README directs vuln reports to **Tidelift security contact** ([repo](https://github.com/getmoto/moto))
  - Latest release **5.1.22**, **March 8, 2026** ([repo](https://github.com/getmoto/moto))

- **MiniStack security process**
  - Has `SECURITY.md`; warns of no auth, ignored creds, in-memory unencrypted data, and Docker socket host-access risk ([GitHub security](https://github.com/Nahuel990/ministack/security))
  - No published GitHub advisories ([same](https://github.com/Nahuel990/ministack/security))
  - Latest release **v1.1.52**, **April 8, 2026**; Docker tags updated **about 3 hours ago** in the crawl snapshot ([GitHub](https://github.com/Nahuel990/ministack), [Docker tags](https://hub.docker.com/r/nahuelnucera/ministack/tags))

- **Floci security process**
  - No `SECURITY.md`; no published GitHub advisories ([GitHub security](https://github.com/floci-io/floci/security))
  - Latest release **1.4.0**, **April 8, 2026**; Docker Hub updated **3 days ago** ([GitHub](https://github.com/floci-io/floci), [Docker Hub](https://hub.docker.com/r/hectorvent/floci))

- **Base-image burden snapshots**
  - `python:3.13-slim-trixie`: **21** vulns, **0/0/1/20** ([scan](https://sliplane.io/tools/cve/library/python%3A3.13-slim-trixie))
  - `python:3.13-alpine`: **3** vulns, **0/0/1/2** ([scan](https://sliplane.io/tools/cve/library/python%3A3.13-alpine))
  - `eclipse-temurin:25-jre-alpine`: **11** vulns, **1/4/4/2** ([scan](https://sliplane.io/tools/cve/library/eclipse-temurin%3A25-jre-alpine))
  - Official Docker Hub maps `python:3.12-alpine` to **3.12.13-alpine3.23** and `python:3.13-alpine` to **3.13.12-alpine3.23** today ([Docker Hub](https://hub.docker.com/_/python?name=3-alpine&page=1&tab=description))

### Trade-offs

**LocalStack** is the only one with a verified repo-level CVE history here, which is useful because it gives a real test of how the maintainer handled disclosure. The test result is not great: delayed/contested triage, no visible GitHub advisory workflow, and now an archived public repo. Counter-intuitively, though, its current **Debian slim** base scan is not catastrophic; the bigger concern is governance and patch transparency, not raw base-image count.

**Moto** looks better than expected on image burden because `python:3.13-alpine` is currently much cleaner than `python:3.13-slim-trixie`. The downside is process: no `SECURITY.md`, no public advisories, and disclosure is outsourced to Tidelift. That is workable for a commercial company, but less self-service and less transparent than a normal GitHub advisory program.

**MiniStack** has the strongest repo-level warning language and the cleanest plain-English security policy, which is unusually useful for internal risk review. The concern is that this is still a small, fast-moving project with little or no public CVE history, so its “track record” is mostly unproven rather than proven-good. The upside is that its release cadence is fast enough that patch turnaround could be excellent if the maintainer stays engaged.

**Floci** is the most mixed case. Its release velocity is excellent, but the current scanned **Temurin 25 Alpine** base is carrying the heaviest inherited burden among the bases I could verify, and the repo lacks a visible security policy. If you choose Floci, I would strongly treat it as a candidate for **internal rebuild + internal scanning + mirrored registry only**, because the project’s release speed is good but its public security-process maturity is still thin.

### New Questions

- How much of each project’s risk comes from **transitive Python/Java dependencies installed at build time**, not just the base image?
- Which projects publish or can support **machine-readable SBOMs** so CI can enforce vuln-policy gates deterministically?
- For Terraform CI specifically, which emulator images can be run **rootless and without Docker socket mounting**, and how much does that change effective exploitability of inherited CVEs?

I found exact current vulnerability counts for `python:3.13-slim-trixie`, `python:3.13-alpine`, and `eclipse-temurin:25-jre-alpine`, but not for `python:3.12-alpine` or `quarkus-micro-image:2.0` from a public scanner result I could verify in-session. For those two, I could confirm tag lineage and image family, but not an authoritative current count.

---

## Peer Review (claude)

This is a detailed, mostly careful piece of research with some genuine strengths, but it has several issues that would weaken it in a formal risk review context. Here is my line-by-line critique.

---

### Issue 1: Tag mismatch between Dockerfile claim and scan data

- **Type**: factual error / unsupported claim
- **Location**: "LocalStack: `python:3.13.12-slim-trixie@sha256:...`" in the base-image section, versus "python:3.13-slim-trixie: 21 vulns" in the scan evidence
- **Problem**: These are two different Docker tags. `python:3.13.12-slim-trixie` (a pinned patch-version with a digest) and `python:3.13-slim-trixie` (a floating tag) may resolve to the same image layer today, but may not. The scan was run against the floating tag, not the pinned digest that appears in the Dockerfile. The findings never establish that these are the same image SHA, so the CVE count cannot be reliably attributed to LocalStack's actual deployed image.
- **Impact**: The central "21 vs 3 vuln inversion" conclusion rests on a scan of a tag that may differ from the actual image in use. This is a material evidentiary gap for the comparative analysis.

---

### Issue 2: GHSA-hpr6-f4vq-mxch citation conflicts with "no published advisories" claim

- **Type**: contradiction / missing nuance
- **Location**: "GitHub's security page...says 'There aren't any published security advisories'" alongside "[OSV GHSA ref](https://osv.dev/vulnerability/GHSA-hpr6-f4vq-mxch)"
- **Problem**: A GHSA ID (GitHub Security Advisory) exists for this vulnerability. GitHub Security Advisories can be created two ways: by repository maintainers (shows as "published" on the security tab) or by GitHub's advisory curation team ingesting from NVD/OSV (may not appear as maintainer-published). The findings never clarify which kind GHSA-hpr6-f4vq-mxch is. The reader is left with what looks like a contradiction — "no published advisories" but a GHSA ID is cited — when the actual distinction is "maintainer-published vs. database-curated." This distinction matters a lot for the governance conclusion being drawn.
- **Impact**: The conclusion about LocalStack's "weak advisory hygiene" is likely correct, but the evidentiary chain here is muddled and would not survive scrutiny in a formal audit report.

---

### Issue 3: Sliplane.io is an unverified, undated scan source

- **Type**: unsupported claim / missing nuance
- **Location**: All three CVE count figures — "21 vulns", "3 vulns", "11 vulns" — cite sliplane.io scans
- **Problem**: Sliplane.io is a third-party tool, not an authoritative scanner (Docker Scout, Grype/Syft, Snyk, or Trivy would be). The findings do not state when these scans were run, what scanner version or database was used, or how often the site refreshes its data. Docker image CVE landscapes can shift significantly within days as NVD publishes or retracts entries. An undated scan from a non-authoritative tool is weak evidence for specific numeric claims.
- **Impact**: The "surprising inversion" conclusion — the core analytical finding in the base-image section — is built entirely on three counts that have no audit trail. If any of the three numbers is stale by even a few weeks, the inversion may not hold.

---

### Issue 4: The "alpine looks cleaner" narrative lacks a critical scanner methodology caveat

- **Type**: missing nuance
- **Location**: "Moto's Alpine Python base currently looks materially cleaner than LocalStack's Debian slim base"
- **Problem**: Alpine images carry fewer OS packages and use musl libc, both of which reduce the total count of CVE-mapped packages — but this is a property of the image's package surface, not of its actual security posture. Several well-documented scanner behaviors compound this: (1) some scanners historically undercounted musl libc vulnerabilities because CVE records cite glibc, (2) Alpine images' smaller package set means vulnerabilities can also be hidden rather than absent. "Fewer detectable CVEs" and "lower attack surface" are related but not equivalent. The findings present this as a simple win for Moto without caveat.
- **Impact**: A reader making a tooling decision based on this framing could underestimate Moto's base-image risk, particularly if their internal scanner has different alpine/musl coverage.

---

### Issue 5: MiniStack's SECURITY.md practice is framed as a strength when it is actually a weak responsible-disclosure mechanism

- **Type**: missing nuance / unsupported claim
- **Location**: "MiniStack has a SECURITY.md...tells researchers to open a GitHub issue tagged `security`" and later "MiniStack has the best explicit repo-level security policy of the three smaller alternatives"
- **Problem**: Directing security researchers to open a public GitHub issue for a vulnerability is the opposite of responsible disclosure. A public issue discloses the vulnerability to all observers before a patch exists or is deployed. This is generally considered an antipattern and would fail most enterprise responsible-disclosure assessments. The findings praise this as "the best...security policy" without noting the fundamental problem.
- **Impact**: A reader relying on this assessment might incorrectly favor MiniStack on security-process grounds. The distinction between "has a SECURITY.md" and "has a good SECURITY.md" is elided entirely.

---

### Issue 6: SonarSource's blog post is treated as objective, uncontested testimony

- **Type**: missing nuance
- **Location**: "SonarSource says it reported the issues in October 2020, got a response in January 2021 that they were not treated as a key concern"
- **Problem**: The SonarSource blog post is the only source for how LocalStack behaved during the disclosure window. It is a marketing/PR artifact written by the disclosing party after the fact. The findings do not acknowledge that the characterization of LocalStack's response ("not treated as a key concern") is SonarSource's interpretation of a private communication, not a documented fact from the vendor. LocalStack's internal reasoning, the actual text of the January 2021 response, and whether they disputed this characterization are all unknown.
- **Impact**: The conclusion about LocalStack's "process risk" rests partly on this account. Treating one-sided disclosure narrative as established fact weakens the credibility of the governance assessment.

---

### Issue 7: Editorial judgment appears in the findings section without being flagged as such

- **Type**: missing nuance
- **Location**: "That is not the behavior of a mature security response program."
- **Problem**: This is a conclusion, not a finding. It belongs in the Trade-offs section or should be qualified as an evaluative judgment. As written, in the middle of the findings, it reads like an evidenced fact rather than an opinion derived from the evidence. The findings section should describe what happened; the trade-offs section is where normative assessments belong.
- **Impact**: Minor, but it erodes the findings/analysis distinction that makes research reports credible to skeptical readers.

---

### Issue 8: LocalStack archival context is entirely absent

- **Type**: gap
- **Location**: "LocalStack public OSS is effectively frozen: repo archived March 23, 2026"
- **Problem**: The findings report the archival without explaining why. The most likely explanation — LocalStack pivoting to a commercial, closed-source model — has significant downstream implications: (1) security patches for the commercial product may continue in a private repo; (2) the enterprise contract may include a disclosure SLA that the open-source record entirely misses; (3) the CVE history of the open-source version may have no bearing on the commercial version's security posture. None of this is addressed. For an organization evaluating Terraform CI tooling, the distinction between "abandoned" and "commercialized" is critical.
- **Impact**: The comparative framing implicitly treats the archived repo as the full picture. If LocalStack's commercial offering has a functioning security program, the research's governance critique is substantially undermined.

---

### Issue 9: Quarkus native image reference is tangential and potentially inapplicable

- **Type**: missing nuance / unsupported claim
- **Location**: "Quarkus docs show native builds commonly default to `quay.io/quarkus/ubi9-quarkus-micro-image:2.0`"
- **Problem**: The evidence section already establishes that Floci's actual Dockerfile uses `eclipse-temurin:25-jre-alpine` — a JVM runtime image, not a native binary. If Floci is running in JVM mode (which the Dockerfile confirms), the Quarkus native image base is irrelevant. The UBI micro reference adds noise and may confuse a reader into thinking there are two possible images to assess when only one is in use.
- **Impact**: Low-severity, but it dilutes the Floci base-image analysis and could prompt a reader to investigate the wrong image.

---

### Issue 10: "Outsourced to Tidelift" slightly mischaracterizes Tidelift's role

- **Type**: missing nuance
- **Location**: "disclosure is outsourced to Tidelift"
- **Problem**: Tidelift is a security coordination and support subscription service, not a security outsourcing firm. Moto's use of Tidelift means a reporting channel exists through a structured third party — which is different from "outsourcing." The distinction matters because Tidelift provides a paper trail, a paid maintainer relationship, and structured SLA expectations that purely ad-hoc disclosure channels lack. Calling it "outsourced" carries a negative connotation that isn't clearly earned and undersells the signal that Moto has a commercial coordination agreement in place.
- **Impact**: Small, but the framing influences the comparative scoring. Moto's Tidelift channel is arguably more enterprise-grade than "GitHub issue tagged security," which the research rates more favorably.

---

### Issue 11: Base-image CVE counts are the primary metric, but the research's own caveats about transitive dependencies are buried in "New Questions"

- **Type**: gap / structural
- **Location**: Main analysis uses base-image scans as the primary risk signal; "How much of each project's risk comes from transitive Python/Java dependencies installed at build time" appears only in "New Questions"
- **Problem**: For Python applications like LocalStack and Moto, the installed pip packages almost certainly carry more CVE surface than the base OS image. A `python:3.13-slim-trixie` image running boto3, cryptography, requests, and dozens of other packages at runtime presents a materially different attack surface than the 21 OS-level CVEs the scan found. The findings acknowledge this implicitly by deferring it to "New Questions," but the comparative conclusions are stated as if base-image counts are a reliable proxy for total risk. They are not, and the findings should prominently caveat this before presenting the inversion result.
- **Impact**: This is the most consequential gap. A reader could act on the "Moto is materially cleaner" conclusion without knowing that they've only seen roughly 10–20% of the actual vulnerability surface (at best).

---

### Issue 12: Release and version counts are point-in-time snapshots stated without a timestamp

- **Type**: missing nuance
- **Location**: "MiniStack shows 62 releases," "Moto...67 releases," "Floci shows 20 releases"
- **Problem**: GitHub release counts change continuously. Without stating the date these counts were observed, a reader checking a week later will see different numbers and may doubt the research's accuracy across the board, including on claims that are correct. This is a minor fixable documentation issue, but it affects reproducibility.
- **Impact**: Low on its own, but combined with other timestamp gaps (scan dates, Docker Hub last-pushed times), the research lacks a consistent reference date for its "current state" claims.

---

## Summary

**Total issues found**: 12 (2 factual/contradictions, 4 unsupported claims, 5 missing nuance, 1 gap/structural)

**Overall reliability**: **Medium**

The research is clearly the product of real investigation — the CVE history is correct, the disclosure timeline is documented, the base-image sourcing is specific enough to be checkable, and the comparative framing is directionally sound. But several of the conclusions that matter most for a decision-maker are built on evidence that is weaker than it appears: undated third-party scans, a single advocacy source for the LocalStack disclosure narrative, and a base-image metric that the authors themselves acknowledge is incomplete.

**What would most improve the findings, in priority order**:

1. Replace or supplement the sliplane.io scans with timestamped output from Grype, Docker Scout, or Trivy run against the pinned image digests actually used in each project's Dockerfile. This would fix Issues 1, 3, and 4 simultaneously.
2. Add a one-paragraph caveat before the base-image section stating that OS-level CVE counts exclude application dependency surface, and that the counts should be treated as a lower bound, not a total risk score (Issue 11).
3. Clarify whether GHSA-hpr6-f4vq-mxch was maintainer-published or database-curated, and fix the apparent contradiction with "no published advisories" (Issue 2).
4. Revise the MiniStack SECURITY.md assessment to note that public GitHub issues are a poor responsible-disclosure mechanism (Issue 5).
5. Add a sentence on why LocalStack was archived and whether the commercial offering has a separate security program (Issue 8).
