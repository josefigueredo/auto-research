# Iteration 027 — done

**Status:** discard  
**Scores:** coverage=100.0, quality=50.0, total=70.0  
**Timestamp:** 2026-04-06T11:27:16.145979+00:00  

---

## Findings

All planned research dimensions have been completed. This iteration delivers the final synthesis for the senior cloud architect.

---

### Decision Framework: Which API Gateway Product for Which Workload

#### The Core Choice Matrix

| Workload Type | Recommended Product | Key Reason |
|--------------|-------------------|------------|
| External/third-party REST API | **REST API** | API keys, usage plans, WAF, developer portal — non-negotiable for monetization or partner access |
| Internal microservices (JWT auth) | **HTTP API** | 71% cheaper, native JWT authorizer, sufficient feature set |
| Internal microservices (IAM auth) | **HTTP API or REST API** | Either works; HTTP API cheaper unless you need WAF or request validation |
| Real-time bidirectional (chat, collab) | **WebSocket API** | Only serverless option for true server-initiated push with custom routing |
| LLM/AI response streaming | **REST API (streaming)** | Nov 2025 feature: >10MB payloads, 15-min timeout, WAF support — purpose-built |
| Large fan-out push (>100K concurrent) | **IoT Core or AppSync Events** | WebSocket API's 500 conn/s and missing broadcast are architectural blockers |
| GraphQL real-time subscriptions | **AppSync Events** | Managed connection lifecycle, native pub/sub, April 2025 WebSocket support |
| High-volume SSE-style server push | **REST API (streaming)** | WebSocket adds unnecessary complexity; streaming REST is simpler |

---

### Cost Decision Points

#### HTTP API vs REST API Break-Even

HTTP API costs 71% less at identical request volumes **unless**:
1. **Payload > ~1,536 KB**: HTTP API meters in 512 KB increments, REST API meters per-request. A 2 MB payload costs 4× on HTTP API vs 1× on REST API.
2. **You add CloudFront+WAF**: Adds ~$0.60/M requests (CloudFront) + WAF costs, eroding the savings.
3. **You need caching**: REST API cache eliminates backend hits entirely for cacheable responses; HTTP API has no cache.

#### WebSocket API vs HTTP API Polling Break-Even

| Update Frequency | Cheaper Option | Why |
|-----------------|---------------|-----|
| < 1 msg/min/client | HTTP API polling | Zero connection-minute charge vs continuous billing |
| ~1 msg/min/client | Break-even | ~$1/M messages ≈ polling cost at 60s intervals |
| > 1 msg/min/client | WebSocket API | Avoids duplicate polling requests per interval |
| Bidirectional | WebSocket API | Polling cannot substitute for client→server initiation |

#### WebSocket Fan-Out Hidden Cost

Broadcasting to N clients = N @connections POST calls = N billed messages. At 100K concurrent users receiving 10 updates/minute:
- **Fan-out messages**: 10 updates × 100K clients × 60 min × 730 hr/mo = **43.8 billion messages/month**
- **Cost**: ~$34,000/month in message charges alone, plus $22.50 connection-minutes
- **IoT Core equivalent**: Publish once per topic, all subscribers receive it — dramatically cheaper at scale

---

### Enterprise Architecture Patterns

#### Pattern 1: Layered API Platform (Most Common Enterprise Pattern)

```
CloudFront (edge cache + WAF rules)
    ↓
REST API (external-facing: API keys, usage plans, request validation)
    ↓
HTTP API (internal service mesh: JWT auth, 71% cheaper)
    ↓
VPC Link → ECS/EKS/Lambda
```

**When to use**: Multi-tenant SaaS, partner API programs, enterprises with external API consumers.

#### Pattern 2: Real-Time + REST Hybrid

```
REST API (CRUD, query operations)     WebSocket API (live updates)
         ↓                                      ↓
    Lambda                           Lambda → DynamoDB (connection store)
                                              ↓
                                     @connections POST per client
```

**When to use**: Chat applications, collaborative tools, live dashboards at moderate scale (<50K concurrent).

#### Pattern 3: Streaming-First (Post-Nov 2025)

```
REST API with response streaming
    ↓
Lambda (streaming response mode)
    ↓
Chunked transfer to client
```

**Replaces WebSocket for**: LLM chat interfaces, large report generation, real-time log streaming, any unidirectional server-push scenario. Benefits: WAF protection, API keys, response caching headers, standard HTTP tooling, 15-min timeout.

#### Pattern 4: Scale-Out Real-Time (>100K concurrent)

```
IoT Core (MQTT over WebSocket)
    ↓
Topic-based pub/sub (native broadcast)
    ↓
DynamoDB-backed subscription tracking (optional)
```

**Or for GraphQL teams:**
```
AppSync Events (April 2025)
    ↓
Channel namespaces (built-in fan-out)
    ↓
Multi-auth (API key, Cognito, IAM, Lambda)
```

---

### Definitive Limit Reference

| Limit | REST API | HTTP API | WebSocket API | Notes |
|-------|----------|----------|---------------|-------|
| Max payload | 10 MB | 10 MB | 128 KB (32 KB frames) | WebSocket severely constrains binary/large data |
| Integration timeout | 50ms–29s (extendable) | 30s hard | 29s | REST API extendable for regional/private |
| Streaming timeout | **15 min** | N/A | N/A | REST API only, Nov 2025 |
| Account RPS throttle | 10K/5K burst | 10K/5K burst | Shared | Shared pool — WebSocket traffic eats REST quota |
| New connections/s | N/A | N/A | 500/s (adjustable) | Hard to increase; 2-week lead time for large asks |
| Connection duration | N/A | N/A | 2 hr hard | No exceptions; reconnect logic mandatory |
| Idle timeout | N/A | N/A | 10 min hard | No server-side pings; heartbeats are billable |
| Integrations per API | 300 (increasable) | **300 hard** | 300 (increasable) | HTTP API hard limit blocks one-Lambda-per-endpoint at scale |
| Payload metering | Per request | Per 512 KB | Per 32 KB | All three meter differently |
| Small region throttle | 2,500/1,250 | 2,500/1,250 | 2,500/1,250 | Africa Cape Town, EU Milan, AP Jakarta, ME UAE |

