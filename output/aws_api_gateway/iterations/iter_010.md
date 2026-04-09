# Iteration 010 — Authentication and authorization: IAM, Cognito, Lambda authorizers, JWT

**Status:** discard  
**Scores:** coverage=86.0, quality=50.0, total=64.4  
**Timestamp:** 2026-04-05T22:01:37.339838+00:00  

---

## Findings

### Authentication and Authorization Across API Gateway Types

---

### 1. Authorizer Type Availability Matrix

| Authorizer Type | REST API | HTTP API | WebSocket API |
|----------------|----------|----------|---------------|
| IAM (SigV4) | Yes | Yes | Yes ($connect only) |
| Cognito User Pools (native) | Yes | No (use JWT) | No (use Lambda) |
| JWT authorizer (native) | **No** | **Yes** | No |
| Lambda TOKEN authorizer | Yes | No | No |
| Lambda REQUEST authorizer | Yes | Yes (v1.0 + v2.0 payload) | Yes ($connect only) |
| Resource policies | Yes | **No** | No |
| API keys + usage plans | Yes | **No** | No |
| Mutual TLS (mTLS) | Yes | Yes | No |

**Key insight:** REST API supports every auth mechanism. HTTP API trades resource policies and API keys for a native JWT authorizer. WebSocket API supports only IAM and Lambda authorizers, both evaluated exclusively at `$connect` — all subsequent messages on the connection are unauthenticated.

---

### 2. IAM Authorization (SigV4)

#### How It Works

All three API types use AWS Signature Version 4. The caller includes a cryptographic signature derived from AWS credentials in the request headers. API Gateway verifies the signature internally — no Lambda invocation, no external call.

**REST API unique capability:** Supports **resource policies** (JSON policy documents attached to the API) in addition to IAM identity policies. The authorization decision is the logical intersection of both. This enables cross-account access without role assumption — just grant the external principal in the resource policy.

**HTTP API limitation:** No resource policies. Cross-account access requires the caller to `sts:AssumeRole` into the API owner's account, then sign with temporary credentials. There is no shortcut.

**WebSocket API:** IAM auth evaluated only at `$connect`. Once connected, credentials can expire without affecting the connection. However, if the backend uses those same credentials for `@connections` callbacks, expired credentials will fail on the backend side.

#### Latency Overhead

IAM auth adds **~8ms** to median latency on REST API (measured on mock endpoint). This is purely signature verification + IAM policy evaluation — no Lambda cold starts, no external calls. On HTTP API, the baseline overhead is lower (~5-10ms total vs ~15-29ms for REST), so IAM auth on HTTP API likely adds a similar ~8ms on a lower base.

#### Caching Behavior

**IAM authorization decisions are NOT cached** by API Gateway in the way authorizer results are cached. There is no configurable TTL. Every request undergoes full SigV4 verification and IAM policy evaluation. AWS's internal IAM infrastructure has its own optimizations (policy compilation/caching) but these are opaque.

#### Cross-Account Evaluation Rules

This is one of the most confusing aspects and a frequent source of misconfiguration:

**Same-account (OR logic):**
| IAM Policy | Resource Policy | Result |
|-----------|-----------------|--------|
| Allow | Allow | ALLOW |
| Allow | Neither/Deny | ALLOW |
| Neither/Deny | Allow | ALLOW |
| Deny | Any | DENY |

**Cross-account (AND logic):**
| IAM Policy | Resource Policy | Result |
|-----------|-----------------|--------|
| Allow | Allow | ALLOW |
| Allow | Neither/Deny | **DENY** |
| Neither/Deny | Allow | **DENY** |
| Deny | Any | DENY |

Cross-account requires **both policies to explicitly allow**. Silence in either = implicit deny. This catches teams who configure only one side.

#### Known Gotchas

