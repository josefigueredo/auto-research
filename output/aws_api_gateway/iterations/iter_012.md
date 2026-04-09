# Iteration 012 — done

**Status:** keep  
**Scores:** coverage=100.0, quality=87.5, total=92.5  
**Timestamp:** 2026-04-06T11:49:36.674573+00:00  

---

## Findings

### Synthesis: AWS API Gateway — Complete Decision Framework for Enterprise Architects

All dimensions have been researched. This iteration synthesizes the full findings into an actionable decision framework.

---

### The Three Products Side by Side

AWS API Gateway is three distinct products that share a name and console:

| Dimension | REST API | HTTP API | WebSocket API |
|-----------|----------|----------|---------------|
| **Primary use case** | Full-featured external/managed APIs | Low-cost internal proxy | Persistent bidirectional connections |
| **Feature count** | ~47 | ~22 | ~18 |
| **Base price (per million)** | $3.50 | $1.00 | $1.00 messages + $0.25/M conn-min |
| **WAF support** | Yes | No | No |
| **API keys / usage plans** | Yes | No | No |
| **Response caching** | Yes | No | No |
| **Response streaming** | Yes (Nov 2025) | No | N/A |
| **Investment trajectory** | Active (all 2024–2025 features) | Maintenance mode | Stable |
| **Connection model** | Stateless | Stateless | Stateful (2hr max) |
| **Max payload** | 10 MB (streaming: unlimited) | 10 MB | 128 KB |
| **Broadcast/fan-out** | N/A | N/A | Manual (@connections loop) |

---

### Decision Tree: Which Product to Use

```
Is this a persistent, bidirectional, low-latency connection?
├── YES → Consider WebSocket API (see caveats below)
│          └── >100K concurrent OR need broadcast? → IoT Core or AppSync Events
└── NO → Stateless API
           ├── External consumers, API monetization, or third-party access?
           │    → REST API (API keys, usage plans, WAF, dev portal)
           ├── WAF required without CloudFront?
           │    → REST API
           ├── Response caching needed?
           │    → REST API
           ├── Global clients without your own CloudFront?
           │    → REST API (edge-optimized endpoints)
           ├── LLM/streaming responses (Nov 2025+)?
           │    → REST API (response streaming: >10MB, 15-min timeout)
           └── Internal microservices, JWT auth, high volume, simple proxy?
                → HTTP API (71% cheaper, marginally faster)
```

---

### Cost Comparison at Scale

**Stateless workload — 1B requests/month:**

| Product | Cost |
|---------|------|
| REST API | $3,033 |
| HTTP API | $930 |
| ALB + Lambda (no API Gateway) | ~$200–400* |

*ALB charges $0.008/LCU-hour; at 1B req/mo the economics often favor ALB for pure internal traffic.

**WebSocket — 100K concurrent users, 30 min/day, 10 msg/min:**

| Component | Monthly Cost |
|-----------|-------------|
| Connection minutes (90M) | $22.50 |
| Messages (900M) | $900.00 |
| Heartbeat overhead | $10.00 |
| **Total** | **$932.50** |

**WebSocket vs polling break-even:** WebSocket beats HTTP API polling only when server push frequency exceeds ~1 message/minute/client. Below that, HTTP API polling is cheaper.

---

### Critical Constraints Summary

| Constraint | REST API | HTTP API | WebSocket API |
|-----------|----------|----------|---------------|
| Payload max | 10 MB | 10 MB | 128 KB |
| Integration timeout | 29s (extendable) | 30s (hard) | 29s (hard) |
| Integrations per API | 300 (increasable) | **300 (hard limit)** | 300 (increasable) |
| Connection duration | N/A | N/A | **2hr (hard)** |
| Idle timeout | N/A | N/A | **10min (hard)** |
| New connections/s | N/A | N/A | 500/s (increasable, slowly) |
| Account throttle | 10K RPS shared | 10K RPS shared | 10K RPS shared |

**Shared throttle is the most overlooked constraint.** REST, HTTP, and WebSocket APIs all consume the same 10K RPS / 5K burst quota. A WebSocket broadcast storm throttles your REST APIs.

---

## Evidence

**All pricing confirmed from AWS official pricing page and CostGoat:**
- REST API: $3.50 → $2.80 → $2.38/M (tiered at 333M and 1B)
- HTTP API: $1.00 → $0.90/M (tiered at 300M+)
- WebSocket: $1.00 → $0.80/M messages; $0.25/M connection-minutes (flat)
- HTTP API meters in 512 KB increments; WebSocket in 32 KB increments

**Feature matrix:** AWS official docs comparison (docs.aws.amazon.com/apigateway/latest/developerguide/http-api-vs-rest.html) — 2025 state confirms HTTP API has received no new features since 2023.

**Latency benchmark (cloudonaut.io, independent):** HTTP API 14.13ms avg vs REST API 16.83ms avg. AWS claims <10ms p99 HTTP API overhead.

