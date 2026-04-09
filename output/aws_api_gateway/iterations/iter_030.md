# Iteration 030 — done

**Status:** discard  
**Scores:** coverage=93.0, quality=50.0, total=67.2  
**Timestamp:** 2026-04-06T11:32:11.250887+00:00  

---

## Synthesis: AWS API Gateway — Enterprise Decision Guide

All planned research dimensions have been completed. This is the final synthesis for a senior cloud architect.

---

### Executive Summary

API Gateway offers three distinct products: **REST API**, **HTTP API**, and **WebSocket API**. The decision matrix has shifted significantly in 2025 due to REST API response streaming (Nov 2025) and AppSync Events WebSocket support (Apr 2025). The TL;DR:

- **REST API** is the enterprise default for external-facing APIs. AWS is actively investing in it; HTTP API is in maintenance mode.
- **HTTP API** is narrowly correct for high-volume internal JWT-authed microservices with simple proxy patterns and payloads under ~1.5 MB.
- **WebSocket API** is the right choice for bidirectional real-time at moderate scale (<50K concurrent). Above that, managed alternatives (IoT Core, AppSync Events) are operationally superior.

---

### Findings

#### Product Positioning Reality (2025)

The conventional wisdom — "HTTP API is the modern replacement for REST API" — is **wrong** as of 2024–2025. AWS has added every significant feature to REST API: response streaming, routing rules, developer portal, TLS 1.3, SIGv4a, ALB private integrations, custom domains for private APIs. HTTP API received no new features in this period. The feature gap is widening.

This matters for architectural decisions: teams choosing HTTP API to be "future-proof" are betting on a product receiving no investment.

#### Full Feature Matrix (Consolidated)

| Capability | REST API | HTTP API | WebSocket API |
|-----------|----------|----------|---------------|
| AWS WAF integration | Yes | No | No |
| Resource policies | Yes | No | No |
| API keys + usage plans | Yes | No | No |
| Per-client throttling | Yes | No | No |
| Response caching | Yes | No | No |
| Request validation | Yes | No | No |
| Request/response transforms | Yes | No | No |
| Canary deployments | Yes | No | No |
| Response streaming (>10MB, 15min) | Yes (Nov 2025) | No | No |
| Routing rules (A/B, cell-based) | Yes (Jun 2025) | No | No |
| Developer portal | Yes (Nov 2025) | No | No |
| X-Ray tracing | Yes | No | No |
| Execution logs | Yes | No | No |
| Edge-optimized endpoints | Yes | No | No |
| Private endpoints | Yes | No | No |
| Native JWT authorizer | No | **Yes** | No |
| Automatic deployments | No | **Yes** | No |
| Cloud Map integration | No | **Yes** | No |
| Bidirectional persistent connections | No | No | **Yes** |
| Route-based message dispatch | No | No | **Yes** |
| mTLS | Yes | Yes | No |
| IAM auth | Yes | Yes | Yes |
| Lambda authorizer | Yes | Yes | Yes ($connect only) |
| VPC Link | Yes | Yes | Yes |
| Regional endpoints | Yes | Yes | Yes |

#### Pricing Comparison (US East, all values current as of Apr 2026)

**REST API vs HTTP API:**

| Monthly Requests | REST API | HTTP API | REST API Premium |
|-----------------|----------|----------|-----------------|
| 1M | $3.50 | $1.00 | +250% |
| 100M | $350 | $100 | +250% |
| 1B | $3,033 | $930 | +226% |

REST API is 2.5–3x more expensive per request at all scales. For a 100M-request/month workload, that's **$250/month** — significant but often dwarfed by Lambda, RDS, or egress costs. The calculus changes if you're running a high-volume API: at 10B requests/month, REST API costs ~$30K vs ~$9K for HTTP API.

**HTTP API payload trap:** HTTP API meters in 512 KB increments. Request+response payloads exceeding ~1.5 MB flip the economics — HTTP API becomes **more expensive** than REST API. This affects file upload/download APIs and LLM-response APIs with large outputs.

**WebSocket API:**

| Scale | Messages (10/min, 30min/day) | Connection-Minutes | Total/Month |
|-------|------------------------------|-------------------|-------------|
| 10K concurrent | 90M ($90) | 9M ($2.25) | **$92** |
| 100K concurrent | 900M ($900) | 90M ($22.50) | **$923** |
| 1M concurrent | 9B ($7,400) | 900M ($225) | **$7,625** |

WebSocket fan-out hidden cost: broadcasting 10 updates/minute to 100K users = 1B additional messages/month = **$800+** on top of the base cost.

**Break-even vs polling:**
- REST API polling (every 6s): 100K users → 432M requests/month → $1,404
- HTTP API polling (every 6s): 100K users → 432M requests/month → $432
- WebSocket API: 100K users, 10 msg/min → $923

