# Iteration 004 — Authentication and authorization: IAM, Cognito, Lambda authorizers, JWT

**Status:** discard  
**Scores:** coverage=93.0, quality=50.0, total=67.2  
**Timestamp:** 2026-04-05T21:17:25.934153+00:00  

---

Now I have all the research data from the three parallel agents. Let me synthesize this into the required output structure.

## Findings

### Authorizer Support Matrix Across API Types

| Authorizer Type | REST API | HTTP API | WebSocket API |
|----------------|----------|----------|---------------|
| **IAM (SigV4)** | Yes | Yes (SigV4 + SigV4a) | Yes ($connect only) |
| **Cognito User Pools** | Yes (native `COGNITO_USER_POOLS`) | Via JWT authorizer only | Via Lambda authorizer only |
| **Lambda (TOKEN type)** | Yes | No | No |
| **Lambda (REQUEST type)** | Yes | Yes (payload 1.0 + 2.0) | Yes ($connect only) |
| **Native JWT** | No | Yes | No |
| **Resource Policies** | Yes | No | No |
| **mTLS** | Yes | Yes | No |
| **WAF** | Yes | No | No |
| **API Keys / Usage Plans** | Yes | No | No |

---

### 1. IAM Authorization (SigV4)

**How it works:** Client signs every request with AWS SigV4. API Gateway validates the cryptographic signature against IAM policies. No caching — signature is validated on **every request**. This is fundamentally different from all other authorizer types.

**Latency overhead:** ~8ms median for SigV4 validation alone (independent benchmark on mock endpoints). Since there's no caching, this cost is paid per-request, but it's consistent — no cold starts, no cache misses.

**Cross-account behavior differs by API type:**
- **REST API (with resource policy):** Same-account uses **OR logic** (either IAM policy or resource policy can Allow). Cross-account uses **AND logic** (both must explicitly Allow). Explicit Deny always wins.
- **HTTP API:** No resource policies. Cross-account requires assuming a role in the API-owning account via `sts:AssumeRole`.
- **WebSocket API:** IAM auth only at `$connect`. After handshake, connection is authorized for its 2-hour lifetime.

**SigV4 vs SigV4a:** HTTP API supports SigV4a (Signature Version 4a), relevant for multi-region signing where a single signature covers requests to multiple AWS regions. REST and WebSocket APIs use SigV4 only.

| Resource Policy + IAM (REST API) | IAM Policy | Resource Policy | Result |
|----------------------------------|------------|-----------------|--------|
| Same-account | Allow | Silent | **Allow** |
| Same-account | Silent | Allow | **Allow** |
| Cross-account | Allow | Allow | **Allow** |
| Cross-account | Allow | Silent | **Deny** |
| Any | Any | Deny | **Deny** |

---

### 2. Cognito User Pools Authorization

#### REST API: Native Cognito Authorizer
- Dedicated `COGNITO_USER_POOLS` authorizer type pointing to one or more User Pool ARNs
- Validates JWT signature, expiration (`exp`), issuer (`iss`), audience (`aud`), and optionally OAuth scopes
- **No Lambda invocation** — validation is performed internally by API Gateway
- **Caching:** Configurable TTL from 0 to 3,600 seconds (default: **300 seconds**). Cache key is the token value itself
- Decoded claims available in `$context.authorizer.claims` for mapping templates and backend access
- Supports multiple User Pool ARNs on a single authorizer

#### HTTP API: JWT Authorizer (with Cognito)
- No dedicated Cognito authorizer — uses the generic **JWT authorizer** with Cognito's OIDC issuer URL
- Issuer: `https://cognito-idp.{region}.amazonaws.com/{userPoolId}`
- Validates same claims as REST API but via standard OIDC discovery
- **Caching:** AWS-managed internally — **not configurable** by the user
- Can only point to one issuer per authorizer (REST API supports multiple User Pool ARNs)
- Works identically with any OIDC provider (Auth0, Okta, Azure AD, Keycloak)

