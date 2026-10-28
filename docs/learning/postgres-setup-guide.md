# From SQLite to Postgres — Everything We Did & Why

> [!NOTE]
> You have 10 years of frontend experience. Every concept here maps to something you already know. That's the lens we'll use.

---

## The Big Picture — What Changed

```mermaid
flowchart LR
    A["Before\nFastAPI → SQLite file\non disk"] -->|"What we did"| B["After\nFastAPI → psycopg2 driver\n→ Postgres in Docker"]
```

Before: your app talked to a single file (`insta_clone.db`) sitting on disk.  
After: your app talks to a **real database server** running in a container, over a network connection.

---

## Step 1 — Docker Compose

### What is Docker?
Think of Docker like **an npm package, but for entire programs** — including their OS dependencies.

- A **Docker image** = a snapshot of a program and everything it needs to run (like a `node_modules` folder, but for an entire Linux environment)
- A **Docker container** = a running instance of that image (like running `node server.js`)

### What is Docker Compose?
A `docker-compose.yml` is like a `package.json` for your infrastructure. Instead of declaring JS dependencies, you declare **which services to run**.

```yaml
# docker-compose.yml
services:
  db:                               # name of this service (like a variable name)
    image: postgres:16-alpine       # which Docker image to use (like an npm package)
    environment:                    # env vars passed into the container
      POSTGRES_USER: insta
      POSTGRES_PASSWORD: insta_secret
      POSTGRES_DB: insta_clone
    ports:
      - "5433:5432"                 # HOST_PORT:CONTAINER_PORT
    volumes:
      - postgres_data:/var/lib/postgresql/data  # persist data between restarts

  pgadmin:                          # a web UI to browse the DB (like Redux DevTools for your DB)
    image: dpage/pgadmin4:latest
    ports:
      - "5050:80"

volumes:
  postgres_data:                    # named volume — survives container restarts
```

### The ports line explained
`"5433:5432"` means: **forward port 5433 on your laptop to port 5432 inside the container**.

Postgres always listens on 5432 inside. But since another Postgres was already using 5432 on your machine, we exposed it as 5433 outside. Your app connects to `localhost:5433` — Docker handles the rest.

> [!TIP]
> **Frontend equivalent**: Like running `vite --port 3001` because 3000 is taken. The app inside still thinks it's on port 3000.

### Key commands
```bash
docker compose up -d      # start all services in background (-d = detached, like & in bash)
docker compose down       # stop and remove containers (data in volumes is preserved)
docker compose ps         # see what's running
docker compose logs db    # see Postgres logs
```

---

## Step 2 — The `.env` File & `DATABASE_URL`

Your app reads config from `.env` via `pydantic-settings`. This is the same concept as `.env.local` in Next.js.

```bash
# .env
DATABASE_URL=postgresql+psycopg2://insta:insta_secret@localhost:5433/insta_clone
```

Let's break down the URL like a regular URL:

```
postgresql+psycopg2 :// insta : insta_secret @ localhost : 5433 / insta_clone
│─── protocol ──────│   │user│  │──password─│   │─host─│  │port│  │─db name─│
```

| Part | Meaning | Frontend analogy |
|---|---|---|
| `postgresql+psycopg2` | Use Postgres with the psycopg2 driver | `https://` — which protocol/transport to use |
| `insta` | DB username | API key username |
| `insta_secret` | DB password | API key secret |
| `localhost:5433` | Where the DB server is | API base URL |
| `insta_clone` | Which database to connect to | Which API workspace/project |

> [!IMPORTANT]
> `.env` is in `.gitignore` — **never commit it**. `.env.example` is the template you commit. This is the same convention as every frontend framework.

---

## Step 3 — psycopg2 (The Driver)

```bash
pip install psycopg2-binary
```

SQLAlchemy doesn't talk to Postgres directly. It needs a **driver** — a low-level adapter that handles the actual TCP connection, wire protocol, and data serialization.

| Layer | What it does | Frontend analogy |
|---|---|---|
| **Your code** | `db.query(User).all()` | `fetch('/api/users')` |
| **SQLAlchemy** | Translates Python → SQL | `axios` — handles request/response abstraction |
| **psycopg2** | Sends SQL over TCP to Postgres | The browser's native `XMLHttpRequest` under the hood |
| **Postgres** | Executes the SQL, returns rows | The API server |

`psycopg2-binary` includes pre-compiled C extensions so you don't need to compile from source. The `-binary` suffix = convenience build, perfect for local dev.

---

## Step 4 — Alembic (Database Migrations)

### Why migrations?

When you modified `User` model to add `full_name`, you just changed a Python class. But the **database table** doesn't know about it. Without migrations, you'd have to manually write `ALTER TABLE users ADD COLUMN full_name VARCHAR(100)` in SQL every time.

**Alembic automates this.** It's the backend equivalent of what Prisma Migrate, Knex migrations, or TypeORM migrations do.

> [!NOTE]
> **Frontend analogy**: Like git for your database schema. Each migration is a commit. You can `upgrade` (go forward) or `downgrade` (roll back).

### How we configured it