- **SigV4 clock skew:** AWS rejects requests where the timestamp differs from server time by more than **5 minutes**. Mobile/IoT devices with drifting clocks are the most common source of 403 errors. AWS SDKs include automatic clock skew correction, but Amplify Flutter lacked this until recently.
- **WebSocket credential expiry:** IAM auth runs once at `$connect`. If temporary credentials (STS AssumeRole, Cognito Identity Pool) expire after connection establishment, the connection stays alive for up to 2 hours. No re-auth mechanism exists.
- **`X-Amz-Security-Token` required:** For temporary credentials, this header must be included in the canonical request. Missing it produces opaque 403 errors.

---

### 3. Cognito User Pool Authorization

#### REST API: Native Cognito Authorizer

- Authorizer type: `COGNITO_USER_POOLS`
- Client sends a Cognito JWT (ID token or access token) in the `Authorization` header
- API Gateway validates locally using Cognito's JWKS public keys — **no Lambda invocation, no call to Cognito service**
- Validates: token signature, expiry (`exp`), issuer (`iss` matches user pool), audience/client ID
- Supports **ID tokens** (identity claims) and **access tokens** (OAuth2 scopes)

**Caching:**
- Default TTL: **300 seconds (5 minutes)**
- Range: 0 (disabled) to **3600 seconds (1 hour)**
- Cache key: the token value itself

#### HTTP API: Cognito via JWT Authorizer

HTTP API has no native Cognito authorizer. Instead, configure a **generic JWT authorizer** pointing to Cognito's OIDC discovery endpoint:
- `issuerUrl`: `https://cognito-idp.{region}.amazonaws.com/{userPoolId}`
- `audience`: Cognito app client ID(s)

**Critical difference: HTTP API JWT authorizer does NOT cache authorization results.** There is no `AuthorizerResultTtlInSeconds`. Every request undergoes full JWT validation. However, it **caches JWKS public keys for up to 2 hours**, so the expensive network call is amortized.

The JWT authorizer validates more claims explicitly than the REST API Cognito authorizer:

| Claim | Validated? |
|-------|-----------|
| `kid` | Must match JWKS key |
| `iss` | Must match configured issuer |
| `aud` or `client_id` | Must match configured audience (`client_id` checked only if `aud` absent) |
| `exp` | Must be in the future |
| `nbf` | Must be in the past |
| `iat` | Must be in the past |
| `scope`/`scp` | Must contain at least one route-configured scope |

**RSA-only:** Only RSA-based algorithms (RS256, RS384, RS512) are supported. ECDSA (ES256) and HMAC (HS256) JWTs are rejected.

#### WebSocket API: Cognito Requires Lambda Authorizer

There is no native Cognito support for WebSocket APIs. The standard pattern:
1. Client passes Cognito JWT as a query parameter on the `$connect` URL (or in headers during upgrade)
2. A Lambda REQUEST authorizer validates the token, extracts user identity
3. Authorizer stores `{userId, connectionId}` in DynamoDB for connection tracking

**Query string token risk:** Tokens appear in server access logs and CloudWatch logs. URI length limit is **4,096 characters**, constraining token size.

#### Token Size Concerns

- Cognito tokens grow with: token revocation enabled (`origin_jti`, `jti` claims), many group memberships (`cognito:groups`), custom claims via pre-token-generation Lambda
- Maximum **100 groups per user** (hard limit)
- API Gateway header limit: **10,240 bytes (10 KB)** for regional/edge REST APIs, **8,000 bytes** for private REST APIs
- WebSocket URL limit: **4,096 characters** for query string tokens

---

### 4. Lambda Authorizers

#### Payload Format Differences

| Aspect | REST API (v1.0) | HTTP API v2.0 (simple) | HTTP API v2.0 (IAM policy) |
|--------|----------------|------------------------|---------------------------|
| Required output | `principalId` + `policyDocument` | `isAuthorized` (boolean) | `principalId` + `policyDocument` |
| Complexity | Must construct valid IAM policy ARNs | **Single boolean** | Same as REST API |
| Context map | String/number/boolean only | Supports non-string values | Supports non-string values |