**WebSocket limits (AWS official quotas page):** 500 conn/s (adjustable), 2hr duration (hard), 10min idle (hard), 32KB frame / 128KB message (hard).

**DAZN production case study:** 500 conn/s limit = 1.8M/hr — insufficient for millions of concurrent sports viewers. No native broadcast means N clients = N @connections POST calls.

**REST API streaming (Nov 2025 GA):** Payloads beyond 10MB, timeouts up to 15 minutes, all regions including GovCloud — changes LLM and large-response use cases fundamentally.

**Smaller region defaults:** Africa Cape Town, Europe Milan, Asia Pacific Jakarta, Middle East UAE: 2,500 RPS / 1,250 burst (not 10K/5K).

---

## Trade-offs

### REST API: The Enterprise Default for External APIs

**Use it when:** Third-party consumers exist, API monetization is needed, WAF/compliance is required, global distribution without managing CloudFront, debugging complex integrations (X-Ray + execution logs), or streaming large responses (Nov 2025+).

**Watch out for:** Cost at scale vs HTTP API. Edge-optimized endpoints silently capitalize headers (`cookie` → `Cookie`). Usage plan throttling is best-effort, not guaranteed — don't rely on it for cost control or security. The `/ping` and `/sping` root paths are reserved.

### HTTP API: Internal Microservices Only

**Use it when:** Pure internal service-to-service communication, JWT identity providers (native authorizer is simpler), Cloud Map service discovery, and high-volume traffic where 71% savings compound materially.

**Watch out for:** The 300-integration hard limit (not increasable) blocks one-Lambda-per-endpoint architectures past 300 routes. No WAF means you're one `Host:` header injection away from a bad day. Large payloads (>1.5MB) can make HTTP API *more expensive* than REST API due to 512KB metering. The product appears to be in maintenance mode — new enterprise features are landing in REST API only.

### WebSocket API: A Narrower Niche Than It Appears

**Use it when:** True bidirectional messaging (chat, collaborative editing, multiplayer), moderate scale under ~50K concurrent connections, high-frequency small-payload updates where polling economics are worse.

**Avoid it when:**
- **Massive fan-out (>100K concurrent):** No broadcast primitive, 10K RPS shared throttle, mandatory DynamoDB connection tracking, and zombie connection management from missed `$disconnect` events combine to create severe operational overhead. IoT Core or AppSync Events are better choices.
- **One-way server→client streaming (LLM responses, SSE-style):** REST API streaming (Nov 2025) is strictly better — higher limits, WAF, API keys, no connection tracking, simpler client code.
- **Low-frequency updates (<1 msg/min/client):** HTTP API polling is cheaper once you account for continuous connection-minute billing even during idle periods.

**Hidden operational requirements:**
1. Reconnection logic mandatory (2hr hard cap — reconnect proactively at ~90min to avoid thundering herd)
2. Application-level heartbeats mandatory every <10min — and they're billable
3. DynamoDB connection table with TTL mandatory (zombie connection cleanup)
4. SigV4 signing required for all @connections callbacks
5. `GoneException` (410) handling required for stale connection references
6. VPC Link integration requires explicit `connectionId` header mapping

### The "CloudFront in Front" Anti-Pattern

Placing CloudFront in front of HTTP API to regain WAF, caching, and edge distribution is technically valid but means you've rebuilt the REST API feature set manually at higher operational complexity. The cost savings rarely justify it past moderate traffic levels.

### The AppSync Events Inflection Point (April 2025)

AppSync Events added WebSocket publishing in April 2025 with managed connection lifecycle, built-in channel/namespace pub-sub, and multi-auth support. For new projects requiring real-time push at scale, AppSync Events has become a strong alternative to WebSocket API — particularly because it handles broadcast natively without requiring a DynamoDB connection table or @connections fan-out loops. Existing WebSocket API investments don't need to migrate, but new greenfield real-time projects should evaluate AppSync Events first.

---

## New Questions

1. **ALB + Lambda vs API Gateway break-even for internal APIs:** For high-volume internal services without API keys, caching, or WAF requirements, ALB with Lambda targets often undercuts both REST and HTTP API on cost. What is the per-request price comparison at 100M, 500M, and 1B requests/month, and what operational features does each approach gain or lose?

2. **Multi-region active-active WebSocket architecture:** WebSocket API is single-region with no built-in failover. For globally distributed real-time applications, what is the operational cost of building multi-region WebSocket with Route 53 + DynamoDB Global Tables vs using AppSync or IoT Core which handle global distribution natively?

3. **REST API Routing Rules (Jun 2025) for multi-tenant SaaS:** The new routing rules feature enables A/B testing and cell-based routing by header/hostname/cookie without path changes. How does this replace or augment the previous CloudFront-based weighted routing pattern for SaaS canary deployments, and what are its limits compared to CloudFront's traffic splitting?
