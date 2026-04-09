# Iteration 005 — Authentication and authorization: IAM, Cognito, Lambda authorizers, JWT

**Status:** discard  
**Scores:** coverage=100.0, quality=50.0, total=70.0  
**Timestamp:** 2026-04-05T21:27:33.724453+00:00  

---

Now I have all the research data. Let me synthesize and output the complete findings.

## Findings

### Authorizer Support Matrix Across API Types

| Authorizer Type | REST API | HTTP API | WebSocket API |
|----------------|----------|----------|---------------|
| **IAM (SigV4)** | Yes (SigV4 + SigV4a) | Yes (SigV4 only) | Yes (all routes, not just $connect) |
| **Cognito User Pools** | Yes (native `COGNITO_USER_POOLS`) | Via JWT authorizer only | Via Lambda authorizer only |
| **Lambda (TOKEN type)** | Yes | No | No |
| **Lambda (REQUEST type)** | Yes | Yes (payload 1.0 + 2.0) | Yes ($connect only) |
| **Native JWT** | No | **Yes** (exclusive) | No |
| **Resource Policies** | Yes | No | No |
| **mTLS** | Yes | Yes | No |
| **WAF** | Yes | No | No |
| **API Keys / Usage Plans** | Yes | No | No |

---

### 1. IAM Authorization (SigV4)

**How it works:** Client signs every request with AWS SigV4. API Gateway validates the cryptographic signature locally — it does NOT call STS or IAM on each request. This means STS throttling (600 req/s per account per region) is a client-side credential-acquisition problem, not an API Gateway validation problem.

**Latency overhead:** ~5–10ms median (Lumigo/Yan Cui benchmark, cloudonaut.io). Consistent — no cold starts, no cache misses, no external calls.

**Key differences across API types:**

| Aspect | REST API | HTTP API | WebSocket API |
|--------|----------|----------|---------------|
| Signing | SigV4 **and SigV4a** (multi-region) | SigV4 only | SigV4 only |
| Resource policies | Yes — combined evaluation with IAM | **Not supported** | Yes (similar to REST) |
| Auth granularity | Per-method | Per-route | **All routes** (not just $connect) |
| Unique IAM actions | `Invoke`, `InvalidateCache` | `Invoke` | `Invoke`, `InvalidateCache`, **`ManageConnections`** |

**Cross-account evaluation (REST API, critical nuance):**

| Account Context | IAM Policy | Resource Policy | Result |
|-----------------|------------|-----------------|--------|
| Same-account | Allow | Silent | **Allow** (OR logic) |
| Same-account | Silent | Allow | **Allow** (OR logic) |
| Cross-account | Allow | Allow | **Allow** (AND logic) |
| Cross-account | Allow | Silent | **Deny** (AND logic) |
| Any | Any | Explicit Deny | **Deny** (Deny wins) |

HTTP API cannot implement this pattern — all conditions must live in the caller's IAM policy or SCPs.

**WebSocket IAM auth applies to ALL routes**, not just `$connect`. This contrasts with Lambda authorizers, which only run at `$connect`. IAM policies can grant/deny specific route keys. The WebSocket API also adds `execute-api:ManageConnections` for controlling @connections callback API access.

---

### 2. Cognito User Pools Authorization

#### Implementation Differences

