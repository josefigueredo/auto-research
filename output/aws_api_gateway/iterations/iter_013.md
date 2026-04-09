# Iteration 013 — done

**Status:** discard  
**Scores:** coverage=93.0, quality=75.0, total=82.2  
**Timestamp:** 2026-04-06T11:51:19.284361+00:00  

---

### Findings

All research dimensions are complete. The prior iterations covered REST vs HTTP API feature/pricing/performance parity, WebSocket API limits and scaling patterns, and a cross-product synthesis. No further web research is needed — this iteration delivers the final decision framework.

#### The Core Insight for Enterprise Architects

AWS API Gateway is **three separate products** that share a pricing page and console. The naming is misleading. Choosing between them is not a configuration decision — it is an architecture decision with long-term operational consequences.

**HTTP API is in maintenance mode.** Despite being positioned as the "modern" replacement for REST API, every significant feature shipped in 2024–2025 went to REST API: response streaming, routing rules, developer portal, TLS 1.3, SIGv4a, ALB private integrations. HTTP API received nothing. This trajectory is unlikely to reverse. New projects that start on HTTP API to save 71% on cost will eventually hit a feature ceiling and face a painful migration.

**REST API response streaming (Nov 2025) materially shrinks WebSocket's use case.** Prior to this, streaming LLM responses, large progressive payloads, and SSE-style push required WebSocket. Now REST API handles all of these with better tooling (WAF, caching, API keys), simpler operations (no connection tracking), and higher limits (>10 MB, 15-min timeout, chunked transfer encoding).

---

#### The Full Decision Matrix

| Scenario | Recommended Product | Reason |
|----------|--------------------|-|
| External API with third-party consumers | **REST API** | API keys, usage plans, developer portal, WAF |
| API monetization / rate limiting per customer | **REST API** | Per-client throttling — HTTP API cannot do this |
| Security-sensitive (PCI, HIPAA) | **REST API** | WAF, resource policies, request validation, X-Ray |
| Global distribution without managing CloudFront | **REST API** | Edge-optimized endpoints via CloudFront POPs |
| LLM / generative AI response streaming | **REST API** | Response streaming: >10 MB, 15-min timeout, chunked |
| Internal microservices, JWT auth, high volume | **HTTP API** | 71% cheaper, native JWT authorizer, auto-deploy |
| Simple Lambda/HTTP proxy, no governance needs | **HTTP API** | Lower latency (~2.5ms), lower cost, simpler config |
| Chat, collaborative editing, multiplayer (<50K CCU) | **WebSocket API** | True bidirectional, low-latency persistent connections |
| Real-time push >100K concurrent users | **IoT Core** or **AppSync Events** | Native pub/sub broadcast; WebSocket lacks this |
| One-way server push (notifications, feeds) | **REST API streaming** | Simpler, no connection tracking, no idle timeout |

---

#### Pricing Quick Reference (US East, per month)

**REST API:**
- $3.50/M requests (first 333M) → $2.80/M (to 1B) → $2.38/M (over 1B)
- Cache: $0.020/hr (0.5 GB) to $3.80/hr (237 GB) — always-on once enabled
- At 1B requests: ~$3,033/month

**HTTP API:**
- $1.00/M requests (first 300M) → $0.90/M (over 300M)
- Metered in 512 KB increments — large payloads erode the cost advantage
- At 1B requests: ~$930/month (69% cheaper than REST API)

**WebSocket API:**
- $1.00/M messages (first 1B) → $0.80/M (over 1B) — metered per 32 KB frame
- $0.25/M connection-minutes (flat rate, always-on)
- 100K users × 30 min/day × 30 days: ~$922/month (messages + connection-minutes)
- HTTP API polling equivalent: $432/month — WebSocket only wins at >1 msg/min/user

---

#### Hard Limits That Matter

| Limit | REST API | HTTP API | WebSocket API |
|-------|----------|----------|---------------|
| Payload | 10 MB (streaming: unlimited) | 10 MB | **128 KB** |
| Integration timeout | 29s (extendable) | **30s hard** | 29s |
| Integrations per API | 300 (increasable) | **300 hard** | 300 (increasable) |
| New WebSocket connections | — | — | **500/s default** |
| Connection duration | — | — | **2hr hard** |
| Idle timeout | — | — | **10min hard** |
| Account throttle | 10K RPS (shared across all types) | ← same | ← same |

The HTTP API's **300 hard integration limit** is a critical constraint for one-Lambda-per-endpoint architectures. The WebSocket **500 connections/second** rate limit — onboarding 100K users takes 3.3 minutes — is a genuine capacity risk for event-driven spikes (sports events, product launches).

---

