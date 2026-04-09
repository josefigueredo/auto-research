Below is a distilled summary of the research, preserving the main facts, numbers, corrections, and trade-offs.

**Licensing and commercial-use risk**

The main licensing conclusion is that **LocalStack is the outlier**, but not because public evidence clearly shows a repo-wide switch to BUSL. The last public GitHub repo snapshot and PyPI metadata still show **Apache-2.0**. The more important change is operational and contractual: starting **March 23, 2026**, LocalStack moved current LocalStack-for-AWS releases to a **single authenticated image**, and the public OSS repo was archived the same day. The legally relevant distinction is therefore not “Apache vs BUSL in the repo,” but **“last public Apache-licensed OSS snapshot vs current authenticated commercial product path.”**

That matters for commercial CI/CD. LocalStack’s **February 27 and March 5, 2026** public communications say the **free tier is non-commercial** and that CI/team/commercial use should move to paid offerings. Public pricing showed **Free: $0**, **Base: $39/license/month billed annually**, and **Ultimate: $89/license/month billed annually**, with published service counts of **30+**, **55+**, and **110+**. Older pricing surfaces also showed **300 CI credits/month/workspace** for Base and **1000/month/workspace** for Ultimate. However, the evidence was inconsistent: older docs still discuss CI credits and earlier tiering, while newer 2026 blog posts say CI is now unrestricted across plans under fair usage, including the free non-commercial plan. Because that contradiction was not fully resolved, the strongest defensible conclusion is narrower: **LocalStack’s current product path creates materially more legal and procurement complexity for commercial users than the alternatives, and exact CI entitlements should be validated against the actual ToS/EULA, not blog posts.**

Peer review tightened several points. The binding documents are the **ToS/EULA**, not blog posts. Saying “current repo” was misleading because the repo is archived; the accurate phrasing is that the **last public OSS release** remained Apache-2.0. A major omitted mitigation was **version pinning**: pre-transition LocalStack versions on PyPI may remain usable under Apache-2.0 without auth tokens. Marketing claims such as “MIT forever” are not legal guarantees against future change. Governance risk was underweighted for **MiniStack**, especially because it is hosted under a personal GitHub account. And “no sign of AGPL” is weaker than directly confirming the `LICENSE` file.

By contrast, the alternatives are legally straightforward at the top level:
- **MiniStack**: **MIT**
- **Floci**: **MIT**
- **Moto**: **Apache-2.0**

Those licenses generally allow **commercial use**, **private/internal use**, modification, and redistribution subject to notice obligations, and they do **not** impose AGPL-style source disclosure for internal CI pipelines. The research found no public evidence of AGPL or BUSL applying to MiniStack or Floci, and no project-level AGPL issue for Moto. The practical implication is that **MiniStack, Floci, and Moto are all low-friction from a license perspective for internal commercial CI/CD**, while **LocalStack’s current latest-release path is the commercial-policy and licensing outlier**.

That cleaner top-level posture does not eliminate legal risk. The main residual concerns are:
1. **Transitive dependency and container-layer licenses**, including possible LGPL/GPL components inside images.
2. **Redistribution rights for prebuilt images**, especially for internal mirroring or republishing to private registries.
3. **Governance risk**, because permissive licensing does not guarantee durability; small or single-maintainer projects can stagnate or change terms later.

The licensing bottom line is:
- **LocalStack** is best if a company accepts a vendor-controlled, authenticated product with likely commercial terms.
- It is worst if **legal simplicity**, **vendor independence**, or **policy stability** matter most.
- **MiniStack, Floci, and Moto** are materially simpler for internal commercial CI/CD from a pure license perspective.
- The main LocalStack risk is **commercial-use gating, auth-token dependence, and policy drift**, not AGPL contamination and not clearly published BUSL.

**Supply-chain security, provenance, and image trust**

On supply-chain posture, the research compared signing, provenance, SBOMs, base-image hygiene, and dependency surface. The first draft said none of the standard public images clearly met a strict **publisher-signed plus SBOM-attested** standard, and peer review kept that conclusion broadly intact but corrected important details.

