# Iteration 006 — Container security: non-root execution, read-only filesystem support, seccomp/AppArmor profiles, minimal attack surface

**Status:** keep  
**Scores:** coverage=61.7, quality=75.0, total=69.7  
**Timestamp:** 2026-04-08T20:44:09.053951+00:00  

---

### Findings

**Bottom line for hardened CI containers**

On this dimension alone, **Floci is the clear best fit**, **Moto is the cleanest if you only need pure in-process emulation and can avoid Lambda’s Docker-backed path**, and **LocalStack and MiniStack are materially weaker** because their official images still default to root and their higher-fidelity features rely on Docker socket access.

**LocalStack**
- The last public Dockerfile creates a `localstack` user but does **not** switch to it with a final `USER` directive, so the official image runs as **root by default**. That is visible in the public Dockerfile: it creates `localstack`, changes ownership on some paths, then ends with `ENTRYPOINT` and no `USER` switch. Source: archived Dockerfile and repo docs.  
- I did **not** find current official documentation for running the LocalStack container itself rootless. The docs instead focus on running the **host-side CLI** as a non-root user, which is different.  
- Read-only root filesystem support is **not documented**. The current filesystem docs say `/var/lib/localstack` must be mounted for correct operation, and the Dockerfile also prepares writable paths such as `/tmp/localstack` and `/.npm`. My assessment is therefore an **inference**: read-only rootfs is not a supported/cleanly documented mode, and if attempted it would need at least a writable `/var/lib/localstack` plus writable temp space.  
- For capabilities, current official docs do **not** ask for `privileged: true` or `cap_add`, but they do require `/var/run/docker.sock` for Lambda. In a hardened CI environment, that is usually the more important problem than Linux caps because Docker socket access effectively hands the container control over the host daemon. Docker’s own security docs treat socket access as sensitive administrative access.  
- Practical consequence: LocalStack is acceptable only for Terraform plans that stay away from Docker-backed services. If your Terraform apply path exercises Lambda locally, the Docker socket dependency is a major hardening failure.

**MiniStack**
- MiniStack’s Dockerfile also creates a non-root `ministack` user, but again never switches to it with `USER`, so the official image also runs as **root by default**.  
- I found **no documented rootless-container mode** for the official image. The Dockerfile’s ownership fixes on `/tmp/ministack-data` and `/docker-entrypoint-initaws.d` suggest the maintainer anticipated non-root execution, but the published image still defaults to root.  
- Read-only root filesystem support is **not documented**. The Dockerfile sets `S3_DATA_DIR=/tmp/ministack-data/s3`, and the official compose file bind-mounts that path. So the safest conclusion is: a read-only rootfs configuration is **unverified**, and if attempted would need at least a writable mount or tmpfs at `/tmp/ministack-data/s3` and likely writable `/tmp`.  
- No official examples require `privileged` or extra capabilities. But the README and compose file mount `/var/run/docker.sock` for “real infrastructure” modes such as RDS, ECS, and Lambda containers.  
- Practical consequence: MiniStack is less bad than LocalStack in that the socket is optional for basic emulation, but it is still not a clean hardened-container story. For CI that forbids Docker socket mounts, you would need to avoid the “real infrastructure” features.

**Floci**
- Floci’s recommended `latest` image is the strongest here. Its native-image Dockerfile explicitly sets `USER 1001` in the final runtime stage, so it runs as **non-root by default**.  
- This is the only project of the four where the official image has a clearly intentional non-root runtime posture.  
- Floci does **not** explicitly document `--read-only` support, but its runtime layout is the closest to supporting it cleanly. The runtime image prepares `/app/data` as the writable state path, and the docs consistently route persistence through that directory. Inference: for persistent or hybrid modes, mount `/app/data` read-write; for pure memory mode, Floci appears to be the best candidate for a read-only rootfs, though this is still **not an officially documented guarantee**.  
- No official Floci examples require `privileged` or `cap_add`. Docker socket mounting is required only for Docker-backed services: Lambda, ElastiCache, and RDS. The docs explicitly say you can omit the socket if you do not use those services.  
- This is a meaningful security advantage over LocalStack and MiniStack because Floci documents a narrower Docker dependency boundary. It also exposes an `ECS mock` mode that skips Docker for ECS, which is unusually useful for CI hardening.  
- Practical consequence: Floci is the best option for a hardened CI runner if your Terraform workflow can stay within non-Docker-backed services, and it is the least-worst option when you must enable some Docker-backed services.

