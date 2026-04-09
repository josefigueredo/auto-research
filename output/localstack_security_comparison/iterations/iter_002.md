# Iteration 002 — Supply chain security: Docker image provenance, base images, signed images, SBOM availability, dependency audit for each tool

**Status:** keep  
**Scores:** coverage=61.7, quality=75.0, total=69.7  
**Timestamp:** 2026-04-08T20:14:00.116571+00:00  

---

### Findings

1. **I found no public evidence that the primary published images for MiniStack, Floci, Moto, or LocalStack are signed in a way a buyer can independently verify today.**
   - For **MiniStack**, the public Docker Hub repo and GitHub repo expose tags, digests, Dockerfile, and workflow, but I found no published Cosign key, no Notary notation, no Rekor/Sigstore verification instructions, and no SBOM/provenance attestation links. Its publish workflow uses `docker/build-push-action@v5` with `push: true`, but no `sbom`, `provenance`, or `attests` settings are visible.
   - For **Floci**, same pattern: public Docker Hub image plus a public `release.yml` workflow that uses `docker/build-push-action@v6` to push multi-arch images, but no visible Cosign key, no signing step, and no SBOM/provenance attestation step.
   - For **Moto**, the official image exists on Docker Hub as `motoserver/moto` and on GHCR as `ghcr.io/getmoto/motoserver`, but I found no public signing instructions, public key, or attestation references on those public surfaces.
   - For **LocalStack**, the ordinary `localstack/localstack` Docker Hub page does not expose public signing/SBOM verification instructions. However, there is a separate **Docker Hardened Image** variant for LocalStack on `dhi.io/localstack` that Docker says is signed and includes signed attestations and SBOMs. That is a different distribution channel than the ordinary `localstack/localstack` image and should not be conflated with it.  
   Sources: LocalStack Docker Hub, Docker Hardened Images docs/catalog, MiniStack Docker Hub + workflow, Floci Docker Hub + workflow, Moto Docker Hub + GHCR package.

2. **LocalStack has the strongest public evidence of build hardening in the last public Dockerfile, but the evidence applies to the archived OSS repo, not necessarily the current authenticated product image.**
   - The archived public Dockerfile pins its base image to a content digest: `python:3.13.12-slim-trixie@sha256:...`.
   - It also manually downloads Node.js and verifies it with upstream GPG release keys and SHA256 checks before unpacking.
   - That is materially stronger than the other three on base-image provenance and supply-chain hygiene.
   - But the repo is archived, and Docker Hub now points users to the authenticated unified image path. For a senior architect, the important nuance is: **the best publicly inspectable supply-chain evidence is for the last public image recipe, not necessarily for the current production product path.**  
   Sources: archived `localstack/localstack` repo Dockerfile, GitHub archive notice, Docker Hub transition notice.

3. **MiniStack has the weakest provenance posture of the four from a container-build perspective, despite its simplicity.**
   - Current Dockerfile uses `FROM python:3.12-alpine` without digest pinning.
   - It installs Python packages directly with `pip install` inside the image and adds Alpine `nodejs` with `apk`.
   - The image publish workflow does multi-arch pushes but does not show signing, SBOM generation, provenance attestations, or policy checks.
   - The Docker Hub page reports a very small image footprint, but small size is not the same as verifiable provenance.  
   Sources: MiniStack Dockerfile, MiniStack `docker-publish.yml`, Docker Hub repo/tags.

4. **Floci’s base-image choices are from reputable sources, but its image lineage is still largely tag-based and unsigned on public evidence.**
   - JVM image: multi-stage build from `eclipse-temurin:25-jdk` to `eclipse-temurin:25-jre-alpine`.
   - Native image: builder `quay.io/quarkus/ubi-quarkus-mandrel-builder-image:jdk-24`; runtime `quay.io/quarkus/quarkus-micro-image:2.0`.
   - Those are materially better sources than an ad hoc personal base image, and Quarkus documents the micro image as UBI-based.
   - But the tags are not digest-pinned, and the release workflow shows Docker Hub publishing without any visible signing or SBOM attestation.  
   Sources: Floci Dockerfiles, Floci release workflow, Eclipse Temurin official image docs, Quarkus runtime base image docs.

