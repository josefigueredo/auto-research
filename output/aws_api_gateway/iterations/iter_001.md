# Iteration 001 — REST API vs HTTP API: feature matrix, pricing, and performance differences

**Status:** keep  
**Scores:** coverage=93.0, quality=80.0, total=85.2  
**Timestamp:** 2026-04-05T21:03:09.179012+00:00  

---

## Findings

### Feature Comparison Matrix

REST API and HTTP API are fundamentally different products sharing a name. REST API supports ~47 features; HTTP API supports ~22. Only 3 features are HTTP API-exclusive.

#### Security & Authorization

| Feature | REST API | HTTP API |
|---------|----------|----------|
| AWS WAF | **Yes** | No |
| Mutual TLS (mTLS) | Yes | Yes |
| Backend certificates | Yes | No |
| Resource policies | Yes | No |
| IAM authorization | Yes | Yes |
| Amazon Cognito | Yes (native) | Yes (via JWT) |
| Lambda authorizer | Yes | Yes |
| Native JWT authorizer | No | **Yes** |

#### API Management & Development

| Feature | REST API | HTTP API |
|---------|----------|----------|
| API keys / usage plans | Yes | No |
| Per-client rate limiting | Yes | No |
| Response caching | Yes | No |
| Request validation | Yes | No |
| Request body transformation | Yes | No |
| Canary deployments | Yes | No |
| Custom gateway responses | Yes | No |
| Mock integrations | Yes | No |
| Response streaming | Yes (Nov 2025) | No |
| Routing rules | Yes (Jun 2025) | No |
| Developer portal | Yes (Nov 2025) | No |
| Automatic deployments | No | **Yes** |
| Cloud Map integrations | No | **Yes** |

#### Monitoring & Endpoints

| Feature | REST API | HTTP API |
|---------|----------|----------|
| X-Ray tracing | Yes | No |
| Execution logs | Yes | No |
| Access logs (CloudWatch) | Yes | Yes |
| Access logs (Data Firehose) | Yes | No |
| Edge-optimized endpoints | Yes | No |
| Regional endpoints | Yes | Yes |
| Private endpoints | Yes | No |

### Pricing Comparison

All prices US East (N. Virginia).

**Per-request costs:**

| Tier | REST API | HTTP API |
|------|----------|----------|
| First 300-333M/mo | $3.50/M | $1.00/M |
| Next tier | $2.80/M (to 1B) | $0.90/M (300M+) |
| Over 1B | $2.38/M | $0.90/M |

**Cost at scale:**

| Monthly Requests | REST API | HTTP API | Savings |
|-----------------|----------|----------|---------|
| 1M | $3.50 | $1.00 | 71% |
| 10M | $35.00 | $10.00 | 71% |
| 100M | $350.00 | $100.00 | 71% |
| 1B | $3,033 | $930 | 69% |

**Important nuance:** HTTP API meters requests in 512 KB increments. When request+response payloads exceed ~1,536 KB, HTTP API can become **more expensive** than REST API. For typical small-payload microservices, HTTP API saves ~70%.

**Cache pricing (REST API only):** $0.020/hr (0.5 GB) to $3.80/hr (237 GB). Runs 24/7 once enabled.

**Data transfer:** $0.09/GB outbound for both. Private APIs have no data transfer charges (PrivateLink charges apply separately).

### Performance & Latency

**AWS official claim:** HTTP API adds <10ms overhead at p99, representing ~60% reduction vs REST API (implying ~25ms REST API p99 overhead).

**Independent benchmark (cloudonaut.io, m5.large + k6 + Lambda):**

| Metric | HTTP API | REST API | Delta |
|--------|----------|----------|-------|
| Average | 14.13 ms | 16.83 ms | -16% |
| p90 | 15.97 ms | 18.58 ms | -14% |
| p95 | 18.63 ms | 23.05 ms | -19% |

The absolute difference (~2.5ms avg) is real but negligible in practice — backend processing (DB queries, computation) dominates total latency.

**Edge-optimized caveat:** REST API with edge optimization uses CloudFront POPs, which can outperform regional HTTP API for globally distributed clients. HTTP API has no edge-optimized option.

### Limits & Quotas

| Quota | REST API | HTTP API |
|-------|----------|----------|
| Payload size | 10 MB (hard) | 10 MB (hard) |
| Integration timeout | 50ms–29s (extendable for regional) | 30s (hard) |
| Account throttle | 10,000 RPS / 5,000 burst | 10,000 RPS / 5,000 burst |
| Routes per API | 300 (increasable) | 300 (increasable) |
| **Integrations per API** | **300 (increasable)** | **300 (hard, NOT increasable)** |
| VPC links per region | 20 (increasable) | 10 (increasable) |

The 300-integration hard limit on HTTP API is a critical constraint for one-Lambda-per-endpoint architectures.

