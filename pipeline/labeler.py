"""Transcripts -> scrubbed, Claude-labeled call_turns in Postgres.

For each transcript JSON in --in:
  1. deterministically scrub PII (pipeline/scrub.py)
  2. ask Claude to tag each turn (objection_type / tactic) from the closed taxonomy + re-mask names
  3. INSERT the call + turns; join outcomes from --outcomes CSV if provided

--outcomes CSV: call_id,promise_made,promise_kept,amount_promised,amount_paid,days_to_payment
(from Kleva's collections DB). Without it, promise_made comes from Claude's inference and
promise_kept stays NULL — the loop runs but the tactic ranking needs real outcomes.

Usage:
  DATABASE_URL=postgresql://cobranza:pw@localhost:5432/cobranza \
  ANTHROPIC_API_KEY=... \
  python pipeline/labeler.py --in data/transcripts/ --outcomes data/outcomes.csv
"""
import argparse, csv, glob, hashlib, json, os

import anthropic
import psycopg

from scrub import scrub

HERE = os.path.dirname(__file__)
LABEL_PROMPT = open(os.path.join(HERE, "..", "prompts", "label_prompt.txt"), encoding="utf-8").read()
MODEL = os.environ.get("LABEL_MODEL", "claude-sonnet-5")


def load_outcomes(path: str | None) -> dict:
    if not path or not os.path.exists(path):
        return {}
    out = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[row["call_id"]] = row
    return out


def label_call(client, turns: list) -> dict:
    convo = "\n".join(f'{t["turn_index"]} [{t["speaker"]}]: {scrub(t["text"])}' for t in turns)
    msg = client.messages.create(
        model=MODEL, max_tokens=2000,
        system=LABEL_PROMPT,
        messages=[{"role": "user", "content": convo}],
    )
    text = msg.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1].removeprefix("json").strip()
    return json.loads(text)


def upsert(conn, call_id: str, labeled: dict, outcome: dict):
    promise_made = (outcome.get("promise_made") if outcome else None)
    if promise_made is None:
        promise_made = labeled.get("promise_made")

    def b(v):  # csv strings -> bool/None
        if v is None or v == "":
            return None
        return str(v).strip().lower() in ("1", "true", "t", "yes", "si", "sí")

    def n(v):
        return None if v in (None, "") else v

    debtor_hash = hashlib.sha256(call_id.encode()).hexdigest()[:16]
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO calls (call_id, source, debtor_id_hash, promise_made, promise_kept,
                               amount_promised, amount_paid, days_to_payment)
            VALUES (%s,'human',%s,%s,%s,%s,%s,%s)
            ON CONFLICT (call_id) DO UPDATE SET
              promise_made=EXCLUDED.promise_made, promise_kept=EXCLUDED.promise_kept,
              amount_promised=EXCLUDED.amount_promised, amount_paid=EXCLUDED.amount_paid,
              days_to_payment=EXCLUDED.days_to_payment
        """, (call_id, debtor_hash, promise_made,
              b(outcome.get("promise_kept")) if outcome else None,
              n(outcome.get("amount_promised")) if outcome else None,
              n(outcome.get("amount_paid")) if outcome else None,
              n(outcome.get("days_to_payment")) if outcome else None))

        cur.execute("DELETE FROM call_turns WHERE call_id=%s", (call_id,))
        for t in labeled["turns"]:
            cur.execute("""
                INSERT INTO call_turns (call_id, turn_index, speaker, text, objection_type, tactic)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (call_id, t["turn_index"], t["speaker"], t["text"],
                  t.get("objection_type"), t.get("tactic")))
    conn.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="indir", default="data/transcripts")
    ap.add_argument("--outcomes", default=None)
    args = ap.parse_args()

    outcomes = load_outcomes(args.outcomes)
    client = anthropic.Anthropic()
    conn = psycopg.connect(os.environ["DATABASE_URL"])

    files = sorted(glob.glob(os.path.join(args.indir, "*.json")))
    for i, path in enumerate(files, 1):
        data = json.load(open(path, encoding="utf-8"))
        call_id = data["call_id"]
        try:
            labeled = label_call(client, data["turns"])
            upsert(conn, call_id, labeled, outcomes.get(call_id, {}))
            print(f"[{i}/{len(files)}] {call_id}: {len(labeled['turns'])} turns labeled")
        except Exception as e:
            print(f"[{i}/{len(files)}] {call_id}: FAILED {e}")
    conn.close()


if __name__ == "__main__":
    main()
