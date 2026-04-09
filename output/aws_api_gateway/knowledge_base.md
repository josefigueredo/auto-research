

## REST API vs HTTP API: feature matrix, pricing, and performance differences

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

## WebSocket API: capabilities, connection limits, and scaling patterns

Now I have all the data needed. Let me produce the comprehensive findings.

## Findings

### WebSocket API: Capabilities, Connection Limits, and Scaling Patterns

---

### 1. Hard Limits and Quotas

| Quota | Default Value | Adjustable? | Notes |
|-------|--------------|-------------|-------|
| **New connections/second** | 500/s per account per region | **Yes** (Service Quotas) | Critical bottleneck — determines max concurrent connections |
| **Concurrent connections** | No enforced limit | N/A | Derived: connection rate × max duration. At 500/s over 2hrs = **3.6M theoretical max** |
| **Connection duration** | 2 hours | **No** | Hard cap. Client must implement reconnection logic |
| **Idle timeout** | 10 minutes | **No** | No messages = connection dropped. Must send application-level heartbeats |
| **WebSocket frame size** | 32 KB | **No** | Messages >32KB must be split into multiple frames |
| **Message payload size** | 128 KB | **No** | Total across all frames. Exceeding closes connection with code 1009 |
| **Integration timeout** | 50ms–29s | **No** | Same as REST API; cannot be extended |
| **Routes per API** | 300 | **Yes** (Service Quotas) | |
| **Integrations per API** | 300 | **Yes** (Support Center) | Unlike HTTP API's hard 300 limit |
| **Stages per API** | 10 | **Yes** (Service Quotas) | |
| **Lambda authorizers per API** | 10 | **Yes** (Support Center) | |
| **Authorizer result size** | 8 KB | **No** | |
| **Account throttle** | 10,000 RPS / 5,000 burst | Shared | Shared across REST, HTTP, and WebSocket APIs in the region |
| **Callback message size** | 128 KB / 32 KB frames | **No** | Same limits apply to @connections POST |

**The connection rate is the real constraint.** At 500 new connections/second (default), onboarding 100K users takes ~3.3 minutes. For bursty workloads (sports events, flash sales), this is a severe bottleneck. DAZN found the 1.8M new connections/hour cap was a "deal-breaker" for their millions-of-users sports streaming use case.

**Idle timeout creates operational overhead.** The 10-minute idle timeout is not adjustable and API Gateway does **not** send server-side WebSocket ping frames. It responds to client pings with pongs (per RFC), but clients must send application-level heartbeat messages at <10 minute intervals. These heartbeat messages **are billable** (unlike protocol-level ping/pong which are free).

**The 2-hour hard cap** means every client must implement reconnection logic. Best practice: reconnect proactively at ~90 minutes, not at the 2-hour boundary, to avoid thundering-herd reconnection storms.

---

### 2. Pricing Model and Cost Analysis

WebSocket API uses **dual billing**: per-message + per-connection-minute.

**Unit prices (US East):**

| Component | First Billion | Over 1 Billion |
|-----------|--------------|----------------|
| Messages | $1.00/million | $0.80/million |
| Connection minutes | $0.25/million (flat) | $0.25/million (flat) |

