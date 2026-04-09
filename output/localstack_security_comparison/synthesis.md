# Security-First Evaluation: LocalStack, MiniStack, Floci, and Moto for Commercial CI/CD with Terraform

**Report Date**: April 8, 2026  
**Audience**: Senior AWS Cloud Architect  
**Scope**: Production CI/CD pipeline use, Terraform plan/apply workflows, commercial licensing context

---

## Executive Summary

Of the four AWS local emulators evaluated, **Moto** is the strongest default recommendation for commercial CI/CD pipelines where legal simplicity, supply-chain auditability, and Terraform compatibility must all be satisfied simultaneously: it carries a clean Apache-2.0 license, has no mandatory control-plane egress, and is the most operationally familiar tool in the Terraform ecosystem, despite a heavier dependency footprint than its size might suggest. **LocalStack's current authenticated product path** is disqualified from a zero-friction commercial deployment by its non-commercial free-tier policy, mandatory outbound activation requirements, and unclear CI entitlement terms — though the last archived OSS release (Apache-2.0) remains available under pinned-version strategies that legal must validate. **MiniStack** and **Floci** are legally straightforward and network-clean but carry unacceptable governance and supply-chain opacity for a production-grade commercial pipeline: both are young projects, both lack project-controlled image signing or published SBOMs, and both are published under personal or insufficiently verified Docker Hub namespaces. The practical finding is that no standard image from any of these tools meets a strict "publisher-signed, SBOM-attested, scan-transparent" bar out of the box; organizations with formal supply-chain admission policies should plan to rebuild, generate SBOMs, sign, and mirror all candidates internally.

---

## Comparison Table

| Dimension | LocalStack (current auth path) | LocalStack (pinned OSS last release) | MiniStack | Floci | Moto |
|---|---|---|---|---|---|
| **Top-level license** | Commercial / authenticated | Apache-2.0 (archived) | MIT | MIT | Apache-2.0 |
| **Commercial CI/CD use** | Requires paid plan; Free = non-commercial | Legal review required; version-pinning strategy | Permitted | Permitted | Permitted |
| **Vendor independence** | Low — token activation, policy drift risk | Medium — frozen artifact | High | High | High |
| **GitHub account type** | Organization (archived) | — | **Personal** (`Nahuel990`) | Organization (`floci-io`) | Organization (`getmoto`) |
| **Docker Hub publisher** | `localstack` (org) | — | `nahuelnucera` (personal) | **`hectorvent` (personal)** | `motoserver` (org) |
| **Image size** | ~469 MB | — | ~25 MB | ~69 MB | ~97 MB |
| **Base image** | `python:3.13-slim-trixie` (digest-pinned in OSS) | — | `python:3.12-alpine` (no digest pin) | `eclipse-temurin:25-jre-alpine` → `quay.io` native | `python:3.13-alpine` |
| **Base image digest pinning** | Yes (OSS Dockerfile) | Yes (same) | No | Not confirmed | Not confirmed |
| **Builder-generated provenance** | Likely (OSS) | — | Likely (via `docker/build-push-action` v5) | Likely (via v6) | Unknown |
| **Project-controlled Cosign signing** | Not publicly confirmed (standard image) | — | No | No | No |
| **Published SBOM** | No (standard image); Yes (DHI only) | — | No | No | No |
| **DHI / hardened image available** | Yes (paid Docker product) | — | No | No | No |
| **Image CVE transparency** | DHI: 0C/0H/5M/1L (Alpine); 0C/2H/3M/1L (Debian) | — | Not published | Not published | Not published |
| **Known project CVEs** | CVE-2023-48054 (High 7.4) | — | None found | None found | None found |
| **SECURITY.md** | No | — | Yes (public issue channel) | No | No (Tidelift subscribers only) |
| **Published GitHub advisories** | None despite known CVE | — | None | None | None |
| **Mandatory outbound egress** | Yes (token activation, 24h reauth) | No (if offline pinned) | No (self-reported) | No (self-reported) | No |
| **Documented telemetry** | Yes (usage tracking, API metadata) | Limited | No (self-reported) | No (self-reported) | No |
| **Default inbound bind** | `0.0.0.0:4566` (Docker mode) | — | `0.0.0.0:4566` | `0.0.0.0:4566` | `0.0.0.0:5000` |
| **Terraform compatibility** | Excellent (most services, dedicated provider) | Good (same feature set, frozen) | Limited (subset of services) | Limited (subset; non-LTS Java) | Good (explicit Terraform support, more manual) |
| **Accidental real-credential protection** | Strong (explicit key rejection by default) | Same | Moderate (request path only) | Low confidence (less auditable) | Moderate (server mode only) |
| **Governance / longevity risk** | Low (commercial entity) | Medium (frozen version) | **High** (personal repo) | Medium-High (small org, personal Docker Hub) | Low (large community, Apache) |
| **`moto-ext` dependency** | Yes (`moto-ext[all]>=5.1.22`) | Same | No | No | N/A (is the source) |