**Moto**
- Moto’s official Dockerfile has **no `USER` directive**, so the official image runs as **root by default**.  
- I found **no official rootless-container guidance**.  
- Read-only root filesystem support is also **not documented**. However, Moto’s default server mode is in-memory and much simpler than the others: no declared writable volume, no built-in persistence path, and no mandatory Docker socket for basic use. That makes Moto the most plausible candidate for successful read-only operation, but this is still an **inference, not documented support**. I would treat `/tmp` tmpfs as the likely minimum writable path if you test it.  
- No official examples require `privileged` or `cap_add`. For ordinary `moto_server` use, Moto avoids the Docker socket entirely. The exception is Moto’s Lambda emulation, whose docs describe Docker-backed Lambda containers and Docker networking options.  
- Practical consequence: if your Terraform plan/apply coverage does not depend on Lambda container execution or other Docker-backed behavior, Moto has the cleanest hardened-container story after Floci because it can run without Docker socket access and without extra host integrations.

**Current rank for hardened CI**
1. **Floci**
2. **Moto** if Docker-backed Lambda is not needed
3. **MiniStack**
4. **LocalStack**

The ordering between MiniStack and LocalStack is close on pure container hardening. Both default to root, both lean on Docker socket for higher-fidelity features, and neither documents read-only rootfs support. I rank LocalStack lower because its writable-path footprint is broader and its current official path is operationally more complex.

### Evidence

**Default runtime user**
- LocalStack public Dockerfile: creates `localstack` user but does not set final `USER`; image therefore defaults to root.  
  Sources:  
  - https://raw.githubusercontent.com/localstack/localstack/master/Dockerfile  
  - https://github.com/localstack/localstack/blob/main/DOCKER.md
- MiniStack Dockerfile: `adduser -S ministack -G ministack`, but no `USER`; defaults to root.  
  Sources:  
  - https://github.com/Nahuel990/ministack/blob/master/Dockerfile  
  - https://github.com/Nahuel990/ministack
- Floci native Dockerfile: final stage sets `USER 1001`.  
  Sources:  
  - https://github.com/floci-io/floci/blob/main/Dockerfile.native  
  - https://floci.io/floci/configuration/docker-compose/
- Moto Dockerfile: no `USER`; defaults to root.  
  Sources:  
  - https://raw.githubusercontent.com/getmoto/moto/master/Dockerfile  
  - https://docs.getmoto.org/en/5.0.16/docs/server_mode.html

**Docker socket requirements**
- LocalStack: official docs say Docker socket mount is required for Lambda.  
  Sources:  
  - https://github.com/localstack/localstack/blob/main/DOCKER.md  
  - https://docs.localstack.cloud/aws/services/lambda/
- MiniStack: README and compose mount `/var/run/docker.sock`; README says it is needed for “real infrastructure” such as RDS, ECS, Lambda containers.  
  Sources:  
  - https://github.com/Nahuel990/ministack  
  - https://github.com/Nahuel990/ministack/blob/master/docker-compose.yml
- Floci: docs say socket is required for Lambda, ElastiCache, and RDS, and may be omitted otherwise.  
  Sources:  
  - https://floci.io/floci/configuration/docker-compose/  
  - https://floci.io/floci/configuration/application-yml/
- Moto: ordinary server mode docs show Docker image usage with no socket; Lambda docs describe Docker-backed Lambda containers and Docker networking settings.  
  Sources:  
  - https://docs.getmoto.org/en/5.0.16/docs/server_mode.html  
  - https://docs.getmoto.org/en/4.2.10/docs/services/lambda.html

**Privileged mode / extra Linux capabilities**
- I found **no current official config** for any of the four that requires `privileged: true` or explicit `cap_add`.  
- Important nuance: old LocalStack material did use `--privileged` in 2020, but the current official docs no longer do.  
  Sources:  
  - Current LocalStack docs: https://github.com/localstack/localstack/blob/main/DOCKER.md  
  - Historical example only: https://github.com/localstack/localstack/issues/2554