The HTTP API v2.0 simple response (`{"isAuthorized": true/false, "context": {...}}`) eliminates the need to construct IAM policy documents — a major simplification.

#### Cold Start Latency (Real-World Data)

| Runtime | Cold Start (p50) | Cold Start (p99) | Warm Invocation |
|---------|-----------------|-------------------|-----------------|
| Go (provided.al2) | ~10-30ms | ~100-200ms | ~5-10ms |
| Node.js 20 | ~200-400ms | 1.2-2.8s | ~10-20ms |
| Python 3.12 | ~300-500ms | 2.1-3.5s | ~10-30ms |
| .NET 8 (Native AOT) | ~200-400ms | ~1-2s | ~10-20ms |
| Java 21 | ~1-3s | 4-7s | ~15-30ms |
| Java 21 + SnapStart | ~300-500ms | ~782ms (p99.9) | ~15-30ms |

**You pay the cold start penalty twice** — once for the authorizer Lambda and once for your backend Lambda. A fully cold Python request path adds 1-1.5 seconds of auth-only latency.

**Arm64/Graviton2** reduces cold starts by 13-24% across all runtimes.

#### Caching Behavior

| Parameter | REST API | HTTP API | WebSocket API |
|-----------|----------|----------|---------------|
| Default TTL | 300s | 0 (disabled!) | 300s |
| Maximum TTL | 3600s (hard) | 3600s (hard) | 3600s (hard) |
| Cache scope | Per-stage | Per-route (via identity sources) | Per $connect |
| Cache invalidation | `FlushStageAuthorizersCache` (entire stage) | No API; TTL-based only | TTL-based only |

**THE critical vulnerability: REST API authorizer cache is per-stage, not per-resource.**

The cache key defaults to only the token source (e.g., Authorization header). It does NOT include HTTP method or resource path. This means:

1. User has access to `GET /orders/123` but NOT `GET /orders/456`
2. User calls `GET /orders/123` — authorizer returns ALLOW, cached by JWT
3. User calls `GET /orders/456` — API Gateway finds cached ALLOW for same JWT, **skips authorizer**
4. User gains unauthorized access

**This is the default behavior.** As documented by Authress: "While the vulnerability only exists based on improper configuration, the improper configuration is the default."

**Fix:** For REQUEST authorizers, add `$context.httpMethod` and `$context.resourcePath` to identity sources. For TOKEN authorizers, return wildcard policies covering all stage resources. Or set TTL to 0 (at cost of authorizer invocation per request).

**Another pitfall: error responses get cached.** API Gateway caches ANY response, including transient 500 errors. There is no "do not cache" signal. A momentary authorizer failure causes cascading 500s for the TTL duration.

**Missing identity sources:** For REQUEST authorizers with caching enabled, if ANY specified identity source is missing/null/empty, API Gateway returns `401 Unauthorized` WITHOUT invoking the Lambda. This is silent and confusing.

#### Lambda Authorizer Limits

| Limit | Value | Adjustable? |
|-------|-------|-------------|
| Timeout | **10 seconds** | No |
| Policy resource ARN | **512 characters** max | No |
| Method ARN total length | **1,600 bytes** max | No |
| WebSocket authorizer result | **8 KB** max | No |
| Lambda authorizers per WebSocket API | 10 | Yes |
| Context map key `claims` | **Reserved** — cannot be used | N/A |
| Context map values | String/number/boolean only (REST API) | N/A |

#### WebSocket: Auth Runs Once at $connect

This is a fundamental design limitation:
- Token expiry during a 2-hour connection does **not** cause disconnection
- Permission revocation does **not** affect existing connections
- There is no built-in re-authentication mechanism

**Mitigation patterns:**
1. Backend periodically checks token expiry and calls `@connections DELETE` to force-disconnect
2. Client reconnects proactively before token expiry (e.g., at 80% of token lifetime)
3. Application-level message-based re-authentication (client sends fresh token as a message)
4. Set connection idle timeout shorter than token TTL via heartbeat frequency management

---