5. **Moto inherits a large Python dependency surface in server mode, which is a supply-chain concern even if the project itself is well known and Apache-2.0 licensed.**
   - The Dockerfile uses `python:3.13-alpine` and `pip install --editable ".[server]"`.
   - `setup.cfg` shows `server` extras bring in substantial transitive surface including `aws-sam-translator`, `docker`, `graphql-core`, `PyYAML`, `cfn-lint`, `openapi-spec-validator`, `pydantic`, `py-partiql-parser`, `aws-xray-sdk`, `flask`, and `flask-cors`.
   - That makes Moto easy to consume, but harder to audit without an SBOM.  
   Sources: Moto Dockerfile, Moto `setup.cfg`, Docker Hub official image page.

6. **SBOM publication is the major gap across the primary images.**
   - I found no public SBOM artifact or registry-attached SBOM instructions for **MiniStack**, **Floci**, **Moto official image**, or **standard LocalStack Docker Hub image**.
   - The one clear exception is **Docker Hardened Images**, including the LocalStack hardened variant, where Docker documents signed SBOMs, signed attestations, and public-key verification workflows.
   - For the four projects’ normal images, a buyer should currently assume **“bring your own SBOM generation”**.  
   Sources: Docker Hardened Images SBOM/signing docs, project Docker Hub/repo surfaces.

7. **Base-image trust differs meaningfully across the four.**
   - **Best public hygiene:** archived LocalStack OSS image, because of digest pinning plus explicit Node.js verification.
   - **Good but incomplete:** Floci, because it uses official Temurin and Quarkus/UBI lineage, but no digest pinning or public attestations.
   - **Acceptable but lean/minimal rather than auditable:** MiniStack and Moto, both on Docker Official `python:*‑alpine`, which is maintained, but Alpine/musl variants can complicate native dependencies and CVE triage.
   - Counter-intuitive point: the smallest image here is not the safest from a supply-chain-verifiability standpoint.  
   Sources: all four Dockerfiles, Python official image docs, Eclipse Temurin official image docs, Quarkus base image docs.

8. **Vulnerability history is public for LocalStack; for the others, the visible risk is mostly dependency and base-layer drift rather than a strong public record of project-level CVEs.**
   - I found a public OSV/GitHub advisory entry for **LocalStack** (`CVE-2021-32090` / `GHSA-hpr6-f4vq-mxch`) related to command injection in the dashboard component of version `0.12.6`.
   - I did not find comparable clearly indexed project-level CVE/GHSA records during this pass for **MiniStack**, **Floci**, or **Moto**.
   - That should not be over-read: for MiniStack and Floci especially, the more immediate concern is not a known advisory corpus but the lack of published SBOM/provenance and the reliance on mutable tag-based upstreams.  
   Sources: OSV advisory for LocalStack, public repo and registry inspection for the other three.

9. **For a security-first CI/CD pipeline, none of the four primary images currently clear a strict “must be signed and SBOM-attested by publisher” bar.**
   - If that bar is firm, the standard published images for all four are presently deficient on public evidence.
   - The closest workaround is **LocalStack via Docker Hardened Images**, but that is not the same artifact stream as `localstack/localstack`, and it adds separate vendor/distribution considerations.
   - If the organization can generate and enforce its own provenance internally, then Floci and MiniStack remain viable candidates to rebuild and re-sign in-house; Moto is auditable but dependency-heavy; LocalStack’s current product-path transparency is weaker because the public repo is archived while the live product continues elsewhere.  
   Sources: combined review of registries, Dockerfiles, workflows, and Docker Hardened Images docs.

### Evidence

- **MiniStack**
  - Docker Hub latest compressed size: about **26.0 MB** per arch for `1.1`/`latest`.
  - Docker Hub overview claims about **150 MB** image and about **2s** startup.
  - Base image: `python:3.12-alpine`.
  - Direct image-installed deps visible in Dockerfile: `uvicorn==0.30.6`, `cbor2>=5.4.0`, `defusedxml>=0.7`, `docker>=7.0.0`, `pyyaml>=6.0`, `cryptography>=41.0`, plus Alpine `nodejs`.
  - Publish workflow: `docker/build-push-action@v5`, multi-arch `linux/amd64,linux/arm64`, no visible `sbom:` or `provenance:` settings.
  Sources: Docker Hub repo/tags, GitHub Dockerfile, GitHub workflow.