### 2024–2025 Feature Investment Trajectory

**Every significant feature addition in 2024–2025 went to REST API:** response streaming, routing rules, developer portal, enhanced TLS policies, ALB private integrations, custom domains for private APIs, TLS 1.3, SIGv4a. HTTP API received essentially zero new features. The feature gap is **widening, not narrowing** — counter to HTTP API's original positioning as the "future" of API Gateway.

---

## Evidence

**Pricing source:** AWS API Gateway Pricing page (aws.amazon.com/api-gateway/pricing/)
- REST: $3.50 → $2.80 → $2.38 per million (tiered)
- HTTP: $1.00 → $0.90 per million (tiered)

**Latency source:** cloudonaut.io independent benchmark — 14.13ms avg (HTTP) vs 16.83ms avg (REST). AWS blog claims <10ms p99 overhead for HTTP API, ~60% reduction vs REST.

**Feature matrix source:** AWS official comparison at docs.aws.amazon.com/apigateway/latest/developerguide/http-api-vs-rest.html

**2025 feature additions source:** AWS API Gateway Document History (docs.aws.amazon.com/apigateway/latest/developerguide/history.html) and AWS What's New announcements.

**Cache pricing source:** $0.020/hr (0.5 GB) through $3.80/hr (237 GB) — costgoat.com/pricing/amazon-api-gateway

**Throttle in smaller regions:** Africa Cape Town, Europe Milan, Asia Pacific Jakarta, Middle East UAE default to 2,500 RPS / 1,250 burst instead of 10,000/5,000.

---

## Trade-offs

### When REST API is clearly better
- **Third-party API consumers**: API keys, usage plans, per-client throttling, and the new developer portal are essential for external-facing APIs. HTTP API has none of these.
- **Security-sensitive workloads**: WAF integration, resource policies, and request validation provide defense-in-depth that HTTP API cannot match without adding CloudFront+WAF in front.
- **Debugging complex integrations**: Execution logs and X-Ray tracing are invaluable; HTTP API only offers access logs.
- **Global distribution**: Edge-optimized endpoints route through CloudFront POPs automatically. HTTP API requires you to build and manage your own CloudFront distribution.
- **Long-running operations**: REST API timeout can be extended beyond 29s for regional/private endpoints; HTTP API is hard-capped at 30s.

### When HTTP API is clearly better
- **Internal microservices with JWT auth**: Native JWT authorizer is simpler than REST API's Lambda authorizer approach. 71% cost savings add up for high-volume internal traffic.
- **Simple proxy to Lambda/HTTP backends**: If you don't need validation, caching, or API keys, HTTP API is cheaper and marginally faster.
- **Cloud Map service discovery**: HTTP API-exclusive feature for private integrations.

### The "CloudFront in front" escape hatch
Many HTTP API limitations (no WAF, no edge optimization, no caching) can be worked around by placing CloudFront in front. But this adds infrastructure complexity, cost, and means you're building the REST API feature set manually. At that point, the cost savings may not justify the operational overhead.

### Counter-intuitive findings
1. **HTTP API is NOT the future.** Despite initial positioning, AWS has invested exclusively in REST API since 2024. HTTP API appears to be in maintenance mode.
2. **HTTP API can be more expensive** for large payloads due to 512 KB metering increments.
3. **Usage plan throttling is best-effort, not guaranteed.** AWS docs explicitly warn: "Don't rely on usage plan quotas or throttling to control costs or block access." Clients can exceed configured quotas.
4. **Edge-optimized REST API silently capitalizes headers** (e.g., `cookie` → `Cookie`), which can break case-sensitive backends.
5. **REST API reserves `/ping` and `/sping`** as root-level paths for health checks.

### Known gotchas worth flagging
- HTTP API's JWKS endpoint has a hard 1,500ms timeout — slow identity providers will cause auth failures
- REST API's `X-Amzn-Remapped-` header prefix on `Authorization`, `Date`, `Server`, `WWW-Authenticate` can break clients
- Query strings don't support `|`, `{}`, or `;` in REST API; semicolons silently split data
- Stage variable changes in REST API take effect instantly (no deployment required), creating production risk

---

## New Questions

1. **WebSocket API vs AppSync subscriptions vs IoT Core**: Given that REST API is getting response streaming (Nov 2025), when does WebSocket API remain the right choice vs streaming REST or other real-time AWS services?

2. **API Gateway vs ALB + Lambda**: For internal APIs that don't need API keys, caching, or request validation, an ALB with Lambda targets may be cheaper and simpler than either API Gateway variant. What are the break-even points?

3. **The new Routing Rules feature (Jun 2025)**: This enables A/B testing, cell-based architecture, and API versioning by header/hostname/cookie without path changes. How does this change the architecture patterns for multi-tenant SaaS, and does it reduce the need for CloudFront-based routing?