- Docker’s own guidance says protecting the daemon socket is critical; access to it is effectively administrative.  
  Source:  
  - https://docs.docker.com/engine/security/protect-access/

**Read-only rootfs posture**
- LocalStack filesystem docs require `/var/lib/localstack`; Dockerfile also prepares `/tmp/localstack` and `/.npm`. No explicit `--read-only` guidance found.  
  Sources:  
  - https://docs.localstack.cloud/references/filesystem/  
  - https://raw.githubusercontent.com/localstack/localstack/master/Dockerfile
- MiniStack uses `/tmp/ministack-data/s3` as the default S3 state path and exposes `/docker-entrypoint-initaws.d` as a volume. No `--read-only` guidance found.  
  Sources:  
  - https://github.com/Nahuel990/ministack/blob/master/Dockerfile  
  - https://github.com/Nahuel990/ministack/blob/master/docker-compose.yml
- Floci routes persistence through `/app/data`; docs make that path explicit. No explicit `--read-only` doc found, but this is the cleanest writable-path story.  
  Sources:  
  - https://github.com/floci-io/floci/blob/main/Dockerfile.native  
  - https://floci.io/floci/configuration/docker-compose/  
  - https://floci.io/floci/configuration/storage/
- Moto has no documented persistent state path in server mode and no documented `--read-only` mode.  
  Sources:  
  - https://raw.githubusercontent.com/getmoto/moto/master/Dockerfile  
  - https://docs.getmoto.org/en/5.0.16/docs/server_mode.html

**Attack-surface size signals**
- LocalStack Docker Hub `latest`: **468.8 MB** compressed, updated 3 days ago in the crawl.  
  Source: https://hub.docker.com/r/localstack/localstack/
- MiniStack Docker Hub `latest`: **26.02 MB** amd64 compressed, updated about 3 hours ago in the crawl.  
  Source: https://hub.docker.com/r/nahuelnucera/ministack/tags
- Floci Docker Hub `latest`: **69 MB** compressed, updated 3 days ago in the crawl.  
  Source: https://hub.docker.com/r/hectorvent/floci
- Moto Docker Hub `5.1.22`: **96.6 MB** compressed, updated 4 days ago in the crawl.  
  Source: https://hub.docker.com/r/motoserver/moto

**CI / Terraform-adjacent signals**
- Floci publishes **14 Terraform** and **14 OpenTofu** compatibility tests in its repo README.  
  Source: https://github.com/floci-io/floci
- Floci’s docs also publish a CI example that runs without Docker socket for basic service coverage.  
  Source: https://floci.io/floci/configuration/docker-compose/
- MiniStack README explicitly markets Terraform compatibility.  
  Source: https://github.com/Nahuel990/ministack
- LocalStack maintains `terraform-local`, but current container-hardening concerns remain independent of that integration.  
  Source: https://github.com/localstack/localstack

### Trade-offs

**Floci is best when hardened CI policy matters more than service breadth.**  
It is the only one with an official non-root default image and the only one that clearly scopes Docker-socket dependency to specific services. The counter-intuitive part is that Floci still ceases to look “hardened” the moment you enable Lambda, RDS, or ElastiCache with real containers. In other words, its container security story is strong only if you deliberately stay on the non-Docker-backed subset.

**Moto is better than it first appears for strict container hardening.**  
Functionally it is often treated as the “lightweight but less realistic” option, but on this dimension that simplicity helps it. For plain `moto_server`, there is no documented Docker socket dependency, no extra port ranges, and no explicit writable state volume. If your Terraform workflows mostly touch S3, SQS, DynamoDB, IAM-style control planes, Moto may be the easiest to lock down. The trade-off is fidelity and the fact that its Lambda path reintroduces nested Docker.

**MiniStack’s smallest image does not translate into the safest runtime posture.**  
The compressed image is only about 26 MB on amd64, much smaller than the others, but the official image still defaults to root and the higher-fidelity features rely on Docker socket access. That is a good example of why image size is not a sufficient security proxy.

**LocalStack is weaker than its current docs may suggest.**  
Current docs no longer require privileged mode, which is better than older versions, but the practical hardening problem remains the same: root-by-default container plus Docker socket for Lambda. Also, the writable-path story is broader and less clearly constrained than Floci’s.