- **Floci**
  - Docker Hub latest image size: **69 MB**.
  - Base images:
    - JVM builder: `eclipse-temurin:25-jdk`
    - JVM runtime: `eclipse-temurin:25-jre-alpine`
    - Native builder: `quay.io/quarkus/ubi-quarkus-mandrel-builder-image:jdk-24`
    - Native runtime: `quay.io/quarkus/quarkus-micro-image:2.0`
  - Release workflow builds JVM and native images and pushes to Docker Hub with `docker/build-push-action@v6`; no visible signing or SBOM attestation flags.
  - Key Maven deps visible in `pom.xml`: Quarkus BOM `3.32.3`, `docker-java-core 3.4.0`, `docker-java-transport-httpclient5 3.4.0`, Bouncy Castle `1.83`, `cron-utils 9.2.1`, `velocity-engine-core 2.4.1`, `json-schema-validator 1.5.8`, `swagger-parser 2.1.38`.
  Sources: Docker Hub, Floci Dockerfiles, Floci `release.yml`, Floci `pom.xml`, Temurin official image docs, Quarkus runtime base image docs.

- **Moto**
  - Docker Hub latest image size: **96.6 MB** for `5.1.22`.
  - GHCR package `ghcr.io/getmoto/motoserver` latest visible digest in package page: `sha256:0361ac8f...` for `5.1.17` at the time of crawl.
  - Base image: `python:3.13-alpine`.
  - Dockerfile installs `".[server]"` and `curl`.
  - `server` extras include `aws-sam-translator<=1.103.0`, `docker>=3.0.0`, `PyYAML>=5.1`, `cfn-lint<=1.41.0`, `pydantic<=2.12.4`, `flask`, `flask-cors`, and others.
  Sources: Moto Docker Hub, GHCR package page, Moto Dockerfile, Moto `setup.cfg`.

- **LocalStack**
  - Standard Docker Hub latest digest shown: `sha256:94c3730fc…`; compressed size about **468.8 MB**.
  - Archived public Dockerfile base: `python:3.13.12-slim-trixie@sha256:8bc60ca...`.
  - Public Dockerfile installs and verifies Node.js with upstream GPG keys and SHA256 checks.
  - Runtime deps visible in `pyproject.toml` include pinned AWS SDK pieces `boto3==1.42.59`, `botocore==1.42.59`, `awscli==1.44.49`, plus `moto-ext[all]>=5.1.22`, `jpype1>=1.6.0`, `opensearch-py>=2.4.1`, `pymongo>=4.2.0`, and many others.
  - Docker Hardened Image catalog entry for LocalStack reports:
    - distro: **debian 13**
    - packages: **261**
    - vulnerabilities shown: **0 critical / 0 high / 3 medium / 1 low / 0 unspecified**
    - Scout health score: **A**
  Sources: LocalStack Docker Hub, archived repo Dockerfile, `pyproject.toml`, Docker Hardened Images LocalStack catalog.

- **Published signing/SBOM evidence**
  - Docker documents that Docker Hardened Images are **Cosign-signed**, expose public verification keys, and include **signed SBOM/provenance attestations**.
  - I found no analogous public verification instructions for the standard published images of MiniStack, Floci, Moto, or LocalStack.
  Sources: Docker Hardened Images signing/SBOM/provenance docs; project Docker Hub and repo surfaces.

- **Known vulnerability history**
  - LocalStack: OSV lists **`CVE-2021-32090` / `GHSA-hpr6-f4vq-mxch`** affecting `localstack` `0.12.6`.
  Sources: OSV entry; linked GitHub advisory references in OSV.

### Trade-offs

- **LocalStack**
  - Strongest publicly visible build-hygiene signals in the archived OSS Dockerfile.
  - Weakest current transparency for the live product image path, because the publicly inspectable repo is archived while the operational image distribution continues elsewhere.
  - Best option only if you accept either:
    - the weaker attestation story on the standard image, or
    - the separate Docker Hardened Image path with Docker-managed attestations and its own commercial/distribution implications.

- **MiniStack**
  - Best if you want a small, simple image and are willing to rebuild, SBOM, sign, and mirror it yourself.
  - Worst if you require publisher-signed provenance out of the box.
  - The security story is currently “minimal and understandable,” not “cryptographically attestable.”

- **Floci**
  - Better base-image pedigree than MiniStack because it rides on Temurin and Quarkus/UBI lineage.
  - Still not strong enough for a strict provenance policy because public signing/SBOM evidence is absent.
  - Of the alternatives, it is the easiest to defend if your platform team is going to run an internal re-build and signing pipeline.