---

### Feature Investment Trajectory (Strategic Signal)

| Period | REST API | HTTP API | WebSocket API |
|--------|----------|----------|--------------|
| 2024–2025 additions | 8+ major features | ~0 | ~0 |
| 2025 notable additions | Streaming, routing rules, developer portal, TLS 1.3, SIGv4a | None | None |
| Trajectory | **Active investment** | Maintenance mode | Maintenance mode |

**Architectural implication**: REST API is the long-term platform. HTTP API's cost advantage is real but its feature ceiling is fixed. Organizations building for 3–5 year horizons should treat HTTP API as an optimization layer, not a foundation. WebSocket API gaps (no broadcast, no connection management) show no sign of being addressed — plan for IoT Core or AppSync Events for any real-time workload that may need to scale.

---

### Critical Operational Gotchas (Consolidated)

1. **Usage plan throttling is not a security control.** AWS explicitly documents that it's best-effort and clients can exceed quotas. Do not rely on it for cost control or access blocking — use WAF rate limiting instead.

2. **Edge-optimized REST API silently capitalizes headers.** `authorization` → `Authorization`, `cookie` → `Cookie`. Case-sensitive backends break silently.

3. **WebSocket $disconnect is unreliable.** Abrupt disconnects (network loss, mobile backgrounding) never fire $disconnect. DynamoDB TTL on connection records is mandatory, not optional.

4. **The 10K RPS account throttle is shared across all API Gateway types.** A WebSocket fan-out event (broadcasting to 50K connections = 50K @connections calls) can temporarily throttle your REST API endpoints in the same region.

5. **REST API reserves `/ping` and `/sping`.** These root-level paths respond with 200 OK for health checks and cannot be used by your API.

6. **Stage variable changes take effect instantly in REST API** (no deployment required). This is a sharp edge — a mistyped stage variable change hits production immediately.

7. **HTTP API's JWKS endpoint has a 1,500ms hard timeout.** Slow or cold identity providers (Okta under load, custom OIDC) cause authentication failures with no retry. Cache JWKS aggressively.

8. **WebSocket connection rate increases require AWS negotiation.** One documented case: 2-week process, required accepting reduced integration timeout as trade-off. Plan ahead for launch events.

9. **Query strings in REST API don't support `|`, `{}`, or `;`.** Semicolons silently split parameter values — a subtle data corruption vector if your client URL-encodes these.

10. **HTTP API 300-integration hard limit.** Unlike REST API where 300 is a soft quota, HTTP API's limit is hard and non-negotiable. Microservice architectures with >300 Lambda functions need REST API or multiple HTTP API instances behind a router.

---

## Evidence

All pricing, limits, and benchmarks sourced and cross-referenced across:
- AWS API Gateway Pricing page (official, US-East-1 baseline)
- AWS API Gateway developer documentation (quotas tables, feature comparison, history)
- cloudonaut.io independent latency benchmark (14.13ms HTTP avg vs 16.83ms REST avg)
- DAZN Engineering case study (500 conn/s limit as production deal-breaker)
- Ably scaling analysis (DynamoDB connection tracking, $disconnect reliability)
- AWS re:Post community documentation (idle timeout behavior, heartbeat billing)
- CostGoat API Gateway calculator (cache pricing, connection-minute modeling)
- AWS What's New announcements (Nov 2025 streaming, Jun 2025 routing rules, Apr 2025 AppSync Events)

---

## Trade-offs

### The One Genuinely Hard Decision

**HTTP API vs REST API for internal services** is the only case where reasonable architects disagree. The 71% cost savings are real and compound at scale ($270K/year at 1B requests/month). The counter-argument: if you ever need WAF, request validation, or detailed tracing, retrofitting to REST API or adding a CloudFront layer is expensive. The pragmatic answer: start with HTTP API for net-new internal services, migrate only the ones that hit HTTP API's ceiling, and never use HTTP API for external-facing APIs.

**WebSocket API is a narrow tool.** Its value proposition is genuine for true bidirectional, persistent connections at moderate scale. Outside that niche — unidirectional streaming, massive fan-out, GraphQL subscriptions — better-fitted AWS services exist. The Nov 2025 REST API streaming feature has materially shrunk WebSocket's addressable use cases.

---

## New Questions

1. **AppSync Events limits and pricing (April 2025)**: AppSync Events added WebSocket publishing with managed channels/namespaces and multi-auth. What are its hard limits (concurrent connections, message size, fan-out capacity), pricing model, and where does it break down vs WebSocket API for custom routing needs?

2. **IoT Core cost/complexity break-even for non-IoT workloads**: IoT Core is purpose-built for pub/sub fan-out but carries "IoT" baggage (device registration, thing shadows, certificate management). At what scale does adopting IoT Core's operational complexity justify its broadcast efficiency vs accepting WebSocket API's per-client @connections cost? What does a minimal non-IoT architecture on IoT Core actually look like?

3. **REST API routing rules (Jun 2025) for multi-tenant SaaS**: The new routing rules feature enables A/B testing and cell-based routing by header/hostname/cookie without path changes. Does this eliminate the need for CloudFront-based routing for blue/green deployments and tenant isolation, and what are its limits (max rules, condition types, target types)?