---

## Dimension Analysis

### 1. Licensing and Commercial-Use Risk

**Finding**

The legally relevant distinction for LocalStack is not primarily "Apache vs. BUSL in the repo." The last public GitHub release and PyPI metadata for LocalStack still reflect **Apache-2.0**, but that OSS repository was archived on **March 23, 2026**. The operative commercial constraint is LocalStack's **February–March 2026** public communications, which state the free tier is **non-commercial**, and that CI/team/commercial use belongs on paid plans (**Base: $39/license/month**, **Ultimate: $89/license/month**, billed annually). The specific CI entitlement model has been inconsistent across public surfaces — older docs reference 300–1000 CI credits/month/workspace, while newer posts suggest unrestricted CI usage for paid plans under fair use. Because the binding instrument is the **ToS/EULA** and not blog posts, exact CI entitlements must be validated directly with LocalStack before any commercial deployment.

MiniStack (MIT), Floci (MIT), and Moto (Apache-2.0) all allow commercial and private internal use subject only to notice obligations. No public evidence of AGPL, BUSL, or equivalent source-disclosure requirements was found for any of the three.

**Trade-offs**

Permissive top-level licensing does not eliminate risk. Transitive container-layer dependencies may carry LGPL or GPL components. Internal mirroring and redistribution rights for prebuilt images vary by license. Governance risk is also real: permissive licensing is not a durability guarantee, and small or single-maintainer projects can stagnate or change terms.

**Confidence**: High for top-level license classification. Medium for downstream dependency and container-layer licensing, which requires a dependency scan per image to confirm.

---

### 2. Supply-Chain Security and Image Provenance

**Finding**

None of the four tools' standard images provides a clearly documented, project-controlled **signing plus SBOM** story on public evidence. The comparison is therefore not "who passes" but "who is least opaque."

**LocalStack (archived OSS Dockerfile)** showed the strongest public build hygiene: base image pinned by digest (`python:3.13.12-slim-trixie@sha256:...`), Node.js downloaded and verified against upstream GPG keys and SHA256. This applies to the *archived build recipe*, not necessarily the current authenticated commercial image, which is less transparent in public evidence.

**Floci** uses `eclipse-temurin:25-jre-alpine` → `quay.io/quarkus/quarkus-micro-image:2.0` for JVM and `quay.io/quarkus/ubi-quarkus-mandrel-builder-image:jdk-24` for native builds. The upstream image pedigree from Eclipse Temurin and Quarkus is reasonable. However, **Java 25** and **JDK 24** are non-LTS versions with shorter support lifecycles than JDK 21 LTS. That is a concrete maintenance liability. The workflow uses `docker/build-push-action@v6`, which likely emits builder-generated SLSA provenance by default, but no project-controlled Cosign key or published SBOM was found.