**No project here gives a clean, documented `--read-only --cap-drop=ALL` story.**  
That is the surprising shared gap. Floci comes closest operationally. Moto is probably the easiest to make work experimentally. But none of the four publish the kind of hardened-container runbook that a senior platform team would want before standardizing on it.

### New Questions

1. Can each emulator pass a real hardened-runner test matrix: `runAsNonRoot`, `readOnlyRootFilesystem`, `allowPrivilegeEscalation=false`, `capDrop=ALL`, `seccomp=RuntimeDefault`, no Docker socket?
2. For Terraform specifically, which AWS resources force each emulator onto Docker-backed execution paths, and can those paths be selectively disabled without breaking `plan`/`apply` parity?
3. Which projects can be rebuilt internally onto a hardened base image without breaking compatibility, and which depend too heavily on mutable filesystem state or runtime package installs?

If you want, I can do the next iteration on **credential handling and secret exposure inside CI runners** using the same standard.

---

## Peer Review (claude)

## Critical Peer Review

---

### Issue 1: Floci and MiniStack project maturity is not established
- **Type**: Gap / Missing nuance
- **Location**: All sections comparing the four tools as peers
- **Problem**: The report treats four tools as roughly comparable options without disclosing that LocalStack and Moto are widely-used, multi-year projects with large communities, while "Floci" (`hub.docker.com/r/hectorvent/floci`, GitHub org `floci-io`) and "MiniStack" (`github.com/Nahuel990/ministack`) appear to be obscure or personal projects. The Docker Hub publisher for Floci is a personal account (`hectorvent`), not the `floci-io` org — an inconsistency the report does not address. A platform team reading this would need to know whether Floci has production users, a security disclosure process, paid support, or an SLA. None of that is covered.
- **Impact**: High. Ranking Floci #1 without establishing its provenance or maturity could mislead a reader into selecting an unmaintained or minimally-supported tool over LocalStack for a hardened CI strategy. The entire conclusion rests on this tool being a real, viable alternative.

---

### Issue 2: Unsupported claim — Floci's "ECS mock mode"
- **Type**: Unsupported claim
- **Location**: *"It also exposes an `ECS mock` mode that skips Docker for ECS, which is unusually useful for CI hardening."*
- **Problem**: No source is cited for this claim anywhere in the Evidence section. The ECS mock mode is not linked to a doc page, a config option, or a GitHub reference. The rest of the Docker-socket evidence for Floci cites two URLs; this claim cites zero.
- **Impact**: Medium-High. This claim is used to differentiate Floci from the others on a key hardening axis (Docker-socket avoidance for ECS). If the mode does not exist or behaves differently than described, the practical advantage over LocalStack and MiniStack narrows significantly.

---

### Issue 3: MiniStack's claimed RDS, ECS, and Lambda support is implausible at 26 MB
- **Type**: Missing nuance / possible factual error
- **Location**: *"the README and compose file mount `/var/run/docker.sock`; README says it is needed for 'real infrastructure' such as RDS, ECS, Lambda containers."* and the 26.02 MB image size figure.
- **Problem**: RDS, ECS, and Lambda container execution via a Docker socket in a 26 MB image is a claim that deserves scrutiny. Either MiniStack delegates all heavy lifting to the Docker daemon (in which case the "emulation" is mostly a thin wrapper, not a genuine AWS emulator), or the size and service-coverage claims are inconsistent. The report does not reconcile this. If MiniStack's "RDS support" means spinning up a real RDS-compatible container via the Docker socket, that is architecturally very different from LocalStack's or Moto's approach and needs to be explained, not equated.
- **Impact**: Medium. The omission makes MiniStack's feature set look equivalent in kind to LocalStack's when it may be categorically different in implementation.

---