**Metering rules:**
- Messages metered in **32 KB increments** (a 33 KB message = 2 billed messages)
- Ping/pong control frames are **free** (but API Gateway doesn't initiate pings)
- Connection minutes billed continuously, **even with zero message traffic**
- Free tier: 1M messages + 750K connection minutes/month (12 months)

**Realistic cost model — 3 scenarios:**

Assumptions: users connected 30 min/day average, 10 messages/min sent (5 in each direction), 30-day month.

| Metric | 10K concurrent | 100K concurrent | 1M concurrent |
|--------|---------------|-----------------|---------------|
| Daily connection-minutes | 300K | 3M | 30M |
| Monthly connection-minutes | 9M | 90M | 900M |
| **Connection cost/mo** | **$2.25** | **$22.50** | **$225.00** |
| Messages/day (@ 10/min × 30 min) | 3M | 30M | 300M |
| Messages/month | 90M | 900M | 9B |
| **Message cost/mo** | **$90.00** | **$900.00** | **$7,400*** |
| **Total WebSocket cost** | **$92.25** | **$922.50** | **$7,625.00** |
| Heartbeat messages/mo (1/9min) | ~1M | ~10M | ~100M |
| **Heartbeat overhead cost** | **$1.00** | **$10.00** | **$100.00** |

*\*9B messages: first 1B at $1.00/M = $1,000, remaining 8B at $0.80/M = $6,400*

**Comparison to REST API for equivalent polling:**

| Approach | 100K users, 10 events/min | Cost/month |
|----------|--------------------------|------------|
| WebSocket API | 900M messages + 90M conn-min | **$922** |
| REST API (polling every 6s) | 432M requests | **$1,404** |
| HTTP API (polling every 6s) | 432M requests | **$432** |

**Key insight:** WebSocket becomes cost-effective vs REST API polling only when message frequency is moderate (>1 msg/min). For low-frequency updates (<1 msg/min), polling with HTTP API is cheaper because you avoid the continuous connection-minute charges. For high-frequency bidirectional messaging, WebSocket wins clearly.

**The hidden cost: @connections fan-out.** Broadcasting a single update to 100K connected clients requires 100K individual @connections POST calls — each billed as a message. A system that broadcasts 10 updates/minute to 100K users incurs **1 billion** additional messages/month ($800+), plus the 10,000 RPS account throttle means each broadcast takes 10 seconds minimum.

---

### 3. Architecture Patterns and Backend Integration

#### Integration Types

| Type | Description | Use Case |
|------|------------|----------|
| **AWS_PROXY** (Lambda proxy) | Full event passed to Lambda, including connectionId, routeKey, requestContext | Most common pattern. Simplest to implement |
| **AWS** (non-proxy) | Request/response mapping templates transform data before reaching AWS service | Step Functions, DynamoDB direct integration |
| **HTTP_PROXY** | Passes through to HTTP endpoint | Existing WebSocket-aware backend services |
| **HTTP** (non-proxy) | Mapping templates transform request before forwarding | Legacy backends needing request adaptation |
| **VPC Link** | Private integration via NLB | Backend services in VPC (ECS, EKS, EC2) |
| **MOCK** | Returns configured response without backend | Testing, health checks |

#### Route Selection Expression

Routes are selected by evaluating a **route selection expression** against the incoming JSON message payload. Default: `$request.body.action`.

```json
// Client sends:
{"action": "sendMessage", "data": "hello"}

// Route selection expression: $request.body.action
// Matches route key: "sendMessage"
// Falls through to $default if no match
```

**Special routes:**
- `$connect` — fired on WebSocket handshake (only route where authorization runs)
- `$disconnect` — fired on disconnect (best-effort; not guaranteed for abrupt disconnects)
- `$default` — catch-all for unmatched route keys

#### @connections Callback API

The callback URL format: `https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/@connections/{connection_id}`

| Method | Purpose |
|--------|---------|
| **POST** | Send message to connected client (128 KB max payload) |
| **GET** | Retrieve connection status (connectedAt, identity, lastActiveAt) |
| **DELETE** | Force-disconnect a client |

**Critical constraints:**
- All @connections requests require **SigV4 signing** (IAM auth)
- No broadcast/multicast — each client needs its own POST call
- Subject to the shared 10,000 RPS account throttle
- A `GoneException` (410) indicates the client disconnected — must handle gracefully

#### Connection State Management Pattern

API Gateway does **not** manage connection metadata. The standard pattern:

1. **$connect route → Lambda** stores `connectionId`, user metadata, subscription topics in **DynamoDB**
2. **$disconnect route → Lambda** removes the record (best-effort — implement TTL as backup)
3. **Message routes → Lambda** reads connection table to determine recipients, calls @connections POST for each
4. **DynamoDB TTL** cleans up zombie connections from abrupt disconnects where $disconnect never fires

**VPC Link gotcha:** WebSocket APIs don't pass `connectionId` to VPC link integrations by default. You must explicitly map it via `RequestParameters`: `integration.request.header.connectionId` → `context.connectionId`.

#### Scaling Architecture for Fan-Out

For broadcasting at scale, the naive "loop through connections" pattern breaks down. Production patterns:

1. **SNS/SQS fan-out**: Backend publishes to SNS → SQS queues → Lambda consumers batch @connections calls
2. **DynamoDB Streams + Lambda**: Connection table changes trigger downstream processing
3. **Step Functions Distributed Map**: Parallel execution across connection batches (good for 10K–100K range)
4. **EventBridge + Lambda**: Event-driven routing with per-topic fan-out

---

### Evidence

**Quotas source:** [AWS API Gateway WebSocket Quotas](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-execution-service-websocket-limits-table.html) — 500 new connections/s (adjustable), 2hr duration (hard), 10min idle (hard), 32KB frame / 128KB payload (hard).

**Pricing source:** [AWS API Gateway Pricing](https://aws.amazon.com/api-gateway/pricing/) — $1.00/M messages, $0.25/M connection-minutes, $0.80/M messages over 1B.

**Cost modeling cross-reference:** [CostGoat API Gateway Calculator](https://costgoat.com/pricing/amazon-api-gateway) — 10K users × 30 min/day = 900K minutes/month = $0.23 connection cost; confirms $1/M message rate.

**DAZN production experience:** [DAZN Engineering — Serverless WebSockets at Scale](https://medium.com/dazn-tech/aws-serverless-websockets-at-scale-8a79cd5a9f3b) — 500 conn/s limit = 1.8M/hour was "deal-breaker" for millions of sports fans; no native broadcast; each message to N clients = N API calls.

**Scaling analysis:** [Ably — Scaling AWS API Gateway WebSocket APIs](https://ably.com/topic/scaling-aws-api-gateway-websocket-apis) — no built-in connection tracking, DynamoDB required, Lambda concurrency limits compound at scale, zombie connection problem from missed $disconnect events.

**@connections API:** [AWS docs — @connections commands](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-how-to-call-websocket-api-connections.html) — POST/GET/DELETE methods, SigV4 required, GoneException on stale connections.

**Integration types:** [AWS docs — WebSocket integration requests](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-websocket-api-integration-requests.html) — AWS_PROXY, AWS, HTTP_PROXY, HTTP, MOCK; VPC link requires explicit connectionId mapping.

**Idle timeout/heartbeat:** [AWS re:Post — Extend WebSocket idle timeout](https://repost.aws/questions/QUFbNpkJJvTySYuHA7uHQAeQ/extend-websocket-idle-connection-timeout) and [AWS re:Post — Server-side Ping/Pong](https://repost.aws/questions/QUV-egTr6_Skylz2_OHp8irw/websocket-api-server-side-ping-pong) — 10min hard limit, no server-initiated pings, client must send app-level heartbeats.

**REST API streaming:** [AWS announcement Nov 2025](https://aws.amazon.com/about-aws/whats-new/2025/11/api-gateway-response-streaming-rest-apis/) — payloads >10MB, timeouts up to 15 minutes, improved TTFB, all regions including GovCloud.

---

### Trade-offs

#### When WebSocket API is the right choice
- **True bidirectional communication**: Chat, collaborative editing, multiplayer gaming — where both client and server initiate messages unpredictably
- **Moderate scale (< 50K concurrent)**: Connection management is tractable; @connections fan-out stays under throttle limits
- **High-frequency updates with small payloads**: Stock tickers, IoT dashboards, live scoreboards at small-to-medium scale
- **Server-initiated push is frequent**: When the server pushes >1 message/minute/client, WebSocket beats polling economics

#### When WebSocket API is NOT the right choice
- **Massive fan-out (>100K concurrent)**: The lack of broadcast + 10K RPS shared throttle + mandatory connection tracking makes this operationally painful. DAZN's experience is cautionary
- **One-way server→client streaming**: REST API response streaming (Nov 2025) handles this better — 15-minute timeout, >10MB payloads, no connection management overhead, standard HTTP semantics
- **Low-frequency updates (<1/min)**: HTTP API polling is cheaper due to zero connection-minute charges during idle periods
- **LLM/generative AI responses**: REST API streaming with chunked transfer is purpose-built for this; WebSocket adds unnecessary bidirectional complexity

#### WebSocket API vs IoT Core MQTT for real-time push
- **IoT Core** supports **native pub/sub with topic-based broadcast** — one publish reaches all subscribers. No connection tracking database needed
- IoT Core meters messages per **5 KB** (vs WebSocket's 32 KB), making it ~6.5x more expensive per byte for large messages but more efficient for small sensor-type payloads
- IoT Core manages connection lifecycle, topic subscriptions, and offline message queuing natively
- **Use IoT Core** when you need broadcast/pub-sub semantics at scale; **use WebSocket API** when you need custom routing logic, request/response patterns, or deep Lambda integration

#### WebSocket API vs AppSync Events (2025+)
- **AppSync Events** added WebSocket publishing support (April 2025) with built-in channel/namespace model
- AppSync handles connection management, authentication (multiple types), and fan-out natively
- Less flexible routing than WebSocket API's route selection expressions
- Better for GraphQL-centric architectures; worse for custom protocol needs

#### Counter-intuitive findings
1. **Heartbeat messages are billable.** Keeping 1M connections alive with 1 heartbeat/9min costs ~$100/month in message charges alone — a "tax" on idle connections that doesn't exist with IoT Core or self-managed WebSockets
2. **$disconnect is best-effort.** Abrupt client disconnects (network loss, app kill) may never fire $disconnect, leaving zombie entries in your DynamoDB connection table. TTL-based cleanup is mandatory, not optional
3. **The 10K RPS throttle is shared.** WebSocket messages, @connections callbacks, REST API requests, and HTTP API requests in the same account/region all compete for the same 10K RPS quota. A WebSocket broadcast storm can throttle your REST APIs
4. **Connection rate increases require negotiation.** Even with Enterprise Support, increasing the 500 conn/s limit took one team 2 weeks and required reducing integration timeout as a trade-off. AWS doesn't rubber-stamp large increases
5. **128 KB message limit is restrictive.** REST API supports 10 MB payloads (and streaming supports even more). WebSocket's 128 KB limit means large data transfers require chunking at the application layer

#### The REST API streaming inflection point
With REST API response streaming (Nov 2025), the decision matrix has shifted significantly. Many use cases that previously required WebSocket — LLM streaming, large file downloads, SSE-style notifications — can now use REST API with better tooling (WAF, caching, API keys), simpler architecture (no connection tracking), and higher limits (>10MB, 15-min timeout). WebSocket API's remaining unique value is **bidirectional, low-latency, persistent connections** — a narrower niche than before.

---

### New Questions

1. **IoT Core as a WebSocket backend**: Given IoT Core's native pub/sub, managed connections, and topic-based broadcast, what does a hybrid architecture look like where API Gateway REST API handles request/response traffic and IoT Core handles real-time push? What are the cost break-even points vs pure WebSocket API at 10K/100K/1M connections?

2. **AppSync Events vs WebSocket API for new projects (2025+)**: AppSync Events added WebSocket publishing in April 2025 with managed connection lifecycle and multi-auth. For teams not already invested in WebSocket API, is AppSync Events now the default recommendation for serverless real-time, and what are its limits/quotas?

3. **Multi-region WebSocket architecture**: WebSocket API is single-region with no built-in failover. What patterns exist for global real-time applications — Route 53 failover, EventBridge cross-region replication, DynamoDB Global Tables for connection state — and what is the operational complexity vs using a managed service like AppSync or IoT Core that handles this natively?

## done

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