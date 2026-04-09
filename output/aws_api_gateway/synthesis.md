# AWS API Gateway: Enterprise Decision Guide
*Prepared for senior AWS cloud architects — April 2026*

---

## Executive Summary

AWS API Gateway is three distinct products sharing a name: REST API (full-featured, ~47 capabilities), HTTP API (low-cost proxy, ~22 capabilities), and WebSocket API (stateful bidirectional connections). The feature gap between REST and HTTP API is **widening, not narrowing** — every significant feature added in 2024–2025 went to REST API, while HTTP API appears to be in maintenance mode. HTTP API's 71% cost advantage is real but comes with hard architectural constraints that make it unsuitable for external-facing or security-sensitive workloads. WebSocket API's niche has narrowed significantly since REST API gained response streaming in November 2025, leaving true bidirectional communication as its primary remaining advantage. The shared 10,000 RPS account throttle across all three products is the most commonly overlooked constraint in multi-product deployments.

---

## Comparison Table: All Three Products

| Dimension | REST API | HTTP API | WebSocket API |
|-----------|----------|----------|---------------|
| **Primary use case** | External/managed APIs | Internal microservice proxy | Persistent bidirectional connections |
| **Feature count** | ~47 | ~22 | ~18 |
| **Investment trajectory** | Active (all 2024–2025 features) | Maintenance mode | Stable |
| **Base price** | $3.50/M requests | $1.00/M requests | $1.00/M messages + $0.25/M conn-min |
| **Payload metering unit** | Flat per-request | 512 KB increments | 32 KB increments |
| **Max payload** | 10 MB (streaming: no hard limit) | 10 MB | 128 KB |
| **Integration timeout** | 29s (extendable, regional/private) | 30s (hard) | 29s (hard) |
| **Integrations per API** | 300 (increasable) | **300 (hard, not increasable)** | 300 (increasable) |
| **AWS WAF** | Yes | No | No |
| **API keys / usage plans** | Yes | No | No |
| **Response caching** | Yes | No | No |
| **Response streaming** | Yes (Nov 2025) | No | N/A |
| **Edge-optimized endpoints** | Yes | No | No |
| **Private endpoints** | Yes | No | No |
| **X-Ray tracing** | Yes | No | No |
| **Execution logs** | Yes | No | No |
| **Resource policies** | Yes | No | No |
| **Request validation** | Yes | No | No |
| **Request body transformation** | Yes | No | No |
| **Canary deployments** | Yes | No | No |
| **Per-client rate limiting** | Yes | No | No |
| **Native JWT authorizer** | No | **Yes** | No |
| **Automatic deployments** | No | **Yes** | No |
| **Cloud Map integrations** | No | **Yes** | No |
| **Mutual TLS (mTLS)** | Yes | Yes | No |
| **Lambda authorizer** | Yes | Yes | No |
| **Connection model** | Stateless | Stateless | Stateful (2hr hard max) |
| **Idle timeout** | N/A | N/A | 10min (hard, not adjustable) |
| **New connections/second** | N/A | N/A | 500/s (adjustable, slowly) |
| **Broadcast / fan-out** | N/A | N/A | Manual @connections loop only |
| **Account throttle** | 10K RPS / 5K burst (shared) | 10K RPS / 5K burst (shared) | 10K RPS / 5K burst (shared) |
| **Developer portal** | Yes (Nov 2025) | No | No |

---

## Dimension 1: REST API vs HTTP API

### Feature Reality

The AWS documentation frames these as equivalent alternatives with different price points. They are not. HTTP API was originally positioned as the "modern" successor to REST API — that framing is now demonstrably wrong. Every feature added in 2024–2025 landed in REST API: response streaming (Nov 2025), routing rules (Jun 2025), developer portal (Nov 2025), TLS 1.3, SIGv4a, ALB private integrations, custom domains for private APIs. HTTP API received no new features in this period.

For external APIs — anything with third-party consumers, API monetization, or compliance requirements — HTTP API is not a viable option. It has no API keys, no usage plans, no per-client throttling, no WAF, no resource policies, and no request validation.

### Pricing

All prices US East (N. Virginia):

