# Iteration 025 — done

**Status:** discard  
**Scores:** coverage=100.0, quality=50.0, total=70.0  
**Timestamp:** 2026-04-06T11:23:16.716794+00:00  

---

## Final Synthesis: AWS API Gateway Options for Enterprise REST and WebSocket APIs

All research dimensions have been explored. This is the consolidated decision document.

---

### Findings

#### The Three Products

AWS API Gateway is three distinct products with different maturity, pricing, and intended use cases:

| Dimension | REST API | HTTP API | WebSocket API |
|-----------|----------|----------|---------------|
| **Launched** | 2015 | 2020 | 2018 |
| **Feature count** | ~47 | ~22 | ~15 |
| **Investment trajectory** | Active (all 2024–2025 features) | Maintenance mode | Maintenance mode |
| **Best for** | External/enterprise APIs | Internal microservices | Bidirectional real-time |
| **Pricing model** | Per-request (tiered) | Per-request (tiered) | Per-message + per-connection-minute |

---

#### REST API vs HTTP API: Feature Matrix

**Security & Authorization**

| Feature | REST API | HTTP API |
|---------|----------|----------|
| AWS WAF | Yes | No |
| Mutual TLS | Yes | Yes |
| Backend certs | Yes | No |
| Resource policies | Yes | No |
| IAM auth | Yes | Yes |
| Cognito | Yes (native) | Yes (via JWT) |
| Lambda authorizer | Yes | Yes |
| Native JWT | No | Yes |

**API Management**

| Feature | REST API | HTTP API |
|---------|----------|----------|
| API keys / usage plans | Yes | No |
| Per-client throttling | Yes | No |
| Response caching | Yes | No |
| Request validation | Yes | No |
| Request/response transformation | Yes | No |
| Canary deployments | Yes | No |
| Response streaming (>10MB, 15-min timeout) | Yes (Nov 2025) | No |
| Routing rules (A/B, cell-based) | Yes (Jun 2025) | No |
| Developer portal | Yes (Nov 2025) | No |
| Automatic deployments | No | Yes |
| Cloud Map integration | No | Yes |

**Observability**

| Feature | REST API | HTTP API |
|---------|----------|----------|
| X-Ray tracing | Yes | No |
| Execution logs | Yes | No |
| Access logs (CloudWatch) | Yes | Yes |
| Access logs (Firehose) | Yes | No |

**Endpoints**

| Feature | REST API | HTTP API |
|---------|----------|----------|
| Edge-optimized (CloudFront) | Yes | No |
| Regional | Yes | Yes |
| Private (VPC) | Yes | No |

---

#### Pricing

**REST API vs HTTP API (US East):**

| Monthly Requests | REST API | HTTP API | Savings |
|-----------------|----------|----------|---------|
| 1M | $3.50 | $1.00 | 71% |
| 10M | $35.00 | $10.00 | 71% |
| 100M | $350 | $100 | 71% |
| 1B | $3,033 | $930 | 69% |

**WebSocket API (US East):**

| Component | Rate |
|-----------|------|
| Messages | $1.00/M (first 1B), $0.80/M (over 1B) |
| Connection-minutes | $0.25/M (flat) |
| Message metering | 32 KB increments |

**WebSocket cost at scale (30 min/day connected, 10 msg/min):**

| Scale | Connection cost/mo | Message cost/mo | Total |
|-------|--------------------|-----------------|-------|
| 10K users | $2.25 | $90 | $92 |
| 100K users | $22.50 | $900 | $923 |
| 1M users | $225 | $7,400 | $7,625 |

**HTTP API polling break-even:** For updates arriving <1/minute, HTTP API polling at 6-second intervals costs ~$432/month (100K users) vs $923/month for WebSocket — polling wins. Above ~1 update/minute, WebSocket is cheaper.

**Cache pricing (REST API only):** $0.020/hr (0.5 GB) to $3.80/hr (237 GB) — runs 24/7.

---

#### Hard Limits