**MiniStack** uses `FROM python:3.12-alpine` without digest pinning. It uses `docker/build-push-action@v5`, which also likely emits builder-generated provenance by default — so the first-pass conclusion of "no provenance" was inaccurate. However, no project-controlled Cosign signing story or published SBOM was found. Image size of approximately 25 MB (confirmed from Docker Hub at time of research) is the smallest of the four.

**Moto** uses `python:3.13-alpine`, installs `".[server]"` via pip. Server extras pull in `aws-sam-translator`, `cfn-lint`, `flask`, `flask-cors`, `graphql-core`, `openapi-spec-validator`, `pydantic`, `PyYAML`, and others. The editable install (`pip install --editable`) in the production image is a minor audit liability. Image size is approximately 97 MB.

The critical cascade-risk question is whether LocalStack's dependency on `moto-ext[all]>=5.1.22` creates inherited Moto vulnerability exposure. **`moto-ext` is LocalStack's own maintained fork**, not a simple re-export of `moto`. The packages share lineage, but vulnerability cascade requires verifying whether the specific vulnerable code path appears in `moto-ext`'s resolved tree — not just in `moto`. This was not confirmed from public evidence. The stronger supportable claim is **plausible cascade risk**, not confirmed cascade risk.

**Docker Hardened Images (DHI)** for LocalStack is the only case where a current, public, publisher-exposed image scan exists. DHI LocalStack 4.14.x on Alpine 3.22/amd64 showed **0 critical / 0 high / 5 medium / 1 low**; Debian 13/arm64 showed **0 critical / 2 high / 3 medium / 1 low**; Docker Scout health score **A**. DHI is a separate paid Docker product, not a neutral default.

**Trade-offs**

For organizations with formal supply-chain admission policies (requiring signed images, SBOM attestations, or scan evidence before admission), none of the four standard images passes without additional work. The recommended operational posture is: pull, scan internally (Trivy, Grype, or equivalent), generate SBOMs (Syft), sign with Cosign or Notation, and push to an internal registry. DHI LocalStack reduces that work but introduces a second vendor relationship and additional spend.

**Publisher namespace mismatch for Floci** is a concrete provenance concern: the GitHub organization is `floci-io` but the Docker Hub publisher is `hectorvent`, a personal account namespace. A supply-chain–conscious policy treating personal-namespace images as higher-risk would flag this.

---

### 3. Network Isolation, Egress, and Telemetry

**Finding**

The decisive differentiator is mandatory control-plane dependence, not just port exposure.

**LocalStack authenticated/paid path**: requires `LOCALSTACK_AUTH_TOKEN` at startup, activates against `api.localstack.cloud`, and must reactivate every **24 hours** if the server becomes unreachable. Startup can fail if the license server is down. Published documentation describes usage tracking that can include CI flag, Docker flag, OS/version, session and machine identifiers, and AWS API metadata (service, operation, status code, region, dummy account, user agent, including Terraform activity). `DISABLE_EVENTS=1` disables event reporting, but backend license-activation tracking still occurs.

**LocalStack Community edition** does not require auth-token activation at startup. It should not be placed in the mandatory-control-plane bucket. However, its commercial-use restrictions (discussed in licensing) still apply.

**MiniStack, Floci, Moto**: no mandatory outbound control-plane traffic was found. All three claim no account, no API key, and no telemetry (MiniStack and Floci explicitly; Moto by design and documentation). This is based on self-reported project documentation and was not independently verified by packet-level analysis.

**Inbound exposure**: all four default to `0.0.0.0` binding internally. Docker `-p host:container` without an explicit host IP publishes on all host interfaces. Copy-paste quick-start examples from all four projects can overexpose the container. Explicit localhost binding (`-p 127.0.0.1:4566:4566`) is required for safe CI runner deployment.

MiniStack exposes additional internal ports for RDS (`RDS_BASE_PORT=15432`) and ElastiCache (`ELASTICACHE_BASE_PORT=16379`). These do not themselves create host exposure unless published via `-p`, but teams using those services should verify sidecar binding on their specific runner platform.