| Tier | REST API | HTTP API |
|------|----------|----------|
| First ~333M requests/mo | $3.50/M | $1.00/M |
| Next tier (to 1B) | $2.80/M | $0.90/M |
| Over 1B | $2.38/M | $0.90/M |

**Cost at scale:**

| Monthly Requests | REST API | HTTP API | HTTP API Savings |
|-----------------|----------|----------|-----------------|
| 1M | $3.50 | $1.00 | 71% |
| 100M | $350 | $100 | 71% |
| 1B | $3,033 | $930 | 69% |

**The 512 KB metering trap:** HTTP API meters requests in 512 KB increments. A request+response payload totaling 1,537 KB bills as 4 units ($4.00/M equivalent), while REST API charges flat $3.50/M. For APIs with large payloads — file uploads, bulk responses, large JSON documents — HTTP API can be *more expensive* than REST API. This is not a theoretical edge case; any API returning >1.5 MB responses is at risk.

### Performance

Independent benchmark (cloudonaut.io, m5.large, k6 load generator, Lambda backend):

| Metric | HTTP API | REST API | Delta |
|--------|----------|----------|-------|
| Average | 14.13ms | 16.83ms | −16% |
| p90 | 15.97ms | 18.58ms | −14% |
| p95 | 18.63ms | 23.05ms | −19% |

The ~2.5ms average difference is real and consistent. It is also negligible in virtually every production workload where backend latency (database queries, computation) dominates. The exception: edge-optimized REST API, which routes through CloudFront POPs and can outperform regional HTTP API for geographically distributed clients. HTTP API has no edge-optimized option.

### Hard Limits Comparison

The 300-integration hard limit on HTTP API deserves specific attention. REST API's 300-integration limit is a soft quota, raisable via Support. HTTP API's is hard — AWS will not increase it. For architectures with one Lambda function per endpoint (a common serverless pattern), HTTP API hits a wall at 300 routes. REST API does not have this constraint.

---

## Dimension 2: WebSocket API

### Capabilities and Architecture

WebSocket API provides persistent bidirectional connections with Lambda, HTTP, VPC Link, and direct AWS service integrations. The programming model is route-based: incoming JSON messages are routed by evaluating a **route selection expression** (default: `$request.body.action`) against the payload. Three special routes handle lifecycle events:

- `$connect` — fires on WebSocket handshake; the **only** route where authorization runs
- `$disconnect` — fires on disconnect; **best-effort only**, not guaranteed for abrupt disconnects
- `$default` — catch-all for unmatched route keys

**Sending messages back to connected clients** requires calling the @connections callback API:
```
POST https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/@connections/{connection_id}
```
All @connections calls require SigV4 signing. There is no broadcast or multicast primitive — sending to N clients requires N individual POST calls, each consuming from the shared 10K RPS throttle and billing as a separate message.

### Critical Limits

| Quota | Value | Adjustable? |
|-------|-------|-------------|
| New connections/second | 500/s per account per region | Yes — but slowly |
| Connection duration | 2 hours | **No** |
| Idle timeout | 10 minutes | **No** |
| WebSocket frame size | 32 KB | **No** |
| Message payload | 128 KB total | **No** |
| Integration timeout | 29 seconds | **No** |
| Account throttle | 10K RPS / 5K burst | Shared with REST and HTTP API |

**The connection rate constraint is the architectural bottleneck.** At 500 new connections/second (default), onboarding 100,000 users takes 3.3 minutes. DAZN Engineering documented this publicly: the 1.8M new connections/hour cap was a "deal-breaker" for their sports streaming platform with millions of simultaneous viewers during live events.

**The idle timeout requires active management.** API Gateway does not send server-side WebSocket ping frames. It will respond to client pings per RFC, but clients must send application-level heartbeat messages at under 10-minute intervals. Critically, these heartbeat messages **are billed** at $1.00/million — they are not free like protocol-level ping/pong. At 1 million concurrent connections with one heartbeat per 9 minutes, heartbeat costs alone reach ~$100/month.

**The 2-hour hard cap mandates reconnection logic.** Reconnect proactively at ~90 minutes rather than waiting for the 2-hour boundary — all connections reaching the limit simultaneously creates a thundering-herd reconnection storm that can saturate the 500 conn/s limit.

### Pricing and Cost Modeling