### 5. JWT Authorizer (HTTP API Only)

#### How It Works

Performs **local validation** — no remote calls at request time after JWKS is cached:
1. Extract token from `identitySource` (supports `Bearer` prefix stripping)
2. Decode JWT header and payload
3. Fetch public key from issuer's JWKS endpoint (cached for 2 hours)
4. Verify signature (RSA only)
5. Validate claims: `iss`, `aud`/`client_id`, `exp`, `nbf`, `iat`
6. Check `scope`/`scp` against route's `authorizationScopes`

#### Performance Comparison

| Authorizer Type | Added Latency | Scaling Concern |
|----------------|---------------|-----------------|
| JWT authorizer | **<5ms** (local crypto) | None — no Lambda involved |
| Lambda authorizer (warm) | ~10-30ms | Lambda concurrency limits |
| Lambda authorizer (cold) | 100-750ms+ | Cold start storms under load |
| IAM auth | ~8ms | None — internal to API Gateway |
| Cognito (REST, cached hit) | ~0ms | None |

JWT authorizers are the fastest option for standard JWT validation because they avoid Lambda invocation entirely.

#### What JWT Authorizer CANNOT Do

1. No opaque/reference token support (no token introspection)
2. No custom claims-based authorization logic (e.g., "allow only if `tenant_tier` = `premium`")
3. No external data lookups during authorization
4. No dynamic policy generation
5. No context enrichment beyond passing JWT claims through
6. No non-RSA algorithms (ECDSA, HMAC rejected)
7. Cannot distinguish ID tokens from access tokens
8. No `usageIdentifierKey` return for API key-based throttling
9. Scope matching is **OR** (any one scope matches) — no "all required" mode

#### JWKS Edge Cases

- **2-hour cache TTL is not configurable.** During key rotation, keep old key valid for ≥2 hours after publishing new key, or cached-key validations fail
- **JWKS fetch timeout:** Reported as ~1,500ms. Slow identity providers (behind CDN, geographically distant) can cause initial requests to fail after cache expiry
- **Clock skew tolerance:** Configurable between 0-60 seconds; default ~5 seconds. IdP clock drift beyond this causes token rejection

---

### 6. Multi-Tenant SaaS Authorization Patterns

#### Pattern Comparison

| Pattern | Isolation Level | Latency Impact | API Type Support | Complexity |
|---------|----------------|----------------|-----------------|------------|
| **API keys + usage plans** | Throttling only (not security) | None | REST only | Low |
| **JWT claims routing** | Application-level | <5ms (JWT) or 10-30ms (Lambda) | HTTP API (JWT) or all (Lambda) | Low-Medium |
| **Resource policies** | Network-level | None (evaluated before Lambda) | REST only | High |
| **Lambda authorizer + context injection** | Application-level, flexible | 10-750ms | All API types | High |
| **IAM + STS session policies** | Resource-level | Client-side STS call | All API types | Very High |
| **Silo (separate resources per tenant)** | Infrastructure-level | Varies | All | Very High |

#### Per-Tenant API Keys (REST API Only)

- Each tenant gets a unique API key mapped to a usage plan
- Usage plans enforce throttle rate, burst capacity, and quota per-tenant
- Lambda authorizer can return `usageIdentifierKey` to dynamically associate requests with API keys when `apiKeySource` = `AUTHORIZER`
- **API keys are NOT a security mechanism** — they are plaintext in headers, easily leaked. Must combine with IAM or Cognito auth
- Limited to **10,000 API keys per account** (soft limit)
- Usage plan quotas are **best-effort, not guaranteed** — AWS docs warn explicitly not to rely on them for cost control or access blocking

#### JWT Claims-Based Tenant Isolation

- Extract `tenant_id` from custom JWT claim (e.g., `custom:tenant_id` in Cognito)
- HTTP API passes claims to backend via `$event.requestContext.authorizer.jwt.claims.tenant_id`
- Lambda authorizer can enrich context: `context.tenantId = "tenant-123"`
- **Backend MUST enforce tenant isolation** — the JWT authorizer cannot do it
- Security risk: if the pre-token-generation Lambda or IdP is compromised, tenant claims can be spoofed

