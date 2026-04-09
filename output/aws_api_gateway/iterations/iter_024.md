# Iteration 024 — done

**Status:** discard  
**Scores:** coverage=93.0, quality=50.0, total=67.2  
**Timestamp:** 2026-04-06T11:21:15.638355+00:00  

---

## Final Synthesis: AWS API Gateway for Enterprise REST and WebSocket APIs

All research dimensions have been explored. Below is the consolidated analysis for a senior cloud architect.

---

### Findings

#### The Three Products

AWS API Gateway is three separate products that share a name and pricing page:

| Product | Best For | Status |
|---------|----------|--------|
| **REST API** | External APIs, API management, security-sensitive workloads | Actively developed (all 2024–2025 features) |
| **HTTP API** | Internal microservices, JWT-authed high-volume traffic | Maintenance mode |
| **WebSocket API** | Bidirectional persistent connections <50K concurrent | Stable, no recent feature additions |

---

### Evidence

#### REST API vs HTTP API: Decision Criteria

**Choose REST API when any of the following apply:**
- External API consumers who need API keys, usage plans, or per-client rate limiting
- AWS WAF is required (HTTP API cannot attach WAF without a CloudFront layer)
- Request validation or transformation is needed before hitting the backend
- X-Ray tracing or execution logs are required for debugging
- Global distribution matters and you don't want to manage your own CloudFront
- Response caching reduces backend load (REST API-only feature)
- New (Nov 2025) response streaming, routing rules, or developer portal are needed

**Choose HTTP API when:**
- Internal microservices with JWT auth (native JWT authorizer, 71% cost savings)
- Simple Lambda proxy with no management overhead needed
- Cloud Map service discovery (HTTP API-exclusive)
- You will never exceed 300 integrations (hard limit, not increasable)

**The cost math at scale:**

| Monthly Requests | REST API | HTTP API |
|-----------------|----------|----------|
| 10M | $35 | $10 |
| 100M | $350 | $100 |
| 1B | $3,033 | $930 |

**Critical nuance:** HTTP API meters in 512 KB increments. When request+response payloads exceed ~1,536 KB, HTTP API becomes more expensive than REST API.

**Feature investment trajectory is decisive:** Every significant 2024–2025 feature (response streaming, routing rules, developer portal, TLS 1.3, ALB private integrations, SIGv4a, custom domains for private APIs) went to REST API. HTTP API received nothing. For any production system expecting to be maintained for 3+ years, this trajectory matters.

---

#### WebSocket API: Hard Limits That Determine Feasibility

| Constraint | Value | Adjustable | Impact |
|-----------|-------|------------|--------|
| New connections/second | 500/s | Yes (quota increase) | Bottleneck for bursty onboarding |
| Connection duration | 2 hours | **No** | Reconnection logic is mandatory |
| Idle timeout | 10 minutes | **No** | App-level heartbeats required |
| Frame size | 32 KB | **No** | Frames must be split client-side |
| Message payload | 128 KB | **No** | Large data requires app-layer chunking |
| @connections throttle | Shared 10K RPS | No | Fan-out to 10K clients takes ≥1 second |
| Account-wide RPS | 10K RPS / 5K burst | Yes (Support) | Shared with REST/HTTP APIs |

**The fan-out problem is the central WebSocket API architectural challenge.** There is no broadcast primitive. Sending one update to N connected clients requires N sequential @connections POST calls, each consuming 1 RPS from the shared 10K RPS account quota. At 100K concurrent users, a single broadcast event takes ≥10 seconds just in API calls.

**WebSocket API cost model (100K concurrent users, 30 min/day, 10 msg/min):**
- Connection-minutes: 90M/month = **$22.50**
- Messages: 900M/month = **$900**
- Heartbeats (1/9min): 10M/month = **$10**
- **Total: ~$932/month**

Compared to HTTP API polling every 6 seconds for same users: **$432/month** — polling is cheaper unless message frequency justifies WebSocket overhead.

---

### Trade-offs

#### The REST API Response Streaming Inflection Point (Nov 2025)

REST API streaming fundamentally changes the WebSocket API value proposition. Many historical WebSocket use cases now have a better-fit alternative:

| Use Case | Old Answer | New Answer (2025) |
|----------|-----------|-------------------|
| LLM token streaming | WebSocket | REST API streaming (simpler, WAF support, API keys) |
| Large file delivery | WebSocket chunking | REST API streaming (10MB+, 15-min timeout) |
| SSE-style server push | WebSocket | REST API streaming (standard HTTP, no connection state) |
| Server-sent events | WebSocket | REST API streaming |
| Bidirectional chat | WebSocket | **Still WebSocket** |
| Collaborative editing | WebSocket | **Still WebSocket** |
| Multiplayer gaming | WebSocket | **Still WebSocket** |