| Component | Rate |
|-----------|------|
| Messages (first 1B/mo) | $1.00/million |
| Messages (over 1B/mo) | $0.80/million |
| Connection minutes | $0.25/million (flat, no tiering) |

Connection minutes bill continuously regardless of message traffic. An idle but connected client costs the same per minute as an active one.

**Realistic cost model** (100K concurrent users, 30 min/day average, 10 messages/min bidirectional):

| Component | Volume/month | Cost |
|-----------|-------------|------|
| Connection minutes | 90M | $22.50 |
| Messages | 900M | $900.00 |
| Heartbeats (1/9min) | ~10M | $10.00 |
| **Total** | | **$932.50** |

**Break-even vs HTTP API polling** (same 100K users, 6-second polling interval):

| Approach | Volume/month | Cost |
|----------|-------------|------|
| WebSocket API | 900M messages + 90M conn-min | $932 |
| REST API polling | 432M requests | $1,404 |
| HTTP API polling | 432M requests | $432 |

**WebSocket is cheaper than REST API polling at moderate message frequency, but more expensive than HTTP API polling.** The break-even point is approximately 1 message/minute/client. Below that frequency, HTTP API polling wins on cost. Above it, WebSocket wins. This assumes small payloads — for larger payloads, HTTP API's 512 KB metering reverses the calculation.

### Mandatory Operational Requirements

Production WebSocket API deployments require all of the following — these are not optional optimizations:

1. **DynamoDB connection table** with TTL for zombie connection cleanup. `$disconnect` is best-effort; abrupt disconnects (network loss, process kill) may never fire it. Without TTL-based cleanup, stale `connectionId` records accumulate and cause `GoneException` (HTTP 410) errors on @connections calls.

2. **Reconnection logic in every client.** The 2-hour hard cap is non-negotiable. Clients that do not reconnect will be silently dropped.

3. **Application-level heartbeats** sent by clients every <10 minutes. Budget for the message cost.

4. **SigV4 signing** for all @connections API calls from backend code.

5. **`GoneException` handling** in @connections call paths. A 410 response means the client disconnected; remove the `connectionId` from DynamoDB immediately.

6. **VPC Link `connectionId` mapping** if using private backend integrations — it is not passed automatically. Requires explicit `RequestParameters` mapping: `integration.request.header.connectionId` → `context.connectionId`.

### The Fan-Out Problem at Scale

Broadcasting a message to N clients requires N @connections POST calls. At 100K concurrent users:
- Each broadcast: 100K API calls
- At 10K RPS shared throttle: minimum 10 seconds per broadcast wave
- At 10 broadcasts/minute: the account throttle is **permanently saturated by WebSocket alone**

This throttle is shared with REST and HTTP APIs in the same region. A WebSocket broadcast storm will throttle your synchronous REST APIs. There is no isolation.

For workloads requiring broadcast at scale, the architecture patterns are:
- **SNS → SQS → Lambda fan-out**: Backend publishes once; Lambda consumers batch @connections calls
- **Step Functions Distributed Map**: Parallel execution across connection batches (practical for 10K–100K)
- **DynamoDB Streams + Lambda**: Event-driven processing from connection table changes

None of these eliminate the N-calls-per-broadcast requirement — they just parallelize it.

### The REST API Streaming Inflection Point (November 2025)

REST API response streaming, GA in November 2025, changed the WebSocket decision matrix. Capabilities:
- Payloads beyond 10 MB
- Integration timeouts up to 15 minutes
- Improved time-to-first-byte
- All regions including GovCloud

This directly addresses the most common WebSocket use cases that were not genuinely bidirectional:
- LLM/generative AI streaming responses
- Large file downloads with progress feedback
- Server-sent events (SSE) style notification streams
- Long-running computation with incremental results

For all of these, REST API streaming is now strictly better: higher payload limits, full WAF support, API key authentication, no connection tracking overhead, standard HTTP semantics with better client library support, and no 128 KB per-message limit.

WebSocket API's remaining unique value is **true bidirectional, low-latency, persistent connections** — scenarios where both client and server initiate messages unpredictably and a request/response model is genuinely insufficient. This is a narrower category than it was in 2023.

---

## Dimension 3: Authentication and Authorization

### Authorization by Product