#### IAM + STS Token Vending (AWS Recommended for Data Plane)

1. Client authenticates with Cognito, receives JWT
2. Lambda authorizer or backend calls `sts:AssumeRole` with **session policy** scoped to tenant resources (e.g., DynamoDB leading key condition, S3 prefix)
3. Resulting temporary credentials can only access that tenant's data
4. This is the **AWS SaaS Factory reference architecture** recommended approach for data-plane isolation
5. Adds client-side STS call latency but provides resource-level isolation

#### Real-World Multi-Tenant Failure

A documented case: a multi-tenant SaaS platform experienced cross-tenant data leakage where a user from Tenant A retrieved Tenant B's records. Root causes:
- JWT validation existed but **lacked tenant-specific claim validation** in the authorizer
- Database queries lacked tenant scope filters
- Cache keys shared data between tenants
- Fix was a single line of code, but the vulnerability exposed systemic architectural weaknesses

---

### 7. Caching Summary Across All API Types and Authorizer Types

| API Type | Authorizer | Result Cache | Default TTL | Max TTL | JWKS Cache |
|----------|-----------|-------------|-------------|---------|------------|
| REST | COGNITO_USER_POOLS | Yes | 300s | 3600s | Internal |
| REST | Lambda (TOKEN/REQUEST) | Yes | 300s | 3600s | N/A |
| REST | IAM | **No** | N/A | N/A | N/A |
| HTTP | JWT | **No** | N/A | N/A | 2 hours |
| HTTP | Lambda (REQUEST) | Yes | **0 (disabled!)** | 3600s | N/A |
| HTTP | IAM | **No** | N/A | N/A | N/A |
| WebSocket | Lambda (REQUEST) | Yes (at $connect) | 300s | 3600s | N/A |
| WebSocket | IAM | **No** | N/A | N/A | N/A |

**Note the HTTP API Lambda authorizer default of 0** — caching is disabled by default, meaning every request invokes the Lambda. This is the opposite of REST API's default of 300s. Teams migrating from REST to HTTP API who rely on authorizer caching must explicitly configure it.

---

### 8. Cross-Account Lambda Authorizer Pattern

A central security team can maintain authorizer Lambda in a shared services account, referenced by multiple API-owning teams:

1. API in Account A specifies full Lambda ARN from Account B
2. Account B grants `lambda:InvokeFunction` to API Gateway in Account A via resource-based policy
3. Caching works normally (TTL 300s default, max 3600s)

**Gotchas:**
- Missing permissions produce **500 Internal Server Error** with no useful client-side message
- CloudFormation/CDK do NOT automatically create cross-account permissions — manual setup required
- CloudWatch Logs for the authorizer remain in Account B — need cross-account log aggregation

---

## Evidence

**IAM auth latency:** ~8ms overhead measured on mock endpoint (Daniil Sokolov, Medium performance analysis of Lambda-backed REST API). HTTP API base overhead 5-10ms vs REST API 15-29ms (kindatechnical.com comparison).

**Authorizer cache TTL:** Default 300s, max 3600s (AWS CloudFormation UserGuide, aws-resource-apigateway-authorizer). HTTP API Lambda authorizer default TTL is 0 (AWS docs, http-api-lambda-authorizer).

**JWKS cache:** 2 hours for HTTP API JWT authorizer (AWS docs, http-api-jwt-authorizer). Not configurable.

**JWT authorizer algorithms:** RSA-only — ES256, HS256 rejected (AWS docs, http-api-troubleshooting-jwt).

**Cold start benchmarks:** Node.js 200-400ms p50, Python 300-500ms p50, Go 10-30ms p50, Java 1-3s p50 (maxday.github.io/lambda-perf daily updated benchmarks; zircon.tech 2025 optimization guide). SnapStart reduces Java p99.9 to ~782ms (AWS Compute Blog).