### Issue 4: LocalStack Lambda can be configured to run without Docker
- **Type**: Factual omission / Missing nuance
- **Location**: *"LocalStack is acceptable only for Terraform plans that stay away from Docker-backed services. If your Terraform apply path exercises Lambda locally, the Docker socket dependency is a major hardening failure."*
- **Problem**: LocalStack supports Lambda execution modes that do not require Docker. The `LAMBDA_EXECUTOR=local` environment variable (or the newer `LAMBDA_RUNTIME_ENVIRONMENT_TIMEOUT` / hot-reload configurations in recent versions) allows running Lambda handler code in-process or in a subprocess on the host without the Docker socket. The report presents the Docker socket as a binary requirement for any Lambda use in LocalStack, which is incorrect. This also means the gap between LocalStack and Floci on the Docker-socket axis is narrower than stated for teams that configure Lambda execution appropriately.
- **Impact**: High. This is the central practical hardening claim against LocalStack. Omitting a documented workaround materially weakens the comparative analysis.

---

### Issue 5: Moto's in-process library mode is not mentioned
- **Type**: Gap
- **Location**: The entire Moto section and the ranking rationale
- **Problem**: Moto's most common CI use is not `moto_server` at all — it is the Python decorator/context-manager API used in-process without any container. This is Moto's primary design and removes the container attack surface entirely for Python-based test runners. For teams using Python or Terratest with Python helpers, `@mock_aws` in-process mode is the strongest hardening story of any tool reviewed here. The report treats `moto_server` as the only relevant mode, which understates Moto's actual security position.
- **Impact**: Medium-High. Moto's rank as #2 is undersold if `moto_server` is the only comparison point, and the report's framing does not help a reader understand when Moto is actually #1.

---

### Issue 6: Image size conflated with attack surface
- **Type**: Missing nuance
- **Location**: *"Attack-surface size signals"* section header and the trade-offs note: *"MiniStack's smallest image does not translate into the safest runtime posture."*
- **Problem**: The report correctly notes that image size is not a security proxy in one sentence, then uses a table of compressed image sizes as an "attack surface signal." Image attack surface depends on the number and patch level of included packages, base image CVE history, and runtime behavior — not compressed bytes. A 26 MB Alpine image could contain an unpatched OpenSSL; a 96 MB Debian image could be fully patched. Without a CVE scan baseline (e.g., Trivy or Grype output), the size column is noise. The report does not run or cite any such scan.
- **Impact**: Low-Medium. The section is labeled "signals" rather than "findings," but readers may over-index on the size column when evaluating the four options.

---

### Issue 7: Evidence timestamps are relative to an unstated crawl date
- **Type**: Factual ambiguity
- **Location**: *"LocalStack Docker Hub `latest`: 468.8 MB compressed, updated 3 days ago in the crawl."* and all similar "updated N ago" citations.
- **Problem**: "3 days ago in the crawl" and "about 3 hours ago in the crawl" are relative to a crawl timestamp that is never specified. The reader cannot determine whether this evidence is current, weeks old, or months old. Docker Hub metadata is particularly volatile — image sizes and update times change with every push. Without an absolute date, these figures cannot be verified or cited downstream.
- **Impact**: Low-Medium. The image size figures look precise but are unanchored in time, which undermines their use as comparative evidence.

---

### Issue 8: LocalStack community vs. Pro image distinction is absent
- **Type**: Gap
- **Location**: All LocalStack sections
- **Problem**: LocalStack ships two images: `localstack/localstack` (community, free) and `localstack/localstack-pro` (paid). The Dockerfile and Docker Hub URL cited are for the community image. LocalStack Pro has different Lambda execution options, a different internal architecture, and potentially different filesystem layout. For a team evaluating hardened CI options, the Pro vs. community distinction matters because many real Terraform workflows hit services that are Pro-only (e.g., RDS, ECS). The report draws conclusions about LocalStack's Docker socket dependency without acknowledging that the community image's Lambda is far more constrained than the Pro image's, and that Pro users may have different configuration options.
- **Impact**: Medium. Teams evaluating LocalStack for production CI are often evaluating the Pro tier. The analysis may not apply to them.

---