WebSocket beats REST API polling economically at >1 message/minute/user. WebSocket loses to HTTP API polling at <1 message/minute/user (idle connection-minutes dominate).

#### Hard Limits Summary

| Limit | REST API | HTTP API | WebSocket API |
|-------|----------|----------|---------------|
| Payload size | 10 MB | 10 MB | 128 KB (32 KB frames) |
| Streaming payload | >10 MB (Nov 2025) | No | N/A |
| Integration timeout | 50ms–29s (extendable) | 30s (hard) | 29s (hard) |
| Account throttle | 10K RPS / 5K burst | 10K RPS / 5K burst | Shared pool |
| Integrations per API | 300 (increasable) | **300 (hard limit)** | 300 (increasable) |
| Connection duration | N/A | N/A | 2 hours (hard) |
| Idle timeout | N/A | N/A | 10 min (hard) |
| New connections/sec | N/A | N/A | 500/s (increasable) |

The **HTTP API 300-integration hard limit** is non-negotiable — AWS will not increase it. For one-Lambda-per-endpoint architectures with >300 endpoints, HTTP API is disqualifying.

The **WebSocket 500 connections/second** default creates a serious bottleneck for bursty workloads. At 500 conn/s, onboarding 100K users takes 3.3 minutes. Increasing this requires manual AWS engagement and can take 2+ weeks even with Enterprise Support.

#### The Shared Throttle Problem

REST API, HTTP API, and WebSocket API in the same account/region **share the 10K RPS / 5K burst quota**. A WebSocket broadcast storm — e.g., pushing a message to 100K connections at once — consumes 10K RPS for 10 seconds minimum on the @connections callback API, throttling all other API traffic in your account during that window. This is a critical architecture concern for multi-product AWS accounts.

---

### Evidence

**Pricing:** AWS API Gateway Pricing page — REST $3.50/$2.80/$2.38/M (tiered), HTTP $1.00/$0.90/M, WebSocket $1.00/$0.80/M messages + $0.25/M connection-minutes.

**Limits:** AWS docs (apigateway-execution-service-websocket-limits-table) — 500 conn/s adjustable, 2hr hard, 10min idle hard, 32KB frame / 128KB payload hard.

**Feature matrix:** AWS official comparison (docs.aws.amazon.com/apigateway/latest/developerguide/http-api-vs-rest.html) — authoritative enumeration of per-product features.

**Feature investment trajectory:** AWS API Gateway Document History and What's New (2024–2025) — every new feature (streaming, routing rules, developer portal, TLS 1.3, SIGv4a) went to REST API; HTTP API received zero.

**Latency benchmark:** cloudonaut.io (m5.large, k6, Lambda) — HTTP API 14.13ms avg vs REST API 16.83ms avg; ~2.5ms difference, real but negligible vs backend latency.

**REST API streaming:** AWS announcement Nov 2025 — payloads >10MB, 15-minute timeout, improved TTFB, all regions including GovCloud.

**AppSync Events WebSocket:** AWS announcement Apr 2025 — managed connection lifecycle, multi-auth (IAM, Lambda, Cognito), channel/namespace pub-sub model.

**Production WebSocket at scale:** DAZN Engineering blog — 500 conn/s cap was "deal-breaker" for millions of concurrent sports fans; mandatory connection tracking via DynamoDB; no native broadcast means N API calls per broadcast.

**Ably scaling analysis** — zombie connection problem, Lambda concurrency limits compound at scale, DynamoDB required for connection state, no built-in fan-out.

**Throttle in smaller regions:** Africa (Cape Town), Europe (Milan), Asia Pacific (Jakarta), Middle East (UAE) — default 2,500 RPS / 1,250 burst, not 10K/5K.

---

### Trade-offs

#### Decision Matrix: Which Product for Which Workload

**Use REST API when:**
- API is consumed by third parties (API keys, usage plans, developer portal are non-negotiable)
- Security posture requires WAF, resource policies, or request validation for defense-in-depth
- Clients are globally distributed (edge-optimized endpoints via CloudFront POPs; HTTP API has no equivalent)
- You need response streaming for LLM outputs or large payloads (>10MB, up to 15-min timeout)
- Debugging requires execution logs and X-Ray tracing
- You need canary deployments for production traffic migration
- Operations that run >29 seconds (regional/private REST API timeout is extendable; HTTP API is hard at 30s)

**Use HTTP API when:**
- Internal microservice-to-microservice communication only (never external consumers)
- Authentication is purely JWT-based and your IdP is fast (<1.5s JWKS endpoint response time — hard limit)
- Request+response payloads are reliably under ~1.5 MB
- You have fewer than 300 endpoints/integrations and won't grow beyond that
- Monthly request volume is high enough that 71% cost savings materially impact your bill (~$250+ savings at 100M requests/month)
- You don't need WAF, caching, request validation, or API keys