**Cache vulnerability:** Default per-stage caching without method/path in cache key enables cross-resource access (Authress knowledge base article "api-gateway-authorizers-vulnerable-by-design"; tmmr.uk "Understanding API Gateway Authorizer Caching").

**Cross-account policy evaluation:** Same-account uses OR logic, cross-account uses AND logic (AWS docs, apigateway-authorization-flow.html).

**Cognito group limit:** 100 groups per user, 10,000 per user pool (AWS Cognito quotas documentation).

**Header size limits:** 10,240 bytes for regional/edge REST APIs, 8,000 bytes for private REST APIs (ntsblog.homedev.com.au).

**Multi-tenant breach:** Cross-tenant data leakage from missing tenant claim validation (The Cloud Playbook, "API Gateway Custom Authorizers for Tenant-Aware Security").

**Lambda tenant isolation mode:** New feature enabling per-tenant execution environment isolation (AWS Compute Blog, "Building multi-tenant SaaS with Lambda tenant isolation mode", 2024-2025).

**Cross-account Lambda authorizer:** Requires explicit `lambda:InvokeFunction` grant; missing permissions yield 500 error (AWS docs, apigateway-lambda-authorizer-cross-account-lambda-authorizer).

**WebSocket $connect-only auth:** Documented in AWS docs (apigateway-websocket-api-control-access). $disconnect is best-effort, not guaranteed (apigateway-websocket-api-route-keys-connect-disconnect).

**Error response caching:** API Gateway caches all authorizer responses including errors; no "do not cache" mechanism (Auth0 Community thread, AWS re:Post threads on authorization-lambda-caching).

**SigV4 clock skew:** 5-minute tolerance window (AWS IAM UserGuide, reference_sigv-troubleshooting). Amplify Flutter lacked correction until GitHub issue #4174.

---

## Trade-offs

### When Each Auth Mechanism Wins

**IAM auth is best when:**
- Caller is an AWS service, another Lambda, or an internal system with AWS credentials
- You need cross-account access with resource policies (REST API) or role assumption (HTTP API)
- Latency matters — ~8ms overhead with no cold starts, no external calls
- **Worst for:** External/mobile clients — SigV4 signing is complex for client-side JavaScript

**Native JWT authorizer (HTTP API) is best when:**
- Using any OIDC-compliant identity provider (Cognito, Auth0, Okta, Azure AD)
- Internal microservices with standard JWT auth patterns
- Latency-sensitive: <5ms overhead after JWKS cached
- High volume: no Lambda scaling concerns, 71% cheaper than REST API per request
- **Worst for:** Custom authorization logic, opaque tokens, non-RSA algorithms, multi-tenant enforcement beyond scope matching

**Cognito native authorizer (REST API) is best when:**
- Already using Cognito User Pools and need the full REST API feature set (WAF, API keys, usage plans)
- Want result caching (5-min default) to reduce validation overhead
- Need both ID token and access token support with explicit type handling
- **Worst for:** Non-Cognito IdPs (use Lambda authorizer instead)

**Lambda authorizer is best when:**
- Need custom authorization logic (tenant validation, external lookups, complex rules)
- Using opaque tokens requiring introspection
- Need context enrichment (inject computed values into request context)
- Multi-IdP federation or non-standard token formats
- **Worst for:** Latency-sensitive APIs without provisioned concurrency budget. Cold starts add 100-750ms+ depending on runtime

### The Authorizer Cache Security Trade-off

The REST API authorizer cache is simultaneously the best performance optimization and the most dangerous default configuration:

- **With cache (300s):** Eliminates repeated Lambda invocations, saving ~10-30ms/request and reducing Lambda costs. But the per-stage cache key defaults create a cross-resource authorization bypass.
- **Without cache (TTL=0):** Every request invokes the Lambda. Secure by default but expensive at scale and adds consistent latency.
- **Sweet spot:** Cache with identity sources including `$context.httpMethod` + `$context.resourcePath` + the auth token. This gives per-resource caching without the bypass vulnerability.

