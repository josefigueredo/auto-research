# Iteration 003 — WebSocket API: capabilities, connection limits, and scaling patterns

**Status:** keep  
**Scores:** coverage=100.0, quality=82.5, total=89.5  
**Timestamp:** 2026-04-05T21:09:25.116032+00:00  

---

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
