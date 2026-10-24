"""Groq wrapper: disk cache + replay mode, rate limiter, retry, JSON validation, leakage tripwire."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

import yaml
from pydantic import ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "llm_cache"
MIN_INTERVAL_S = 2.5          # ~24 requests/min, under typical free-tier limits
JSON_RULE = "\nRespond with ONE valid JSON object only. No prose, no markdown fences."


class ReplayMiss(Exception):
    """Replay mode and this prompt is not in the cache."""


class LLMError(Exception):
    pass


def models() -> dict:
    return yaml.safe_load(open(ROOT / "configs" / "models.yaml"))


def _extract_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if not m:
            raise
        return json.loads(m.group(0))


class LLM:
    def __init__(self, client=None, mode=None, clock=None):
        self.mode = mode or os.environ.get("LLM_MODE", "live")   # live | replay
        self._client = client
        self.clock = clock
        self._last = 0.0
        self.stats = {"cache_hit": 0, "api_call": 0}

    @property
    def client(self):
        if self._client is None:
            from groq import Groq
            self._client = Groq(api_key=os.environ["GROQ_API_KEY"])
        return self._client

    @staticmethod
    def _key(model, system, user, temperature):
        raw = json.dumps([model, system, user, temperature], ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()

    def _throttle(self):
        wait = MIN_INTERVAL_S - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=2, max=20), reraise=True)
    def _api(self, model, system, user, temperature):
        self._throttle()
        extra = {"reasoning_effort": "low"} if "gpt-oss" in model else {}
        resp = self.client.chat.completions.create(
            model=model, temperature=temperature, max_completion_tokens=1500,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            **extra,
        )
        self.stats["api_call"] += 1
        return resp.choices[0].message.content or ""

    def call_json(self, role, system, user, schema, as_of=None, temperature=0.0):
        """role = 'fast' | 'strong' (see configs/models.yaml). Returns a validated schema object."""
        if as_of is not None and self.clock is not None:
            self.clock.check_text(system + "\n" + user, as_of)   # raises LeakageError
        model = models()[role]
        system = system + JSON_RULE
        last_err = None
        for attempt in range(2):
            u = user if attempt == 0 else (
                user + "\n\nYour previous reply was invalid. Return ONLY the JSON object.")
            f = CACHE / f"{self._key(model, system, u, temperature)}.json"
            if f.exists():
                text = json.loads(f.read_text())["text"]
                self.stats["cache_hit"] += 1
            elif self.mode == "replay":
                raise ReplayMiss(f"{role}: prompt not in cache")
            else:
                text = self._api(model, system, u, temperature)
            try:
                out = schema.model_validate(_extract_json(text))
            except (ValueError, ValidationError) as e:
                last_err = e
                continue
            CACHE.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps({"model": model, "text": text}, ensure_ascii=False))
            return out
        raise LLMError(f"{role}: invalid output after retry: {last_err}")