HTTP API Lambda authorizers default to TTL=0 (no cache), which is safer but slower/costlier. Teams must explicitly opt into caching.

### Multi-Tenant Auth Architecture Decision Tree

1. **External API consumers (B2B)?** → REST API + API keys (usage plans) + Cognito or Lambda authorizer. Only REST API has per-client throttling.
2. **Internal microservices, standard OIDC?** → HTTP API + JWT authorizer. Cheapest, fastest, simplest. Enforce tenant isolation in backend.
3. **Complex tenant rules (tier-based features, cross-tenant sharing)?** → Lambda authorizer on any API type. Accept latency cost or use provisioned concurrency.
4. **Data-plane isolation requirement (compliance)?** → IAM + STS session policies (token vending). AWS SaaS Factory recommended pattern. Highest complexity but strongest isolation.
5. **Real-time WebSocket + Cognito?** → Lambda authorizer at $connect + DynamoDB connection tracking + application-level re-auth for long connections.

### Counter-Intuitive Findings

1. **HTTP API JWT authorizer does NOT cache authorization results.** Despite being the "simpler" option, every request undergoes full JWT validation. REST API's Cognito authorizer caches results for 5 minutes by default. For high-volume APIs, this means HTTP API does more crypto work per request.

2. **REST API authorizer cache default is a security vulnerability.** The cache key excludes method and path, enabling cross-resource access. The "insecure by default" configuration is documented by multiple security researchers but not prominently warned in AWS docs.

3. **Error responses are cached.** A transient 500 from a Lambda authorizer causes all requests with the same cache key to fail for the TTL duration. There is no "do not cache" signal. This makes short TTLs (30-60s) safer than long ones for authorizers with external dependencies.

4. **HTTP API Lambda authorizer caching defaults to OFF.** Unlike REST API (300s default), HTTP API defaults to TTL=0. Teams migrating from REST to HTTP lose caching silently, causing Lambda invocation spikes and latency increases.

5. **WebSocket auth is fundamentally fire-and-forget.** No re-auth, no token refresh, no permission revocation for established connections. The 2-hour max duration is the only hard boundary. For security-sensitive applications, this means implementing an entire application-layer auth protocol on top of the WebSocket connection.

6. **Lambda tenant isolation mode (2024-2025)** guarantees execution environments are never reused across tenants — a new option for compute-level isolation that was previously impossible without dedicated infrastructure per tenant.

7. **JWT `aud` vs `client_id` behavior:** Cognito access tokens use `client_id` (no `aud` claim). The JWT authorizer checks `client_id` only when `aud` is absent. Mixing IdPs where some use `aud` and others use `client_id` creates validation inconsistencies that are difficult to debug.

---

## New Questions

1. **Lambda authorizer cost optimization at scale:** At what request volume does the cost of Lambda authorizer invocations (even with caching) exceed the price difference between HTTP API and REST API? If a team uses HTTP API for the 71% cost savings but adds a Lambda authorizer for custom tenant logic, the Lambda invocation costs and provisioned concurrency charges may negate the savings. What are the break-even points at 10M/100M/1B requests/month?

2. **API Gateway vs CloudFront + Lambda@Edge for auth:** CloudFront Functions and Lambda@Edge can perform JWT validation at the edge with sub-millisecond latency (CloudFront Functions) or full Lambda capability (Lambda@Edge). For globally distributed APIs, is CloudFront-based auth in front of HTTP API a better architecture than REST API's built-in auth, especially given CloudFront's 10M RPS limit vs API Gateway's 10K RPS default?

3. **Verified Permissions integration:** AWS launched Amazon Verified Permissions (Cedar policy engine) which integrates with API Gateway Lambda authorizers for fine-grained, policy-based authorization. How does this change the multi-tenant authorization landscape — does it make Lambda authorizer the default recommendation for enterprise SaaS despite its latency overhead, and what are the Cedar policy evaluation latency numbers?