| Method | REST API | HTTP API | WebSocket API |
|--------|----------|----------|---------------|
| IAM (SigV4) | Yes | Yes | Yes ($connect only) |
| Amazon Cognito (native) | Yes | Via JWT | No |
| Lambda authorizer | Yes | Yes | Yes ($connect only) |
| Native JWT authorizer | No | **Yes** | No |
| Resource policies | Yes | No | No |
| mTLS | Yes | Yes | No |
| Backend client certificates | Yes | No | No |

**WebSocket authorization runs only on `$connect`.** Once a connection is established, API Gateway does not re-authenticate individual messages. If your security model requires per-message authorization, it must be implemented in application code within the route Lambda handlers — API Gateway will not enforce it.

**HTTP API's native JWT authorizer** is meaningfully simpler than REST API's Lambda authorizer approach for JWT/OIDC workloads. It validates tokens directly against a JWKS endpoint without requiring a Lambda function. Important constraint: the JWKS endpoint has a **hard 1,500ms timeout**. Identity providers with slow JWKS responses (cold starts, throttling, geographic distance) will cause authentication failures that are difficult to diagnose.

**REST API's resource policies** enable IP-based restrictions, VPC endpoint restrictions, and cross-account access without Lambda authorizers. This is the primary mechanism for locking down private APIs to specific VPCs or accounts. HTTP API has no equivalent.

**Usage plan throttling is best-effort, not guaranteed.** The AWS documentation explicitly states: *"Don't rely on usage plan quotas or throttling to control costs or block access to your APIs."* Client requests can exceed configured quotas. If hard rate enforcement is required, WAF rate-based rules (REST API only) or application-layer enforcement is necessary.

---

## Decision Framework

### Primary Decision Tree

```
Start here: What communication pattern do you need?
│
├── Persistent bidirectional (both sides initiate messages unpredictably)
│   ├── Scale > 100K concurrent OR need broadcast semantics
│   │   ├── Primarily server→client push with topics/channels → AppSync Events (Apr 2025+)
│   │   └── IoT-style pub/sub, offline queuing, MQTT semantics → IoT Core
│   └── Scale < 100K concurrent, true bidirectional, custom routing → WebSocket API
│
└── Stateless request/response (or server→client streaming)
    │
    ├── Response streaming needed (LLM, large payloads, long operations)?
    │   → REST API (streaming GA Nov 2025: >10MB, 15-min timeout)
    │
    ├── External consumers, third-party developers, or API monetization?
    │   → REST API (API keys, usage plans, developer portal, WAF)
    │
    ├── WAF required without managing a CloudFront distribution?
    │   → REST API
    │
    ├── Global clients without your own CDN/CloudFront?
    │   → REST API (edge-optimized; HTTP API is regional only)
    │
    ├── Compliance: request validation, execution logging, X-Ray?
    │   → REST API
    │
    ├── Response caching (TTL-based, per-parameter)?
    │   → REST API
    │
    ├── A/B testing, cell-based routing by header/hostname/cookie?
    │   → REST API (Routing Rules, Jun 2025)
    │
    ├── Internal microservices, JWT/OIDC auth, high volume, simple proxy?
    │   ├── < 300 Lambda functions total → HTTP API (71% cheaper)
    │   └── > 300 Lambda functions → REST API (HTTP API 300-integration hard limit)
    │
    └── Internal service with no API keys, caching, or WAF requirements,
        and cost is primary constraint?
        └── Evaluate ALB + Lambda directly (may undercut HTTP API at high volume)
```

### Use REST API When

- Third-party developers or partners consume the API (API keys, usage plans, developer portal are essential)
- WAF integration is required without adding CloudFront
- Request validation must be enforced at the gateway layer
- Debugging complex integration behavior (execution logs + X-Ray are available only here)
- Edge distribution is needed without managing a separate CloudFront distribution
- Response streaming for LLM or large-payload workloads (Nov 2025+)
- Canary deployments with traffic shifting by percentage
- Long-running operations: regional/private REST API timeout can exceed 29 seconds
- API monetization with per-client rate limiting and quota enforcement
- Compliance requirements mandate request/response transformation at the gateway
- You are writing infrastructure that needs to be maintainable long-term — REST API is receiving all new investment

### Use HTTP API When