The strongest public hardening signal belonged to **LocalStack’s last public Dockerfile**, not necessarily its current live product image. That archived public Dockerfile:
- pins the base image by **digest** (`python:3.13.12-slim-trixie@sha256:...`)
- downloads **Node.js** manually
- verifies Node using upstream **GPG release keys** and **SHA256 checks**

That is materially better public build hygiene than the others. But it applies to the **archived OSS recipe**, while the current product path uses an authenticated image whose build recipe is not equally transparent in public evidence. The standard LocalStack Docker Hub image showed a latest digest like `sha256:94c3730fc…` and compressed size around **468.8 MB**. Its public `pyproject.toml` also showed a broad dependency set including **`boto3==1.42.59`**, **`botocore==1.42.59`**, **`awscli==1.44.49`**, **`moto-ext[all]>=5.1.22`**, plus `jpype1`, `opensearch-py`, `pymongo`, and others.

That dependency detail materially changed the comparison. Peer review noted the original analysis treated **LocalStack** and **Moto** like independent supply chains even though LocalStack itself depends on **`moto-ext[all]`**. In practice, LocalStack’s supply-chain surface is at least partly a **superset of Moto’s**, so any criticism of Moto’s dependency breadth also applies to LocalStack.

For **MiniStack**, the provenance posture looked weakest:
- Dockerfile uses **`FROM python:3.12-alpine`** without digest pinning
- installs packages directly with `pip install`
- adds Alpine `nodejs` with `apk`
- publishes multi-arch images via `docker/build-push-action@v5`
- public Docker Hub showed about **26.0 MB** compressed per architecture for `latest`/`1.1`, while project copy claimed about **150 MB** and **~2s startup**

That image-size discrepancy was unresolved and may reflect stale marketing. More importantly, the original report wrongly inferred “no provenance” from the absence of explicit `sbom`, `provenance`, or `attests` flags. Peer review identified that as a major factual error: `docker/build-push-action` **v4+ generally emits SLSA provenance attestations by default**, so MiniStack’s use of **v5** means the absence of explicit flags does **not** prove absence of provenance. The corrected view is:
- MiniStack still lacks public evidence of a **project-controlled signing story** such as a published Cosign key.
- Public **SBOM publication** still appears absent.
- But it may well include **builder-generated SLSA provenance** by default.

For **Floci**, base-image pedigree looked better than MiniStack’s:
- JVM path: `eclipse-temurin:25-jdk` to `eclipse-temurin:25-jre-alpine`
- native path: `quay.io/quarkus/ubi-quarkus-mandrel-builder-image:jdk-24` to `quay.io/quarkus/quarkus-micro-image:2.0`
- Docker Hub image around **69 MB**
- workflow uses `docker/build-push-action@v6`

Again, v6 likely emits builder-generated provenance by default, so the first draft understated that. But Floci still showed no public evidence of a **project-published Cosign key** or published **SBOMs**. Peer review added two important cautions: Floci’s JVM runtime is also **Alpine-based**, so Alpine/musl caveats apply, and it uses **non-LTS Java versions** (**Java 25** and **JDK 24**), which have shorter support lifecycles than **JDK 21 LTS** and therefore create a real maintenance risk.

For **Moto**, the supply-chain picture is operationally simple but dependency-heavy:
- image size about **96.6 MB** for **5.1.22**
- GHCR digest surfaced for **5.1.17** as `sha256:0361ac8f...`
- base image `python:3.13-alpine`
- Dockerfile installs **`".[server]"`**
- `server` extras pull in dependencies such as `aws-sam-translator`, `docker`, `graphql-core`, `PyYAML`, `cfn-lint`, `openapi-spec-validator`, `pydantic`, `py-partiql-parser`, `aws-xray-sdk`, `flask`, and `flask-cors`

Peer review also flagged **`pip install --editable ".[server]"`** in the production image as a minor quality concern because editable installs leave more source-tree artifacts and complicate auditability.

Across all four, the largest shared gap is still **public SBOM availability**. The research did not find public SBOM artifacts or registry-attached SBOM workflows for:
- MiniStack
- Floci
- Moto’s official image
- standard LocalStack Docker Hub image