| Quota | REST API | HTTP API | WebSocket API |
|-------|----------|----------|---------------|
| Payload size | 10 MB | 10 MB | 128 KB (32 KB frames) |
| Integration timeout | 29s (extendable, regional) | 30s hard | 29s |
| Streaming timeout | 15 min (Nov 2025) | N/A | N/A |
| Account throttle (RPS/burst) | 10K/5K shared | 10K/5K shared | 10K/5K shared |
| Integrations per API | 300 (increasable) | **300 hard** | 300 (increasable) |
| New connections/s | N/A | N/A | 500/s (increasable, but slowly) |
| Connection duration | N/A | N/A | 2hr hard |
| Idle timeout | N/A | N/A | 10min hard |

**The HTTP API 300-integration hard limit** is a critical architectural constraint — it cannot be raised via Service Quotas or Support, unlike REST API's equivalent limit.

**The WebSocket 10K RPS throttle is shared** with all other API Gateway traffic in the account/region. A fan-out broadcast storm can throttle REST API production traffic.

---

#### Performance

**HTTP API vs REST API latency (cloudonaut.io, independent benchmark):**

| Metric | HTTP API | REST API | Delta |
|--------|----------|----------|-------|
| Average | 14.1 ms | 16.8 ms | −16% |
| p90 | 16.0 ms | 18.6 ms | −14% |
| p95 | 18.6 ms | 23.1 ms | −19% |

The ~2.5ms average difference is real but negligible when backends involve any DB query. AWS official claim: HTTP API adds <10ms p99 overhead, ~60% reduction vs REST API.

**Edge-optimized REST API** routes through CloudFront POPs globally — can outperform regional HTTP API for geographically distributed clients. HTTP API has no edge-optimized option.

---

#### 2024–2025 Investment Reality

Every significant feature addition in this period went to REST API:
- **Nov 2025**: Response streaming (payloads >10MB, 15-min timeout, all regions including GovCloud)
- **Nov 2025**: Developer portal (built-in API discovery for external consumers)
- **Jun 2025**: Routing rules (A/B testing, cell-based routing, version routing by header/hostname/cookie)
- **2025**: ALB private integrations, custom domains for private APIs, TLS 1.3, SIGv4a support

HTTP API and WebSocket API received zero major features. The original positioning of HTTP API as the "future" of API Gateway has not materialized.

---

### Evidence

| Claim | Source |
|-------|--------|
| REST API tiered pricing $3.50→$2.80→$2.38/M | AWS API Gateway Pricing page |
| HTTP API tiered pricing $1.00→$0.90/M | AWS API Gateway Pricing page |
| HTTP API 300-integration hard limit (not adjustable) | AWS docs — HTTP API vs REST API comparison table |
| Cache pricing $0.020/hr–$3.80/hr | costgoat.com API Gateway pricing |
| HTTP API <10ms p99, ~60% latency reduction | AWS official blog |
| Independent benchmark 14.1ms vs 16.8ms avg | cloudonaut.io (m5.large, k6, Lambda) |
| WebSocket $1.00/M messages, $0.25/M connection-minutes | AWS API Gateway Pricing page |
| WebSocket 500 new conn/s (adjustable), 2hr hard, 10min idle hard | AWS WebSocket Quotas docs |
| 32KB frame / 128KB message hard limits | AWS WebSocket Quotas docs |
| DAZN 500 conn/s "deal-breaker" at millions-of-users scale | DAZN Engineering — Serverless WebSockets at Scale (Medium) |
| No server-initiated WebSocket pings | AWS re:Post |
| Response streaming Nov 2025, all regions, 15-min timeout | AWS What's New announcements |
| Routing rules Jun 2025 | AWS API Gateway Document History |
| AppSync Events WebSocket publishing Apr 2025 | AWS What's New |
| Africa/Milan/Jakarta/UAE default to 2,500 RPS not 10,000 | AWS regional quota tables |

---

### Trade-offs

#### REST API: Choose When