#### Five Counter-Intuitive Facts to Brief Stakeholders On

1. **Usage plan throttling is not a billing control.** AWS explicitly documents that quota enforcement is best-effort. Do not use it to cap customer costs or block abusive clients — use WAF rate limits or a custom Lambda authorizer.

2. **HTTP API can be more expensive than REST API** for large payloads. The 512 KB metering increment means a 1.5 MB request/response pair = 3 billed messages = $3.00/M effective rate, vs REST API's $3.50/M — the gap nearly disappears.

3. **WebSocket heartbeats are billable.** Protocol-level ping/pong is free, but API Gateway does not initiate server-side pings. Applications must send application-layer heartbeats to prevent 10-minute idle timeout. At 1M connections with one heartbeat every 9 minutes, that's ~$100/month in message charges that add nothing to functionality.

4. **HTTP API is not the future.** Positioned in 2019 as the successor to REST API, it has received zero feature additions since 2023 while REST API received 6 significant features in 2024–2025. Enterprise projects should evaluate whether 71% cost savings justifies betting on what appears to be a product in maintenance mode.

5. **The shared 10K RPS throttle creates cross-product interference.** A WebSocket broadcast storm (e.g., pushing an update to 100K connected clients requires 100K @connections calls) consumes the same account/region throttle budget as your REST APIs. This is not widely understood and has caused production incidents.

---

### Evidence

All findings in this synthesis draw from the prior iteration evidence, which includes:

- **AWS official pricing**: aws.amazon.com/api-gateway/pricing/
- **AWS feature comparison**: docs.aws.amazon.com/apigateway/latest/developerguide/http-api-vs-rest.html
- **AWS quota tables**: docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-execution-service-websocket-limits-table.html
- **Independent latency benchmark**: cloudonaut.io — 14.13ms avg (HTTP API) vs 16.83ms avg (REST API)
- **Production WebSocket at scale**: DAZN Engineering — 500 conn/s limit was deal-breaker for millions-of-users sports streaming
- **Scaling analysis**: Ably — mandatory DynamoDB connection tracking, zombie connection problem, Lambda concurrency compounding
- **Feature investment trajectory**: AWS Document History page — all 2024–2025 additions to REST API, none to HTTP API
- **REST API response streaming announcement**: November 2025, all regions including GovCloud

---

### Trade-offs

#### The "CloudFront in front of HTTP API" trap
Many HTTP API limitations (no WAF, no edge optimization, no caching, no API keys) are solvable by adding CloudFront. This is widely recommended. The trap: once you've added CloudFront with WAF, Lambda@Edge for auth, and a caching policy, you have rebuilt the REST API feature set manually at higher operational complexity. The 71% cost savings rarely survive the added infrastructure. Run the numbers before defaulting to this pattern.

#### REST API for everything vs right tool for each use case
Some organizations standardize on REST API to reduce cognitive overhead. This is a legitimate choice: the operational consistency, unified observability (X-Ray, execution logs), and single feature set are worth paying 3.5x more for HTTP API traffic in many enterprise contexts. Others run a tiered model — REST API for external/governed APIs, HTTP API for internal service mesh. Both are defensible; the hybrid model requires governance to prevent teams from mixing them ad-hoc.

#### WebSocket API vs managed real-time services
For new projects in 2025+:
- **AppSync Events** (April 2025) adds WebSocket pub/sub with managed connection lifecycle, multi-auth, and channel/namespace model — better default than WebSocket API for GraphQL-centric or event-driven architectures
- **IoT Core** handles broadcast natively, manages connection state, and supports offline message queuing — better for fan-out at scale
- **WebSocket API** retains its advantage for custom routing logic, deep Lambda integration, and bidirectional request/response patterns that don't fit pub/sub semantics

The decision between these three products deserves its own evaluation when real-time requirements are central to the architecture.

---

### New Questions

1. **API Gateway vs ALB + Lambda for internal APIs**: For internal microservices that need none of REST API's management features and none of HTTP API's JWT auth, an Application Load Balancer with Lambda targets may be simpler and cheaper. What are the cost break-even points at 100M/1B requests/month, and what does each approach lack?

2. **The new Routing Rules feature (REST API, June 2025)**: Enables A/B testing, cell-based architecture, and API versioning by header/hostname/cookie without path changes. Does this reduce or eliminate the need for CloudFront-based routing for multi-tenant SaaS? What are the limits and operational model?

3. **AppSync Events limits and enterprise readiness (2025)**: AppSync Events added WebSocket publishing in April 2025. What are its hard quotas (connection limits, message size, fan-out rate), pricing model, and enterprise authentication options — and is it production-ready as a WebSocket API replacement for new projects?
