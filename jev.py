"""Shared TypeSafe/Jev client for the RFM pipeline.

Every Jev call in this project goes through `ask()`. It adds three things on top
of the SDK:

  1. On-disk caching, keyed by the exact (model, state, questions) triple. Re-running
     a deck build or a scoring pass costs nothing and returns identical judgments.
  2. An offline stub mode so the deterministic half of the pipeline — filtering,
     weighting, rendering — can be exercised without an API key. Stub answers are
     synthetic and loudly labelled; they are not judgments.
  3. A clear failure when TYPESAFE_API_KEY is missing, instead of an SDK traceback.

Get a key at https://console.typesafe.ai/ and export it:

    export TYPESAFE_API_KEY=sk-...
"""

import hashlib
import json
import os
import sys

from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

# ── CONFIG ────────────────────────────────────────────────────────────────────
MODEL      = os.environ.get('JEV_MODEL', 'jev-latest')
OFFLINE    = os.environ.get('JEV_OFFLINE') == '1' or '--offline' in sys.argv

# Stub answers live in their own directory. Sharing one cache would let an offline
# run poison a later real one: the fingerprint covers the model, state and questions,
# none of which change when you finally set an API key.
CACHE_DIR  = os.path.join('.jev_cache', 'offline' if OFFLINE else 'live')

_client = None


# ── .env ──────────────────────────────────────────────────────────────────────
def _load_dotenv(path='.env'):
    """Read KEY=value lines from a local .env, without taking on a dependency.

    A real environment variable always wins, so `export TYPESAFE_API_KEY=...` in
    your shell overrides whatever the file says.
    """
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


# ── CLIENT ────────────────────────────────────────────────────────────────────
def get_client():
    """Return a shared TypeSafeClient, or explain what's missing."""
    global _client
    if _client is None:
        if not os.environ.get('TYPESAFE_API_KEY'):
            raise SystemExit(
                "TYPESAFE_API_KEY is not set.\n\n"
                "  Get a key at https://console.typesafe.ai/ then either:\n"
                "    1. paste it into a .env file in this directory:\n"
                "         cp .env.example .env    # then edit the one line\n"
                "    2. or export it in your shell:\n"
                "         export TYPESAFE_API_KEY=sk-...\n\n"
                "  .env is git-ignored. Do not commit the key or paste it into a chat.\n"
                "  Or re-run with --offline to exercise the pipeline with stub\n"
                "  answers (synthetic values, not real judgments)."
            )
        _client = TypeSafeClient(model=MODEL)
    return _client


# ── CACHE ─────────────────────────────────────────────────────────────────────
def _fingerprint(state, questions):
    payload = {
        'model': MODEL,
        'state': state,
        'questions': {k: q.model_dump(mode='json') for k, q in sorted(questions.items())},
    }
    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:32]


def _cache_read(key):
    path = os.path.join(CACHE_DIR, key + '.json')
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def _cache_write(key, answers):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(os.path.join(CACHE_DIR, key + '.json'), 'w') as f:
        json.dump(answers, f, indent=2)


# ── OFFLINE STUBS ─────────────────────────────────────────────────────────────
def _stub(key, questions):
    """Deterministic fake answers so non-Jev code paths stay testable offline.

    Values are derived from a hash of the question id and the state fingerprint.
    They are stable across runs and meaningless as judgments.
    """
    answers = {}
    for qid, q in questions.items():
        seed = int(hashlib.sha256((key + qid).encode()).hexdigest()[:8], 16)
        if isinstance(q, Noul):
            answers[qid] = {'type': 'noul', 'noul': round((seed % 1000) / 1000, 3)}
        elif isinstance(q, Choice):
            opts = list(q.criteria)
            pick = opts[seed % len(opts)]
            answers[qid] = {
                'type': 'choice',
                'choice': pick,
                'confidence': round(0.35 + (seed % 60) / 100, 3),
                'probabilities': {o: round(1 / len(opts), 3) for o in opts},
            }
        elif isinstance(q, Score):
            top = len(q.criteria) - 1
            answers[qid] = {
                'type': 'score',
                'score': round((seed % (top * 100 + 1)) / 100, 2),
                'confidence': round(0.35 + (seed % 60) / 100, 3),
                'legend': {i: str(c) for i, c in enumerate(q.criteria)},
                'probabilities': {},
            }
    answers['_offline'] = True
    return answers


# ── ASK ───────────────────────────────────────────────────────────────────────
def ask(state, questions, use_cache=True):
    """Ask a batch of independent questions about one state. Returns a plain dict.

    Questions passed together run in parallel in a single request and cannot see
    one another's answers — so only ask things that are independent given `state`.
    """
    key = _fingerprint(state, questions)

    if use_cache:
        hit = _cache_read(key)
        if hit is not None:
            return hit

    if OFFLINE:
        answers = _stub(key, questions)
    else:
        response = get_client().system_one(state=state, questions=questions)
        answers = {qid: a.model_dump(mode='json') for qid, a in response.answers.items()}
        answers['_usage'] = response.usage.model_dump(mode='json')
        answers['_model'] = response.model

    if use_cache:
        _cache_write(key, answers)
    return answers


def weakest(answers):
    """(question_id, confidence) of the least certain Choice/Score answer.

    Nouls are excluded: a Noul carries no separate confidence, and a value near
    0.5 means 'genuinely balanced', not 'unreliable'.
    """
    scored = [(qid, a['confidence']) for qid, a in answers.items()
              if isinstance(a, dict) and 'confidence' in a]
    return min(scored, key=lambda x: x[1]) if scored else (None, 1.0)


def banner():
    """Warn once, visibly, when output is built on stub answers."""
    if OFFLINE:
        print('!! OFFLINE MODE — answers below are synthetic stubs, not Jev judgments\n')