The one explicit exception was **Docker Hardened Images (DHI)**. Docker documents **Cosign signing**, **signed SBOMs**, and **signed attestations/provenance** for DHI. There is a DHI LocalStack variant whose catalog metadata showed:
- distro: **debian 13**
- packages: **261**
- vulnerabilities: **0 critical / 0 high / 3 medium / 1 low / 0 unspecified**
- Docker Scout health score: **A**

But DHI is not a neutral fallback. It is a **paid Docker product**, so it introduces another vendor and subscription dependency.

The corrected supply-chain ranking is therefore more nuanced than “everyone fails”:
- **LocalStack**: strongest publicly inspectable hardening in the last public OSS Dockerfile, but less transparency for the current authenticated path; also inherits a large dependency surface including Moto-related code.
- **Floci**: relatively good upstream lineage, but weakened by missing public signing/SBOM clarity, Alpine JVM runtime, and non-LTS JDK choices.
- **MiniStack**: simplest and easiest to understand, but weaker base pinning and no public project-controlled signing/SBOM story; may still benefit from builder-generated provenance.
- **Moto**: familiar and Apache-licensed, but dependency-heavy and not especially lightweight from a supply-chain perspective.

The safest conclusion is not that all four categorically fail provenance. It is:
- none of the standard images has a clearly documented, **project-controlled signing plus SBOM** story on public evidence
- MiniStack and Floci may still have **builder-generated provenance**
- organizations with strict provenance requirements should expect to **rebuild, generate SBOMs, sign, and mirror internally**
- **DHI LocalStack** is the clearest attested option, but it is a **separate paid distribution channel**

**Network isolation, egress, telemetry, and exposed ports**

The strongest network differentiator was **mandatory control-plane dependence**, not just port exposure.

The first draft treated LocalStack broadly as the egress outlier because current auth flows require **`LOCALSTACK_AUTH_TOKEN`**, activation against `api.localstack.cloud`, and, if offline, reactivation every **24 hours**. Public docs also describe usage tracking that can include session data and AWS API metadata such as service, operation, status code, region, dummy account, and user agent, including **Terraform**. `DISABLE_EVENTS=1` disables event reporting, but backend license activation tracking still occurs. In strict-egress CI, that makes the **paid/authenticated LocalStack path** materially different.

Peer review identified the key scoping mistake: that analysis effectively described **paid/authenticated LocalStack**, not **LocalStack Community edition**. The free community image on Docker Hub does **not** require auth-token activation at startup. So the corrected conclusion is:
- **paid/current LocalStack authenticated path** is the outlier on mandatory egress
- **LocalStack Community edition** should not automatically be placed in the same mandatory-control-plane bucket

Even with that correction, LocalStack’s paid path remains the most network-sensitive. Public docs say:
- activation can fail startup
- unreachable license server may require reactivation every **24 hours**
- some CI token activation flows consume **1 CI credit**
- usage tracking can include CI flag, Docker flag, OS/version, session and machine identifiers, and AWS API metadata

On inbound exposure, LocalStack’s defaults are mixed:
- internal Docker bind: `0.0.0.0:4566`
- host mode: `127.0.0.1:4566`
- archived compose example maps `127.0.0.1:4566:4566` and `127.0.0.1:4510-4559:4510-4559`
- current auth-token docs show `-p 4566:4566 -p 4510-4559:4510-4559`, which Docker exposes on **all host addresses by default**

So LocalStack can be run safely, but copy-paste examples may overexpose it unless users explicitly bind to localhost.

For **MiniStack**, the outbound picture is cleaner. Public materials claim **“no account, no API key, no telemetry”**, and the Dockerfile shows Uvicorn bound to `0.0.0.0:4566`. The usual quick-start uses `docker run -p 4566:4566`, which again exposes on all host interfaces unless localhost is pinned. The main risk is therefore not phone-home behavior but **accidental host exposure**.

MiniStack also has service-specific extra ports:
- `RDS_BASE_PORT=15432`
- `ELASTICACHE_BASE_PORT=16379`

Its site shows Postgres on `localhost:15432` and Redis on `localhost:16379`. Peer review refined the original concern: those internal service ports do **not** themselves create exposure unless operators publish them. The better conclusion is that MiniStack may have a **broader internal port surface** than its one-port marketing suggests, and teams using RDS/ElastiCache features should verify sidecar binding on their runner platform.