### Issue 9: The MiniStack vs. LocalStack ranking justification is circular
- **Type**: Unsupported claim / Missing nuance
- **Location**: *"I rank LocalStack lower because its writable-path footprint is broader and its current official path is operationally more complex."*
- **Problem**: The report spends nearly equal space establishing that both MiniStack and LocalStack default to root, both require Docker socket for higher-fidelity features, and neither documents read-only rootfs support. The stated basis for ranking LocalStack below MiniStack — "broader writable-path footprint" and "more complex official path" — is asserted without a comparative measurement. What specific writable paths does LocalStack have that MiniStack does not? `/var/lib/localstack`, `/tmp/localstack`, and `/.npm` are named for LocalStack; `/tmp/ministack-data/s3` and `/docker-entrypoint-initaws.d` are named for MiniStack. The report does not count, compare, or score these systematically. The ranking conclusion may be correct, but the reasoning provided does not support it.
- **Impact**: Medium. A reader cannot evaluate whether the #3/#4 ordering is defensible or an artifact of unexamined assumptions.

---

### Issue 10: The `/.npm` path implication is under-analyzed
- **Type**: Missing nuance
- **Location**: *"the Dockerfile also prepares writable paths such as `/tmp/localstack` and `/.npm`"*
- **Problem**: A writable `/.npm` in a container suggests the runtime may install npm packages at startup — a significant security concern independent of the root-user question. Runtime package downloads mean the container's behavior depends on external registries at launch time, introduces a supply-chain risk window, and breaks air-gapped CI environments. This is a more actionable security concern than the read-only rootfs discussion, but the report mentions it only as an item in a list of writable paths without drawing the implication.
- **Impact**: Medium. For a platform team evaluating supply-chain risk in CI, this is a higher-priority finding than several of the ones that are expanded upon.

---

### Issue 11: Rootless container mode (Podman, user-namespace remapping) is not mentioned
- **Type**: Gap
- **Location**: The entire hardened-CI framing
- **Problem**: The report frames root-by-default as a static property of each image. In practice, platform teams running hardened CI commonly use Podman (which is rootless by default and runs containers as non-root on the host even when the image specifies root) or Docker with user-namespace remapping (`--userns-remap`). Under these runtimes, the `USER` directive in the Dockerfile becomes less critical because the host UID mapping provides the hardening boundary. The report's conclusion that Floci is the "clear best fit" because of its `USER 1001` directive implicitly assumes Docker without user-namespace remapping, but this assumption is not stated and many modern hardened CI runners do not share it.
- **Impact**: Medium. If the target runtime is Podman or user-namespace-remapped Docker, the ranking changes materially — the `USER` directive advantage that makes Floci #1 largely disappears.

---

### Issue 12: No discussion of network exposure defaults
- **Type**: Gap
- **Location**: Nowhere in the findings
- **Problem**: Hardened CI container policies typically also govern network exposure: which ports are published by default, whether services bind to `0.0.0.0` vs. `127.0.0.1`, and whether inter-container networking is needed. LocalStack by default binds to `0.0.0.0:4566`. The report does not compare default port exposure or binding behavior for any of the four tools. In a multi-tenant CI runner or shared Kubernetes namespace, this matters as much as the runtime user.
- **Impact**: Low-Medium. The gap does not invalidate the conclusions but leaves a practical hardening question unanswered.

---

## Summary

**Issues found**: 12

**Overall reliability**: **Medium-Low**

The findings are internally consistent on the narrow claim that Floci has the best-documented non-root posture among the four tools. The evidence for LocalStack and Moto is broadly credible and well-cited. The analysis breaks down in three places:

1. **The winner is unverified**: Floci's project legitimacy, maintenance health, and at least one key feature claim (ECS mock mode) are not supported by cited evidence. Recommending it as the "clear best fit" for a production CI hardening decision without establishing these basics is the most serious reliability problem.

2. **The primary alternative is undersold**: Moto's in-process library mode — its most common CI use — is absent from the comparison, which understates its actual hardening position for Python-centric stacks and makes the ranking less useful.

3. **A key LocalStack caveat is missing**: `LAMBDA_EXECUTOR=local` (or equivalent) is a documented path that removes the Docker socket requirement for Lambda, which is the central argument against LocalStack. Omitting it overstates the LocalStack-vs-Floci gap.

**What would most improve this research**:
- Verify Floci's project maturity (stars, contributors, release cadence, known production users) and the ECS mock mode claim with a direct doc citation.
- Add the LocalStack local-Lambda-executor configuration as a documented mitigation.
- Add Moto in-process mode as a comparison point.
- Run a container image CVE scan (Trivy or similar) on each image and replace the size table with that output.
- State the crawl date explicitly on all Docker Hub evidence.
