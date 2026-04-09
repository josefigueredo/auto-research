# Iteration 004 — Credential handling: how each tool handles AWS credentials, secrets in env vars, credential leakage in logs or temp files

**Status:** keep  
**Scores:** coverage=61.7, quality=67.5, total=65.2  
**Timestamp:** 2026-04-08T20:26:02.288422+00:00  

---

### Findings

For this dimension, the clearest credential-handling result is that **none of the four tools needs real AWS secrets to function in a normal local-endpoint Terraform workflow**, but they differ materially in how safely they behave if real credentials are present.

**LocalStack** has the strongest explicit safeguard against accidental use of real AWS access keys. Its credential docs state that by default it only accepts LocalStack-style structured keys (`LSIA...`/`LKIA...`) for account extraction, rejects `AKIA...`/`ASIA...` access keys to the fallback account `000000000000`, and currently **ignores the secret access key value** entirely. The docs also warn that disabling `PARITY_AWS_ACCESS_KEY_ID` can cause accidental AWS connections. A public source snapshot of `accounts.py` and issue `#8225` show the implementation logs a warning/debug message when “production AWS credentials” are detected, but the message does **not** include the actual key material. I did not find evidence that LocalStack persists `AWS_SECRET_ACCESS_KEY` or `AWS_SESSION_TOKEN` to disk itself in the normal server path. The main residual risk is operator-side: if credentials are passed as container env vars, they remain visible in `docker inspect`, CI metadata, and any user-added debug tooling. Sources: [LocalStack credentials docs](https://docs.localstack.cloud/aws/capabilities/config/credentials/), [issue #8225](https://github.com/localstack/localstack/issues/8225), [accounts.py mirror](https://fossies.org/linux/localstack/localstack-core/localstack/aws/accounts.py), [coverage view](https://coveralls.io/builds/76691042/source?filename=localstack-core%2Flocalstack%2Faws%2Faccounts.py).

**MiniStack** appears to treat AWS credentials as **opaque request syntax**, not as secrets it validates. Its README repeatedly uses `AWS_ACCESS_KEY_ID=test` / `AWS_SECRET_ACCESS_KEY=test`, and its router code extracts only the service name and region from the SigV4 `Authorization` header. The account ID comes from `MINISTACK_ACCOUNT_ID` or the fixed default `000000000000`; there is no code evidence in the inspected files that it validates, persists, or forwards access key, secret key, or session token values. That is good for avoiding outbound AWS use, but there is a concrete indirect leak path: MiniStack runs init and ready shell scripts with `env=os.environ`, logs their stdout/stderr, and in detached mode writes logs to `/tmp/ministack-<port>.log`. So MiniStack itself is not logging credentials by default, but **any init script that echoes env vars will leak them into logs**. I found no public issue reporting credential leakage, and its documented internal endpoints are only health/reset, not credential introspection. Sources: [MiniStack README](https://github.com/Nahuel990/ministack), [MiniStack Dockerfile](https://github.com/Nahuel990/ministack/blob/master/Dockerfile), [MiniStack app.py](https://github.com/Nahuel990/ministack/blob/master/ministack/app.py), [MiniStack router.py](https://github.com/Nahuel990/ministack/blob/master/ministack/core/router.py).

**Floci** is directionally similar to MiniStack, but the evidence quality is weaker. Its public site and GitHub README say “credentials can be anything,” and describe the common workflow as pointing SDKs or Terraform-compatible tools at `http://localhost:4566` with dummy creds. The same README also says some services use “real IAM” and SigV4 validation, especially for Lambda, ElastiCache, RDS, and ECS. That implies Floci parses auth material locally for emulation, but I was not able to isolate the exact auth/logging implementation classes from the repo via the available crawler, so I cannot make as strong a code-level claim here as for MiniStack. I found **no public issue evidence** of credentials being logged, written to temp files, or exposed via debug endpoints. I also found no documented credential debug API. The main security conclusion is therefore moderate-confidence: Floci probably follows the same “dummy credentials accepted locally” model, but its credential-leak posture is **less auditable from public evidence** than MiniStack’s. Sources: [Floci site](https://floci.io/), [Floci GitHub README](https://github.com/floci-io/floci).

**Moto** splits into two different security postures. In normal **server mode**, it is relatively safe for Terraform-style local emulation: the docs show explicit endpoint override to `http://localhost:5000`, and the Terraform example sets `skip_credentials_validation`, `skip_metadata_api_check`, and `skip_requesting_account_id`, which reduces pressure to use real credentials at all. In that mode, I found no evidence that Moto writes temp credential files or exposes credentials through its reset API. But **Moto proxy mode is a real credential-risk edge case**: the docs explicitly instruct users to set `HTTPS_PROXY` so SDK traffic destined for AWS is intercepted by Moto. That means clients may still load real AWS credentials from the normal AWS credential chain and sign requests as if they were going to AWS. Even if Moto intercepts locally, this mode is much easier to misconfigure and is worse for a security-first CI posture than server mode with explicit endpoint URLs. Sources: [Moto server mode docs](https://docs.getmoto.org/en/latest/docs/server_mode.html), [Moto environment variables docs](https://docs.getmoto.org/en/stable/docs/configuration/environment_variables.html), [Moto proxy mode docs](https://docs.getmoto.org/en/latest/docs/proxy_mode.html).

A cross-tool point matters operationally: **container env vars are not private secrets storage**. If any of these tools are run with `-e AWS_ACCESS_KEY_ID=... -e AWS_SECRET_ACCESS_KEY=...`, those values are ordinarily visible through container metadata, CI runner diagnostics, and process environment inheritance. That is not unique to any one emulator, but it means a “tool does not log creds” finding does **not** eliminate credential exposure risk in CI.

### Evidence

- **LocalStack**
  - Default behavior: `AKIA...`/`ASIA...` access keys are rejected for account extraction unless `PARITY_AWS_ACCESS_KEY_ID` is enabled; fallback account is **`000000000000`**. Source: [credentials docs](https://docs.localstack.cloud/aws/capabilities/config/credentials/).
  - Secret key handling: docs say **“The value of the secret access key are currently ignored”**. Source: [credentials docs](https://docs.localstack.cloud/aws/capabilities/config/credentials/).
  - Code snapshots show the warning/debug line only logs the generic message, not the actual credential value. Sources: [issue #8225](https://github.com/localstack/localstack/issues/8225), [Fossies snapshot](https://fossies.org/linux/localstack/localstack-core/localstack/aws/accounts.py), [Coveralls source view](https://coveralls.io/builds/76691042/source?filename=localstack-core%2Flocalstack%2Faws%2Faccounts.py).

- **MiniStack**
  - Default API port: **4566**. Source: [Dockerfile](https://github.com/Nahuel990/ministack/blob/master/Dockerfile).
  - Detached log file path: **`/tmp/ministack-<port>.log`**. Source: [app.py](https://github.com/Nahuel990/ministack/blob/master/ministack/app.py).
  - Request logging in inspected code logs only `method`, `path`, `service`, `region`; no default header/body logging was found in the main request path. Sources: [app.py](https://github.com/Nahuel990/ministack/blob/master/ministack/app.py), [router.py](https://github.com/Nahuel990/ministack/blob/master/ministack/core/router.py).
  - Init/ready scripts inherit full environment via `env=os.environ`, and stdout/stderr is logged. Source: [app.py](https://github.com/Nahuel990/ministack/blob/master/ministack/app.py).

- **Floci**
  - Default API port: **4566**. Sources: [Floci site](https://floci.io/), [Floci GitHub README](https://github.com/floci-io/floci).
  - Public docs say **credentials can be anything**. Sources: [Floci site](https://floci.io/), [Floci GitHub README](https://github.com/floci-io/floci).
  - Compatibility suite includes **`compat-terraform` 14 tests** and **`compat-opentofu` 14 tests**. Source: [Floci GitHub README](https://github.com/floci-io/floci).
  - Config includes `FLOCI_ECR_BASE_URI` defaulting to **`public.ecr.aws`**, which is relevant to supply-chain/egress but not evidence of credential forwarding. Source: [Floci GitHub README](https://github.com/floci-io/floci).

- **Moto**
  - Server mode default endpoint: **`http://localhost:5000`**. Source: [server mode docs](https://docs.getmoto.org/en/latest/docs/server_mode.html).
  - Terraform example uses:
    - `skip_credentials_validation = true`
    - `skip_metadata_api_check = true`
    - `skip_requesting_account_id = true`
    Source: [server mode docs](https://docs.getmoto.org/en/latest/docs/server_mode.html).
  - `TEST_SERVER_MODE=true` rewires decorated boto3 clients to **`http://localhost:5000`**. Sources: [server mode docs](https://docs.getmoto.org/en/latest/docs/server_mode.html), [environment variables docs](https://docs.getmoto.org/en/stable/docs/configuration/environment_variables.html).
  - Proxy mode requires `HTTPS_PROXY` and therefore sits in the path of requests otherwise destined for AWS. Source: [proxy mode docs](https://docs.getmoto.org/en/latest/docs/proxy_mode.html).

### Trade-offs

**LocalStack**
- Better when the security team wants an emulator that explicitly guards against accidental use of real AWS access key IDs.
- Worse if the pipeline may ever run with `PARITY_AWS_ACCESS_KEY_ID=1`, because that deliberately removes the safeguard.
- Counter-intuitive point: on this narrow credential dimension, LocalStack’s stricter behavior is actually better than the “accept anything” model.

**MiniStack**
- Better when you want a straightforward local-only emulator and can control startup scripts tightly.
- Worse if your CI pattern relies on init/ready scripts from multiple teams, because MiniStack will pass the full environment into those scripts and log their output.
- Surprising point: the concrete leak path is not the request handler; it is the shell-script execution path.

**Floci**
- Better if you want the same “dummy creds are fine” ergonomics and strong Terraform compatibility claims.
- Worse if auditability matters as much as behavior, because public evidence for credential handling is thinner than for LocalStack or MiniStack.
- Main residual risk is not a known leak, but **insufficiently verifiable handling** from public sources.

**Moto**
- Better in explicit endpoint/server mode, where Terraform can be configured to skip credential validation and stay entirely local.
- Worse in proxy mode, which is much closer to real AWS client behavior and therefore much riskier for accidental use of real credentials.
- Important edge case: “Moto is safe” is only true if you mean `moto_server`/server mode, not proxy mode.

### New Questions

1. For MiniStack and Floci, when Lambda/RDS/ECS sidecars inherit environment variables, do any child containers receive full AWS credential env vars by default, and are those visible through Docker APIs or task inspection?
2. Do any of the four tools emit `Authorization`, `X-Amz-Security-Token`, or presigned-query parameters in trace/debug logs when verbose logging is enabled?
3. For Terraform specifically, which provider settings are required per tool to guarantee the AWS SDK never falls back to the default credential chain or IMDS during `plan` and `apply`?

I was able to reach firm source-backed conclusions for LocalStack, MiniStack, and Moto. Floci’s public README and site were available, but I could not isolate its exact auth/logging implementation classes through the available web crawler, so the Floci conclusion is lower-confidence than the others.

---

## Peer Review (claude)

## Critical Peer Review

---

### Issue 1: Internal Contradiction on `PARITY_AWS_ACCESS_KEY_ID` Risk Direction

- **Type**: Contradiction
- **Location**: Findings section — *"The docs also warn that disabling `PARITY_AWS_ACCESS_KEY_ID` can cause accidental AWS connections"* vs. Trade-offs section — *"Worse if the pipeline may ever run with `PARITY_AWS_ACCESS_KEY_ID=1`, because that deliberately removes the safeguard"*
- **Problem**: These two statements say opposite things. If the default behavior rejects real AKIA keys, then *enabling* `PARITY_AWS_ACCESS_KEY_ID` (setting it to 1) removes the safeguard — consistent with the trade-offs section. But the findings text says *disabling* it causes accidental AWS connections, which is the reverse of that logic. One of these is wrong and they cannot both be correct.
- **Impact**: High. This is the most operationally consequential claim in the LocalStack section. A reader who acts on the finding text instead of the trade-offs section will misconfigure their environment. If the flag controls whether LocalStack accepts real AKIA keys for account parsing, the risk direction matters enormously.

---

### Issue 2: Unverified Key Prefix Format (`LSIA...`)

- **Type**: Possible factual error
- **Location**: *"only accepts LocalStack-style structured keys (`LSIA...`/`LKIA...`)"*
- **Problem**: `LKIA` is the documented LocalStack access key prefix (analogous to AWS's `AKIA`). `LSIA` does not appear in LocalStack's canonical documentation as a standard prefix. It may conflate LocalStack session token formats or be an error. The finding cites `accounts.py` for implementation, but does not quote the actual prefix strings the code checks against. Without quoting the exact code check, the `LSIA` claim is unverified.
- **Impact**: Medium. If `LSIA` is wrong, the characterization of what LocalStack accepts is inaccurate, which undercuts the credibility of the strongest evidence in the document.

---

### Issue 3: Comparative Superiority Claim on Unequal Evidence Bases

- **Type**: Unsupported claim
- **Location**: *"LocalStack has the strongest explicit safeguard against accidental use of real AWS access keys"*
- **Problem**: This comparative conclusion is drawn using code-level evidence for LocalStack, README-level evidence for Floci, and no internal code review for Moto. The ranking is only valid if the evidence is comparable. A safeguard that exists in Floci's code but wasn't visible to the crawler would invalidate this ranking. The finding itself acknowledges Floci's evidence is weaker, but does not caveat the comparative conclusion accordingly.
- **Impact**: Medium. The conclusion may be correct, but it is stated with more confidence than the evidence supports. It should be scoped as "LocalStack has the most *verifiable* safeguard from public sources."

---

### Issue 4: Temporal Qualifier on LocalStack Secret Key Handling Is Unaddressed

- **Type**: Missing nuance
- **Location**: *"docs say 'The value of the secret access key are currently ignored'"*
- **Problem**: The word "currently" in the quoted doc text signals that this behavior is explicitly acknowledged as temporary or subject to change. The finding quotes this correctly but does not flag its implication: any security posture built on "secret key is ignored" could break in a future LocalStack release without it constituting a breaking change. This is especially relevant because the finding uses this as a positive security property.
- **Impact**: Medium. For long-lived CI pipelines, a silent behavior change in a dependency is a real risk. The finding should recommend checking release notes on this point.

---

### Issue 5: Moto Proxy Mode Risk Is Partially Misstated

- **Type**: Missing nuance
- **Location**: *"clients may still load real AWS credentials from the normal AWS credential chain and sign requests as if they were going to AWS. Even if Moto intercepts locally, this mode is much easier to misconfigure"*
- **Problem**: The actual risk in proxy mode is not that requests are "signed as if going to AWS" — they are signed that way in all SDK use, including against `localhost:5000`. The distinct risk in proxy mode is that if the proxy intercept fails (Moto not running, wrong port, TLS error), the SDK falls through to real AWS rather than failing loudly. The finding identifies proxy mode as riskier but for an imprecise reason. The correct framing is: proxy mode has a silent-fallback-to-real-AWS failure mode that server mode does not.
- **Impact**: Medium. The conclusion (proxy mode is riskier) is correct, but the reasoning given would not help a practitioner understand what specific misconfiguration to guard against.

---

### Issue 6: Floci "Real IAM" Claim Is Ambiguously Stated and Weakly Supported

- **Type**: Unsupported claim / missing nuance
- **Location**: *"The same README also says some services use 'real IAM' and SigV4 validation, especially for Lambda, ElastiCache, RDS, and ECS. That implies Floci parses auth material locally for emulation"*
- **Problem**: "Real IAM" is ambiguous. It could mean (a) Floci validates SigV4 signatures against a locally-emulated IAM engine, (b) Floci delegates to actual AWS IAM for certain calls, or (c) it is marketing language meaning "complete IAM emulation." These have very different credential-security implications. Interpretation (b) would be a major finding — Floci making outbound IAM calls with whatever credentials it received. The finding treats this as supporting local emulation but does not rule out the more serious interpretation, and it acknowledges the code is not auditable. The caveat appears only in the closing paragraph, not adjacent to this claim.
- **Impact**: High. If Floci forwards credentials outbound for certain service calls, it is the worst-performing tool in this analysis. That possibility deserves a prominent flag, not a buried acknowledgment.

---

### Issue 7: Negative Persistence Finding for LocalStack Is Weak Evidence

- **Type**: Missing nuance
- **Location**: *"I did not find evidence that LocalStack persists `AWS_SECRET_ACCESS_KEY` or `AWS_SESSION_TOKEN` to disk itself in the normal server path"*
- **Problem**: This is framed as reassurance, but it is an argument from ignorance. LocalStack has a persistence layer (used in Pro/licensed modes and configurable in community mode via `PERSISTENCE=1`). The finding's scope — "normal server path" — is not defined. If persistence is enabled (not uncommon in staging environments), credential-containing request payloads could be written to disk as part of state snapshots. The finding does not examine or exclude this path.
- **Impact**: Medium. Users who enable LocalStack persistence based on a reading that "LocalStack doesn't persist credentials" are not warned about this gap.

---

### Issue 8: Port Collision Between Tools Is Not Mentioned

- **Type**: Gap
- **Location**: Evidence section — MiniStack default port: **4566**, Floci default port: **4566** (same as LocalStack default)
- **Problem**: All three tools default to port 4566. The findings note these separately but never flag that running any two simultaneously causes a port conflict — and more importantly, that a Terraform configuration pointing at `localhost:4566` could silently hit a *different* tool than intended if the intended tool failed to start. This is an operational security gap: a credential-handling property of Tool A could be bypassed if Tool B is accidentally running.
- **Impact**: Low-medium for credential security specifically, higher for correctness in multi-tool CI environments.

---

### Issue 9: MiniStack Project Maturity Not Assessed

- **Type**: Gap
- **Location**: MiniStack section generally
- **Problem**: The finding treats MiniStack as a peer to LocalStack and Moto without assessing its maintenance status. The GitHub repo (`Nahuel990/ministack`) appears to be a small, low-visibility project. If it is unmaintained, the "no credential leak found" conclusion has a shelf life tied to the last reviewed commit, and future changes won't receive security scrutiny. The finding relies on specific file snapshots from an unspecified version. For a security-focused credential analysis, the absence of a version/commit pin is a gap.
- **Impact**: Medium. The security posture of an unmaintained tool is weaker than its current code suggests, and this should be called out.

---

### Issue 10: No Coverage of Non-Environment-Variable Credential Chains

- **Type**: Gap
- **Location**: Cross-tool section — *"If any of these tools are run with `-e AWS_ACCESS_KEY_ID=...`"*
- **Problem**: The credential-risk analysis focuses almost entirely on environment variable injection. Modern CI environments increasingly use AWS SSO, instance profiles (EC2/ECS), EKS pod identity, or IRSA. In those patterns, there is no `AWS_ACCESS_KEY_ID` env var; instead, the SDK calls IMDS or a token endpoint. The finding does not analyze whether any of the four tools intercept or log IMDS calls or what happens when the SDK falls back to the metadata service. Moto's `skip_metadata_api_check` setting is noted but not explained in this context.
- **Impact**: Medium. For cloud-native CI (EKS, ECS tasks, GitHub Actions with OIDC), the env-var-centric analysis is incomplete.

---

### Issue 11: Moto `skip_*` Flags Applied Only to Terraform Provider, Not SDK Broadly

- **Type**: Missing nuance
- **Location**: *"`skip_credentials_validation`, `skip_metadata_api_check`, and `skip_requesting_account_id`, which reduces pressure to use real credentials at all"*
- **Problem**: These are Terraform AWS provider settings. They only suppress the provider's own credential validation calls (e.g., `sts:GetCallerIdentity`). They have no effect on boto3 clients used directly in test code, Lambda functions invoked through Moto, or any SDK usage outside the Terraform provider. The phrasing "reduces pressure to use real credentials at all" overstates the scope of these flags for a general-purpose security recommendation.
- **Impact**: Low-medium. Developers who see this and assume their entire test suite is credential-safe because they set these three Terraform flags will be wrong if they also use boto3 directly.

---

## Summary

**Total issues found**: 11 (1 contradiction, 1 possible factual error, 3 unsupported or overstated claims, 4 missing nuance, 2 gaps)

**Overall reliability**: **Medium**

The findings are well-structured, honest about evidence quality for Floci, and reach defensible conclusions for LocalStack and Moto. The cross-tool operational note about env vars is genuinely useful. However, the internal contradiction on `PARITY_AWS_ACCESS_KEY_ID` (Issue 1) is serious enough that a practitioner acting on the findings section rather than the trade-offs section could misconfigure their environment in the opposite of the intended direction. The Floci "real IAM" ambiguity (Issue 6) is also high-impact because the most dangerous interpretation — outbound IAM delegation — is not explicitly ruled out.

**What would most improve this findings document**:
1. Resolve the `PARITY_AWS_ACCESS_KEY_ID` contradiction by quoting the source directly and picking one direction.
2. Add a prominent caveat to all Floci claims that "real IAM" could mean outbound delegation, and flag it as an unresolved open question rather than a parenthetical.
3. Pin the MiniStack analysis to a specific commit hash, given the project's apparent low visibility.
4. Add a paragraph covering IMDS/instance-profile credential chains, which are absent from the current analysis.