**`alembic/env.py`** is the config brain. We wired it to your app:
```python
from app.core.config import settings   # reads DATABASE_URL from .env
from app.core.database import Base     # your SQLAlchemy Base
import app.models                      # MUST import all models so Alembic can "see" them

config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata        # Alembic compares this against the live DB
```

### The workflow — 3 commands you'll use forever

```bash
# 1. Generate a migration — Alembic diffs your models vs the live DB
alembic revision --autogenerate -m "add bio field to users"
# → creates alembic/versions/abc123_add_bio_field_to_users.py

# 2. Apply migrations — runs the SQL against the DB
alembic upgrade head
# "head" means "latest migration"

# 3. Roll back one step (if you made a mistake)
alembic downgrade -1
```

### What autogenerate actually does

When you ran `alembic revision --autogenerate`, it:
1. Connected to your Postgres DB (which was empty)
2. Looked at `Base.metadata` — all your SQLAlchemy models
3. **Diffed** them — found 8 new tables that exist in code but not in DB
4. Generated Python code to create them:

```python
# alembic/versions/fe5ecda06d7d_initial_schema.py (auto-generated!)
def upgrade() -> None:
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        ...
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

def downgrade() -> None:
    op.drop_table('users')  # auto-generated rollback too!
```

> [!TIP]
> After every model change (add a column, rename a field, add a new model), the cycle is always:
> ```bash
> alembic revision --autogenerate -m "describe what changed"
> alembic upgrade head
> ```

---

## Step 5 — The Seed Script

The seed script (`scripts/seed.py`) is a plain Python script that creates realistic fake data so you can test the API without manually clicking through forms.

### Key concepts used

**1. Guard against double-seeding**
```python
if db.query(User).count() > 0:
    print("Already seeded — skipping")
    return
```
Without this, running the script twice would create duplicate users and crash on the unique email constraint.

**2. `db.flush()` vs `db.commit()`**
```python
db.add_all(users)
db.flush()   # sends SQL to DB but doesn't COMMIT the transaction
             # now users have IDs we can use for foreign keys (post.author_id)

# ... create posts that reference user IDs ...

db.commit()  # writes everything permanently, atomically
```

> [!NOTE]
> **Frontend analogy**: `flush()` is like staging changes in git (`git add`). `commit()` is `git commit`. If anything fails between flush and commit, the rollback in our `except` block undoes everything — nothing is half-written.

**3. `db.rollback()` in the except block**
```python
except Exception:
    db.rollback()   # undo everything if any step fails
    raise
```
This is **database transaction safety** — all-or-nothing. Either all 8 users + 15 posts + 30 follows are created, or none are. No partial state.

---

## The Problem We Hit — Port Conflict

When `docker compose up` failed:
```
Bind for 0.0.0.0:5432 failed: port is already allocated
```

Another Postgres container (`corpus-postgres-1`) was already using port 5432 on your machine.

**Fix:** Changed `docker-compose.yml` to expose on port `5433` instead:
```yaml
ports:
  - "5433:5432"   # was "5432:5432"
```
And updated `DATABASE_URL` to match: `@localhost:5433/insta_clone`

---

## The Driver Mismatch We Hit

```
ModuleNotFoundError: No module named 'psycopg'
```

SQLAlchemy saw `postgresql://` and assumed you wanted `psycopg` (v3 driver). We installed `psycopg2-binary` (v2). The fix — be explicit in the URL:

```bash
# Before (ambiguous — SQLAlchemy picks the driver)
postgresql://...

# After (explicit — forces psycopg2)
postgresql+psycopg2://...
```

> [!TIP]
> Always use `postgresql+psycopg2://` when using `psycopg2-binary`. If you ever upgrade to `psycopg` v3, change it to `postgresql+psycopg://`.

---

## Mental Model — The Full Stack

```mermaid
flowchart TD
    A["uvicorn app.main:app\n(your FastAPI server)"]
    B["SQLAlchemy ORM\n(Python ↔ SQL translator)"]
    C["psycopg2\n(TCP driver)"]
    D["Docker container\nPostgres :5432 internally\n:5433 on your machine"]
    E["Volume: postgres_data\n(data persists on disk)"]
    F["pgAdmin :5050\n(browser DB GUI)"]

    A -->|"db.query(User)"| B
    B -->|"SELECT * FROM users"| C
    C -->|"TCP localhost:5433"| D
    D --- E
    F -->|"browse tables"| D
```

---

## Cheat Sheet — Commands to Never Forget

```bash
# === Docker ===
docker compose up -d          # start Postgres + pgAdmin
docker compose down           # stop (data preserved in volume)
docker compose down -v        # stop AND delete all data (nuclear reset)

# === Alembic (run from project root) ===
alembic upgrade head          # apply all pending migrations
alembic revision --autogenerate -m "what changed"  # generate migration
alembic downgrade -1          # undo last migration
alembic history               # see all migrations
alembic current               # see which migration the DB is at

# === Seed ===
python scripts/seed.py        # populate with fake data (safe to run — guarded)

# === Inspect the DB directly ===
docker compose exec db psql -U insta -d insta_clone
# then inside psql:
# \dt              → list tables
# \d users         → describe users table
# SELECT * FROM users;
# \q               → quit
```