- **External API consumers**: API keys, usage plans, per-client throttling, and the new developer portal are non-negotiable for third-party integrators. HTTP API has none of these.
- **Security-sensitive workloads**: WAF integration, resource policies, and request validation provide defense-in-depth impossible to replicate with HTTP API alone. Adding CloudFront+WAF in front of HTTP API recreates the REST API feature set at higher complexity.
- **Complex debugging requirements**: Execution logs and X-Ray tracing are invaluable. HTTP API offers access logs only.
- **Global distribution**: Edge-optimized endpoints automate CloudFront routing. HTTP API requires building and operating your own CloudFront distribution.
- **One-Lambda-per-endpoint architectures at >300 endpoints**: REST API's 300-integration limit is increasable; HTTP API's is not.
- **Long-running operations**: REST API regional timeout is extendable beyond 29s; HTTP API is hard-capped at 30s.
- **LLM/streaming responses (Nov 2025+)**: Response streaming with 15-min timeout, >10MB payloads, full WAF/caching/API key support — purpose-built for generative AI APIs.
- **Multi-tenant SaaS with A/B or cell-based routing**: The Jun 2025 routing rules feature (header/hostname/cookie-based routing without path changes) is REST API-only and eliminates the need for CloudFront-based routing in many architectures.

#### HTTP API: Choose When

- **Internal microservices with JWT auth**: Native JWT authorizer is simpler than REST API's Lambda authorizer. 71% cost savings compound at scale for high-volume internal traffic.
- **Simple Lambda/HTTP proxies**: No validation, caching, or API keys needed — HTTP API is cheaper and marginally faster.
- **Cloud Map service discovery**: HTTP API-exclusive feature for private service discovery integrations.
- **Architectures staying under 300 integrations**: The hard limit is irrelevant at small scale.
- **Cost is the primary constraint for internal traffic**: At 1B requests/month, HTTP API saves ~$2,100 vs REST API.

**The "CloudFront in front" escape hatch:** HTTP API limitations (no WAF, no edge optimization, no caching) can be partially worked around by adding CloudFront. But this adds infrastructure complexity and cost. When CloudFront + WAF + Lambda@Edge is required, the operational overhead often exceeds the 71% cost savings, and you're manually rebuilding the REST API feature set.

#### WebSocket API: Choose When

- **True bidirectional communication at moderate scale (<50K concurrent)**: Chat, collaborative editing, multiplayer gaming — where both client and server initiate messages unpredictably.
- **High-frequency push at small-medium scale**: Stock tickers, IoT dashboards, live scoreboards where server pushes >1 msg/min and connection count is tractable.
- **Custom routing logic required**: Route selection expressions provide more flexibility than AppSync Events' channel/namespace model.

#### WebSocket API: Do NOT Choose When

- **Fan-out to >100K concurrent connections**: No native broadcast + 10K RPS shared throttle + mandatory connection tracking DynamoDB + zombie connection cleanup = serious operational burden. Broadcasting 10 updates/minute to 100K clients = 1B additional billed messages/month ($800+) and each broadcast takes ≥10 seconds at the 10K RPS limit.
- **One-way server→client streaming**: REST API response streaming (Nov 2025) is strictly better — 15-min timeout, >10MB, WAF/caching/API keys, no connection management, standard HTTP semantics.
- **LLM/generative AI responses**: REST API streaming is purpose-built. WebSocket adds bidirectional complexity that provides no value.
- **Low-frequency updates (<1/min)**: HTTP API polling is cheaper; connection-minute charges dominate when messages are infrequent.
- **Guaranteed delivery required**: $disconnect is best-effort. Abrupt disconnects (network loss, app kill) leave zombie connections. TTL-based DynamoDB cleanup is mandatory, not optional.

#### When REST API Streaming Changes the Decision (Post-Nov 2025)

The addition of REST API response streaming materially narrows WebSocket API's viable use cases. The updated decision tree:

```
Does the use case require client→server messages AFTER the connection is established?
  No  → Use REST API streaming (simpler, cheaper, better tooling)
  Yes → Is concurrent connection count >50K?
          Yes → Consider IoT Core (native pub/sub) or AppSync Events (managed connections)
          No  → WebSocket API is appropriate
```

#### Critical Counter-Intuitive Findings

