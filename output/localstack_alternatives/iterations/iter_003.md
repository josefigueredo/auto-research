# Iteration 003 — Docker image size, startup time, and resource usage

**Status:** keep  
**Scores:** coverage=67.5, quality=67.5, total=67.5  
**Timestamp:** 2026-04-08T16:41:13.513320+00:00  

---

### Findings

For this dimension, the cleanest practical split is:

- **Floci** has the strongest published footprint story for a full multi-service emulator.
- **MiniStack** is still lightweight, but its published size numbers are inconsistent across its own properties.
- **Moto server mode** is usable as a Dockerized endpoint, but I could not find current official startup or memory benchmarks.
- **ElasticMQ** is the lightest serious option if you only need SQS, especially with its **native** image.

On **actual Docker image size**, the current published Docker Hub metadata is:

- **MiniStack**: `nahuelnucera/ministack:latest` is **26.02 MB compressed** for `linux/amd64` on the Docker Hub tags page, while MiniStack’s own GitHub README now says **~200 MB** and its website says **~250 MB**. This is the biggest discrepancy I found. The most likely explanation is **compressed transfer size on Docker Hub vs rounded installed/unpacked size in project marketing**, but the project does not currently explain that difference explicitly. [Docker Hub tags](https://hub.docker.com/r/nahuelnucera/ministack/tags), [GitHub README](https://github.com/Nahuel990/ministack), [site](https://ministack.org/)
- **Floci**: Docker Hub currently lists **69 MB** for `hectorvent/floci:latest`, while Floci’s own README/site consistently say **~90 MB**. Same likely explanation: Hub is showing compressed image size, while the project is quoting a round-number packaged/runtime size. [Docker Hub](https://hub.docker.com/r/hectorvent/floci), [GitHub README](https://github.com/floci-io/floci), [site](https://floci.io/)
- **Moto server**: `motoserver/moto:latest` is **96.69 MB compressed** for `linux/amd64`. I did not find an official second source that publishes the size numerically, only docs confirming this is the official Docker image. [Docker Hub tags](https://hub.docker.com/r/motoserver/moto/tags), [Moto server docs](https://docs.getmoto.org/en/latest/docs/server_mode.html)
- **ElasticMQ JVM**: `softwaremill/elasticmq:latest` is **226.08 MB compressed** for `linux/amd64`; the official README and Docker Hub overview describe it as about **240 MB**. [Docker Hub tags](https://hub.docker.com/r/softwaremill/elasticmq/tags), [GitHub README](https://github.com/softwaremill/elasticmq), [Docker Hub overview](https://hub.docker.com/r/softwaremill/elasticmq)
- **ElasticMQ native**: `softwaremill/elasticmq-native:latest` is **31.08 MB compressed** for `linux/amd64`; the official README and Docker Hub overview describe it as about **30 MB**. [Docker Hub tags](https://hub.docker.com/r/softwaremill/elasticmq-native/tags), [GitHub README](https://github.com/softwaremill/elasticmq), [Docker Hub overview](https://hub.docker.com/r/softwaremill/elasticmq-native)

For **cold-start behavior in CI-like environments**, only Floci and MiniStack publish direct numbers:

- **Floci** claims **~24 ms startup** and frames that as a native-binary advantage. Its README/site are explicit that this is from its own benchmark suite against LocalStack. That is the strongest published startup number in this set. [GitHub README](https://github.com/floci-io/floci), [site](https://floci.io/)
- **MiniStack** claims **under 2 seconds** in the README, while another comparison table in the same README says **`<1s`**. A MiniStack-authored GitHub Actions example uses `sleep 2` before health-checking, which is at least directionally consistent with “low single-digit seconds,” not tens of seconds. [GitHub README](https://github.com/Nahuel990/ministack), [DEV post with Actions example](https://dev.to/nahuel990/localstack-is-dead-ministack-runs-real-databases-for-free-1lim)
- **Moto server** has no current official startup benchmark that I could verify. What I did find is multiple community examples that wait **5 seconds** before running bootstrap code against Moto. That is not a benchmark, but it is a useful practical signal: users treat Moto as something that may need a short readiness buffer in containerized workflows. [Moto server docs](https://docs.getmoto.org/en/latest/docs/server_mode.html), [community example 1](https://qiita.com/lqqtotzo/items/8383388e207c3e9701fb), [community example 2](https://qiita.com/pban/items/93644f40957598f7a74a)
- **ElasticMQ native** does not publish a CI-container benchmark, but the official project documentation repeatedly says **“milliseconds instead of seconds”** for native startup, versus **seconds** for the full JVM image. That is credible and consistent with the image design, but it is still vendor-published and not tied to a named CI runner. [GitHub README](https://github.com/softwaremill/elasticmq), [Docker Hub native overview](https://hub.docker.com/r/softwaremill/elasticmq-native)

For **memory and CPU footprint**, the evidence is uneven:

- **Floci** publishes the best current numbers: **~13 MiB idle memory**, plus moderate-load indicators of **289 Lambda requests/sec** and **2 ms average warm latency**. I did **not** find a published CPU-percent benchmark. [GitHub README](https://github.com/floci-io/floci), [site](https://floci.io/)
- **MiniStack** publishes **~30 MB idle RAM** in one place and **~40 MB** in another comparison table; a newer MiniStack-authored benchmark post says **39 MB after load**. I found no current published CPU-percent figure. [GitHub README](https://github.com/Nahuel990/ministack), [site](https://ministack.org/), [benchmark post](https://dev.to/nahuel990/ministack-vs-floci-vs-localstack-honest-performance-benchmark-april-3rd-2026-479p)
- **Moto server**: I found no current official idle-memory, loaded-memory, or CPU benchmark. The strongest defensible statement is that Moto server mode exists and is meant for non-Python SDKs, but its performance footprint is not being actively marketed with current numbers. [Moto server docs](https://docs.getmoto.org/en/latest/docs/server_mode.html)
- **ElasticMQ**: I found no current official numeric RAM figure for either the JVM or native image. The official project only says native has a **lower baseline memory footprint** than JVM. What it does publish is useful moderate-load throughput: about **2,540 req/s** at 20 threads and **2,600 req/s** at 40 threads through the SQS REST interface, on an old 2012 MacBook Pro. That is old hardware and not container-specific, but it is still a meaningful lower-bound signal for queue-heavy CI tests. [GitHub README](https://github.com/softwaremill/elasticmq)

The most surprising result is that **the “actual image size” depends heavily on which metric you mean**. For MiniStack and Floci, Docker Hub’s current published transfer sizes are materially smaller than the projects’ own headline image-size claims. For an architect optimizing **CI pull time**, Docker Hub compressed size is usually the more relevant number. For disk pressure on runners after unpacking, the larger README/site numbers may be closer to what matters. Neither project currently documents the distinction clearly.

Another non-obvious point: **ElasticMQ native is the footprint winner if SQS is enough**. Its current compressed image is about **31 MB**, with official startup claims in **milliseconds**. That is substantially lighter than every multi-service option here. If your pipeline mostly needs queue semantics, this is still the most efficient OSS path I found.

### Evidence

Current published image sizes and runtime claims:

| Tool | Image | Published Docker size | Startup | Idle memory | Moderate-load data |
|---|---|---:|---|---|---|
| MiniStack | `nahuelnucera/ministack:latest` | **26.02 MB compressed** on Docker Hub; project says **~200-250 MB** | **under 2s**; same README also says **<1s** in comparison table | **~30 MB**; same README also says **~40 MB** | founder benchmark says **39 MB after load** |
| Floci | `hectorvent/floci:latest` | **69 MB** on Docker Hub; project says **~90 MB** | **~24 ms** | **~13 MiB** | **289 Lambda req/s**, **2 ms** warm latency |
| Moto server | `motoserver/moto:latest` | **96.69 MB compressed** | no official benchmark found | no official benchmark found | no official benchmark found |
| ElasticMQ JVM | `softwaremill/elasticmq:latest` | **226.08 MB compressed**; project says **~240 MB** | **seconds** | no numeric figure found | **~2540 req/s** at 20 threads; **~2600 req/s** at 40 threads |
| ElasticMQ native | `softwaremill/elasticmq-native:latest` | **31.08 MB compressed**; project says **~30 MB** | **milliseconds** | no numeric figure found | same queue engine; native image is positioned as lower-baseline-footprint |

Practical CI-readiness signals I could verify:

- **MiniStack**: published GitHub Actions example waits **2 seconds** before probing health. [source](https://dev.to/nahuel990/localstack-is-dead-ministack-runs-real-databases-for-free-1lim)
- **Floci**: a community migration article also uses **`sleep 2`** after starting the container, despite the official 24 ms claim. That suggests teams may still keep a conservative buffer in generic CI scripts. [source](https://dev.to/peytongreen_dev/your-localstack-ci-is-broken-here-are-your-three-options-41o8)
- **Moto**: multiple community bootstrapping examples wait **5 seconds** after startup before seeding Cognito resources. [source 1](https://qiita.com/lqqtotzo/items/8383388e207c3e9701fb), [source 2](https://qiita.com/pban/items/93644f40957598f7a74a)
- **ElasticMQ**: the project exposes a `/health` endpoint for orchestrators, and official docs say native starts in milliseconds. I did not find a community CI example with explicit timing numbers. [source](https://github.com/softwaremill/elasticmq)

### Trade-offs

**Floci**
- Better when CI pull time, startup latency, and idle memory are the primary decision drivers for a multi-service emulator.
- Worse when you need independently replicated benchmarks; nearly all strong numbers are still project-published.
- Practical read: strongest current candidate for ephemeral CI jobs if you accept young-project risk.

**MiniStack**
- Better when you want a broader all-in-one emulator but still care about footprint.
- Worse when you need clean, stable performance claims. Its own docs currently disagree on image size, startup time, and idle RAM.
- Practical read: probably still light enough for CI, but the metrics need independent validation before using them in an architecture review.

**Moto server**
- Better when your team already accepts Moto’s model and just needs a Dockerized endpoint, especially for mixed-language SDK tests.
- Worse when startup predictability and measured resource footprint matter. I could not verify current official numbers.
- Practical read: acceptable for functional mocking, weak for a footprint-driven selection argument.

**ElasticMQ**
- Better when you only need SQS.
- Worse when you need a LocalStack-like multi-service replacement; it is not one.
- Practical read: if the architecture can decompose local emulation by service, **ElasticMQ native** is the most efficient CI component in this group.

### New Questions

1. How much do these tools’ published footprint numbers change once you enable their heavier features: Lambda containers, RDS/Redis sidecars, persistence, and seeded test data?
2. For CI cost, what matters more in practice: **compressed pull size** or **expanded on-runner disk/RAM footprint** for each image?
3. Would a composed stack such as **ElasticMQ + S3Mock + Dynalite** beat Floci/MiniStack on total CI runtime and stability for common app workloads?

One gap remains: I found strong published footprint data for Floci, partial but inconsistent data for MiniStack, and very limited current numeric memory/startup data for Moto and ElasticMQ beyond image size and ElasticMQ’s own throughput/startup claims. That limits how hard I can compare idle/load resource use across all four without running fresh benchmarks, which your constraints did not allow.

---

## Peer Review (claude)

### Issue 1: MiniStack's 10x compression ratio is not explained and likely wrong

- **Type**: Missing nuance / unsupported claim
- **Location**: "The most likely explanation is compressed transfer size on Docker Hub vs rounded installed/unpacked size in project marketing"
- **Problem**: A 26 MB compressed → 200–250 MB unpacked ratio implies roughly 8–10x compression. Typical Docker layer compression (gzip) achieves 2–4x for mixed workloads. A 10x ratio is anomalous and suggests the explanation is incomplete or wrong. More plausible alternatives not considered: the Docker Hub image is a different, stripped variant not representative of the full product; the README figure refers to a different architecture or a bundled multi-arch manifest; or the README is simply stale. The research acknowledges the discrepancy but accepts an explanation that doesn't fit the math.
- **Impact**: High. This is labeled the "biggest discrepancy" and the explanation given may mislead an architect comparing CI pull times to on-runner disk costs.

---

### Issue 2: Floci's 24 ms startup benchmark has no disclosed methodology

- **Type**: Missing nuance / unsupported claim
- **Location**: "Floci claims ~24 ms startup and frames that as a native-binary advantage. Its README/site are explicit that this is from its own benchmark suite against LocalStack."
- **Problem**: The benchmark is vendor-published, run against LocalStack (not the other tools in this comparison), on undisclosed hardware, with no stated definition of what "startup" means (process launch? first successful API response? health endpoint ready?). Container cold-start in CI also depends on image pull, layer extraction, and DNS, none of which are captured in a process-launch timer. The research calls this "the strongest published startup number in this set" without flagging these limitations.
- **Impact**: High. Treating a vendor benchmark of unknown methodology as the primary differentiator for CI selection overstates confidence significantly.

---

### Issue 3: The community `sleep 2` for Floci is treated as a minor footnote rather than a substantive contradiction

- **Type**: Missing nuance / contradiction
- **Location**: "a community migration article also uses `sleep 2` after starting the container, despite the official 24 ms claim. That suggests teams may still keep a conservative buffer in generic CI scripts."
- **Problem**: If Floci genuinely became API-ready in 24 ms, no CI practitioner would write `sleep 2`. The more parsimonious reading is that real-world container readiness (including layer extraction, Docker networking, JIT, service init) is materially longer than the claimed figure, and the 24 ms measures something narrower than "container is ready to receive API calls." The research softens this into "conservative buffer," but it is in fact direct behavioral evidence that the 24 ms claim does not translate to container-ready time.
- **Impact**: High. This contradicts the core Floci CI argument and should be surfaced as a primary finding, not a parenthetical.

---

### Issue 4: The Moto 5-second wait is Cognito-specific, not general Moto startup behavior

- **Type**: Missing nuance / overgeneralization
- **Location**: "multiple community examples that wait 5 seconds before running bootstrap code against Moto... users treat Moto as something that may need a short readiness buffer"
- **Problem**: Both cited sources are Qiita articles that specifically initialize Cognito user pools. Cognito is one of the more complex Moto service simulations. Inferring general Moto startup behavior from Cognito-specific initialization scripts is an overgeneralization. Moto's SQS or S3 mock may be ready much faster; Cognito initialization may involve extra processing. The research uses these two data points to characterize Moto's general CI readiness posture.
- **Impact**: Medium. It unfairly penalizes Moto's startup story for a service-specific initialization cost.

---

### Issue 5: ElasticMQ throughput benchmarks are presented as CI-relevant despite being run on 2012 MacBook Pro hardware

- **Type**: Missing nuance
- **Location**: "about 2,540 req/s at 20 threads and 2,600 req/s at 40 threads through the SQS REST interface, on an old 2012 MacBook Pro. That is old hardware and not container-specific, but it is still a meaningful lower-bound signal"
- **Problem**: The benchmark is from a README that has not been updated with modern hardware numbers. A 2012 MacBook Pro is roughly 12–13 years old at time of writing. Modern CI runners (GitHub Actions ubuntu-latest, etc.) have significantly different I/O and CPU profiles. Calling this a "meaningful lower-bound signal" is a stretch — it could just as easily be a floor from hardware that no longer exists in any production CI context. More importantly, these are throughput numbers, not latency or startup numbers, so they address a different dimension than the rest of the comparison.
- **Impact**: Medium. Presenting hardware-obsolete benchmarks without a stronger caveat introduces false precision into the comparison.

---

### Issue 6: Service coverage comparison is entirely absent

- **Type**: Gap
- **Location**: Throughout — particularly in the opening summary ("Floci has the strongest published footprint story for a full multi-service emulator") and in trade-offs
- **Problem**: The research never enumerates which AWS services each tool supports. This is foundational to the "footprint story" framing. A 69 MB image emulating 5 services is not comparable to one emulating 30. Calling Floci "the strongest... full multi-service emulator" without listing supported services is an unsupported claim. Similarly, the comparison between Floci's Lambda throughput and ElasticMQ's SQS throughput (in the table) compares fundamentally different workloads.
- **Impact**: High. An architect selecting a tool needs service coverage before footprint. Omitting it makes the comparison incomplete for any real decision.

---

### Issue 7: LocalStack Community Edition is absent from the comparison

- **Type**: Gap
- **Location**: The framing throughout positions these tools as alternatives to LocalStack, but no LocalStack baseline is included
- **Problem**: LocalStack has a free Community Edition (open-source) with Docker image and startup characteristics. If the purpose of the research is to help teams choose a LocalStack alternative, the reader needs to know what they're comparing against. Without a LocalStack row in the evidence table, there is no way to evaluate whether the "alternatives" actually improve on the tool they are positioned to replace.
- **Impact**: High. This is the single most important missing baseline for the stated use case.

---

### Issue 8: `nahuelnucera/ministack` is a personal Docker Hub namespace, not an organization account

- **Type**: Missing nuance
- **Location**: "MiniStack: `nahuelnucera/ministack:latest`"
- **Problem**: The image is published under a personal Docker Hub username rather than an organization namespace (e.g., `ministack/ministack`). This is a meaningful difference for production or CI use: personal accounts have no SLA, no organization-level access controls, and a higher risk of abandonment or accidental deletion. The research presents this as the authoritative image without flagging the governance implication.
- **Impact**: Low-medium. Relevant to any team assessing long-term maintenance risk.

---

### Issue 9: The "founder benchmark" cited for MiniStack is from April 3, 2026 — 5 days before the analysis date

- **Type**: Missing nuance
- **Location**: "a newer MiniStack-authored benchmark post says 39 MB after load" with date "April 3rd, 2026" in the URL
- **Problem**: A self-authored benchmark published five days before the analysis has had no time for community review, replication, or criticism. It is not treated differently from older, more established citations. The research uses it to adjudicate among MiniStack's own inconsistent figures ("~30 MB" vs "~40 MB" vs "39 MB"), but a brand-new founder post is the weakest possible tie-breaker.
- **Impact**: Medium. The freshness of this source is relevant to reliability and should be disclosed explicitly.

---

### Issue 10: Floci's Lambda throughput figure is not comparable to ElasticMQ's SQS throughput figure

- **Type**: Missing nuance / misleading framing
- **Location**: In the evidence table — Floci row: "289 Lambda req/s, 2 ms warm latency"; ElasticMQ rows: "~2540 req/s at 20 threads; ~2600 req/s at 40 threads"
- **Problem**: Lambda invocations and SQS message sends/receives are architecturally different operations with different costs. Presenting them in the same "moderate-load data" column implies they are comparable metrics. A reader could incorrectly infer that ElasticMQ is ~9x faster than Floci, when the two numbers measure unrelated things.
- **Impact**: Medium. Misleads direct comparison in the evidence table.

---

### Issue 11: The claim that Floci's startup benchmark is "against LocalStack" is not the same as being against the other tools compared here

- **Type**: Missing nuance
- **Location**: "Its README/site are explicit that this is from its own benchmark suite against LocalStack. That is the strongest published startup number in this set."
- **Problem**: The benchmark compares Floci to LocalStack, not to MiniStack, Moto, or ElasticMQ. "Strongest number in this set" is technically true only because the other tools don't publish equivalent figures — but the benchmark was not designed to answer the comparative question this research is investigating. There is no cross-tool startup benchmark with controlled methodology anywhere in these findings.
- **Impact**: Medium. The framing conflates "they published a number" with "the number is valid for this comparison."

---

### Issue 12: The research does not disclose when the community sources (Qiita articles) were written

- **Type**: Missing nuance / gap
- **Location**: "community example 1" and "community example 2" on Qiita cited for Moto 5-second waits
- **Problem**: Qiita articles are not dated in the citations. Moto has had significant development activity and these could be several years old, referring to an older version with different performance characteristics. Without dates, the "practical signal" value is unknowable.
- **Impact**: Low-medium. Affects reliability of the Moto startup characterization.

---

## Summary

**Issues found**: 12

**Overall reliability**: **Medium-low**

The research is methodologically transparent about its limitations (vendor-published numbers, missing benchmarks) and the evidence table is well-structured. However, the **analytical judgments drawn from that evidence are frequently stronger than the evidence warrants** — particularly for Floci, where vendor consistency is conflated with factual accuracy.

**What would most improve the findings, in priority order**:

1. **Add LocalStack Community Edition as the baseline row** — without it, the "alternatives" framing has no anchor.
2. **Add a service-coverage table** — which services each tool emulates is more fundamental than any footprint number.
3. **Reframe the Floci 24 ms claim** — the community `sleep 2` behavior is not a footnote; it is the most actionable real-world signal and directly undermines the headline claim.
4. **Investigate the MiniStack 10x compression anomaly** rather than accepting the "compressed vs. unpacked" explanation at face value.
5. **Date all third-party community sources** so readers can weight their relevance.