For **Floci**, public claims were similarly favorable:
- “No account required”
- “No auth tokens”
- “No sign-ups”
- “No telemetry”

Its quick-start also centers on **4566**, but the Dockerfile `EXPOSE`s **`4566 6379-6399`**. `EXPOSE` is metadata only; it does not itself publish host ports. The first draft warned that CI platforms might auto-publish exposed ports, but peer review correctly noted common CI platforms usually do not. So the correct reading is:
- Floci appears clean on mandatory egress from public evidence
- there is a wider internal advertised port range than the one-port quick-start implies
- actual host exposure still depends on explicit publishing configuration

For **Moto**, the core story is “simple and mostly local, but easy to expose if used carelessly.” The docs show server mode defaults to **port 5000**, and the CLI-native path is safer because it defaults to loopback. But the official Dockerfile hardcodes:
- `moto_server -H 0.0.0.0`
- `EXPOSE 5000`

So `docker run -p 5000:5000` will publish a broadly listening Moto server unless the host bind is pinned. The original write-up also highlighted a Moto Lambda edge case where mocked Lambda code may reach real AWS; peer review said that is real but largely out of scope for Terraform-centric CI, so it should be treated as a niche edge case rather than a headline finding.

The corrected network-isolation conclusion is:
- **Paid/current LocalStack authenticated path** has the clearest mandatory control-plane dependency and documented telemetry/usage reporting; this is the biggest network-isolation differentiator.
- **LocalStack Community**, **MiniStack**, **Floci**, and **Moto server mode** look much cleaner on mandatory outbound traffic.
- **All four** still need explicit hardening around Docker port publishing, because `-p host:container` without a host IP usually exposes on all interfaces.
- For MiniStack and Floci, the main residual uncertainty is not documented telemetry but limited independent verification beyond project self-description.

**Credential handling and secret exposure**

Across all four tools, the most important shared conclusion is that **none requires real AWS secrets for a normal local-endpoint Terraform workflow**. The differences are in how they behave if real credentials are present and how transparently they document that behavior.

**LocalStack** had the strongest explicit safeguards. Its docs say that by default it rejects normal AWS-style **`AKIA...` / `ASIA...`** access keys for account extraction and instead uses LocalStack-style structured keys, falling back to account **`000000000000`**. The docs also say the **secret access key is currently ignored**. Public code snapshots and issue evidence showed warning/debug behavior around production credentials without logging the actual secret material. The residual risk is mostly operational: if real credentials are passed into the container as env vars, they remain visible through `docker inspect`, CI diagnostics, or custom debugging.

Peer review fixed one important contradiction: **enabling** `PARITY_AWS_ACCESS_KEY_ID=1` removes some of the anti-footgun protection. So the safe conclusion is that LocalStack is protective **unless** permissive compatibility flags are enabled. Peer review also emphasized that “secret access key is currently ignored” is explicitly time-sensitive and could change.

**MiniStack** appears to treat AWS credentials mostly as opaque request syntax rather than real secrets to validate. The inspected code path extracted service and region from SigV4-related data, while account ID comes from `MINISTACK_ACCOUNT_ID` or defaults to **`000000000000`**. The bigger risk is not request handling but script execution:
- MiniStack runs init and ready shell scripts with `env=os.environ`
- logs their stdout/stderr
- in detached mode writes logs to **`/tmp/ministack-<port>.log`**

So MiniStack itself did not appear to log credentials by default in the normal request path, but **user-provided scripts can leak credentials very easily** if they echo environment variables or enable verbose debugging.

**Floci** looked broadly similar in user-facing behavior but with weaker code-level visibility. Public docs say **credentials can be anything**, which suggests a dummy-credential local-emulation model. But the README also says some services use **“real IAM”** and SigV4 validation, especially around Lambda, ElastiCache, RDS, and ECS. Because the underlying auth and logging implementation could not be cleanly isolated from public code inspection, the fairest conclusion is that Floci is **probably** in the same broad category as MiniStack, but its credential-handling posture is **less auditable from public evidence**. Peer review emphasized that “real IAM” is ambiguous and could, in the worst case, imply outbound delegation rather than pure local emulation; that remained unresolved and should be treated as an open risk question.

