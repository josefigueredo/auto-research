# Iteration 028 — done

**Status:** discard  
**Scores:** coverage=100.0, quality=50.0, total=70.0  
**Timestamp:** 2026-04-06T11:28:50.428786+00:00  

---

## Final Synthesis: AWS API Gateway — Enterprise Decision Guide

All research dimensions have been completed. This is the synthesized output for a senior cloud architect making infrastructure decisions.

---

### Findings

#### The Product Landscape (2026)

AWS API Gateway is three distinct products sharing a name:

| Product | Best For | Maturity Signal |
|---------|----------|-----------------|
| **REST API** | External-facing, managed APIs | Active investment — every 2024–2025 feature went here |
| **HTTP API** | Internal microservices, JWT auth | Maintenance mode — no new features since ~2023 |
| **WebSocket API** | Bidirectional persistent connections | Stable but constrained — no broadcast, hard limits |

**The most important strategic fact:** HTTP API was originally positioned as the "future" of API Gateway. That positioning is now inverted. REST API received response streaming, routing rules, a developer portal, TLS 1.3, SIGv4a, enhanced ALB integrations, and custom domains for private APIs between 2024–2025. HTTP API received nothing. Architectural decisions made in 2022–2023 to "use HTTP API because it's simpler and cheaper" need to be revisited.

---

### Feature Decision Matrix

#### External / Partner APIs
REST API is the only viable option. HTTP API has no API keys, no usage plans, no per-client throttling, no WAF integration, no request validation, and no developer portal. These are not optional for APIs consumed by third parties.

#### Internal Microservices (High Volume, Simple Auth)
HTTP API is appropriate **if**: JWT auth is sufficient, you don't need request validation or caching, payloads stay under ~1,500 KB, and you won't exceed 300 integrations. The 71% cost savings are real and compound at scale.

**Hard stop:** If your microservice architecture has >300 Lambda functions as endpoints, HTTP API's hard 300-integration cap (not increasable) forces a redesign or forces you back to REST API.

#### Real-Time / Streaming (2026 Recommendation)
REST API response streaming (Nov 2025) has materially changed this. The decision tree is now:

```
Need bidirectional (client AND server initiate messages unpredictably)?
├── Yes → WebSocket API (if <50K concurrent) or IoT Core / AppSync Events (if >50K)
└── No (server→client only)?
    ├── LLM/generative AI → REST API streaming (15min timeout, >10MB, WAF-protected)
    ├── SSE-style notifications → REST API streaming or HTTP API polling
    └── High-frequency broadcast → IoT Core MQTT or AppSync Events
```

---

### Evidence

#### Pricing Summary

| Product | Base Rate | Break-even / Notes |
|---------|-----------|-------------------|
| REST API | $3.50/M requests | Tiered to $2.38/M at >1B/month |
| HTTP API | $1.00/M requests | Tiered to $0.90/M at >300M/month; **metered per 512 KB — large payloads erode savings** |
| WebSocket | $1.00/M messages + $0.25/M connection-minutes | Message = 32 KB increment; heartbeats are billable |

**HTTP API payload metering trap:** A REST+response of 600 KB = 2 billed messages at $2.00/M effective rate. At 1,024 KB = 3 messages = $3.00/M — more expensive than REST API. Always model your actual payload sizes before committing to HTTP API.

**WebSocket heartbeat tax:** 1M persistent connections with 1 heartbeat/9min = ~100M messages/month = $100/month purely to keep connections alive. This is a fixed cost floor that doesn't exist with polling or streaming.

**Cache cost (REST API only):** $0.020/hr (0.5 GB) to $3.80/hr (237 GB). Cache runs 24/7 once enabled — a 237 GB cache costs $2,736/month whether you use it or not.

#### Hard Limits That Cannot Be Increased

| Limit | Value | Impact |
|-------|-------|--------|
| HTTP API integrations | 300 | Hard ceiling on microservice granularity |
| WebSocket frame size | 32 KB | Requires application-layer chunking |
| WebSocket payload size | 128 KB | vs REST API's 10 MB |
| WebSocket connection duration | 2 hours | Mandatory client-side reconnection logic |
| WebSocket idle timeout | 10 minutes | Mandatory application-level heartbeats |
| HTTP API integration timeout | 30 seconds | vs REST API's extendable limit |

#### Throttle Architecture

All three products share the **same regional account-level throttle**: 10,000 RPS / 5,000 burst. A WebSocket fan-out broadcast to 100K clients at 1 message each takes **10 seconds minimum** at this limit, and consumes throttle capacity that REST API requests in the same account must compete for.

Smaller regions (Africa Cape Town, Europe Milan, Asia Pacific Jakarta, Middle East UAE) default to 2,500 RPS / 1,250 burst.

---

### Trade-offs

#### REST API vs HTTP API

| Dimension | REST API Wins | HTTP API Wins |
|-----------|--------------|---------------|
| Cost | — | 71% cheaper for small payloads |
| External consumers | Strongly (API keys, usage plans, portal) | — |
| Security depth | Strongly (WAF, resource policies, validation) | — |
| Debugging | Strongly (X-Ray, execution logs) | — |
| Global distribution | Strongly (edge-optimized CloudFront POPs) | — |
| Internal JWT auth | — | Simpler native JWT authorizer |
| Large integration count | Equal (both 300, both increasable) | — |
| Long-running ops | Strongly (extendable timeout) | — |
| Future investment | Strongly (active development) | — |