Floci's Dockerfile `EXPOSE`s port range `4566 6379-6399`. `EXPOSE` is metadata-only and does not publish host ports; major CI platforms (GitHub Actions, GitLab CI, CircleCI) do not auto-publish exposed ports.

**Trade-offs**

For air-gapped or strict-egress CI environments, the **paid LocalStack authenticated path** is the hardest fit. For teams running LocalStack Community or the pinned OSS version offline, the egress concern largely disappears, but the commercial-use policy concern remains. MiniStack, Floci, and Moto are materially simpler for strict-egress deployment but lack the independent verification that would make "no telemetry" a confirmed rather than claimed property.

---

### 4. Credential Handling and Secret Exposure

**Finding**

None of the four tools requires real AWS credentials for a normal local-endpoint Terraform workflow. The differences are in defaults, auditability, and failure modes.

**LocalStack**: strongest explicit documented safeguard. By default, LocalStack rejects normal AWS-style `AKIA...`/`ASIA...` access keys for account extraction and falls back to account `000000000000`. The secret access key is documented as currently ignored. Warning/debug behavior around production credentials was observed in public code snapshots without logging secret material. **Critical caveat**: enabling `PARITY_AWS_ACCESS_KEY_ID=1` removes these anti-footgun protections. The "secret access key is currently ignored" documentation is explicitly time-sensitive.

**MiniStack**: request path appears safe — account ID comes from `MINISTACK_ACCOUNT_ID` or defaults to `000000000000`, and SigV4-related data is used for service/region extraction, not secret validation. The concrete risk is the init/ready shell script execution model: MiniStack runs user-provided scripts with `env=os.environ` and logs stdout/stderr, with detached-mode logs written to `/tmp/ministack-<port>.log`. User-provided scripts that echo environment variables or enable verbose debugging will leak any credentials present in the environment.

**Floci**: the README states credentials can be anything, consistent with a dummy-credential local-emulation model. However, the README also notes some services use "real IAM" and SigV4 validation (particularly Lambda, ElastiCache, RDS, ECS). Whether "real IAM" implies local emulation of IAM or outbound delegation was not resolvable from public evidence. This is an open risk question that requires direct confirmation from the project before using Floci with those services.

**Moto server mode**: acceptable for Terraform-style local emulation, particularly when the Terraform provider is configured with `skip_credentials_validation = true`, `skip_metadata_api_check = true`, and `skip_requesting_account_id = true`. Moto **proxy mode** is materially riskier: proxy failure can silently fall through to actual AWS rather than failing explicitly.

**Overarching risk**: container environment variables are not secret storage for any of these tools. Any tool running with real `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` present in the container environment exposes those values through `docker inspect`, CI diagnostics, debug commands, or inherited child processes — regardless of whether the tool itself logs them.

---

### 5. CVE and Vulnerability History

**Finding**

The only clearly documented project-specific CVE among the four is **LocalStack CVE-2023-48054**: missing SSL certificate validation in LocalStack 2.3.2, published **November 16, 2023**, rated **CVSS 7.4 (High)** by NVD. The attack vector is Network. In practice, for an isolated CI runner without external network access to the LocalStack container, this CVE's exploitability is substantially reduced — but for shared CI environments or cloud dev boxes with broader network reachability, it applies more directly. The NVD and OSV records do not clearly name a fixed release version, a data-hygiene concern that complicates automated policy gating. However, this may partly reflect NVD's well-known metadata lag rather than LocalStack's remediation failure; LocalStack's own release notes were not confirmed to also lack this information.

No project-level CVEs were found for Moto, MiniStack, or Floci in current public sources. This is absence of evidence, not confirmed cleanliness.

**Disclosure maturity**:

- **LocalStack**: no SECURITY.md in archived repo, no published GitHub advisories despite having one public CVE in the package ecosystem. The mismatch is a negative signal for advisory-channel hygiene, though the commercial organization may now operate a separate security channel not visible in the archived repo.
- **Moto**: no SECURITY.md, no published GitHub advisories. Tidelift is mentioned as a disclosure contact, but Tidelift is a subscriber-facing commercial service, not a general public disclosure channel. Non-Tidelift-subscribing security researchers have no effective private disclosure path.
- **MiniStack**: has a SECURITY.md and explicitly warns the tool is for local dev/CI only. However, reporting goes through a public GitHub issue tagged `security` — not a private advisory workflow. Personal repo governance (see below) amplifies this concern.
- **Floci**: no SECURITY.md, no published advisories. GitHub exposes a "Report a vulnerability" button by default, which creates a private advisory channel, but no formal security process exists beyond that. Weakest on disclosure process documentation.

**Cascade risk note**: LocalStack depends on `moto-ext[all]>=5.1.22`. `moto-ext` is LocalStack's own maintained fork of Moto, not a transparent re-export. Vulnerability cascade from `moto` into LocalStack via `moto-ext` requires verifying whether the specific vulnerable code path exists in `moto-ext`'s resolved tree — this was not confirmed. The Flask-CORS advisory (GHSA-7rxf-gvfg-47g4 / CVE-2024-6839, Medium 4.3, March 2025) was identified as potentially relevant to Moto-style server stacks, but Flask-CORS's presence in Moto's actual dependency tree was not confirmed from `pyproject.toml` inspection. This should be treated as a hypothesis requiring verification, not a confirmed present-image finding.

**Moto release cadence** shows versions 5.1.19 and 5.1.20 absent from public evidence (5.1.17 → 5.1.18 → 5.1.21 → 5.1.22). These versions may be yanked releases, security patches, or gaps in the observed listing. If yanked, that is relevant to patch-response hygiene and warrants direct verification on PyPI.

---

### 6. Governance and Longevity Risk

This dimension was underweighted in earlier analysis and is critical for production CI/CD decisions.

**LocalStack**: operates as a commercial entity with a funded organization. Longevity risk is the lowest of the four, but vendor-lock risk is the highest — policy changes and pricing evolution are ongoing as demonstrated by the March 2026 transition.

**Moto**: large open-source community, Apache Software Foundation–style governance posture (Apache-2.0 licensed, broad contributor base), regular releases, widely used across the industry. Longevity risk is low.

**Floci**: `floci-io` GitHub organization suggests some organizational intent, but the Docker Hub publisher is `hectorvent`, a personal account. The discrepancy between the GitHub org namespace and the personal Docker Hub publisher namespace creates supply-chain opacity. The project is relatively new and small. Medium-high longevity risk.

**MiniStack**: hosted under personal GitHub account `Nahuel990`. Personal repos can be deleted, transferred, or abandoned with no community recourse. This is the highest structural longevity risk of the four. For a production commercial CI pipeline, reliance on a personally hosted, personally published (Docker Hub: `nahuelnucera`) project is difficult to justify regardless of its technical quality.

---

## Decision Framework

### Use LocalStack (paid, current authenticated path) when:

- Your organization has budgeted for $39–$89/license/month and has validated CI entitlements against the actual EULA
- You need the broadest AWS service coverage (55+ on Base, 110+ on Ultimate) and Terraform feature parity
- You accept mandatory outbound activation and documented usage tracking as part of the vendor relationship
- You want the strongest anti-footgun defaults for accidental real-credential use
- DHI LocalStack is available and the Docker subscription cost is acceptable, giving you the only out-of-box attested image in this comparison

### Use LocalStack (pinned OSS, last archived release) when:

- Legal has reviewed the archived Apache-2.0 artifact and confirmed the version-pinning strategy is permissible under LocalStack's current ToS
- You need a frozen, offline-capable image that does not require auth-token activation
- You can accept a frozen feature set and no upstream security patches
- This is a transitional posture while evaluating alternatives, not a long-term strategy

### Use Moto when:

- Legal simplicity is the primary gate (Apache-2.0, no commercial-use restrictions, no vendor lock)
- Strict egress control is required and you cannot accept any mandatory phone-home behavior
- Your Terraform workflows cover the service subset Moto supports (broad, but not complete)
- You are already operating in a Python ecosystem and can integrate `moto` directly for unit/integration test layers alongside Terraform CI tests
- You are willing to invest in an internal rebuild, SBOM generation, and signing pipeline — Moto's dependency footprint is well-understood and auditable

### Use MiniStack when:

- You are in early exploration / proof-of-concept phase only
- The specific service subset it supports covers your actual CI needs
- You intend to rebuild from source internally and are not relying on the personal-namespace Docker Hub image
- Legal and procurement risk tolerance is high and governance continuity is not a blocking concern
- **Do not use for production commercial CI/CD** without legal sign-off on the personal-repo governance risk and a plan for internal image ownership

### Use Floci when:

- You specifically need RDS, ElastiCache, or ECS local emulation that MiniStack or Moto do not cover, and LocalStack's commercial path is ruled out
- You have resolved the "real IAM" ambiguity with the maintainers and confirmed it does not imply outbound delegation
- You are rebuilding the image internally with a pinned, LTS Java base (JDK 21 vs. the default non-LTS JDK 24/25)
- You are not relying on the personal-namespace `hectorvent` Docker Hub image for production pipelines
- **Do not use for production commercial CI/CD** without resolving the IAM delegation question and the publisher-namespace provenance gap

---

## Recommendations (Ranked by Confidence)

### High Confidence

**1. Standardize on Moto for legal-simple, egress-clean commercial CI/CD.**  
Apache-2.0 license, no mandatory egress, no documented telemetry, familiar tooling, and the largest open-source community of the three unrestricted alternatives. For Terraform-centric workflows, use explicit server mode (`moto_server -H 127.0.0.1 -p 5000`) rather than the default `0.0.0.0` binding. Configure the Terraform AWS provider with `skip_credentials_validation`, `skip_metadata_api_check`, and `skip_requesting_account_id` set to `true` and `access_key`/`secret_key` set to dummy values.

**2. Build an internal image pipeline regardless of which tool you choose.**  
No standard image from any of these four tools provides a publisher-signed, SBOM-attested artifact suitable for a strict supply-chain admission policy. The minimum viable pipeline: pull from upstream, scan with Trivy or Grype, generate SBOM with Syft, sign with Cosign, push to your internal registry, and gate admission on digest + signature verification.

**3. Bind all emulator containers to 127.0.0.1 explicitly.**  
Replace every `-p <port>:<port>` in your CI Docker run commands with `-p 127.0.0.1:<port>:<port>`. This applies to all four tools. A misconfigured cloud CI runner that publishes `0.0.0.0` binding for the emulator port can expose mock AWS endpoints to other network-adjacent workloads.

