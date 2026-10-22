"""Semantic (embedding-based) detection of situational signals in a complaint.

Instead of matching fixed keywords, each signal is described by a handful of
*example sentences* (prototypes). The complaint is split into sentences, every
sentence is embedded with the Sentence-BERT model CivicFlow already uses for
duplicate detection, and the signal strength is how close the best sentence is
to the best prototype (cosine similarity, rescaled to 0..1). So "the crack is
spreading across the whole wall" matches *worsening* without containing the word
"worse". If the embedding model is unavailable the engine falls back to the
keyword patterns in ``priority_engine`` so priority never fails.

Tuning knobs (env): SEMANTIC_SIGNAL_LOW (similarity mapped to 0, default 0.35),
SEMANTIC_SIGNAL_HIGH (mapped to 1, default 0.60). Use
``python backend/training/calibrate_semantic_signals.py`` to check them.
"""
from __future__ import annotations

import os
import re

import numpy as np

LOW = float(os.getenv("SEMANTIC_SIGNAL_LOW", "0.35"))
HIGH = float(os.getenv("SEMANTIC_SIGNAL_HIGH", "0.60"))

PROTOTYPES = {
    "worsening": [
        "The problem is getting worse every day.",
        "The damage keeps spreading and is becoming bigger.",
        "The situation is deteriorating rapidly.",
        "The crack has widened a lot since last week.",
        "It was small earlier but now it is much more serious.",
    ],
    "recurring": [
        "This problem keeps happening again and again.",
        "The same issue occurs every single day.",
        "It was fixed before but the issue has come back.",
        "We face this repeatedly every week.",
    ],
    "missed_deadline": [
        "Officials promised to fix it by a certain date but nothing was done.",
        "We were assured it would be resolved soon but no one came.",
        "The deadline given to us has already passed and the work is still pending.",
        "Nobody has visited even though we complained long ago.",
    ],
    "failed_repair": [
        "The temporary repair did not last and it broke again.",
        "They only patched it and it got damaged again after a few days.",
        "The earlier fix failed and the problem returned.",
        "It was repaired but it stopped working again.",
    ],
    "essential": [
        "The hospital does not have electricity or water.",
        "Patients cannot get medicine or treatment.",
        "There is no drinking water supply in our area.",
        "The school building is unsafe for students.",
        "Power supply to essential services has stopped.",
    ],
    "critical_time": [
        "This is happening during the night and people are in the dark.",
        "Students have exams and cannot study without it.",
        "During the heatwave there is no water or electricity.",
        "It is raining heavily and the problem makes things dangerous.",
    ],
    "public_health": [
        "Sewage is overflowing and mixing with drinking water.",
        "The water is contaminated and people are falling sick.",
        "Garbage is rotting and spreading disease and mosquitoes.",
        "There is a risk of an outbreak of infection in the area.",
        "Dirty drain water has a foul smell and is a health hazard.",
    ],
    "infrastructure": [
        "A bridge or building has structural damage and may collapse.",
        "The road has caved in forming a large hole.",
        "A main water pipeline has burst and flooded the street.",
        "An electric pole or transformer has fallen or is badly damaged.",
        "The wall has major cracks and could fall.",
    ],
    "vulnerable": [
        "Small children and elderly people are suffering because of this.",
        "Patients and disabled people cannot manage.",
        "Students and infants are at risk.",
        "Pregnant women and senior citizens are affected.",
    ],
    "danger": [
        "This is an immediate danger to life and needs urgent action.",
        "Someone could get seriously injured or killed.",
        "There is a risk of fire, electric shock or an accident.",
        "It is an emergency that cannot wait.",
    ],
    "wide_scale": [
        "The entire neighbourhood is affected by this problem.",
        "Hundreds of families in the whole village are suffering.",
        "All the houses in our colony have the same issue.",
        "Many residents across several streets are affected.",
    ],
}

_PROTO_EMB = None
_TEXT_CACHE: dict = {}
_TEXT_CACHE_MAX = 3000


def _default_encode(sentences):
    """Encode with the shared SBERT model; returns None if unavailable."""
    try:
        from app.services.incident_service import _get_sbert_model
        model = _get_sbert_model()
        if model is None:
            return None
        return np.asarray(model.encode(list(sentences), convert_to_numpy=True,
                                       normalize_embeddings=True, show_progress_bar=False))
    except Exception:
        return None


def _split(text: str):
    parts = [s.strip() for s in re.split(r"(?<=[.!?\n])\s+", str(text or "")) if len(s.strip()) > 8]
    whole = re.sub(r"\s+", " ", str(text or "")).strip()
    if whole and (len(parts) != 1 or parts[0] != whole):
        parts.append(whole[:400])           # also compare the complaint as a whole
    return parts[:12]


def _rescale(sim: float, low: float, high: float) -> float:
    return float(min(1.0, max(0.0, (sim - low) / max(high - low, 1e-6))))


def signal_strengths(text: str, encode=None, low=None, high=None):
    """Return {signal: strength 0..1} or None when embeddings are unavailable.

    ``encode`` maps a list of sentences to an (n, d) array of unit vectors; it is
    injectable so the logic can be tested without downloading a model.
    """
    global _PROTO_EMB
    low = LOW if low is None else low
    high = HIGH if high is None else high
    use_cache = encode is None
    key = re.sub(r"\s+", " ", str(text or "")).strip().lower()
    if not key:
        return {k: 0.0 for k in PROTOTYPES}
    if use_cache and key in _TEXT_CACHE:
        return _TEXT_CACHE[key]
    enc = encode or _default_encode

    names = list(PROTOTYPES)
    if use_cache:
        if _PROTO_EMB is None:
            flat = [s for n in names for s in PROTOTYPES[n]]
            vecs = enc(flat)
            if vecs is None:
                return None
            _PROTO_EMB, idx = {}, 0
            for n in names:
                k = len(PROTOTYPES[n]); _PROTO_EMB[n] = vecs[idx:idx + k]; idx += k
        proto = _PROTO_EMB
    else:
        flat = [s for n in names for s in PROTOTYPES[n]]
        vecs = enc(flat)
        proto, idx = {}, 0
        for n in names:
            k = len(PROTOTYPES[n]); proto[n] = vecs[idx:idx + k]; idx += k

    sents = _split(text)
    if not sents:
        return {k: 0.0 for k in PROTOTYPES}
    emb = enc(sents)
    if emb is None:
        return None
    result = {n: _rescale(float(np.max(emb @ proto[n].T)), low, high) for n in names}
    if use_cache:
        if len(_TEXT_CACHE) >= _TEXT_CACHE_MAX:
            _TEXT_CACHE.pop(next(iter(_TEXT_CACHE)))
        _TEXT_CACHE[key] = result
    return result
