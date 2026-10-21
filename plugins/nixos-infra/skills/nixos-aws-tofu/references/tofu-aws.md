# OpenTofu on AWS: state, credentials, ingress

One shared module, one root per environment, one bucket:

```
tofu/modules/host/   instance, EIP, security group, DNS record
tofu/staging/        -> s3://<bucket>/staging.tfstate
tofu/prod/           -> s3://<bucket>/prod.tfstate
```

The roots share the module and **nothing else**. Separate state files are what
make a staging apply structurally incapable of touching production — not
discipline, not naming. Preserve that. Each root also holds its own
`variables.tf`, so a permissive staging value cannot leak into prod.

Never commit tfstate. It stores resource attributes in plaintext.

## The bucket is created out of band

State cannot manage the bucket that holds it — the chicken-and-egg is real, so
it is created once by hand with versioning, encryption and public access
blocked. Versioning is the recovery path for truncated or corrupted state;
leave it on.

Locking is `use_lockfile = true`, which uses S3 conditional writes. The
DynamoDB table older guides insist on is obsolete — do not add one.

## Credentials: the failure you will actually hit

`aws login` (SSO) writes its session to `~/.aws/login/`, and **only the CLI
reads that directory**. The provider's Go SDK does not, and fails with "No
valid credential sources found" even though `aws s3 ls` works fine in the same
shell.

Bridge them into the environment before running tofu:

```sh
eval "$(aws configure export-credentials --format env)"
```

An expired session reports `Your session has expired` on any call, including
`sts get-caller-identity` — check that first when tofu cannot authenticate,
before suspecting the backend config. Reauthentication is interactive and
browser-based; it cannot be done from an agent's shell.

## Resource traps

- **`key_name` is ForceNew on `aws_instance`.** Renaming the key pair
  *replaces the machine*. The AMI hands this key to root on first boot, which
  is what makes the first `nixos-rebuild` possible — after that it is inert,
  but the dependency remains in state.
- **EC2 key pair names are account-global.** Two roots in one account need two
  distinct names for what is materially the same key.
- **`lifecycle { ignore_changes = [ami] }` is deliberate.** NixOS publishes a
  new AMI weekly; adopting one would replace the instance, and the AMI only
  matters at first boot. Never "fix" a plan by removing this.
- **The EIP exists so DNS survives instance recreation.** Destroying and
  recreating an instance is cheap; losing the address is not.
- **`proxied = false` on the DNS record.** Cloudflare's proxy carries neither
  PostgreSQL nor Redis, and Caddy terminates TLS itself over ACME.
- IMDSv2 is required (`http_tokens = "required"`). Leave it.

Read every `must be replaced` line in a plan before applying. A one-character
variable edit that replaces a database host is a plan you were shown and
approved.

## Security groups

Security groups are **stateful and allow-only**. There is no deny rule, so
policy is expressed purely as an enumeration of what may connect.

That enumeration has a budget: **60 inbound rules per group by default**, with
a hard ceiling of 1000 rules per network interface. Any policy requiring an
enumerated geography is therefore not expressible — a single mid-sized
country runs to hundreds of aggregated CIDR blocks, the United States to tens
of thousands. Country allowlists are not a tighter option that costs more
effort; they are not an option. Do not build one.

Two further facts worth internalising before proposing an allowlist:

- **"All of one large country" is not a restriction.** US-allocated space is
  roughly 37% of IPv4. That rule is `0.0.0.0/0` with extra steps.
- **The AWS region is irrelevant to ingress.** A security group filters who
  connects *in*. An instance living in `us-east-1` creates no need to admit US
  sources; the only ones that matter are the specific services that dial the
  host.

### Allowlisting a residential operator

A `/32` for a home connection fails within days. Consumer ISPs hand out CGNAT
leases that rotate, so the pinned address goes stale and locks out the only
person who deploys — and if the same variable guards the database ports, it
locks out `psql` at the same time.

Find the real allocation before choosing:

```sh
curl -s https://checkip.amazonaws.com                    # current source address
curl -s https://rdap.arin.net/registry/ip/<addr> | jq '{name,startAddress,endAddress,cidr0_cidrs}'
```

Three defensible outcomes, in rough order of preference:

1. **Drop the allowlist for SSH, keep it for the database ports.** With
   `PasswordAuthentication = false` and key-only root, an exposed port 22 has
   nothing to brute-force; the cost is log noise. Postgres and Redis
   authenticate with passwords, so source filtering there buys something real.
   This is usually the right answer for a disposable host.
2. **Allowlist the ISP's allocation** (typically a `/20`ish block). One rule,
   survives lease rotation, still orders of magnitude narrower than a country.
   Costs you access from mobile data, travel, or any other network.
3. **Tailscale.** Port 22 leaves the security group entirely and SSH
   authenticates by WireGuard key, so location stops mattering. Managed
   platforms that cannot join a tailnet still need their own allowlist entry,
   so this rarely removes the database rule.

Whichever is chosen, record the reasoning in the variable's comment. The next
reader needs to know an open CIDR was a decision, not an oversight.

## Diagnosing "I cannot reach the host"

In order, because each step rules out a layer:

```sh
getent hosts <fqdn>                                # DNS -> expected EIP?
timeout 5 ssh -o BatchMode=yes -o ConnectTimeout=5 root@<fqdn> true
curl -s https://checkip.amazonaws.com              # did *your* address move?
```

- **Timed out** — a packet was dropped. Security group first, host firewall
  second. If DNS still resolves to the right EIP, the instance is almost
  certainly alive and you are the thing that changed.
- **Refused** — you reached the host and nothing is listening. sshd down, or
  the wrong port.
- **DNS wrong** — the EIP moved or the record drifted; a `plan` will say.

Do not open the AWS console before making this distinction. The failure mode
names the layer.