**4. Never pass real AWS credentials into emulator containers.**  
Regardless of tool choice, ensure CI pipeline steps that launch the emulator do not inherit `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, or session tokens from the runner environment. Use a dedicated step to inject dummy values (`AWS_ACCESS_KEY_ID=test`, `AWS_SECRET_ACCESS_KEY=test`) immediately before launching the container.

### Medium Confidence

**5. If LocalStack features are required and budget is available, use DHI LocalStack rather than the standard Docker Hub image.**  
DHI provides the only currently available, publisher-exposed scan evidence (0C/0H/5M/1L on Alpine 4.14.x) and a documented signing and SBOM attestation chain. The trade-off is a second vendor relationship (Docker subscription) and higher total cost. Validate CI entitlement terms against the actual EULA before committing.

**6. Do not rely on the personal-namespace MiniStack or Floci images for production CI/CD without an internal rebuild strategy.**  
`nahuelnucera/ministack` and `hectorvent/floci` are both published from personal Docker Hub namespaces. Any CI pipeline that pulls directly from these names is one deleted account or namespace transfer away from a broken supply chain. If either tool is used, fork the build, verify the source, and publish from your own registry.

**7. Pin Moto to a specific image digest, not a floating tag.**  
Use `motoserver/moto@sha256:1e3802c95...` (or the current confirmed digest at deployment time) rather than `motoserver/moto:latest` or `motoserver/moto:5.1.22`. Digest pinning ensures the image byte-for-byte matches what you scanned and signed. Combine with a Dependabot or Renovate configuration to surface digest bumps as reviewed PRs.

### Lower Confidence (Requires Further Investigation)

**8. Verify whether Moto versions 5.1.19 and 5.1.20 were yanked from PyPI and, if so, why.**  
The absence of these versions from public evidence may indicate security-motivated yanks, which would be a positive patch-response signal, or they may simply not appear in sampled data. Check `pip index versions moto` and PyPI's release history directly before treating the observed cadence gaps as unexplained.

**9. If evaluating LocalStack Community edition for a commercial pipeline, obtain explicit written confirmation from LocalStack that your specific use case is permitted under the current ToS.**  
The public communications are inconsistent about Community edition CI use for commercial organizations. A written vendor confirmation is the only reliable instrument for legal clearance.

**10. Request that Floci clarify the "real IAM" language before any production evaluation.**  
The Floci README's claim that some services use "real IAM" is ambiguous: it could mean a local emulation of IAM semantics, or it could imply outbound delegation to real AWS IAM. In the latter case, real credentials would be required and real API calls would occur. This question must be answered before Floci can be evaluated for credential-handling risk.

---

## Known Gaps and Areas for Further Investigation

| Gap | Risk Impact | Recommended Action |
|---|---|---|
| `moto-ext` dependency tree not directly inspected | Overstates or understates LocalStack→Moto cascade risk | `pip show moto-ext` and `pip-audit` on the `moto-ext[all]` resolution; compare `flask-cors` presence against the GHSA-7rxf-gvfg-47g4 affected range |
| Current LocalStack commercial image `pyproject.toml` not accessible | Dependency composition and CVE exposure for the authenticated commercial build are unknown | Request LocalStack's SBOM or dependency manifest for the current authenticated image as part of vendor security assessment |
| LocalStack CVE-2023-48054 fixed-version metadata not confirmed in release notes | May be NVD lag rather than maintainer hygiene failure | Check LocalStack's own changelog and GitHub release notes for explicit remediation reference before using this as a negative signal |
| Flask-CORS present in Moto's actual dependency tree not confirmed | "Cascade risk example" claim rests on unverified dependency link | Inspect `moto`'s `pyproject.toml` or `setup.cfg` server extras directly: `pip show moto` and `pip install moto[server]; pip show flask-cors` |
| No packet-level egress analysis for MiniStack or Floci | "No telemetry" is self-reported, not independently verified | Run each container with `tcpdump` or network namespace monitoring in a test environment; compare observed outbound connections against claimed behavior |
| Moto versions 5.1.19 and 5.1.20 unexplained | Unknown whether security-motivated yanks or data gap | `pip index versions moto` and PyPI release history |
| Floci "real IAM" ambiguity unresolved | Could imply outbound real-AWS IAM calls with real credentials | Direct inquiry to `floci-io` maintainers; inspect Floci Lambda/ECS handler source code for outbound IAM endpoint calls |
| Reachable attack surface per service not mapped | CVSS scores cite Network attack vector but exploitability depends on whether the service is even loaded during Terraform plan/apply | Profile which emulator services are activated by a representative Terraform run; assess whether vulnerable dependency paths are in the loaded module graph |
| No current image-level scan evidence for MiniStack, Floci, or Moto standard images | Comparison is asymmetrical (DHI LocalStack has publisher scan data; others do not) | Run Trivy or Grype against each pinned digest and publish results to your internal security dashboard |
| MiniStack personal-repo continuity risk unmitigated | Entire supply chain at risk if `Nahuel990` account is deleted or abandoned | Fork to your organization's VCS if MiniStack is used in any capacity; do not depend on upstream availability |

---

*Research period: through April 8, 2026. Evidence is point-in-time; license terms, image digests, CVE records, and project governance status should be reverified at deployment and on each major dependency update.*