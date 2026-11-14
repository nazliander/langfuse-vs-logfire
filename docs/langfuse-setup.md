# Langfuse self-hosted setup

CAUTION: The stack uses about 4 GB of memory. Stop it with `scripts/langfuse.sh down` after the runs.

The official compose file binds the web UI, the AI gateway, and MinIO to all network interfaces, and it uses public default secrets. This project changes two things:

- `docker/langfuse.override.yml` binds every port to `127.0.0.1`.
- `docker/langfuse.env` holds random secrets. Git ignores this file.

`scripts/langfuse.sh` wraps `docker-compose` with both files and the project name `langfuse`.

## Start

1. Start OrbStack.
2. Clone the official repository into `langfuse-server/` (git ignores this folder):

```bash
git clone --depth 1 https://github.com/langfuse/langfuse.git langfuse-server
```

3. Start the stack:

```bash
scripts/langfuse.sh up -d
```

4. Open http://localhost:3000.
5. Sign up with a local account. This account exists only in your local Postgres.
6. Create an organization and a project.
7. Create API keys in the project settings.
8. Copy the keys to `.env` as `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY`.

## Stop

```bash
scripts/langfuse.sh down
```

Add `-v` to also delete the data volumes.