- Pure internal service-to-service communication with no external consumers
- JWT/OIDC identity provider is already in place (native authorizer is simpler than Lambda authorizer)
- High-volume internal traffic where 71% cost reduction compounds materially
- Cloud Map service discovery for private integrations (HTTP API-exclusive)
- Total endpoint count stays under 300 per API
- Request+response payloads are consistently small (<1.5 MB to avoid metering penalty)
- You have explicitly accepted that this product is in maintenance mode

### Use WebSocket API When

- Genuine bidirectional communication where both sides initiate messages unpredictably (chat, collaborative editing, multiplayer gaming, live trading)
- Concurrent connections stay below ~50K (fan-out and throttle constraints are tractable)
- Message frequency exceeds ~1/minute/client (below this, HTTP API polling is cheaper)
- Custom routing logic by message content is needed (route selection expressions)
- Deep Lambda integration per message type is required
- You can accept the mandatory operational requirements: DynamoDB connection table, reconnection logic, heartbeats, SigV4, GoneException handling

### Do Not Use WebSocket API When

- **Server→client streaming only** (LLM responses, SSE): Use REST API streaming — it is strictly better in every dimension as of Nov 2025
- **Broadcast to >100K clients**: The N-calls-per-broadcast constraint + shared 10K RPS throttle makes this operationally untenable. Use AppSync Events or IoT Core
- **Low-frequency updates (<1 msg/min/client)**: HTTP API polling is cheaper once connection-minute billing is accounted for
- **Real-time push at massive scale**: DAZN's production experience (500 conn/s = deal-breaker for millions of users) is the canonical reference

---

## Concrete Recommendations (Ranked by Confidence)

### High Confidence

**1. Default to REST API for any external-facing API.**
HTTP API's missing features (WAF, API keys, resource policies, request validation, X-Ray) are not optional for external APIs. The 71% cost savings do not compensate for the security and operational gaps. *Confidence: 98%*

**2. HTTP API's 300-integration hard limit is a go/no-go constraint, not a footnote.**
Evaluate total Lambda function count before committing to HTTP API. If your microservice architecture trends toward one-function-per-endpoint and you have >300 services, REST API is the only option. Increasing the HTTP API limit is not possible regardless of Support tier. *Confidence: 98%*

**3. For LLM/streaming workloads, use REST API streaming over WebSocket.**
Since November 2025, REST API streaming handles >10 MB payloads with up to 15-minute timeouts, full WAF support, and no connection tracking overhead. WebSocket for unidirectional streaming is now an antipattern. *Confidence: 95%*

**4. Treat the 10K RPS shared throttle as an account-level resource, not a per-product limit.**
Any organization running REST API, HTTP API, and WebSocket API in the same region is sharing a single 10K RPS / 5K burst bucket. Model peak load across all products before assuming capacity. Request increases via Service Quotas proactively. *Confidence: 95%*

**5. Never build WebSocket at scale without DynamoDB TTL-based zombie connection cleanup.**
`$disconnect` is best-effort. Any production WebSocket implementation without TTL on the connection table will accumulate stale records, produce GoneException errors, and eventually exhaust DynamoDB capacity for connection lookups. This is mandatory, not a best practice. *Confidence: 95%*

### Medium Confidence

**6. HTTP API is in de facto maintenance mode — factor this into multi-year architecture decisions.**
No evidence of feature investment since 2023 despite REST API receiving 6+ significant features in 2024–2025. For infrastructure expected to evolve over 3–5 years, REST API is the lower-risk choice even at higher cost. This is an inference from observed investment patterns, not an AWS statement. *Confidence: 80%*

**7. For new real-time push projects at scale, evaluate AppSync Events before WebSocket API.**
AppSync Events (April 2025) provides native channel/namespace pub-sub, managed connection lifecycle, multi-auth support, and built-in fan-out — eliminating the DynamoDB connection table and @connections loop requirements that make WebSocket operationally expensive at scale. This is a newer service with less production history than WebSocket API. *Confidence: 75%*

**8. REST API Routing Rules (Jun 2025) may reduce or eliminate the need for CloudFront-based canary routing in SaaS architectures.**
Header/hostname/cookie-based routing without path changes enables cell-based architecture and A/B testing at the gateway layer. This simplifies multi-tenant SaaS routing that previously required CloudFront weighted behaviors. Limits and production track record at high cardinality are not yet fully documented. *Confidence: 70%*