**The counter-intuitive finding that matters most:** There is no longer a compelling reason to choose HTTP API for new greenfield projects unless the workload is specifically: (a) internal-only, (b) JWT-authenticated, (c) high volume with small payloads, and (d) never needs WAF or per-client throttling. Outside that narrow band, REST API is defensible on cost after accounting for CloudFront+WAF add-ons that HTTP API workloads often eventually need.

#### WebSocket API: Genuine Constraints vs Perception

**Genuine constraints (not workaroundable):**
- No native broadcast — fan-out requires N individual @connections calls
- $disconnect is best-effort — zombie connections accumulate without TTL cleanup
- 128 KB message limit — large data transfer requires chunking
- 10K RPS throttle shared with all API Gateway products in the account
- 500 new connections/second default — bursty traffic (sports events, flash sales) hits this immediately

**Perceived constraints (workaroundable but with complexity):**
- No connection tracking → DynamoDB pattern is well-established
- No auth persistence across routes → $connect authorizer caches result for connection duration
- Fan-out at scale → SNS/SQS/Step Functions Distributed Map patterns work

**The honest assessment:** WebSocket API is appropriate for persistent bidirectional communication at moderate scale (<50K concurrent) where you control both client and server, your team is comfortable with DynamoDB-backed connection state, and you need the flexibility of custom routing logic. It is a poor fit for broadcast-heavy scenarios, massive fan-out, or cases where the "bidirectional" requirement could be met by server-initiated streaming alone.

#### REST API Response Streaming: The 2026 Shift

REST API response streaming (Nov 2025) eliminates the primary use case that drove teams toward WebSocket API for non-bidirectional workloads:

| Scenario | Pre-Nov 2025 | Post-Nov 2025 |
|----------|-------------|---------------|
| LLM token streaming | WebSocket or custom Lambda streaming | REST API streaming (WAF-protected, API keys, 15min) |
| Large file download | WebSocket chunking | REST API streaming (>10MB, no chunking needed) |
| SSE-style push | WebSocket or polling | REST API streaming or HTTP API |
| Progress notifications | WebSocket | REST API streaming |

Only true bidirectional communication remains as WebSocket API's unambiguous use case.

#### The "CloudFront in Front" Anti-Pattern

A common pattern is to use HTTP API (cheaper) with CloudFront in front (for WAF, caching, edge distribution). The problem: you've now built the REST API feature set manually, added a CloudFront distribution to manage, and added latency (extra hop). The total cost often exceeds REST API, and the operational overhead is higher. This pattern is justified only when:
1. Request volume is very high (>500M/month) and payload sizes are small, making the HTTP API per-request savings material
2. You need granular CloudFront behaviors beyond what REST API edge optimization provides

#### Known Gotchas for Production

1. **Edge-optimized REST API silently capitalizes headers** (`authorization` → `Authorization`, `cookie` → `Cookie`). Case-sensitive backends break silently.
2. **REST API reserves `/ping` and `/sping`** at root level. These are AWS health check paths — your API cannot expose them.
3. **Usage plan throttling is best-effort.** AWS docs explicitly state: "Don't rely on usage plan quotas or throttling to control costs or block access." Clients can exceed quotas.
4. **HTTP API JWKS endpoint has 1,500ms hard timeout.** Slow identity providers (including Cognito in degraded state) cause auth failures across all requests.
5. **Stage variable changes in REST API apply instantly** without a deployment. This is convenient but creates production change risk — a typo in a stage variable propagates immediately to live traffic.
6. **WebSocket $disconnect is fire-and-forget.** Lambda execution after $disconnect has no guaranteed completion window. Don't put critical cleanup logic here without a TTL fallback.
7. **REST API `X-Amzn-Remapped-*` headers** — `Authorization`, `Date`, `Server`, `WWW-Authenticate` are remapped with this prefix. Clients parsing raw headers break.
8. **Query string characters** `|`, `{}`, `;` cause issues in REST API. Semicolons silently split parameter values. Validate and encode before sending.

---

### New Questions

These surfaced from the research and represent unresolved decision points:

1. **AppSync Events (April 2025) as the default real-time recommendation:** AppSync Events added WebSocket publishing with built-in channel/namespace model, managed connection lifecycle, and multi-auth. For teams starting a new real-time feature today, is AppSync Events now the default choice over WebSocket API, and what are its quotas/limits vs WebSocket API's? The managed connection tracking and native fan-out directly address WebSocket API's biggest operational pain points.

2. **ALB + Lambda vs API Gateway for internal APIs at scale:** For high-volume internal microservice traffic (>1B requests/month) that needs none of API Gateway's management features, ALB with Lambda targets costs significantly less ($0.008/LCU vs $1.00–$3.50/M requests). What is the actual break-even, and what operational capabilities do you lose (tracing, throttling, stage management)?

3. **Multi-region WebSocket resilience:** WebSocket API is single-region with no native failover. For globally distributed real-time applications requiring >99.9% uptime, what are the production-proven patterns — Route 53 health check failover, EventBridge cross-region replication of connection state, DynamoDB Global Tables — and at what complexity/cost do managed alternatives (AppSync, IoT Core, Ably, Pusher) become more economical than building this yourself?