#### WebSocket API: Lambda Authorizer Required
- **No native Cognito support.** Must use a Lambda REQUEST authorizer on `$connect`
- Token passed via **query string** (browser WebSocket API doesn't support custom headers): `wss://api.execute-api.region.amazonaws.com/stage?token=<JWT>`
- Lambda validates the JWT manually (signature, expiration, issuer, audience) against Cognito's JWKS endpoint
- Returns IAM policy document allowing/denying `execute-api:Invoke`
- Authorization applies for **lifetime of connection** — no per-message re-authorization

#### Token Size Limits — The Multi-Tenant Time Bomb

| Limit | Value | Adjustable |
|-------|-------|------------|
| API Gateway header size (Regional/Edge) | **10,240 bytes** | No |
| API Gateway header size (Private API) | **8,000 bytes** | No |
| Cognito total claims per token | **10,000 characters** | No |
| Cognito custom attribute value | **2,048 characters** | No |

**The problem:** Each Cognito group membership adds to the `cognito:groups` claim. With token revocation enabled, additional `origin_jti` and `jti` claims increase size further. Real-world failure reported at ~35 groups with ~60-character names exceeding CloudFront's 8,192-byte header limit. At API Gateway's 10,240-byte limit, the ceiling is ~40-50 groups depending on claim complexity.

**Mitigation:** Use a Pre Token Generation Lambda trigger to filter `cognito:groups` to relevant groups, or use a custom `tenantId` claim instead of group-based tenant identification.

---

### 3. Lambda Authorizers

#### Type Support and Payload Formats

| Feature | REST API | HTTP API | WebSocket API |
|---------|----------|----------|---------------|
| TOKEN type | Yes | No | No |
| REQUEST type | Yes | Yes | Yes ($connect only) |
| Payload format | Fixed (REST) | 1.0 or 2.0 (configurable) | Fixed (REST-like) |
| Simple boolean response | No | Yes (format 2.0 only) | No |
| Context value types | Strings, numbers, booleans | Strings only (1.0) / All types (2.0) | Strings, numbers, booleans |

**HTTP API Payload Format 2.0 vs 1.0:**
- Format 2.0 adds `enableSimpleResponses: true` option — return just `{"isAuthorized": true}` instead of full IAM policy
- Format 2.0 uses `routeArn` (not `methodArn`), identity sources as array (not comma-separated string), and supports non-string context values
- **Must explicitly specify** `authorizerPayloadFormatVersion` via CLI/CloudFormation; console defaults to 2.0

#### Caching Behavior — The Most Dangerous Configuration

**Cache TTL:** 0–3,600 seconds (default 300s). Setting 0 disables caching.

**Cache Key Composition:**

| Authorizer Type | Cache Key |
|-----------------|-----------|
| TOKEN (REST only) | Value of configured token header (typically `Authorization`) |
| REQUEST (REST) | Composite of ALL configured identity sources |
| REQUEST (HTTP) | Configured identity source values |
| REQUEST (WebSocket) | `route.request.header.*` and `route.request.querystring.*` values |

**The wildcard resource policy caching gotcha (CRITICAL):**

When caching is enabled, the cached IAM policy applies to **ALL routes** using that authorizer within the stage. If the Lambda returns a policy allowing only `GET /pets/cats`:
1. Request to `GET /pets/cats` → authorizer runs → Allow → policy cached
2. Request to `GET /pets/dogs` (same token) → **cached policy used** → resource doesn't match → **403 Forbidden**

**Solutions ranked by preference:**
1. Return wildcard resource: `arn:aws:execute-api:*:*:*/stage/*/*` (simplest, least secure)
2. Add `$context.httpMethod` + `$context.resourcePath` to REQUEST identity sources (per-route caching on REST)
3. Add `$context.routeKey` to identity sources (per-route caching on HTTP)
4. Set TTL to 0 (no caching — Lambda invoked every request)

**TOKEN authorizers cannot use `$context` variables in cache keys**, making per-route caching impossible. You must either use wildcard resources or disable caching.

#### Cold Start Latency Impact

| Scenario | Latency | Source |
|----------|---------|--------|
| Node.js/Python authorizer cold start (minimal deps) | **200–400ms** | Lambda Perf Benchmarks |
| Complex authorizer (heavy dependencies) | **500ms–3s** | Community benchmarks |
| Warm invocation (simple token validation) | **<10ms** | General Lambda benchmarks |
| Provisioned Concurrency improvement | **~43% p99 reduction** | AWS Compute Blog |
| Arm64 vs x86 cold start | **13–24% faster** on arm64 | 2025 runtime benchmarks |

**Double cold-start penalty:** If both authorizer Lambda AND integration Lambda are cold, penalties are **additive**: 400ms (auth) + 400ms (integration) = 800ms+ on first request.

#### Cost at Scale

For **100M API requests/month** with 128MB Lambda authorizer, 50ms avg duration:
- Without caching: 100M invocations = **$30.42** (requests + compute)
- With 300s TTL (~95% cache hit): ~5M invocations = **$1.52**
- **Caching saves ~$29/month** on authorizer Lambda costs alone

**Key cost insight:** Lambda authorizer is invoked even when it denies the request. But if identity sources are configured and **missing** from the request, API Gateway returns 401 without invoking Lambda — saving invocation cost.

---

### 4. Native JWT Authorizer (HTTP API Only)

**Validation pipeline:**
1. Extract token from identity source (default: `Authorization` header, accepts `Bearer` prefix)
2. Decode JWT
3. Fetch JWKS from issuer's `/.well-known/openid-configuration` → `jwks_uri`
4. Verify signature (**RSA-based algorithms only**)
5. Validate: `iss` matches issuer, `aud` or `client_id` matches audience, `exp`/`nbf`/`iat` temporal checks
6. Check `scope` or `scp` includes required `authorizationScopes` (if configured)

**JWKS Caching:**
- Public keys cached for **up to 2 hours**
- Cache refresh is automatic on expiry
- No manual flush mechanism available
- During refresh, if JWKS endpoint is unreachable, API Gateway continues using last cached keys

**The 1,500ms Hard Timeout (Critical for non-AWS IdPs):**
- API Gateway enforces a **hard 1,500ms timeout** for JWKS endpoint communication
- Not configurable
- If Auth0/Okta/Azure AD JWKS endpoint is slow → **401 Unauthorized** with no retry
- Error in logs: `"OIDC discovery endpoint communication error"`
- **Real-world impact:** Auth0 community reports intermittent 401s due to this timeout, with no resolution other than switching providers or adding CloudFront caching in front of the JWKS endpoint

**Supported Identity Providers:**

| Provider | Issuer URL | Confirmed Working |
|----------|-----------|-------------------|
| Cognito | `https://cognito-idp.{region}.amazonaws.com/{userPoolId}` | Yes |
| Auth0 | `https://{tenant}.auth0.com/` | Yes (1,500ms caveat) |
| Okta | `https://{domain}.okta.com` | Yes |
| Azure AD | `https://login.microsoftonline.com/{tenant}/v2.0` | Yes |
| Keycloak | `https://{host}/realms/{realm}` | Yes |

**JWT authorizer vs Lambda authorizer for JWT validation:**
- JWT authorizer: zero compute cost, sub-millisecond after JWKS cached, but can only validate standard claims + scopes
- Lambda authorizer: ~$1.52/100M requests (with caching), but can extract custom claims, call external services, generate tenant-scoped context

---

### 5. Multi-Tenant SaaS Authorization Patterns

#### Pattern 1: Cognito Groups per Tenant + Lambda Authorizer (REST API)
- Create Cognito group per tenant (`tenant-acme`, `tenant-globex`)
- Lambda authorizer extracts `cognito:groups`, generates tenant-scoped IAM policy
- **Scales to:** ~40-50 tenants per user before hitting token size limits
- **Best for:** Users belonging to few tenants with clear group boundaries

#### Pattern 2: Custom `tenantId` Claim + JWT Authorizer (HTTP API)
- Pre Token Generation Lambda trigger injects `custom:tenant_id` claim
- JWT authorizer validates token; backend reads tenant from `$context.authorizer.claims.custom:tenant_id`
- **Token size:** Constant regardless of tenant count
- **Limitation:** JWT authorizer can't enforce tenant-scoped access — must be done in backend

#### Pattern 3: API Key per Tenant + Usage Plans (REST API only)
- Lambda authorizer returns `usageIdentifierKey` mapping to tenant's API key
- Each tier (Basic/Standard/Premium) gets its own Usage Plan with different rate/burst/quota
- **Hard limit:** 10,000 API keys per region per account — does not scale beyond this
- **Usage plans are best-effort:** AWS docs warn "Don't rely on usage plan quotas to control costs or block access"

#### Pattern 4: Dynamic IAM Policy per Tenant (Pool Model)
- Lambda authorizer generates IAM policy with DynamoDB `LeadingKeys` conditions scoped to tenant
- Single shared DynamoDB table with tenant ID as partition key prefix
- AWS SaaS Factory reference architecture uses this pattern
- **Most secure pool-model approach** — tenant isolation at the IAM level

#### Pattern 5: Lambda Tenant Isolation Mode (2025+)
- AWS Lambda's tenant isolation mode processes invocations in **separate execution environments per tenant**
- Simplifies compute isolation without full silo deployment
- **Trade-off:** More cold starts (N execution environments vs shared pool)

#### Authorization Composition Rules

**REST API — one identity authorizer + layered defenses:**
- Exactly ONE of: IAM, Cognito, or Lambda authorizer per method
- Plus: resource policy + mTLS + WAF + API keys (all can be applied simultaneously)
- **Cannot** combine IAM + Lambda, or Cognito + Lambda, on same method

**HTTP API — one authorizer per route:**
- Exactly ONE of: IAM, JWT, or Lambda authorizer per route
- Plus: mTLS (can be combined)
- Different routes CAN have different authorizer types
- **Cannot** combine JWT + Lambda on same route

**Evaluation order (REST API, all layers):**
WAF → mTLS → Resource Policy (explicit Deny check) → Identity Authorizer → Resource Policy (combined evaluation) → API Key check → Backend

---

### 6. Security Gotchas

#### WebSocket Query String Token Leakage
- Browser WebSocket API cannot set custom headers → token must be in query string
- Query strings appear in: browser history, proxy/CDN logs, HTTP Referer headers, CloudWatch access logs
- **Mitigation:** Use short-lived, single-use tokens consumed on `$connect`

#### WebSocket No Per-Message Authorization
- Auth only at `$connect` — compromised connection or revoked user retains access until disconnect
- Token expiration not enforced on existing connections
- **Mitigation:** Application-level auth in `$default` route Lambda, proactive disconnection when permissions change

#### Cache Confusion / Cross-Tenant Vulnerability
- **Patched (May 2023):** Header smuggling via `x-amzn-remapped-` prefix allowed cache key manipulation
- **Still by-design risk:** TOKEN authorizer cache key is only the token value — doesn't include path, method, or tenant ID. If authorizer returns tenant-scoped policy, same token hitting a different tenant's endpoint gets the **cached (wrong) policy**
- **Mitigation:** Use REQUEST authorizer with tenant-identifying headers in identity sources

#### Revoked Cognito Tokens Still Accepted
- API Gateway validates JWT locally (signature + expiration) — does NOT call back to Cognito
- `GlobalSignOut` / `AdminUserGlobalSignOut` has no immediate effect on API Gateway
- Revoked tokens work until natural expiration OR authorizer cache TTL expires
- **Mitigation:** Short access token lifetimes (15-30 min) + short authorizer cache TTLs

#### mTLS No CRL/OCSP Checking
- API Gateway validates client certificates against truststore but does **not** check CRLs or OCSP
- Revoked certificates remain valid until removed from truststore
- **Mitigation:** Implement CRL checking in Lambda authorizer that receives certificate details

---

## Evidence

**IAM auth latency:** ~8ms median overhead (Daniil Sokolov, Medium — performance analysis of Lambda-backed REST API)

**Cognito authorizer cache TTL:** 0–3,600 seconds, default 300s (AWS docs: `apigateway-integrate-with-cognito.html`; cross-referenced: tmmr.uk API Gateway auth caching deep dive)

**JWT authorizer JWKS timeout:** Hard 1,500ms (AWS docs: `http-api-jwt-authorizer.html`; confirmed by Auth0 community thread on intermittent 401s)

**JWKS cache TTL:** Up to 2 hours (AWS docs: `http-api-troubleshooting-jwt.html`; cross-referenced: awslabs/aws-jwt-verify README)

**Lambda cold start:** 200–400ms typical Node.js/Python (maxday.github.io/lambda-perf benchmark; Edge Delta 2025 analysis)

**Provisioned Concurrency improvement:** ~43.5% p99 reduction (AWS Compute Blog: "Creating low-latency, high-volume APIs with Provisioned Concurrency")

**Header size limit:** 10,240 bytes Regional/Edge, 8,000 bytes Private (AWS docs: `api-gateway-execution-service-limits-table.html`)

**API key limit:** 10,000 per region per account (AWS API Gateway quotas page)

**Token size failure:** ~35 groups with ~60-char names exceeded CloudFront 8,192-byte limit (Amplify JS GitHub issue #9695; ntsblog.homedev.com.au writeup)

**Header smuggling patch:** May 2023 (securityblog.omegapoint.se/en/writeup-apigw/)

**Usage plans best-effort:** "Don't rely on usage plan quotas or throttling to control costs or block access" (AWS docs: Usage Plans documentation)

**Resource policy evaluation matrix:** Explicit AND/OR logic tables (AWS docs: `apigateway-authorization-flow.html`)

**Lambda authorizer billing:** Charged per invocation even on deny; not charged when identity sources missing (AWS re:Post, Stormit pricing guide)

**Lambda tenant isolation mode:** Separate execution environments per tenant (AWS Compute Blog, 2025)

---

## Trade-offs

### IAM Auth: Best for service-to-service, worst for browser clients
- **Strengths:** No caching = no stale auth, immediate credential revocation, no Lambda cost, deeply integrated with AWS IAM policies
- **Weakness:** Requires SigV4 signing — impractical for browser/mobile clients without an intermediary. Forces SDK dependency (AWS SDK) on all callers
- **Best for:** Internal microservices, cross-account service integrations, Lambda-to-API calls

### Cognito Native (REST) vs JWT Authorizer (HTTP): Different trade-off curves
- **Cognito on REST:** Multi-pool support, configurable cache TTL, WAF + resource policy layering — maximum control
- **JWT on HTTP:** 71% cheaper per-request, works with any OIDC provider, simpler setup — but no cache TTL control, no WAF, no resource policies
- **Decision driver:** If you need per-tenant throttling (usage plans) or WAF, you must use REST API. If you're purely internal with JWT auth, HTTP API saves significant cost

### Lambda Authorizer: Maximum flexibility, maximum operational burden
- **Unique capability:** Only authorizer type that can make external calls, generate dynamic IAM policies, inject arbitrary context, and implement custom business logic
- **Cold start tax:** 200–400ms on first request, mitigated by caching (300s default) or Provisioned Concurrency ($)
- **The caching trap:** Default caching behavior is a security risk for multi-tenant applications if identity sources don't include tenant identifiers

### JWT Authorizer: Cheapest and simplest, but narrowest
- **Zero compute cost** and sub-millisecond validation after JWKS caching
- **1,500ms JWKS timeout** is a real operational risk with non-AWS identity providers
- **RSA-only** — doesn't support ECDSA or EdDSA algorithms
- **Cannot** extract custom claims for authorization decisions — only validates standard claims + scopes
- **Best for:** Simple scope-based authorization with well-performing OIDC providers

### Multi-tenant authorization: No silver bullet
- **< 50 tenants per user:** Cognito groups work; token size manageable
- **50–10,000 tenants:** Custom `tenantId` claim + Lambda authorizer generating scoped IAM policies
- **> 10,000 tenants:** Can't use API keys (10K limit). Must use Lambda authorizer with external tenant registry
- **Pool vs silo:** Pool model (shared API Gateway) is 5-10x cheaper but requires careful IAM policy scoping. Silo model (separate API per tenant) provides strongest isolation at highest cost

### Counter-intuitive findings
1. **Cognito token revocation doesn't work with API Gateway.** `GlobalSignOut` is a no-op for API Gateway — tokens remain valid until expiration because validation is local JWT checking, not a Cognito callback
2. **HTTP API JWT cache is a black box.** Unlike REST API's configurable 0–3,600s TTL, HTTP API's JWT caching is AWS-managed with no configuration or flush mechanism
3. **TOKEN authorizers are a security risk with caching.** The cache key cannot include route information, so cached policies can leak across endpoints. REQUEST authorizers should be strongly preferred
4. **The header smuggling vulnerability was only patched in May 2023.** The `x-amzn-remapped-` prefix attack affected Lambda authorizer cache evaluation — anyone running pre-May 2023 configurations without re-deployment may still be vulnerable
5. **Lambda authorizer is NOT charged when identity sources are missing.** API Gateway returns 401 directly — a useful cost optimization for malformed/bot requests

---

## New Questions

1. **Amazon Verified Permissions + API Gateway integration (2024+):** AWS launched Verified Permissions (Cedar policy engine) as a managed authorization service. How does it integrate with API Gateway Lambda authorizers for fine-grained, policy-based access control in multi-tenant SaaS? Does it replace the need for hand-crafted IAM policy generation in Lambda authorizers, and what are the latency/cost implications at scale?

2. **API Gateway VPC Lattice as an alternative for service-to-service auth:** VPC Lattice (launched 2023) provides built-in IAM auth for service-to-service communication within and across VPCs, with SigV4 and no API Gateway required. For internal microservice architectures that currently use API Gateway primarily for IAM auth, is VPC Lattice a simpler/cheaper replacement, and what are its authorization model limitations?

3. **CloudFront + Lambda@Edge as an auth preprocessing layer:** For HTTP API's JWT authorizer limitations (no configurable cache, 1,500ms JWKS timeout, no WAF), can CloudFront with Lambda@Edge act as an auth preprocessing layer — caching JWKS keys more aggressively, adding WAF, and reducing latency — without losing the cost benefits of HTTP API?