**Moto** divides into two distinct modes:
- **server mode**: relatively safe for Terraform-style local emulation, especially when Terraform uses `skip_credentials_validation = true`, `skip_metadata_api_check = true`, and `skip_requesting_account_id = true`
- **proxy mode**: materially riskier, because clients still behave more like they are talking to real AWS and misconfiguration can silently fall through toward actual AWS

Peer review sharpened that risk: the main proxy-mode danger is not just that requests are signed with real credentials, but that **proxy failure can lead to silent fallback to actual AWS**, whereas explicit endpoint server mode fails much more safely.

Across all tools, the overarching operational reality is that **container environment variables are not secret storage**. If any tool runs with real `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, or session tokens in environment variables, those can often surface through container metadata, CI logs, diagnostics, inherited child processes, or debug commands. A tool not logging secrets by default does not remove that wider exposure class.

The corrected credential-handling ranking is:
- **LocalStack**: strongest explicit and verifiable safeguard against accidental use of real AWS access keys, assuming permissive compatibility flags are not enabled.
- **MiniStack**: request path appears safe enough, but init/ready scripts are a concrete log-leak channel.
- **Floci**: likely dummy-credential-friendly, but lower confidence because implementation details were not directly confirmed.
- **Moto**: safe enough in explicit server mode; meaningfully riskier in proxy mode.

**Overall synthesis**

Across these dimensions, the pattern is consistent.

For **licensing and commercial use**, the cleanest top-level legal posture belongs to **MiniStack**, **Floci**, and **Moto**. **LocalStack** is the outlier because current latest-release usage depends on authenticated access, commercial-use limits, and changing vendor policy, even though the last public OSS artifacts remain Apache-2.0.

For **supply-chain security**, none of the standard images provides a complete, clearly documented project-controlled **signing plus SBOM** story on public evidence. LocalStack’s archived OSS Dockerfile shows the strongest public hardening signals; Floci has relatively strong upstream lineage but weaker Java lifecycle choices; MiniStack is simplest but lightly attested; Moto is familiar but dependency-heavy. Organizations with strict provenance requirements should assume they may need to **rebuild, SBOM, sign, and mirror internally**.

For **network isolation**, the decisive factor is **control-plane dependence**. The **paid/authenticated LocalStack path** clearly depends on outbound activation and includes documented usage tracking; the others appear cleaner on mandatory egress. But all four can be overexposed if Docker `-p` is used without explicit localhost binding.

For **credential handling**, none of the tools inherently requires real AWS secrets for a normal local-endpoint Terraform flow. **LocalStack** has the strongest explicit anti-footgun defaults; **MiniStack** is mostly safe on the request path but weaker around script logging; **Floci** is less auditable; **Moto** is acceptable in server mode but less safe in proxy mode.

The most defensible high-level bottom line is:
- If **legal simplicity and low-friction internal commercial CI/CD** matter most, **MiniStack, Floci, and Moto** are easier to clear than current LocalStack latest-release usage.
- If **strict provenance and publisher attestation** matter most, none of the standard images is ideal; LocalStack’s archived OSS build hygiene and the **DHI** path are the strongest signals, but both come with trade-offs.
- If **strict egress control or zero phone-home behavior** matter most, the **paid/current LocalStack authenticated path** is the hardest fit.
- If **protection against accidental real AWS credential use** matters most, **LocalStack’s documented defaults** are strongest, followed by **MiniStack** and **Moto server mode**, with **Floci** less verified.

The practical takeaway is not that one tool wins every category. The trade-offs are asymmetrical:
- **LocalStack**: strongest on maturity and some explicit security safeguards, weakest on legal simplicity, vendor independence, and authenticated control-plane dependence.
- **MiniStack**: strongest on licensing simplicity and low-friction local use, but weaker on governance maturity and supply-chain attestability.
- **Floci**: similar legal and network advantages to MiniStack, with stronger-looking upstream image pedigree, but lower implementation auditability and real Java lifecycle concerns.
- **Moto**: legally easy and widely known, but heavier and less naturally aligned with Terraform-heavy workflows than it first appears.

## CVE and vulnerability history

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