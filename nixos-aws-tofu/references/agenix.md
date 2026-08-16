# agenix: secrets, recipients, rotation

Encrypted `.age` files are committed; private keys never are. One keypair
does double duty: the operator's `~/.ssh/id_ed25519` authenticates SSH *and*
opens secrets, so there is no separate age key to provision or lose.

```
secrets/secrets.nix          recipients per file
secrets/<name>.age           the ciphertext, committed
modules/secrets-<scope>.nix  age.secrets.<name> declarations, imported per host
```

Consumers reference `config.age.secrets.<name>.path` (`/run/agenix/<name>`).

## Recipients are SSH public keys

The single most expensive mistake in this setup is converting keys with
`ssh-to-age`. That is a sops-nix idiom and it is wrong here.

agenix decrypts on the host by handing `/etc/ssh/ssh_host_ed25519_key` to
`age -i`. age opens **only `ssh-ed25519` stanzas** with an SSH identity. An
`age1...` recipient in `secrets.nix` produces an X25519 stanza, and the host
fails with "no identity matched any of the recipients" — surfacing as an empty
`/run/agenix` and a unit that will not start.

Put the raw key in, exactly as `ssh-keyscan` prints it:

```sh
ssh-keyscan -t ed25519 <host>          # -> ssh-ed25519 AAAAC3Nza...
# paste into secrets/secrets.nix, then
cd secrets && nix run github:ryantm/agenix -- --rekey
```

Verify what a file is actually encrypted to before deploying — the recipient
tags are readable without decrypting:

```sh
grep -a '^-> ' secrets/<name>.age      # every line must be ssh-ed25519
```

`age.identityPaths` defaults to `/etc/ssh/ssh_host_rsa_key` and
`/etc/ssh/ssh_host_ed25519_key`. Setting it explicitly is redundant unless the
host keeps its keys somewhere else.

## Writing a value non-interactively

`agenix -e` branches on `[ -t 0 ]`:

- **TTY present** — launches `$EDITOR` on a decrypted temp file.
- **No TTY** — runs `cp /dev/stdin "$FILE"`, and `$EDITOR` is never consulted.

The trap: an `EDITOR=./write-value.sh` shim under automation hits the second
branch. stdin is empty, so the secret is overwritten with **zero bytes** and
the command reports success. A second run then prints "wasn't changed,
skipping re-encryption" — because empty still equals empty — which reads like
a no-op rather than the data loss it is.

Correct form, always:

```sh
cd secrets
openssl rand -hex 24 | tr -d '\n' \
  | nix run github:ryantm/agenix -- -e <name>.age
```

`tr -d '\n'` matters downstream: a trailing newline ends up inside the
password. Note the consequence — `read -r pw` on such a file exits **non-zero
at EOF**, silently breaking any `cmd && cmd` chain that consumes it. Use
`pw=$(cat)`.

`agenix` resolves `secrets.nix` **relative to the working directory**. Run it
from `secrets/`, or it fails with "There is no rule for <file>".

Reading a value back:

```sh
nix run .#secret                       # fzf picker, value to the clipboard
nix run .#secret -- --print <query>    # stdout; lands in scrollback
cd secrets && nix run github:ryantm/agenix -- -d <name>.age
```

## Declarations must match what the host can decrypt

agenix decrypts during **activation**. A declared secret the host is not a
recipient of fails the whole activation, not merely the unit that wanted it.

So a single shared `modules/secrets.nix` listing production secrets will break
every non-production rebuild. Split declarations by scope and import only what
that host can open (`modules/secrets-staging.nix` for the staging host). When
a secret is operator-only — a database password the server stores as a hash
and never needs again — list it in `secrets.nix` for recoverability and
declare it in **no** module.

NixOS `mkIf` laziness is a genuine safety net here: a reference to a missing
`config.age.secrets.<x>` inside a disabled `mkIf` branch never evaluates. An
unguarded reference in an enabled path is an eval error.

## Rotation

Rotation is four steps and the third is the one everyone skips:

1. Write the new value (piped, as above).
2. Deploy — `nixos-rebuild switch`.
3. **Restart the consuming unit.**
4. Authenticate with the new value; confirm the old one now fails.

Step 3 is not optional. `nixos-rebuild` compares store paths. The unit's
store path is derived from its *configuration*, and rotating a secret changes
only the bytes at `/run/agenix/<name>` — so systemd sees an unchanged unit,
does nothing, and the daemon keeps serving the credential it read at startup.
Redis will happily answer `WRONGPASS` to the value you just deployed.

```sh
ssh root@<host> systemctl restart <unit>
```

For a database password, the server stores its own verifier, so rotation is an
`ALTER ROLE` rather than a restart. Pipe it so it never reaches shell history:

```sh
cd secrets
nix run github:ryantm/agenix -- -d postgres-<env>.pass.age \
  | ssh root@<host> "pw=\$(cat) && sudo -u postgres psql -qc \"ALTER ROLE <role> PASSWORD '\$pw'\""
```

Confirm both directions: the new value authenticates, the old value is
rejected. A rotation you only tested in the positive direction is not a
rotation.

## Rekeying

`--rekey` decrypts with your identity and re-encrypts to the current recipient
list. Run it after:

- adding or removing a host,
- **rebuilding a host from scratch** — a fresh instance generates a fresh SSH
  host key, so the old recipient is dead and the unit will not start,
- rotating the operator key.

## Key loss

- Host key lost (instance destroyed): fine. Your key still decrypts; rekey to
  the new host key and redeploy.
- Operator key lost, a host still decrypts: recoverable — re-encrypt from that
  host to a new key.
- Both lost: the `.age` files are inert. Every secret must be rotated at
  source. The operator key also opens SSH, so back it up.
