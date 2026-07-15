# cobranza-poc

Contained test env to see whether **pattern-retrieval + a fast open model (Qwen3)** makes a Spanish
collections agent measurably smarter — *before* any fine-tuning or touching production.

It's text-first on purpose (isolates the pattern logic from voice/telephony) and fully contained: its
own droplet, its own Postgres, scrubbed data only, locked to you behind Cloudflare Access, and torn
down with one command.

## What it does

```
debtor line ──► classify objection ──► look up the tactic that historically CONVERTS for it
                                          (pattern_stats) ──► inject into the prompt ──► Qwen3 ──► reply
```

A **"patterns on/off" toggle** lets you see the difference the learned patterns make, side by side.
A **model switch** (qwen3:8b ↔ qwen3:4b) lets you compare Spanish quality *and* latency.

## The pieces (all in docker-compose)

| service | what |
|---|---|
| `ollama` | runs Qwen3, OpenAI-compatible endpoint |
| `postgres` | `call_turns` pattern store + `pattern_stats` rollup |
| `api` | FastAPI — the retrieval loop, logs latency (TTFT + tok/sec) |
| `cloudflared` | CF Tunnel, gated by CF Access = you only |

Plus a `web/` chat page and a `pipeline/` (S3 audio → Deepgram → scrub → Claude auto-label → DB).

## Quick start (local or on a DO droplet)

```bash
cp .env.example .env          # fill in POSTGRES_PASSWORD; keys only needed for the pipeline
docker compose up -d postgres api ollama

# pull the models (once; qwen3:4b or qwen3:1.7b if you're on CPU)
docker compose exec ollama ollama pull qwen3:8b
docker compose exec ollama ollama pull qwen3:4b

# seed the sample patterns so the UI works before real data lands
docker compose exec -T postgres psql -U cobranza -d cobranza < db/seed_sample.sql

open http://localhost:8000     # type a debtor line, toggle patterns on/off
```

The schema (`db/schema.sql`) loads automatically on first `postgres` start.

## Load your real calls (the fuel)

```bash
pip install -r pipeline/requirements.txt

# 1) S3 audio -> diarized Spanish transcripts (Deepgram)
python pipeline/transcribe.py --bucket <bucket> --prefix <folder/> --out data/transcripts/

# 2) transcripts -> scrubbed, Claude-labeled call_turns in Postgres
python pipeline/labeler.py --in data/transcripts/ --outcomes data/outcomes.csv
```

`data/outcomes.csv` = `call_id,promise_made,promise_kept,amount_paid,days_to_payment` from Kleva's
collections DB. Without it the loop still runs, but the "which tactic converts" ranking needs it.

## The bake-off (fast + good Spanish)

Set `OLLAMA_MODEL=qwen3:4b` in `.env`, restart `api`, rerun the same debtor lines, compare the
`ttft_ms` / `tok_per_sec` the UI shows against `qwen3:8b`. Pick the fastest size that still reads well.

## Expose it privately (Cloudflare)

1. Create a **CF Tunnel**, put its token in `.env` as `TUNNEL_TOKEN`, point a hostname (e.g.
   `cobranza-test.openkleo.com`) at `http://api:8000`.
2. Add a **CF Access** policy on that hostname: allow `ed@kleva.co` only.
3. `docker compose up -d cloudflared`.

Same pattern as the orchestrator (`docs/INFRA.md` in ide-personal).

## Teardown

`docker compose down -v` and destroy the droplet. Nothing persists.

## Not in scope (later)

Real-time voice + LiveKit wiring · fine-tuning (LoRA/SFT on Together → vLLM) · voice-signal patterns
from the raw audio · DPO from winning-vs-losing pairs.
