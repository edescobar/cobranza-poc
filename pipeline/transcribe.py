"""S3 audio -> diarized Spanish transcripts (Deepgram) -> one JSON per call in --out.

Each transcript JSON:
  {"call_id": "<s3 key stem>", "turns": [{"turn_index":0,"speaker":"agent","text":"...","start":0.0}, ...]}

Speaker roles: Deepgram diarization returns speaker indices (0/1), not roles. We use the heuristic
"whoever speaks first = agent" (collections agents open the call). The Claude labeler can correct
obvious role flips later. For higher accuracy, wire real role labels from your telephony metadata.

Usage:
  python pipeline/transcribe.py --bucket <bucket> --prefix calls/ --out data/transcripts/
"""
import argparse, json, os, tempfile

import boto3
from deepgram import DeepgramClient, PrerecordedOptions, FileSource

AUDIO_EXTS = (".wav", ".mp3", ".m4a", ".ogg", ".flac", ".opus")


def utterances_to_turns(utterances: list) -> list:
    """Merge Deepgram utterances into turns, collapsing consecutive same-speaker utterances."""
    turns = []
    first_speaker = utterances[0]["speaker"] if utterances else 0
    for u in utterances:
        role = "agent" if u["speaker"] == first_speaker else "debtor"
        if turns and turns[-1]["speaker"] == role:
            turns[-1]["text"] += " " + u["transcript"]
        else:
            turns.append({"turn_index": len(turns), "speaker": role,
                          "text": u["transcript"], "start": round(u.get("start", 0.0), 2)})
    return turns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--prefix", default="")
    ap.add_argument("--out", default="data/transcripts")
    ap.add_argument("--limit", type=int, default=0, help="max files (0 = all)")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    s3 = boto3.client("s3")
    dg = DeepgramClient(os.environ["DEEPGRAM_API_KEY"])
    opts = PrerecordedOptions(model="nova-2", language="es", diarize=True,
                              punctuate=True, utterances=True, smart_format=True)

    paginator = s3.get_paginator("list_objects_v2")
    count = 0
    for page in paginator.paginate(Bucket=args.bucket, Prefix=args.prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.lower().endswith(AUDIO_EXTS):
                continue
            call_id = os.path.splitext(os.path.basename(key))[0]
            out_path = os.path.join(args.out, f"{call_id}.json")
            if os.path.exists(out_path):
                continue

            with tempfile.NamedTemporaryFile() as tmp:
                s3.download_fileobj(args.bucket, key, tmp)
                tmp.seek(0)
                payload: FileSource = {"buffer": tmp.read()}
                resp = dg.listen.rest.v("1").transcribe_file(payload, opts)

            # SDK returns a typed object; normalize to a plain dict
            data = resp.to_dict() if hasattr(resp, "to_dict") else resp
            utterances = data.get("results", {}).get("utterances", [])
            turns = utterances_to_turns(utterances)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump({"call_id": call_id, "s3_key": key, "turns": turns}, f, ensure_ascii=False, indent=2)
            count += 1
            print(f"[{count}] {key} -> {out_path} ({len(turns)} turns)")
            if args.limit and count >= args.limit:
                return


if __name__ == "__main__":
    main()
