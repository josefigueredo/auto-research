# Iteration 009 — CVE and vulnerability history

**Status:** keep  
**Scores:** coverage=76.7, quality=67.5, total=71.2  
**Timestamp:** 2026-04-08T21:09:21.310517+00:00  

---

### Findings

As of **April 8, 2026**, the only clearly documented **project-specific CVE** I found among these four is **LocalStack CVE-2023-48054**: missing SSL certificate validation in LocalStack 2.3.2, published **November 16, 2023**, rated **High 7.4 CVSS v3.1** by NVD. NVD, OSV, and GitLab’s advisory mirror all agree on the defect and affected package lineage; the unusual part is that public advisory metadata still does **not** clearly name a fixed release, which is a security-hygiene concern in itself because it complicates automated policy gating and remediation tracking. Sources: [NVD](https://nvd.nist.gov/vuln/detail/CVE-2023-48054), [OSV](https://osv.dev/vulnerability/CVE-2023-48054), [GitLab advisory](https://advisories.gitlab.com/pkg/pypi/localstack/CVE-2023-48054/).

For **Moto**, **MiniStack**, and **Floci**, I did **not** find a published project-level CVE or GitHub Security Advisory for the main project/image itself in current public sources. That is not the same as “clean.” It means the public record is sparse. The more important difference is disclosure maturity:
- **MiniStack** has a public `SECURITY.md` and an explicit warning that it is for local dev/CI only, but says to report issues via a normal GitHub issue tagged `security`, not a private advisory workflow. Its GitHub security page currently shows **no published advisories**. Source: [MiniStack security page](https://github.com/Nahuel990/ministack/security).
- **Floci** has **no SECURITY.md** on GitHub, but GitHub does expose “Report a vulnerability”; its security page shows **no published advisories**. Source: [Floci security page](https://github.com/floci-io/floci/security).
- **Moto** also has **no SECURITY.md** and **no published advisories** on GitHub, but its README does at least direct reporters to **Tidelift** for coordinated disclosure. Sources: [Moto security page](https://github.com/getmoto/moto/security), [Moto README](https://github.com/getmoto/moto).
- **LocalStack**’s archived OSS repo shows **no SECURITY.md** and **no published GitHub advisories** despite having at least one public CVE in the package ecosystem. That mismatch is a negative signal for advisory-channel hygiene. Source: [LocalStack security page](https://github.com/localstack/localstack/security).

On **published image scan results**, LocalStack is the only one where I found a current, public, image-level vulnerability view with useful detail: the **Docker Hardened Images** LocalStack variants. Those are a separate paid distribution, not the normal Docker Hub image, but they are the only public scan artifacts I found that expose current counts. On Docker Hub’s DHI catalog, LocalStack **4.14.x** showed:
- **Alpine 3.22 / amd64**: **0 critical, 0 high, 5 medium, 1 low** on one manifest; another amd64 manifest showed **0 critical, 1 high, 5 medium, 1 low**.
- **Debian 13 / arm64**: **0 critical, 2 high, 3 medium, 1 low**.
- Health score shown as **A**.
Sources: [DHI LocalStack Alpine 4.14.x](https://hub.docker.com/hardened-images/catalog/dhi/localstack/images/localstack%2Falpine-3.22%2F4/sha256-8910913f1dc27cfa77bc73c26858ab06783cc9cbb208ff699dc2dd6a68863c81?order=asc&orderBy=license), [DHI LocalStack Debian 4.14.x](https://hub.docker.com/hardened-images/catalog/dhi/localstack/images/localstack%2Fdebian-13%2F4/sha256-eec34dfc6a710e77e607a269c21e4703d8e542d9445d4df8aaf292dedd43b156?order=desc&orderBy=version), [Docker on DHI CVE methodology](https://docs.docker.com/scout/advisory-db-sources), [DHI product page](https://www.docker.com/products/hardened-images/).

For the **standard images**, I found current public registry metadata but **not** a comparable public vulnerability dashboard:
- **LocalStack standard image**: `sha256:94c3730fc…`, about **468.8 MB**, updated **3 days ago**. Source: [Docker Hub](https://hub.docker.com/r/localstack/localstack/).
- **Moto server**: `sha256:1e3802c95…`, about **96.6 MB**, updated **4 days ago**. Source: [Docker Hub](https://hub.docker.com/r/motoserver/moto).
- **MiniStack**: `sha256:ddb20a5ab…`, about **25.1 MB**, updated **17 minutes ago**. Source: [Docker Hub](https://hub.docker.com/r/nahuelnucera/ministack).
- **Floci**: `sha256:b283336ea…`, about **69 MB**, updated **3 days ago**. Source: [Docker Hub](https://hub.docker.com/r/hectorvent/floci).

That absence matters operationally: if your CI admission policy requires publisher-exposed scan evidence, **MiniStack, Floci, and Moto currently fail on transparency**, not necessarily on actual CVE count.

The **cascade risk from Moto into LocalStack is real**. LocalStack’s public `pyproject.toml` explicitly depends on **`moto-ext[all]>=5.1.22`**. Moto’s published package metadata exposes a very broad extra set including `server` and `all`, meaning LocalStack is not merely “similar to Moto”; it imports a Moto-derived dependency layer into its runtime. Sources: [LocalStack pyproject](https://raw.githubusercontent.com/localstack/localstack/master/pyproject.toml), [Moto PyPI metadata](https://pypi.org/project/moto/).  
Inference from those sources: any unpatched vulnerability in Moto’s web/server dependency path is a **candidate inherited exposure for LocalStack** unless LocalStack explicitly constrains, patches, or makes the vulnerable path unreachable.

The clearest current example is **Flask-CORS GHSA-7rxf-gvfg-47g4 / CVE-2024-6839**, published in **March 2025**, affecting **Flask-CORS 5.0.1** with a **Medium 4.3 CVSS v3** rating. I could confirm the advisory exists, but I could **not** confirm from public image SBOMs whether Moto’s published `motoserver/moto:5.1.22` or LocalStack’s current standard image resolves exactly that vulnerable version. So this should be treated as a **demonstrated dependency-tree risk, not a confirmed present-image finding**. Source: [OSV advisory](https://osv.dev/vulnerability/GHSA-7rxf-gvfg-47g4).

Patch-response hygiene is uneven:
- **LocalStack** has frequent releases, but the public CVE record around CVE-2023-48054 remains ambiguous on remediation, and the archived OSS repo has no GitHub advisory record. That is weak disclosure hygiene for enterprise consumers.
- **Moto** ships regularly and uses Trusted Publishing on PyPI, but it lacks a public GitHub advisory history and formal security policy page. Better than nothing because Tidelift exists, but still weak by enterprise standards.
- **MiniStack** is the most explicit about dangerous-by-design behavior, which is good, but its project is very new, so there is almost no historical vulnerability-response record to judge.
- **Floci** has the weakest public security-process documentation of the four: no `SECURITY.md`, no published advisories, and no current public scan evidence that I could find.

### Evidence

Concrete datapoints:
- **LocalStack project CVE**: **CVE-2023-48054**, published **2023-11-16**, **CVSS 7.4 High**. Sources: [NVD](https://nvd.nist.gov/vuln/detail/CVE-2023-48054), [OSV](https://osv.dev/vulnerability/CVE-2023-48054).
- **LocalStack DHI Alpine 4.14.x**: **0 critical / 0 high / 5 medium / 1 low**, **Health A**, **105.93 MB**, pushed **2 days ago**. Source: [DHI catalog](https://hub.docker.com/hardened-images/catalog/dhi/localstack/images/localstack%2Falpine-3.22%2F4/sha256-8910913f1dc27cfa77bc73c26858ab06783cc9cbb208ff699dc2dd6a68863c81?order=asc&orderBy=license).
- **LocalStack DHI Debian 13 4.14.x**: **0 critical / 2 high / 3 medium / 1 low**, **Health A**, **114.18 MB**, pushed **4 days ago**. Source: [DHI catalog](https://hub.docker.com/hardened-images/catalog/dhi/localstack/images/localstack%2Fdebian-13%2F4/sha256-eec34dfc6a710e77e607a269c21e4703d8e542d9445d4df8aaf292dedd43b156?order=desc&orderBy=version).
- **LocalStack standard image**: **468.8 MB**, digest `sha256:94c3730fc…`, updated **3 days ago**. Source: [Docker Hub](https://hub.docker.com/r/localstack/localstack/).
- **Moto image**: **96.6 MB**, digest `sha256:1e3802c95…`, updated **4 days ago**. Source: [Docker Hub](https://hub.docker.com/r/motoserver/moto).
- **MiniStack image**: **25.1 MB**, digest `sha256:ddb20a5ab…`, updated **17 minutes ago**. Source: [Docker Hub](https://hub.docker.com/r/nahuelnucera/ministack).
- **Floci image**: **69 MB**, digest `sha256:b283336ea…`, updated **3 days ago**. Source: [Docker Hub](https://hub.docker.com/r/hectorvent/floci).
- **LocalStack dependency inheritance**: LocalStack requires **`moto-ext[all]>=5.1.22`**. Source: [LocalStack pyproject](https://raw.githubusercontent.com/localstack/localstack/master/pyproject.toml).
- **Moto release cadence**: **5.1.17** on **2025-11-17**, **5.1.18** on **2025-11-30**, **5.1.21** on **2026-02-08**, **5.1.22** on **2026-03-08**. Source: [Moto PyPI](https://pypi.org/project/moto/).
- **Flask-CORS advisory relevant to Moto-style server stacks**: **GHSA-7rxf-gvfg-47g4 / CVE-2024-6839**, **Medium 4.3**, published **2025-03-20**, affects **Flask-CORS 5.0.1**. Source: [OSV](https://osv.dev/vulnerability/GHSA-7rxf-gvfg-47g4).

### Trade-offs

**LocalStack** has the strongest publicly visible evidence that someone is actively watching image CVEs, but that evidence is mostly in the **DHI distribution**, not the default image most teams would actually use. That is better than nothing, but it means the best security transparency is behind a separate product channel. The downside is that its direct CVE history is worse than the others, and the public remediation metadata for its known CVE is messy.

**Moto** looks moderate-risk rather than obviously bad. I found no direct project CVE, it publishes frequently, and it has at least a coordinated disclosure contact. The problem is its attack surface is dependency-heavy, it lacks a formal public advisory track, and because it is a shared dependency of LocalStack, it can amplify ecosystem risk.

**MiniStack** is the most ambiguous. Its lack of CVE history is probably more a function of youth than of mature security posture. The explicit `SECURITY.md` is a point in its favor, but reporting via public GitHub issues is not enterprise-grade disclosure handling. For a commercial CI platform, that means lower confidence rather than confirmed weakness.

**Floci** is the weakest on evidence, not necessarily on actual code quality. No public CVEs found, but also no security policy, no published advisory history, and no public scan artifact I could verify. For a security-first buyer, “no visible problems” is not enough; absence of evidence is a procurement risk.

**Comparative risk call for this dimension only**:
- Best evidenced: **LocalStack DHI** only.
- Best standard-image balance on public record: **Moto**, narrowly.
- Highest inherited dependency risk: **LocalStack standard image**, because it carries its own CVE history and imports Moto-derived surface.
- Highest uncertainty risk: **Floci** and **MiniStack**, with **Floci** worse on disclosure/process maturity and **MiniStack** worse on short operating history.

### New Questions

- How much of each image actually runs as the network-facing control plane during Terraform `plan/apply`, versus being dormant optional service code? This would separate theoretical dependency risk from reachable attack surface.
- Which of these projects publish immutable SBOMs or attestations that let a CI platform prove “not affected” when scanner databases lag or over-report?
- For LocalStack specifically, does the current authenticated image still preserve the same dependency composition as the archived OSS `pyproject.toml`, or has the private build diverged enough that Moto-cascade risk needs to be re-measured separately?

I found strong public evidence for LocalStack’s direct CVE history and DHI scan posture, and enough public metadata to assess disclosure maturity for all four. I did **not** find equivalent public image-scan dashboards for MiniStack, Floci, or Moto, so the comparison on image-level CVE counts is asymmetrical and should be treated as “evidence available” rather than “evidence of absence.”

---

## Peer Review (claude)

### Issue 1: `moto-ext` and `moto` Conflated Throughout
- **Type**: Factual error / missing nuance
- **Location**: "LocalStack's public `pyproject.toml` explicitly depends on `moto-ext[all]>=5.1.22`... any unpatched vulnerability in Moto's web/server dependency path is a candidate inherited exposure for LocalStack"
- **Problem**: `moto-ext` is LocalStack's own maintained fork of Moto, published separately on PyPI under a different package name. It does not simply re-export `moto`; it carries LocalStack-specific patches and version pinning. The findings treat a vulnerability in `moto` as automatically cascading into LocalStack via `moto-ext`, but that inference requires verifying whether `moto-ext` shares the same vulnerable code path. The package lineage is asserted, not demonstrated.
- **Impact**: The cascade-risk claim — the most operationally significant inference in the findings — rests on an equivalence that is not established. A reader acting on this could overstate the inherited risk or misdirect remediation effort.

---

### Issue 2: Flask-CORS Dependency on Moto Is Unverified
- **Type**: Unsupported claim
- **Location**: "The clearest current example is Flask-CORS GHSA-7rxf-gvfg-47g4 / CVE-2024-6839... relevant to Moto-style server stacks"
- **Problem**: The findings never establish that Moto (or `moto-ext`) actually declares Flask-CORS as a dependency. Moto uses Flask for its server mode, but Flask-CORS is an optional add-on; its presence in the dependency tree requires verification (e.g., checking `moto`'s `setup.cfg` or `pyproject.toml` extras). The phrase "Moto-style server stacks" is vague and sidesteps the dependency-proof requirement. The findings themselves correctly caveat this as "not a confirmed present-image finding," but still use it to illustrate "demonstrated dependency-tree risk" — which it cannot demonstrate without the dependency link.
- **Impact**: Presenting an unconfirmed dependency chain as a "clearest current example" of cascade risk overstates certainty. A security buyer might flag this as a confirmed exposure when it is not.

---

### Issue 3: Inconsistency Between Findings and Evidence Sections on DHI Alpine Scan Results
- **Type**: Contradiction
- **Location**: Findings: "another amd64 manifest showed 0 critical, 1 high, 5 medium, 1 low." Evidence: "LocalStack DHI Alpine 4.14.x: 0 critical / 0 high / 5 medium / 1 low"
- **Problem**: The findings note two different amd64 manifests with differing high-severity counts (0 vs. 1), but the evidence section only cites the 0-high manifest and provides only one source link. The second manifest — with 1 high — has no corresponding source URL in the evidence block.
- **Impact**: A reader verifying the evidence section will not be able to confirm the 1-high figure. The discrepancy also raises a methodological question: which manifest is authoritative for the comparison, and why are two amd64 manifests diverging?

---

### Issue 4: "Archived OSS Repo" Used as Current Evidence Without Explanation
- **Type**: Missing nuance / unsupported claim
- **Location**: "LocalStack's public `pyproject.toml` explicitly depends on `moto-ext[all]>=5.1.22`" sourced from the archived repo; also "LocalStack...archived OSS repo shows no SECURITY.md"
- **Problem**: The findings use evidence from an archived repository in two different ways — as proof of current dependency composition AND as a current disclosure-hygiene signal — without ever explaining what "archived" means in context. If LocalStack's OSS repo is archived, active development has moved to a private or commercial repository. That means: (a) the `pyproject.toml` dependency spec may be stale, (b) the current commercial build may have diverged significantly, and (c) the absence of `SECURITY.md` in the archived repo may simply reflect that the security channel now lives in the commercial org, not the archived one. The findings raise this as a "new question" at the end but should have flagged it as a methodological limitation upfront.
- **Impact**: Dependency cascade risk and disclosure-hygiene conclusions for LocalStack may both be based on evidence that does not reflect the current commercial product. This is the most load-bearing unresolved ambiguity in the entire analysis.

---

### Issue 5: MiniStack Is a Personal GitHub Account Repo — Not Flagged
- **Type**: Gap / missing nuance
- **Location**: "MiniStack has a public `SECURITY.md`..." sourced from `github.com/Nahuel990/ministack`
- **Problem**: MiniStack is hosted under a personal GitHub account (`Nahuel990`), not an organization. This is a materially different longevity and governance signal than an org-owned project. Personal repos can be deleted, transferred, or abandoned with no community recourse. The findings assess MiniStack's disclosure maturity but omit this structural risk entirely.
- **Impact**: The trade-off section describes MiniStack as "most ambiguous" due to youth, but the actual highest risk for MiniStack in an enterprise CI context may be repository continuity, not CVE history. Omitting this skews the comparative assessment.

---

### Issue 6: Floci Publisher Identity Is Inconsistent and Unexplored
- **Type**: Gap / missing nuance
- **Location**: GitHub source `github.com/floci-io/floci` vs. Docker Hub source `hub.docker.com/r/hectorvent/floci`
- **Problem**: The GitHub organization is `floci-io` but the Docker Hub publisher is `hectorvent` — a personal account namespace. The findings cite both without noting this discrepancy or establishing whether they represent the same publisher and build pipeline. A supply-chain–conscious buyer would treat an image published from a personal Docker Hub namespace as higher risk than one from a verified organization publisher, regardless of CVE count.
- **Impact**: The already-weakest disclosure-process rating for Floci understates its supply-chain opacity by not flagging the namespace mismatch as a provenance concern.

---

### Issue 7: Moto Release Sequence Skips Versions 5.1.19 and 5.1.20 Without Explanation
- **Type**: Gap
- **Location**: Evidence: "5.1.17 on 2025-11-17, 5.1.18 on 2025-11-30, 5.1.21 on 2026-02-08, 5.1.22 on 2026-03-08"
- **Problem**: Versions 5.1.19 and 5.1.20 are absent from the evidence. No explanation is given — these could be yanked releases, patch releases with security fixes, or simply omitted from a selective listing. If they were yanked, that would be a relevant data point for patch-response hygiene. If they were skipped intentionally, the omission should be stated.
- **Impact**: Minor, but a reader inferring release cadence from the evidence table will see an irregular gap that could suggest irregular maintenance without that being the actual story.

---

### Issue 8: "17 minutes ago" Timestamp for MiniStack Is Non-Reproducible
- **Type**: Factual error (methodological)
- **Location**: Evidence: "MiniStack image: 25.1 MB, digest sha256:ddb20a5ab…, updated 17 minutes ago"
- **Problem**: A relative timestamp captured at query time is not reproducible evidence. Unlike the "3 days ago" and "4 days ago" figures (which are also relative but less precise), "17 minutes ago" signals an image that was actively being updated mid-research session. This either means the image was just pushed (and the digest may already have changed), or the figure was captured in the middle of a CI push, making it unreliable as a fixed data point.
- **Impact**: The digest `sha256:ddb20a5ab…` may not correspond to the "17 minutes ago" image the researcher actually observed. If the image was being pushed, it may have changed between the digest capture and the timestamp capture.

---

### Issue 9: Tidelift Characterized as a "Coordinated Disclosure" Channel — Inaccurate
- **Type**: Factual error / missing nuance
- **Location**: "its README does at least direct reporters to Tidelift for coordinated disclosure"
- **Problem**: Tidelift is primarily a commercial subscription service through which open-source maintainers receive funding in exchange for maintenance and security commitments from subscribers. It is not a general-purpose coordinated vulnerability disclosure (CVD) platform comparable to GitHub's private advisory system or a dedicated security@ email workflow. Directing reporters to Tidelift means telling them to go through Tidelift's subscriber-facing channel, which is only accessible to paying Tidelift customers. Non-subscribers — including most independent security researchers — have no path through Tidelift.
- **Impact**: The finding uses Tidelift's existence to give Moto a slightly better rating than "no disclosure channel," but this advantage only applies to Tidelift subscribers. For a team not on Tidelift, the practical disclosure path is effectively the same as Floci's: no clear private channel.

---

### Issue 10: CVE-2023-48054 Fixed-Version Ambiguity Overstated as a Current Problem
- **Type**: Missing nuance
- **Location**: "public advisory metadata still does not clearly name a fixed release, which is a security-hygiene concern in itself"
- **Problem**: NVD's CPE/version metadata is notoriously slow to update and often omits fixed-version ranges even for well-remediated CVEs. The absence of a fixed-version field in NVD metadata does not necessarily mean the fix is undocumented — LocalStack's own changelog or GitHub release notes may name the fixed version clearly. The findings cite NVD and OSV as the sources for this ambiguity but do not state whether LocalStack's own changelog was consulted. Attributing this gap to "LocalStack's disclosure hygiene" when it may be an NVD data-lag issue conflates NVD quality with maintainer behavior.
- **Impact**: The "weak disclosure hygiene" conclusion for LocalStack on CVE-2023-48054 may be partly unfair to LocalStack if the fix is documented in their release notes and the gap is an NVD publication artifact.

---

### Issue 11: CVSS 7.4 Attack Vector Context Missing for a Dev-Tool Evaluation
- **Type**: Missing nuance
- **Location**: "High 7.4 CVSS v3.1" for CVE-2023-48054 (missing SSL validation)
- **Problem**: For a tool used exclusively in local dev or CI environments, the attack vector matters more than the raw score. A CVSS 7.4 missing-TLS-validation vulnerability has a very different practical risk profile in an air-gapped CI runner vs. a shared cloud dev environment. The findings cite the score without noting the attack vector (likely "Network" or "Adjacent"), which determines whether the vulnerability is exploitable in the typical use context. For readers making a risk-gating decision about LocalStack in isolated CI pipelines, this context is essential.
- **Impact**: The score is accurate but decontextualized. A reader might reject LocalStack for a use case where the CVE is not reachable.

---

### Issue 12: No Coverage of Container Signing / Attestation as a Transparency Dimension
- **Type**: Gap
- **Location**: "New Questions" section asks about SBOMs and attestations, but no assessment is made in the findings
- **Problem**: Image signing (via Docker Content Trust, Sigstore/cosign, or GitHub Actions artifact attestation) is a distinct and assessable transparency dimension. The findings note the absence of public SBOM artifacts but do not assess whether any of the four projects sign their images or publish provenance attestations (e.g., SLSA level). This is verifiable from Docker Hub metadata and project CI configuration without access to private systems.
- **Impact**: A CI admission policy built around attestation gating would need this data. Moving it to "new questions" instead of addressing it leaves a procurement-relevant gap.

---

### Issue 13: "Cascade Risk Is Real" Conclusion Stated Before Evidence Is Complete
- **Type**: Unsupported claim / logical sequencing
- **Location**: "The cascade risk from Moto into LocalStack is real." (section header-level assertion)
- **Problem**: The sentence is stated as fact before the supporting chain is walked through, and the subsequent analysis correctly walks back to "demonstrated dependency-tree risk, not a confirmed present-image finding." The framing is inconsistent: the header asserts certainty, the body appropriately hedges. Given Issue 1 (moto-ext ≠ moto) and Issue 2 (Flask-CORS dependency unverified), the strongest defensible claim is "plausible cascade risk," not "real."
- **Impact**: The boldest claim in the findings is the one with the least complete evidence chain. Downstream readers who skim headers will retain the stronger framing.

---

## Summary

**Issues found**: 13

**Overall reliability assessment**: **Medium**

The findings demonstrate genuine research effort and appropriate uncertainty in several places (notably the "not a confirmed present-image finding" caveat on Flask-CORS). The disclosure-maturity comparisons are well-structured and the DHI scan evidence is handled carefully. However, the analysis has two structural weaknesses that undermine its most actionable conclusions:

1. The `moto-ext`/`moto` conflation and the unverified Flask-CORS dependency chain together make the "cascade risk is real" claim the least-supported claim in the document — yet it's framed as the strongest.
2. The "archived OSS repo" problem is raised only as a new question when it should appear as a methodological caveat at the top of the LocalStack analysis. If the commercial build has diverged, the dependency composition and disclosure-hygiene conclusions for LocalStack may not apply to what enterprise buyers actually deploy.

**What would most improve the findings**:
- Verify the `moto-ext` PyPI package directly (not inferred from `moto`) to confirm whether Flask-CORS or other flagged dependencies appear in its resolved dependency tree.
- Clarify which LocalStack artifact the analysis applies to (archived OSS community build vs. current commercial build) and whether the `pyproject.toml` evidence reflects the active commercial product.
- Check LocalStack's own release notes for CVE-2023-48054 remediation before concluding NVD's gap is a maintainer hygiene failure.
- Establish publisher provenance for Floci (GitHub org vs. Docker Hub personal namespace) and longevity risk for MiniStack (personal repo) as explicit risk factors in the comparative table.
