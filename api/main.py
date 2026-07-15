"""cobranza-poc API — the retrieval loop.

debtor line -> classify objection -> look up the tactic that converts best for it (pattern_stats)
            -> inject into the prompt -> Qwen3 -> reply, with latency (TTFT + tok/sec).

`patterns=false` skips the retrieval so the UI can show on/off side by side.
"""
import os, time, json
from contextlib import asynccontextmanager

import asyncpg, httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

DATABASE_URL = os.environ["DATABASE_URL"]
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:8b")
PROMPTS_DIR = os.environ.get("PROMPTS_DIR", "/app/prompts")
WEB_DIR = os.environ.get("WEB_DIR", "/app/web")

SYSTEM_PROMPT = open(os.path.join(PROMPTS_DIR, "system_prompt_es.txt"), encoding="utf-8").read()

# keyword fallback if the classifier LLM call misfires
KEYWORDS = {
    "sin_dinero": ["no tengo", "no puedo pagar", "no me alcanza", "sin plata", "no hay plata"],
    "ya_pague": ["ya pague", "ya pagué", "ya lo pague", "ya abone"],
    "desconoce_deuda": ["no conozco", "quien habla", "quién habla", "que deuda", "no debo"],
    "posterga": ["la semana que viene", "mas adelante", "más adelante", "despues", "después", "otro dia"],
    "pago_parcial": ["la mitad", "una parte", "un poco", "parcial"],
    "molesto": ["no me molesten", "dejen de", "basta", "harto"],
    "persona_equivocada": ["numero equivocado", "número equivocado", "no soy", "se equivoco"],
    "promesa_vaga": ["voy a pagar", "en cuanto pueda", "apenas pueda", "ya te pago"],
}

app_state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app_state["pool"] = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    rows = await app_state["pool"].fetch("SELECT objection_type, description_es FROM objection_types ORDER BY objection_type")
    app_state["taxonomy"] = [dict(r) for r in rows]
    yield
    await app_state["pool"].close()


app = FastAPI(lifespan=lifespan)


class ReplyReq(BaseModel):
    text: str
    patterns: bool = True
    model: str | None = None


def keyword_objection(text: str) -> str | None:
    t = text.lower()
    for obj, kws in KEYWORDS.items():
        if any(k in t for k in kws):
            return obj
    return None


async def classify_objection(text: str, model: str) -> str | None:
    labels = app_state["taxonomy"]
    sys = ("Clasificá el mensaje del deudor en UNA de estas categorías. "
           "Respondé SOLO con la etiqueta exacta (la clave), sin explicación.\nCategorías:\n"
           + "\n".join(f"- {o['objection_type']}: {o['description_es']}" for o in labels)
           + "\n\n/no_think")   # Qwen3 soft-switch: disable reasoning (latency)
    payload = {"model": model, "stream": False, "think": False,
               "options": {"temperature": 0},
               "messages": [{"role": "system", "content": sys}, {"role": "user", "content": text}]}
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(f"{OLLAMA_URL}/api/chat", json=payload)
            r.raise_for_status()
            out = (r.json().get("message", {}).get("content") or "").strip().lower()
        for o in labels:
            if o["objection_type"] in out:
                return o["objection_type"]
    except Exception:
        pass
    return keyword_objection(text)


async def chat_stream(model: str, messages: list) -> dict:
    payload = {"model": model, "messages": messages, "stream": True, "think": False,
               "options": {"temperature": 0.5}}
    t0 = time.perf_counter()
    ttft = None
    text = ""
    eval_count = 0
    eval_dur = 0
    async with httpx.AsyncClient(timeout=180) as c:
        async with c.stream("POST", f"{OLLAMA_URL}/api/chat", json=payload) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line.strip():
                    continue
                obj = json.loads(line)
                chunk = obj.get("message", {}).get("content", "")
                if chunk and ttft is None:
                    ttft = time.perf_counter() - t0
                text += chunk
                if obj.get("done"):
                    eval_count = obj.get("eval_count", 0)
                    eval_dur = obj.get("eval_duration", 0)
    total = time.perf_counter() - t0
    tps = (eval_count / (eval_dur / 1e9)) if eval_dur else None
    return {
        "text": text.strip(),
        "ttft_ms": round((ttft or total) * 1000),
        "total_ms": round(total * 1000),
        "tokens": eval_count,
        "tok_per_sec": round(tps, 1) if tps else None,
    }


@app.post("/reply")
async def reply(req: ReplyReq):
    model = req.model or DEFAULT_MODEL
    objection = tactic = tactic_desc = None
    if req.patterns:
        objection = await classify_objection(req.text, model)
        if objection:
            row = await app_state["pool"].fetchrow(
                "SELECT s.tactic, t.description_es, s.conversion_rate, s.n "
                "FROM pattern_stats s JOIN tactics t ON t.tactic = s.tactic "
                "WHERE s.objection_type = $1 ORDER BY s.conversion_rate DESC, s.n DESC LIMIT 1",
                objection)
            if row:
                tactic, tactic_desc = row["tactic"], row["description_es"]

    # `/no_think` disables Qwen3's reasoning mode (a one-line collections reply must be instant,
    # not preceded by thousands of reasoning tokens). Paired with think:false in the payload.
    messages = [{"role": "system", "content": SYSTEM_PROMPT + "\n\n/no_think"}]
    if tactic:
        messages.append({"role": "system",
                         "content": f"Táctica sugerida para esta situación: {tactic} — {tactic_desc}. "
                                    f"Aplicala con naturalidad, no la nombres."})
    messages.append({"role": "user", "content": req.text})

    result = await chat_stream(model, messages)
    return {"model": model, "patterns": req.patterns, "objection": objection,
            "tactic": tactic, "reply": result["text"],
            "ttft_ms": result["ttft_ms"], "total_ms": result["total_ms"],
            "tokens": result["tokens"], "tok_per_sec": result["tok_per_sec"]}


@app.get("/stats")
async def stats():
    rows = await app_state["pool"].fetch(
        "SELECT objection_type, tactic, n, conversion_rate FROM pattern_stats "
        "ORDER BY objection_type, conversion_rate DESC, n DESC")
    return [dict(r) for r in rows]


@app.get("/health")
async def health():
    return {"ok": True, "model": DEFAULT_MODEL}


@app.get("/", response_class=HTMLResponse)
async def index():
    return open(os.path.join(WEB_DIR, "index.html"), encoding="utf-8").read()