WebSocket API's remaining defensible territory is **true bidirectional, low-latency, persistent connections** — a narrower niche than before November 2025.

#### When Each Product Wins

**REST API: external-facing enterprise APIs**
- Every operator requirement (API keys, quotas, throttling, developer portal, WAF, caching) is native
- X-Ray + execution logs make debugging production issues tractable
- Edge-optimized endpoints handle global distribution without additional infrastructure
- HTTP API "CloudFront in front" workaround reconstructs the REST API feature set at higher operational cost

**HTTP API: internal high-volume microservices**
- 71% cost reduction is real and meaningful at 100M+ requests/month
- Native JWT authorizer is simpler than Lambda authorizer for Cognito/OIDC backends
- Automatic deployments reduce deployment pipeline complexity
- Hard 300-integration limit is fine for services with bounded endpoint counts

**WebSocket API: bidirectional real-time at moderate scale (<50K concurrent)**
- Cost-effective vs polling when message frequency >1/min/client
- Deep Lambda integration for custom routing logic
- Manageable operational complexity below ~50K concurrent connections

**IoT Core: fan-out/broadcast at scale**
- Native pub/sub eliminates the N-calls-for-N-clients problem
- Managed connection lifecycle; no DynamoDB connection table required
- Offline message queuing built in
- More expensive per-byte (5 KB metering vs 32 KB) but operationally far simpler at scale

**AppSync Events (April 2025+): serverless real-time for new projects**
- Built-in channel/namespace model with managed fan-out
- Multi-auth support native
- Less operational overhead than WebSocket API + DynamoDB pattern
- Better fit for GraphQL-centric architectures; less flexible for custom protocol needs

---

#### Operational Gotchas That Bite Production Systems

**REST API:**
- Edge-optimized endpoints silently capitalize HTTP headers (`cookie` → `Cookie`) — breaks case-sensitive backends
- `$default` stage is mutable without a deployment — stage variable changes take effect instantly, creating live-production risk
- Usage plan quotas are best-effort: AWS docs explicitly state you cannot rely on them to control costs or block access
- `/ping` and `/sping` are reserved root-level paths

**HTTP API:**
- JWKS endpoint has a hard 1,500ms timeout — slow IdPs cause auth failures
- 300-integration limit is hard and not increasable via support ticket
- No execution logs, only access logs — debugging Lambda integration errors requires CloudWatch Logs Insights on the Lambda side

**WebSocket API:**
- `$disconnect` fires best-effort only; abrupt disconnects (network loss, process kill) never fire it. DynamoDB TTL cleanup is mandatory
- Heartbeat messages are billable — 1M connections × 1 heartbeat/9min = ~$100/month in pure keepalive costs
- 500 conn/s rate limit increases require Support escalation and can take 2+ weeks; AWS sometimes requires trade-offs (reduced integration timeout) as a condition
- The 10K RPS shared throttle means a WebSocket broadcast storm throttles REST API endpoints in the same account/region
- `GoneException` (410) on @connections POST must be caught and trigger DynamoDB cleanup — unhandled, it accumulates zombie connection entries indefinitely

---

### New Questions

These are the highest-value unanswered questions from the full research arc:

1. **API Gateway vs ALB + Lambda break-even analysis**: For internal APIs without API keys, caching, or request validation, an ALB with Lambda targets eliminates API Gateway entirely. ALB pricing: $0.008/LCU-hour + $0.008/GB. At what request volume and payload size does ALB become cheaper than HTTP API? The answer determines whether HTTP API is ever the right default for internal services.

2. **Hybrid architecture: REST API + IoT Core for mixed workloads**: For applications needing both request/response (orders, auth, CRUD) and real-time push (notifications, live updates), what does a canonical architecture look like using REST API for transactional endpoints and IoT Core for push channels? Specifically: connection lifecycle, cost model at 10K/100K/1M users, and how the client SDK complexity compares to a single WebSocket API endpoint.

3. **AppSync Events quotas and limits for production workloads**: AppSync Events (GA April 2025) promises managed fan-out with built-in connection lifecycle. What are its hard limits — concurrent connections, events/second, payload size, fan-out latency at scale — and does it actually eliminate the operational overhead of WebSocket API + DynamoDB, or does it introduce its own constraints that make it unsuitable for high-throughput real-time?