- **Moto**
  - Trustworthy brand and broad adoption help, but the server image pulls in a wide dependency set and exposes no public SBOM/signing story that I found.
  - For pure supply-chain review, Moto is not a clean “lightweight” choice despite its simple Dockerfile, because `.[server]` expands substantially.
  - For Terraform-focused CI, this dependency breadth compounds the separate fit-risk of Moto’s server-mode architecture.

### New Questions

1. **Can each project’s image be rebuilt reproducibly from source, with stable digests across CI runs, or do mutable upstream tags and unpinned package installs make reproducibility unrealistic?**

2. **If the company mirrors and re-signs these images internally, which tool has the lowest operational cost to maintain a secure fork: LocalStack OSS snapshot, MiniStack, Floci, or Moto server?**

3. **Does any project publish a verifiable dependency update policy or security-fix SLA for base-image refreshes, especially when upstream Python/Alpine/Temurin/Quarkus layers ship CVE fixes?**

**Bottom line:** on this dimension alone, the standard published images for all four fail a strict security-first provenance bar. LocalStack has the best public hardening signals in its archived Dockerfile and an attested Docker Hardened Image path, but not a clearly attested standard image. Floci has the cleanest upstream base lineage among the alternatives. MiniStack is simplest but least attested. Moto is familiar but dependency-heavy and still lacks a public SBOM/signing story.

---

## Peer Review (claude)

## Critical Peer Review

---

### Issue 1: Provenance-by-default in docker/build-push-action (Major Factual Error)