| Aspect | REST API (COGNITO_USER_POOLS) | HTTP API (JWT Authorizer) | WebSocket API |
|--------|-------------------------------|---------------------------|---------------|
| Authorizer type | Cognito-specific | Generic OIDC | Lambda authorizer required |
| Configuration | User Pool ARN + App Client IDs | Issuer URL + Audience | Manual JWT validation in Lambda |
| Multi-pool support | Up to 1,000 user pools per authorizer | Single issuer per authorizer | N/A |
| Claims access | `$context.authorizer.claims.*` | `$context.authorizer.jwt.claims.*` | Custom context from Lambda |
| Token delivery | `Authorization` header | `Authorization` header | **Query string** (browsers can't set WebSocket headers) |

#### Caching Behavior — The Security-Critical Difference

| Aspect | REST API (Cognito) | HTTP API (JWT) | WebSocket API |
|--------|-------------------|----------------|---------------|
| Result caching | **Yes** (configurable TTL) | **No** — validates every request | Connection-lifetime |
| Default TTL | 300 seconds | N/A | N/A |
| Max TTL | 3,600 seconds | N/A | N/A |
| Cache flush | `FlushStageAuthorizersCache` API | N/A | Disconnect client |
| JWKS cache | Internal (undocumented TTL) | **2 hours** (fixed) | N/A |
| JWKS timeout | Internal | **Hard 1,500ms** | N/A |

**The revoked token problem:** On REST API with caching enabled, a revoked or expired Cognito token continues to authorize requests until the cache TTL expires. `GlobalSignOut` and `AdminUserGlobalSignOut` have **no immediate effect** — API Gateway validates JWTs locally against cached keys, not by calling back to Cognito. A token with 60-min expiry cached at 300s TTL can work up to 5 minutes after actual expiry.

HTTP API's JWT authorizer avoids this by validating `exp` on **every request** — more secure but adds ~5–15ms per request.

**Resilience during Cognito outage:**
- REST API with caching: cached tokens continue working; new tokens fail with 500
- HTTP API: if JWKS public key is cached (2-hour window), JWT validation proceeds locally even with Cognito down; if JWKS cache expired, all requests fail with 401
- WebSocket (Lambda auth): new `$connect` requests fail; existing connections are unaffected

#### Token Size Limits — The Multi-Tenant Time Bomb

| Limit | Value | Adjustable |
|-------|-------|------------|
| API Gateway header size (Regional/Edge) | **10,240 bytes** | No |
| API Gateway header size (Private API) | **8,000 bytes** | No |
| Cognito total claims per token | **10,000 characters** | No |
| Cognito custom attribute value | **2,048 characters** | No |
| Custom attributes per pool | **25** | No |

Real-world failure: ~35 Cognito groups with ~60-character names exceeded CloudFront's 8,192-byte header limit. At API Gateway's 10,240-byte limit, the ceiling is ~40–50 groups. **Mitigation:** Use a Pre Token Generation Lambda trigger to filter `cognito:groups`, or use a custom `tenantId` claim instead of group-based tenant identification.

---

### 3. Lambda Authorizers — Deep Dive

#### Type Support Across API Types

| Feature | REST API | HTTP API | WebSocket API |
|---------|----------|----------|---------------|
| TOKEN type | Yes | No | No |
| REQUEST type | Yes | Yes | Yes ($connect only) |
| Payload format | Fixed (REST) | **1.0 or 2.0** (configurable) | Fixed (REST-like) |
| Simple boolean response | No | **Yes** (format 2.0 only) | No |
| Context value types | Strings, numbers, booleans | Strings only (1.0) / **All types including arrays/objects** (2.0) | Strings, numbers, booleans |

**TOKEN vs REQUEST (REST API):**
- TOKEN: single bearer token from one header; supports `IdentityValidationExpression` (regex pre-validation before Lambda invocation — saves cost on malformed tokens)
- REQUEST: multiple identity sources (headers, query strings, stage variables, `$context`); AWS recommends REQUEST over TOKEN
- TOKEN cache key = header value only; REQUEST cache key = composite of all configured identity sources

**HTTP API payload format 2.0 key improvement:** The "simple response" format (`{"isAuthorized": true, "context": {...}}`) eliminates the need to construct IAM policy documents. Context supports arrays and objects — REST API context only supports flat string/number/boolean values. The key `claims` is reserved and cannot be used as a context key name.

#### Caching Behavior — The Most Dangerous Configuration

**Cache TTL:** 0–3,600 seconds across all API types. Setting 0 disables caching.

**The wildcard resource policy caching gotcha (CRITICAL):**

When caching is enabled, the cached IAM policy applies to **ALL routes** using that authorizer within the stage. If Lambda returns a narrow policy allowing only `GET /pets/cats`:

1. Request to `GET /pets/cats` → authorizer runs → Allow → policy cached
2. Request to `GET /pets/dogs` (same token) → **cached policy used** → resource doesn't match → **403 Forbidden**

**Solutions ranked by preference:**
1. Return wildcard resource in policy: `arn:aws:execute-api:*:*:*/stage/*/*` (simplest, least granular)
2. Add `$context.httpMethod` + `$context.resourcePath` to REQUEST identity sources (per-route caching on REST)
3. Add `$context.routeKey` to identity sources (per-route caching on HTTP)
4. Set TTL to 0 (no caching — Lambda invoked every request)

**TOKEN authorizers cannot use `$context` variables in cache keys**, making per-route caching impossible. This is a fundamental design flaw — use REQUEST authorizers instead.

**WebSocket caching:** The authorizer runs only on `$connect`. The result applies for the **lifetime of the connection** (up to 2 hours). There is no mid-connection re-authorization. If you need to revoke access mid-connection, you must disconnect the client via `@connections DELETE`.

#### Cold Start and Latency

| Scenario | Latency | Notes |
|----------|---------|-------|
| Node.js/Python cold start (minimal deps) | **200–400ms** | maxday.github.io/lambda-perf benchmark |
| Java 17 without SnapStart | **800–2,000ms** | SnapStart reduces to ~200ms |
| Warm invocation (simple token validation) | **<10ms** | Sub-millisecond for pure JWT check |
| Provisioned Concurrency improvement | **~43% p99 reduction** | AWS Compute Blog |
| Arm64 vs x86 cold start | **13–24% faster** on arm64 | 2025 runtime benchmarks |

**Double cold-start penalty:** If both authorizer Lambda AND integration Lambda are cold, penalties are additive: 400ms (auth) + 400ms (integration) = **800ms+** on first request.

**Authorizer timeout limits:**

| API Type | Authorizer Timeout | Configurable? |
|----------|-------------------|---------------|
| REST API | ~10 seconds | No |
| HTTP API | **10,000ms** (hard) | No |
| WebSocket API | ~10 seconds | No |

#### Failure Modes (Exhaustively Documented)

| Scenario | HTTP Status | Response |
|----------|-------------|----------|
| Lambda **times out** | **500** | `{"message": null}` |
| Lambda **unhandled exception** | **500** | `{"message": null}` |
| Lambda **throws "Unauthorized"** (exact string) | **401** | `{"message": "Unauthorized"}` |
| Lambda returns **malformed response** | **500** | `{"message": null}` |
| Lambda returns **explicit Deny** | **403** | `"User is not authorized..."` |
| **Implicit deny** (no matching statement) | **403** | `"User is not authorized..."` |
| **Missing identity source** (with caching) | **401** | Lambda NOT invoked — saves cost |
| API Gateway **cannot invoke** Lambda (permissions) | **500** | `{"message": null}` |

Key: The only way to get 401 from the authorizer itself is to throw an error with the exact message `"Unauthorized"`. All other failures return 500 (not 504).

#### Cost at Scale

For **100M API requests/month** with 128MB Lambda authorizer, 50ms avg duration:
- Without caching: 100M invocations = **$30.42**
- With 300s TTL (~95% cache hit): ~5M invocations = **$1.52**
- Caching saves ~$29/month on authorizer Lambda costs alone

Lambda is invoked even on deny, but if identity sources are configured and **missing** from the request, API Gateway returns 401 without invoking Lambda — useful cost optimization against bots/malformed requests.

---

### 4. Native JWT Authorizer (HTTP API Exclusive)

**Validation pipeline (in order):**
1. Extract token from identity source (default: `Authorization` header, accepts `Bearer` prefix)
2. Decode as standard JWT (header.payload.signature)
3. Fetch JWKS from issuer's `/.well-known/openid-configuration` → `jwks_uri`
4. Verify signature — **RSA-based algorithms only** (RS256, RS384, RS512). No ECDSA, no EdDSA
5. Validate `iss`, `aud` (or `client_id` if `aud` absent), `exp`, `nbf`, `iat`
6. Check `scope` or `scp` includes at least one required `authorizationScopes` (**OR logic**, not AND)

**JWKS behavior:**
- Public keys cached for **2 hours** (fixed, not configurable)
- Hard **1,500ms timeout** on JWKS endpoint fetch (not configurable)
- If JWKS unreachable or times out → **401 Unauthorized** with no retry
- During key rotation, maintain both old and new keys valid for >2 hours
- Auth0 community reports intermittent 401s from this timeout — no resolution except switching providers or adding CloudFront caching in front of the JWKS endpoint

**What it CANNOT do:**
- Validate custom claims at the gateway (all claims pass through to backend for inspection)
- Support opaque tokens (requires standard JWT format)
- Handle token refresh (client must detect 401 and refresh via IdP)
- Support ECDSA or EdDSA algorithms

**Performance comparison:**

| Metric | JWT Authorizer (native) | Lambda Authorizer (warm, cached) | Lambda Authorizer (cold) |
|--------|------------------------|----------------------------------|--------------------------|
| Latency | **Sub-millisecond** (after JWKS cached) | ~4–50ms | 200–700ms |
| Compute cost | **$0** | $1.52/100M (with caching) | $30.42/100M (no caching) |
| Cold start risk | **None** | Yes (double penalty possible) | Yes |
| Custom logic | No | Yes | Yes |

**Supported providers:** Any OIDC-compliant IdP — Cognito, Auth0, Okta, Azure AD, Keycloak, any provider publishing `.well-known/openid-configuration`.

**Scope handling:** Configured per-route via `authorizationScopes`. At least one matching scope is sufficient (OR). This naturally rejects ID tokens (which typically lack `scope`).

---

### 5. Multi-Tenant SaaS Authorization Patterns

#### Pattern 1: Per-Tenant API Keys + Usage Plans (REST API Only)

| Resource | Limit | Adjustable |
|----------|-------|------------|
| API keys per account per region | **10,000** | **No** |
| Usage plans per account per region | **300** | Yes |
| Usage plans per API key | **10** | Yes |
| API key length | 20–128 chars | N/A |
| CreateApiKey rate | 5/second | N/A |

**Per-tenant rate limiting:** Each usage plan sets throttle (rate + burst) and quota (requests/day/week/month). However, **usage plan throttling is best-effort, not guaranteed** — AWS explicitly warns against relying on it for cost control or access blocking.

**Why API keys cannot be sole authentication:**
1. Not secrets — transmitted in `x-api-key` header, routinely logged
2. No expiry — leaked key grants indefinite access until manual revocation
3. No identity — identifies a calling project/tenant, not a user
4. No cryptographic proof of possession

**Scalability ceiling:** The hard 10,000 API key limit per region makes this pattern unsuitable for platforms with >10K tenants.

#### Pattern 2: Cognito with Tenant Isolation

| Approach | Single Pool + Custom Attributes | Pool per Tenant | App Client per Tenant |
|----------|-------------------------------|-----------------|----------------------|
| Isolation level | Application-level | Infrastructure-level | Middle ground |
| Max tenants | Unlimited (within user limits) | **1,000 pools/account** | **1,000 clients/pool** |
| Same email cross-tenant | Not possible | Possible | Not possible |
| Per-tenant MFA/IdP | No | Yes | Partial (per-client IdP) |
| Custom domains | Shared hosted UI | **4 custom domains/account** (severe limit) | Shared |
| Operational complexity | Low | High | Medium |

**Best practice:** Single pool with `custom:tenantId` attribute for most SaaS. Pool-per-tenant only when regulatory isolation requirements exist (e.g., healthcare, finance with data residency).

#### Pattern 3: Lambda Authorizer with Tenant Context

**Architecture flow:**
1. Client sends JWT in `Authorization` header
2. Lambda extracts and validates JWT
3. Extracts `tenantId` from JWT claims or `X-Tenant-Id` header
4. Optionally validates against tenant registry (DynamoDB)
5. Returns IAM policy + context: `{"tenantId": "abc123", "tier": "premium"}`
6. Backend accesses tenant via `event.requestContext.authorizer.tenantId`

**The multi-tenant caching challenge (CRITICAL):**
- TOKEN authorizer cache key = token value only. Since each user has a unique JWT, caching is per-user (safe but low hit rate)
- REQUEST authorizer: **you MUST include the tenant identifier in the cache key**. If you cache only on `Authorization` header but tenant comes from `X-Tenant-Id`, a cache hit could serve Tenant A's policy to Tenant B
- **Individual cache entries cannot be invalidated** — only flush the entire authorizer cache via `FlushStageAuthorizersCache`. Deactivating a tenant requires waiting for TTL expiry or flushing all caches

#### Pattern 4: Amazon Verified Permissions (Cedar)

- Integrates via **Lambda authorizer** — not directly with API Gateway
- Lambda calls `IsAuthorizedWithToken` API; Verified Permissions evaluates Cedar policies
- AWS recommends **one policy store per tenant** for strict isolation
- Authorization decisions: **single-digit milliseconds** (Convera production deployment)
- GA since June 2023; supports Cedar policy versioning, testing, and CloudFormation/CDK

Cedar tenant isolation example:
```cedar
permit(principal, action in [App::Action::"Read", App::Action::"Write"], resource)
  when { principal.tenant == resource.tenant };

forbid(principal, action, resource)
  when { principal.tenant != resource.tenant };
```

#### Pattern Comparison — Security Trade-offs

| Risk | API Keys | Cognito + JWT | Lambda Authorizer | Verified Permissions |
|------|----------|---------------|-------------------|---------------------|
| Cross-tenant leakage | Low (per-tenant keys) | **Medium** (if `tenantId` not validated server-side) | **Medium** (cache key misconfiguration) | **Low** (per-tenant policy stores) |
| Credential exposure | **High** (no expiry, logged in headers) | Low (tokens expire) | Low (tokens expire) | Low (tokens expire) |
| Cache poisoning | N/A | N/A | **Yes** (duplicate headers can confuse cache lookup) | Same Lambda risk |
| Scalability ceiling | **10K keys/region** | 1K pools or 1K clients | None | None |

---

### 6. WebSocket Authorization — Security Implications

**Auth only at `$connect`:** Once connected, no further authorization checks occur on `$default`, custom routes, or `$disconnect`. The authorized context (`$context.authorizer.*`) persists for the connection's lifetime.

**Security implications:**
1. Token expiry is **not enforced mid-connection** — a JWT used at `$connect` that expires 15 minutes in does not cause disconnection
2. No re-authorization mechanism exists — cannot attach authorizers to custom routes
3. Privilege escalation window: revoked permissions retain access until disconnect
4. Query string token exposure: `wss://api.example.com?token=<JWT>` appears in CloudWatch logs, CloudTrail, browser history

**Mitigation patterns:**
1. **Application-level heartbeat with re-auth:** Periodic messages include fresh token; backend Lambda validates and disconnects on failure via `@connections DELETE`
2. **Short connection lifetimes:** Force reconnection every 15 minutes matching token lifetime
3. **Backend permission checks:** Look up current permissions in database on every message rather than trusting initial auth context
4. **DynamoDB connection registry:** Store `connectionId → userId → authorizedAt`; periodic cleanup Lambda disconnects stale connections

---

### 7. Authorization Composition Rules

**REST API — one identity authorizer + layered defenses:**
- Exactly ONE of: IAM, Cognito, or Lambda authorizer per method
- Plus: resource policy + mTLS + WAF + API keys (all simultaneously)
- Cannot combine IAM + Lambda, or Cognito + Lambda, on same method

**Evaluation order (REST API, all layers):**
WAF → mTLS → Resource Policy (explicit Deny check) → Identity Authorizer → Resource Policy (combined evaluation) → API Key check → Backend

**HTTP API — one authorizer per route:**
- Exactly ONE of: IAM, JWT, or Lambda authorizer per route
- Plus: mTLS (can be combined)
- Different routes CAN have different authorizer types

---

## Evidence

**IAM auth latency:** ~5–10ms median overhead on mock endpoints — SigV4 validation is local cryptographic operation. Sources: Lumigo/Yan Cui API Gateway performance analysis; cloudonaut.io REST vs HTTP benchmark.

**Cognito authorizer cache TTL:** 0–3,600 seconds, default 300s. Source: AWS docs (`apigateway-integrate-with-cognito.html`); cross-referenced: tmmr.uk API Gateway auth caching deep dive.

**JWT authorizer JWKS timeout:** 1,500ms hard limit. Source: AWS docs (`http-api-jwt-authorizer.html`); cross-referenced: Auth0 community reports of `OIDC discovery endpoint communication error`.

**JWKS cache TTL:** 2 hours fixed. Source: AWS docs (`http-api-troubleshooting-jwt.html`); cross-referenced: awslabs/aws-jwt-verify README.

**Lambda authorizer cold start:** 200–400ms typical for Node.js/Python with minimal deps. Source: maxday.github.io/lambda-perf benchmark (2025); Edge Delta Lambda cold start analysis (2025).

**Provisioned Concurrency improvement:** ~43.5% p99 reduction. Source: AWS Compute Blog ("Creating low-latency, high-volume APIs with Provisioned Concurrency").

**API Gateway header size limit:** 10,240 bytes Regional/Edge, 8,000 bytes Private. Source: AWS docs (`api-gateway-execution-service-limits-table.html`).

**Token size failure at ~35 groups:** Source: Amplify JS GitHub issue #9695; ntsblog.homedev.com.au writeup. Cross-referenced against API Gateway's 10,240-byte header limit.

**API key hard limit:** 10,000 per region per account. Source: AWS API Gateway quotas page (`limits.html`). Not adjustable.

**Cognito pool limits:** 1,000 user pools per account, 1,000 app clients per pool. Source: AWS Cognito quotas page (`cognito/latest/developerguide/limits.html`).

**Header smuggling vulnerability:** Patched May 2023. Source: securityblog.omegapoint.se/en/writeup-apigw/. `x-amzn-remapped-*` prefix allowed cache key manipulation affecting Lambda authorizer results.

**Verified Permissions latency:** Single-digit milliseconds. Source: AWS Architecture Blog — Convera case study. GA since June 2023.

**Lambda authorizer failure modes:** Comprehensive testing documented at dev.to/marcogrcr. Confirmed: timeout=500, unhandled exception=500, "Unauthorized" string=401.

**Resource policy evaluation:** Same-account OR logic, cross-account AND logic. Source: AWS docs (`apigateway-authorization-flow.html`) — Tables A and B with all 9 combinations.

**Usage plans best-effort warning:** "Don't rely on usage plan quotas or throttling to control costs or block access." Source: AWS docs — Usage Plans documentation.

**STS throttle:** 600 req/s per account per region (token bucket). Source: AWS IAM reference (`reference_iam-quotas.html`). Does NOT affect API Gateway validation — only client credential acquisition.

---

## Trade-offs

### IAM Auth: Best for service-to-service, impractical for browser clients
- **Strengths:** No caching = no stale auth, immediate credential revocation via IAM, no Lambda cost, deeply integrated with AWS IAM policies, only auth method that applies to all WebSocket routes
- **Weakness:** Requires SigV4 signing — impractical for browser/mobile without intermediary. Forces AWS SDK dependency on all callers
- **Best for:** Internal microservices, cross-account service integrations, Lambda-to-API calls, WebSocket APIs needing per-message authorization

### Cognito Native (REST) vs JWT Authorizer (HTTP): Different security postures
- **Cognito on REST:** Multi-pool support, configurable cache TTL, WAF + resource policy layering — maximum control but revoked tokens persist until cache expires
- **JWT on HTTP:** 71% cheaper per-request, works with any OIDC provider, per-request validation prevents stale tokens — but no cache TTL control, no WAF, 1,500ms JWKS timeout risk
- **Decision driver:** If you need per-tenant throttling (usage plans), WAF, or resource policies → REST API. If purely internal with JWT auth → HTTP API

### Lambda Authorizer: Maximum flexibility, maximum operational burden
- **Unique capability:** Only authorizer type that can make external calls, generate dynamic IAM policies, inject arbitrary context, implement custom business logic
- **Cold start tax:** 200–400ms first request, mitigated by caching (300s default) or Provisioned Concurrency (~$1.52/month per warm environment)
- **The caching trap:** Default caching behavior is a **security risk** for multi-tenant apps if identity sources don't include tenant identifiers. TOKEN authorizer makes this impossible to fix — always use REQUEST type

### JWT Authorizer: Zero cost but narrowest scope
- **Zero compute cost** and sub-millisecond validation after JWKS cached
- **RSA-only** — doesn't support ECDSA or EdDSA algorithms (an increasing limitation as ECDSA adoption grows)
- Cannot extract custom claims for gateway-level authorization — only validates standard claims + scopes
- The 1,500ms JWKS timeout is an operational risk with non-AWS identity providers

### Multi-tenant decision matrix

| Tenant Count | Recommended Pattern | Key Constraint |
|-------------|-------------------|----------------|
| < 50 per user | Cognito groups + Lambda authorizer | Token size (~40–50 group limit) |
| 50–10,000 | Custom `tenantId` claim + Lambda authorizer with tenant-scoped IAM | Cache key must include tenant |
| > 10,000 | Lambda authorizer + external tenant registry | API key limit (10K) rules out key-per-tenant |
| Regulatory isolation | Pool-per-tenant + separate API Gateway per tenant | 1,000 pools/account, 4 custom domains/account |

### Counter-intuitive findings

1. **Cognito token revocation doesn't work with API Gateway.** `GlobalSignOut` is a no-op for cached authorizers — tokens remain valid until natural expiration. This is by design, not a bug.

2. **WebSocket IAM auth is MORE granular than Lambda auth.** IAM applies to every route; Lambda authorizer only runs at `$connect`. For per-message authorization, IAM is the only gateway-level option.

3. **HTTP API JWT cache is a black box.** Unlike REST API's configurable 0–3,600s TTL, HTTP API manages JWT caching internally with no user configuration or flush mechanism.

4. **TOKEN authorizers are a structural security risk with caching.** The cache key cannot include route information, so cached policies leak across endpoints. AWS recommends REQUEST type, but TOKEN remains the default in many tutorials and IaC templates.

5. **Lambda authorizer is NOT charged when identity sources are missing.** API Gateway returns 401 directly — a useful cost optimization against bots and malformed requests that can save significant Lambda invocation costs.

6. **The May 2023 header smuggling patch has deployment implications.** The `x-amzn-remapped-*` prefix vulnerability affected Lambda authorizer cache evaluation. Organizations running pre-May 2023 API Gateway configurations without re-deployment may still carry the vulnerability.

7. **Verified Permissions adds <10ms.** Cedar policy evaluation is single-digit milliseconds, making it viable for real-time authorization — the Lambda authorizer cold start is the actual bottleneck, not the policy engine.

---

## New Questions

1. **VPC Lattice as an IAM-auth alternative to API Gateway:** VPC Lattice (2023) provides built-in SigV4 auth for service-to-service communication within and across VPCs, without API Gateway overhead. For internal microservice architectures using API Gateway primarily for IAM auth, what are the feature gaps, latency differences, and cost break-even points vs API Gateway? Does VPC Lattice support Lambda authorizer-equivalent custom logic?

2. **CloudFront + Lambda@Edge as an auth preprocessing layer for HTTP API:** For HTTP API's JWT authorizer limitations (no configurable cache, 1,500ms JWKS timeout, no WAF), can CloudFront with Lambda@Edge act as an auth preprocessing layer — caching JWKS keys more aggressively, adding WAF, and reducing latency — without losing HTTP API's cost benefits? What is the added latency and cost of this pattern?

3. **Lambda tenant isolation mode (2025) impact on authorizer architecture:** AWS Lambda's new tenant isolation mode processes invocations in separate execution environments per tenant. How does this interact with Lambda authorizers — does it eliminate the need for IAM-policy-based tenant isolation in the authorizer response? What are the cold start implications of per-tenant execution environments vs shared pools?