**Use WebSocket API when:**
- True bidirectional communication: both client and server initiate messages unpredictably (chat, collaborative editing, multiplayer gaming)
- Concurrent connections stay below 50K (connection management and fan-out remain tractable)
- Message frequency is high (>1 message/minute/user) making polling uneconomical
- Custom routing logic is needed (route selection expressions on message payload)
- Deep Lambda/DynamoDB integration is required and you want to avoid a separate managed service

**Consider alternatives to WebSocket API when:**
- Scale exceeds 100K concurrent: IoT Core (native pub/sub, managed connections, topic broadcast) or AppSync Events (Apr 2025, managed WebSocket with channel model)
- Use case is one-way server→client streaming: REST API response streaming (Nov 2025) is simpler — no connection tracking, WAF support, 10MB+ payloads
- Architecture is GraphQL-centric: AppSync Events integrates natively
- Multi-region real-time is required: WebSocket API has no built-in failover; IoT Core and AppSync handle this natively

#### The "CloudFront in Front" Anti-Pattern

A common pattern to compensate for HTTP API's missing features (no WAF, no edge optimization, no caching) is adding CloudFront in front. This works technically but reconstructs the REST API feature set manually, adds infrastructure complexity, and increases cost. At that point, the operational overhead often exceeds the per-request cost savings. Evaluate the total cost of ownership, not just per-request pricing.

#### Counter-Intuitive Findings

1. **HTTP API is in maintenance mode.** AWS has not added a significant feature to HTTP API since 2023. REST API is the product receiving investment. "Choose HTTP API to be forward-compatible" is the opposite of what the evidence supports.

2. **HTTP API can be more expensive than REST API.** The 512 KB metering increment means large payloads flip the economics. A REST/HTTP proxy serving large files or LLM completions may cost more on HTTP API.

3. **WebSocket heartbeats are billable.** Every application-level heartbeat message (needed to prevent idle timeout) costs $1.00/million. At 1M connections with one heartbeat per 9 minutes, that's ~$100/month in "keep-alive tax."

4. **$disconnect is best-effort.** Abrupt network loss or app kill may never fire the $disconnect route, leaving zombie entries in your connection tracking DynamoDB table. TTL-based cleanup is architecturally mandatory, not optional. Design for this from day one.

5. **The shared 10K RPS throttle makes WebSocket fan-out a blast radius.** Broadcasting to 100K connections consumes 10 full seconds of your account's entire API throttle budget. Any concurrent REST or HTTP API traffic will be throttled during this window — across all APIs in the account.

6. **Stage variable changes in REST API are instant and require no deployment.** This is a production risk vector: a misconfigured stage variable takes effect immediately with no deployment artifact, no rollback mechanism, and no audit trail beyond CloudTrail API calls.

7. **Edge-optimized REST API silently capitalizes headers.** `authorization` becomes `Authorization`, `cookie` becomes `Cookie`. Case-sensitive backends break silently. This is documented but obscure.

8. **REST API reserves `/ping` and `/sping` at the root.** These return 200 OK unconditionally as health check endpoints. If your API has routes at these paths, they will be shadowed.

9. **Usage plan throttling is explicitly not a security control.** AWS documentation warns: "Don't rely on usage plan quotas or throttling to control costs or block access." Clients can exceed configured quotas by a non-trivial margin. WAF is the correct tool for rate limiting as a security control.

10. **Response streaming in REST API (Nov 2025) obsoletes many WebSocket use cases.** LLM completion streaming, progress notifications, large file delivery, and server-sent-event patterns — all previously requiring WebSocket — now work better on REST API with less operational complexity.

---

### New Questions

1. **IoT Core as a scalable WebSocket replacement**: IoT Core supports native pub/sub with topic-based broadcast — one publish reaches all subscribers without N API calls. At what concurrent connection count does IoT Core's operational simplicity outweigh its ~6.5x higher per-byte cost (5 KB metering vs WebSocket's 32 KB)? What does a hybrid architecture look like: REST API for request/response + IoT Core for real-time push?

2. **AppSync Events as the new default for serverless real-time (2025+)**: AppSync Events (Apr 2025) added managed WebSocket publishing with built-in connection lifecycle, channel/namespace pub-sub, and multi-auth (IAM, Lambda, Cognito). For net-new serverless real-time projects, is AppSync Events now strictly better than WebSocket API for most use cases? What are its hard limits and pricing compared to WebSocket API at 10K/100K/1M connections?

3. **Routing Rules (Jun 2025) and cell-based architecture**: REST API's new routing rules enable A/B testing, API versioning by header/hostname/cookie, and cell-based routing without path changes. How do these compare to CloudFront Functions + Lambda@Edge for the same use cases? Does this eliminate a class of CDN-routing patterns that previously required CloudFront, and what are the limits on routing rule complexity and evaluation order?