- **Type**: Factual error
- **Location**: Finding 1 — "its publish workflow uses `docker/build-push-action@v5` with `push: true`, but no `sbom`, `provenance`, or `attests` settings are visible" and the same logic applied to Floci's use of v6.
- **Problem**: `docker/build-push-action` enabled SLSA provenance attestations by default starting with v4. Since MiniStack uses v5 and Floci uses v6, both almost certainly push SLSA Level 2 provenance attestations to their registries automatically, even without explicit flags. The absence of explicit flags is not evidence of absence of attestations. A reviewer can inspect these with `docker buildx imagetools inspect <image>`. The finding conflates "no Cosign signing" (a specific key-based signing mechanism) with "no attestations" (a broader category that includes Docker's native SLSA provenance support), which are meaningfully different mechanisms.
- **Impact**: This error propagates directly into Finding 6 ("SBOM publication is the major gap"), Finding 9 ("none of the four primary images currently clear a strict signed and SBOM-attested bar"), and the trade-off summaries. If MiniStack and Floci do carry publisher-generated SLSA provenance, the central conclusion of the research is partially wrong, or at minimum significantly overstated for those two projects.

---

### Issue 2: LocalStack's Runtime Dependency on Moto Is Never Mentioned (Major Gap)

- **Type**: Gap
- **Location**: Evidence section — `pyproject.toml` entry `moto-ext[all]>=5.1.22`; the entire LocalStack vs. Moto comparison.
- **Problem**: The evidence itself shows that LocalStack depends on `moto-ext[all]` at runtime. This means LocalStack's production image carries Moto's entire server dependency surface inside it. The research compares LocalStack and Moto as independent alternatives, but never surfaces the fact that one wraps the other. This has direct implications: LocalStack's supply-chain surface is a superset of Moto's, and any Moto dependency vulnerability would also affect LocalStack. The "Moto is dependency-heavy" criticism in Finding 5 and Trade-offs applies with equal or greater force to LocalStack's standard image.
- **Impact**: This omission materially distorts the comparison. A reader would conclude LocalStack and Moto are independent supply chains when they are not.

---

### Issue 3: Alpine Runtime Criticism Is Applied Inconsistently (Missing Nuance)

- **Type**: Missing nuance
- **Location**: Finding 7 — "MiniStack and Moto, both on Docker Official `python:*-alpine`... Alpine/musl variants can complicate native dependencies and CVE triage." Floci is rated "Good but incomplete" with no mention of Alpine.
- **Problem**: Floci's JVM runtime image is `eclipse-temurin:25-jre-alpine`, also an Alpine/musl variant. The same musl-compatibility and CVE-triage concern applies to Floci's JVM image. Floci escapes the criticism only because the native image uses `quarkus-micro-image:2.0` (UBI-based), but the JVM variant — which may be the one actually used in a given deployment — shares the same trait. The research presents Floci's base-image choice as categorically better without this caveat.
- **Impact**: The tiering in Finding 7 ("Good but incomplete" for Floci vs. "Acceptable but lean" for MiniStack/Moto) is partially unsupported for the JVM image variant.

---

### Issue 4: Docker Hardened Images Require a Paid Subscription (Gap)

- **Type**: Gap
- **Location**: Finding 1 last bullet, Finding 6, Finding 9 — all refer to "Docker Hardened Images" as the closest workaround or exception.
- **Problem**: Docker Hardened Images are a commercial Docker product that requires an active Docker subscription. The research mentions "separate vendor/distribution considerations" only once and briefly, but never explicitly states the cost implication. For an organization evaluating a "security-first CI/CD pipeline," discovering post-recommendation that the only attested path requires an ongoing paid vendor relationship is a material omission.
- **Impact**: The DHI path is presented as a practical fallback without the caveat that kills it for many procurement contexts.

---

### Issue 5: `pip install --editable` in a Production Container Is Not Flagged (Missing Nuance)

- **Type**: Missing nuance
- **Location**: Finding 5 / Evidence — "Dockerfile installs `.[server]` and `curl`." The Dockerfile uses `pip install --editable ".[server]"`.
- **Problem**: Editable installs (`-e` / `--editable`) leave source tree artifacts in the image (a `.egg-link` or `direct_url.json` pointing back to the source directory) and are semantically a development-mode install. Using this in a production container image is a code-quality and surface-area concern: the full source tree remains present, which increases image size unexpectedly and complicates layer analysis. The research notes dependency breadth but misses this installation-mode issue entirely.
- **Impact**: Minor, but relevant to the "harder to audit" point the research makes about Moto — the editable install compounds that difficulty.

---

### Issue 6: MiniStack Image Size Numbers Are Internally Inconsistent and Unexplained (Potential Factual Error / Missing Nuance)

- **Type**: Factual error / missing nuance
- **Location**: Evidence section — "Docker Hub latest compressed size: about **26.0 MB** per arch" and "Docker Hub overview claims about **150 MB** image."
- **Problem**: A 26 MB compressed layer set that decompresses to ~150 MB would imply a ~5.8x compression ratio, which is unusually high for a Python/Alpine image (typical ratios are 2–3x). The more likely explanation is that the 150 MB figure is outdated marketing copy on the Docker Hub overview page that doesn't match the current image. The research presents both numbers without comment or reconciliation. An architect reading this would not know which to trust.
- **Impact**: If the 150 MB figure is stale, the research is citing outdated vendor claims as evidence without flagging the discrepancy.

---

### Issue 7: The LocalStack CVE Entry Is Old and the Vulnerable Component May No Longer Exist (Missing Nuance)

- **Type**: Missing nuance
- **Location**: Finding 8 — "LocalStack: OSV lists `CVE-2021-32090` / `GHSA-hpr6-f4vq-mxch` affecting `localstack` `0.12.6`."
- **Problem**: This CVE is from 2021 and affects version 0.12.6. By April 2026, LocalStack is likely at version 4.x. More importantly, the vulnerability is in the "dashboard component," which LocalStack removed from the open-source edition in a major restructuring. Citing a 5-year-old CVE against a component that has been removed without noting either the age or the removal context is misleading. It implies an ongoing or representative risk profile when the actual signal is that LocalStack had one notable public CVE five years ago in a now-removed feature.
- **Impact**: Creates a spurious negative mark against LocalStack relative to the other three, which simply have no indexed CVEs — not because they are safer, but because they are smaller or less scrutinized projects.

---

### Issue 8: Floci Uses Non-LTS JDK Versions — Not Mentioned (Gap)

- **Type**: Gap
- **Location**: Finding 4 / Evidence — `eclipse-temurin:25-jdk`, `eclipse-temurin:25-jre-alpine`, `quarkus/ubi-quarkus-mandrel-builder-image:jdk-24`.
- **Problem**: Java 25 (September 2025) is a non-LTS release with a 6-month support window. JDK 24 (March 2025) is also non-LTS. The current LTS is JDK 21. Using non-LTS JDK versions in a security-critical production image means the upstream maintainer stops providing security patches within months. The research praises Floci's base-image pedigree without noting this critical support-lifecycle concern, which directly contradicts a "security-first" framing.
- **Impact**: If a security architect adopts Floci partly on the strength of its Temurin JDK lineage, they may not realize the JDK version they are consuming will be EOL before the end of a typical project delivery cycle.

---

### Issue 9: Floci JVM vs. Native Image Uses Different JDK Major Versions (Missing Nuance)

- **Type**: Missing nuance
- **Location**: Evidence — JVM builder uses `jdk-24` in the Mandrel native image path; JVM path uses `eclipse-temurin:25`.
- **Problem**: The JVM and native image variants target different JDK major versions (25 vs. 24). This isn't a supply-chain risk per se, but it is a consistency red flag and means runtime behavior may differ across image variants. A team deploying one variant and testing another could face silent ABI differences. The research does not flag this.
- **Impact**: Minor, but relevant to the completeness of the Floci evaluation.

---

### Issue 10: The Claim That Floci Is "Easiest to Defend" for Internal Rebuild Is Unsupported (Unsupported Claim)

- **Type**: Unsupported claim
- **Location**: Trade-offs — "Of the alternatives, it is the easiest to defend if your platform team is going to run an internal re-build and signing pipeline."
- **Problem**: No reasoning is given for why Floci would be easier to rebuild internally than MiniStack, which is demonstrably simpler (single-stage, Python, ~26 MB). MiniStack's simplicity could equally be argued as the easiest to fork, audit, and maintain a secure internal build of. The claim appears to rest on base-image pedigree, but pedigree and rebuild ease are different properties. The research asserts the conclusion without making the argument.
- **Impact**: A reader might prioritize Floci for internal rebuild without understanding they are accepting a Java build toolchain, a multi-stage multi-variant Dockerfile, and non-LTS JDK dependencies in exchange for unspecified ease.

---

### Issue 11: "New Question 1" Is Already Largely Answered Within the Findings (Contradiction / Structural)

- **Type**: Contradiction (minor)
- **Location**: New Questions — "Can each project's image be rebuilt reproducibly from source, with stable digests across CI runs, or do mutable upstream tags and unpinned package installs make reproducibility unrealistic?"
- **Problem**: The findings already establish that MiniStack uses unpinned `python:3.12-alpine`, Floci uses unpinned `eclipse-temurin:25-jdk`, and Moto uses unpinned `python:3.13-alpine`. The archived LocalStack Dockerfile is the only one that pins to a digest. The answer to this question is implied clearly within the findings: no, except for the archived LocalStack image. Presenting it as an open question implies the research has not drawn a conclusion it has already implicitly drawn.
- **Impact**: Reduces the research's apparent completeness and confidence.

---

### Issue 12: Provenance vs. Signing Terminology Is Used Inconsistently (Missing Nuance)

- **Type**: Missing nuance
- **Location**: Throughout — "no Cosign key," "no signing step," "no SBOM/provenance attestation step" are used interchangeably.
- **Problem**: These are three distinct mechanisms with different trust properties. Cosign signing with a published key allows any third party to verify authenticity against a known identity. SLSA provenance attestations (Docker-native, via build-push-action) allow verification of build inputs but are not signed by the project's own key — they are signed by the build platform. SBOMs describe composition but not authenticity. The research conflates these throughout, which leads to the provenance-by-default error in Issue 1 and makes it impossible for a reader to distinguish what level of assurance is actually missing for each project.
- **Impact**: Medium. A senior architect would notice this conflation and distrust the fine-grained conclusions.

---

## Summary

**Total issues found**: 12 (2 major, 7 medium, 3 minor)

**Overall reliability**: **Medium-Low**

The research demonstrates genuine investigative effort — it inspects actual Dockerfiles, workflows, and registries rather than relying on vendor claims, and the framing of the problem (provenance, SBOM, signing) is appropriate for the domain. However, the central conclusion rests on a material factual error (Issue 1: provenance-by-default in build-push-action v4+), and a critical supply-chain relationship is entirely absent (Issue 2: LocalStack depends on Moto). These two issues alone are enough to invalidate the primary ranking and the "all four fail" conclusion without further investigation.

**What would most improve the findings, in priority order:**

1. Verify whether docker/build-push-action v5/v6 attach SLSA provenance by default for MiniStack and Floci; if so, re-evaluate what exactly is missing (project-controlled Cosign key? independent SBOM? something else?).
2. Address the LocalStack → Moto dependency and what it means for the supply-chain comparison between those two products.
3. Add the Docker Hardened Images subscription-cost caveat explicitly.
4. Apply the Alpine/musl and JDK non-LTS criticisms consistently across all four products.
5. Sharpen the provenance/signing/SBOM terminology into distinct concepts with distinct evidence thresholds.