1. **HTTP API is in maintenance mode, not the future.** Initial AWS positioning suggested HTTP API would replace REST API. The 2024–2025 investment pattern shows the opposite: REST API is actively developed; HTTP API is frozen.

2. **HTTP API can be more expensive than REST API** for large payloads. Messages are metered in 512 KB increments. Request+response payloads exceeding ~1,536 KB make HTTP API cost-equivalent to or more expensive than REST API.

3. **Usage plan throttling is not a security control.** AWS documentation explicitly warns: "Don't rely on usage plan quotas or throttling to control costs or block access." Clients can exceed configured quotas; treat usage plans as rate-limit hints, not enforcement mechanisms.

4. **WebSocket heartbeat messages are billable.** Maintaining 1M idle connections with 1 heartbeat/9min costs ~$100/month in message charges — a continuous "keep-alive tax" that polling architectures don't incur.

5. **The 10K RPS throttle is shared across all API Gateway types.** A WebSocket fan-out storm in the same account/region will throttle REST API production traffic. This is a critical multi-product isolation concern for enterprise accounts.

6. **Edge-optimized REST API silently capitalizes headers.** `cookie` becomes `Cookie`, `content-type` becomes `Content-Type`. Case-sensitive backends will break silently.

7. **REST API reserves `/ping` and `/sping`** at the root level for internal health checks. These paths cannot be used in your API.

8. **Stage variable changes in REST API are immediate** — no deployment required. This creates a risk of live production changes with no deployment audit trail or rollback path.

9. **Increasing WebSocket connection rate limits requires negotiation**, not a Service Quotas click. One team with Enterprise Support reported a 2-week process requiring timeout trade-offs. Plan ahead for events with known connection spikes.

10. **Private WebSocket APIs** are not supported. WebSocket API is always public-facing. Internal WebSocket use cases require a public endpoint with network-level controls (security groups, NACLs, WAF).

#### Known Gotchas for Operations

| Gotcha | Impact | Mitigation |
|--------|--------|-----------|
| HTTP API JWKS endpoint 1,500ms hard timeout | Auth failures with slow identity providers | Pre-warm IdP, use caching, test P99 JWKS latency |
| REST API `X-Amzn-Remapped-` header prefix | Breaks clients expecting `Authorization`, `Date`, `Server` headers | Strip at CloudFront or application layer |
| Query strings don't support `\|`, `{}`, `;` in REST API | Semicolons silently split query parameters | Encode special characters; validate at API layer |
| WebSocket zombie connections from missed $disconnect | DynamoDB connection table grows unbounded | Mandatory TTL on connection records; reconciliation Lambda |
| Response streaming requires chunked transfer encoding awareness | Clients must handle chunked responses | Test with realistic HTTP clients, not just curl |
| Routing rules (Jun 2025) require explicit stage redeployment | Rule changes don't take effect immediately | Include in deployment runbooks |

---

### New Questions

1. **IoT Core as a managed WebSocket alternative**: Given IoT Core's native pub/sub, managed connection lifecycle, offline message queuing, and topic-based broadcast (no connection tracking database needed), what does a hybrid architecture look like — REST API for request/response + IoT Core for push — and at what concurrent connection count does IoT Core's 5 KB message metering become cheaper than WebSocket API's 32 KB metering?

2. **AppSync Events as the 2025+ default for serverless real-time**: AppSync Events (Apr 2025) added WebSocket publishing with built-in channel/namespace model, managed connection lifecycle, and multi-auth (IAM, Cognito, Lambda, API key). For teams starting greenfield real-time projects today, does AppSync Events now outperform WebSocket API on operational simplicity without meaningful capability loss — and what are its hard limits and pricing at 100K concurrent?

3. **The Routing Rules + Private API combination for multi-tenant SaaS isolation**: The Jun 2025 routing rules feature enables cell-based routing by header/hostname/cookie, and REST API supports private VPC endpoints. Does this combination eliminate the need for per-tenant API Gateway deployments (previously required for true data-plane isolation), and what is the operational model for managing routing rule rollouts across hundreds of tenants without a full stage redeployment?