### Lower Confidence (Requires Further Investigation)

**9. ALB + Lambda may undercut both API Gateway products for high-volume pure-internal APIs.**
ALB charges ~$0.008/LCU-hour; at 1B requests/month the economics often favor ALB over HTTP API's $930. However, ALB lacks throttling, authentication, and lifecycle management features. The break-even and the operational trade-offs require workload-specific analysis. *Confidence: 60%*

---

## Known Gaps and Areas for Further Investigation

### Gap 1: ALB + Lambda vs API Gateway Break-Even Analysis

The per-request cost comparison at 100M, 500M, and 1B requests/month between ALB with Lambda targets and HTTP API is not fully quantified here. ALB pricing (per-LCU-hour) does not translate linearly to per-request costs — it depends on connection count, request rate, bandwidth, and rule evaluations simultaneously. For high-volume internal services where 71% HTTP API savings are already compelling, ALB may offer a further 50–80% reduction. This warrants a dedicated cost model with representative traffic profiles before recommending as an architectural alternative.

### Gap 2: AppSync Events Limits and Production Track Record

AppSync Events (April 2025) is positioned here as the recommendation for large-scale WebSocket broadcast, but its service quotas, pricing at scale, and production stability are based on limited public information. Specifically unknown: maximum concurrent connections, message size limits, connection duration limits, and whether its pub-sub model supports the custom routing patterns that make WebSocket API compelling for complex protocols. Evaluate these limits before committing to AppSync Events for high-scale greenfield projects.

### Gap 3: Multi-Region WebSocket Architecture Patterns

WebSocket API is single-region with no built-in failover. The operational patterns for globally distributed real-time applications — Route 53 health check failover, EventBridge cross-region event replication, DynamoDB Global Tables for connection state — are not analyzed here. For latency-sensitive global real-time use cases, the build cost of multi-region WebSocket vs the managed global distribution of AppSync or IoT Core is unquantified.

### Gap 4: REST API Routing Rules Capacity and Limits (Jun 2025)

The Routing Rules feature enables A/B testing and cell-based routing by header/hostname/cookie. The limits — maximum rules per API, supported match expressions, interaction with canary deployment percentages, and behavior at high traffic cardinality — are not documented in sufficient detail in available sources to make confident recommendations about replacing CloudFront-based weighted routing. Validate against AWS documentation and test against representative traffic before adopting for production SaaS routing.

### Gap 5: Authentication Dimension

The detailed comparison of Lambda authorizer caching behavior, Cognito user pool vs identity pool authorization patterns, and mTLS certificate rotation procedures was not successfully researched in this cycle (multiple iterations crashed). For security-sensitive architectures, the auth dimension — particularly Lambda authorizer result TTL, concurrent request behavior during cold start, and resource policy interaction with Cognito — should be investigated separately.

### Gap 6: Observability Gaps in HTTP API

HTTP API's access logs (CloudWatch only) vs REST API's execution logs + X-Ray + Data Firehose access logs is documented at the feature level but not at the operational impact level. The practical difficulty of debugging integration failures, latency outliers, and throttling events in HTTP API without execution logs is not quantified. For teams accustomed to REST API's observability, the operational cost of switching to HTTP API may partially offset the 71% cost savings.

---

## Quick Reference Card

| Question | Answer |
|----------|--------|
| External API with third-party consumers? | REST API — no alternative |
| Internal JWT-authenticated microservice, <300 routes? | HTTP API |
| Internal service, >300 routes? | REST API |
| LLM response streaming? | REST API (Nov 2025 streaming) |
| Chat / collaborative editing / multiplayer? | WebSocket API |
| Real-time push to >100K users? | AppSync Events or IoT Core |
| Real-time push to <50K users? | WebSocket API |
| Polling for low-frequency updates? | HTTP API |
| Cost-critical high-volume internal traffic? | HTTP API (then evaluate ALB) |
| Global API without managing CloudFront? | REST API (edge-optimized) |
| Compliance: WAF, request validation, audit logs? | REST API |
| A/B testing / cell-based routing by header? | REST API (Routing Rules, Jun 2025) |