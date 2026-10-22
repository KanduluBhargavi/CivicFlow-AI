from collections import defaultdict
from sqlalchemy.orm import Session
from app.models.complaint import Complaint
from app.models.complaint_support import ComplaintSupport
from app.services.ai_service import find_duplicate
from app.services.issue_types import incompatible_issues
from difflib import SequenceMatcher
import re
import os
import threading
from pathlib import Path


def _payload(c):
    return {
        "complaint_id": c.complaint_id,
        "text": c.translated_text or c.description or "",
        "area": c.area,
        "pincode": c.pincode,
        "landmark": c.landmark,
        "latitude": c.latitude,
        "longitude": c.longitude,
        "location_source": c.location_source,
        "created_at": c.created_at,
    }


def pair_match(a, b):
    pa, pb = _payload(a), _payload(b)
    if incompatible_issues(pa["text"], pb["text"]):
        return {"classification": "none", "confidence": 0.0}
    forward = find_duplicate(pa["text"], [pb], pa)
    reverse = find_duplicate(pb["text"], [pa], pb)
    return max((forward, reverse), key=lambda r: r.get("confidence", 0.0))


def assign_cluster_for_new_complaint(db: Session, complaint: Complaint, matched: Complaint | None = None):
    """Assign one persisted cluster id after the complaint has an ID."""
    if matched is not None:
        cluster_id = matched.incident_cluster_id or matched.complaint_id
        if matched.incident_cluster_id != cluster_id:
            matched.incident_cluster_id = cluster_id
        complaint.incident_cluster_id = cluster_id
    else:
        complaint.incident_cluster_id = complaint.complaint_id
    return complaint.incident_cluster_id


def backfill_incident_clusters(db: Session):
    """One-time backfill for legacy complaints.

    This intentionally runs only when complaints without a persisted cluster exist.
    After that, page loads are simple indexed queries instead of rebuilding a graph.
    """
    # Fast path: do not load every complaint on every backend restart once the
    # one-time backfill has already completed.
    missing_cluster = (
        db.query(Complaint.complaint_id)
        .filter(Complaint.incident_cluster_id.is_(None))
        .first()
    )
    if not missing_cluster:
        return False

    all_complaints = db.query(Complaint).order_by(Complaint.complaint_id.asc()).all()

    parent = {c.complaint_id: c.complaint_id for c in all_complaints}
    by_id = {c.complaint_id: c for c in all_complaints}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            root = min(ra, rb)
            other = max(ra, rb)
            parent[other] = root

    # Preserve trusted historic high-confidence links.
    for c in all_complaints:
        if c.duplicate_of_id and c.duplicate_of_id in by_id:
            union(c.complaint_id, c.duplicate_of_id)

    # Build high-confidence edges only within the same department + district.
    groups = defaultdict(list)
    for c in all_complaints:
        groups[(c.department_id, (c.district or "").strip().lower())].append(c)

    for group in groups.values():
        # Small civic datasets can be pairwise backfilled once. For a large DB,
        # avoid startup O(n^2); new complaints are clustered incrementally.
        if len(group) > 500:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                result = pair_match(group[i], group[j])
                if result.get("classification") == "high":
                    union(group[i].complaint_id, group[j].complaint_id)

    members = defaultdict(list)
    for cid in parent:
        members[find(cid)].append(cid)

    for ids in members.values():
        cluster_id = min(ids)
        for cid in ids:
            by_id[cid].incident_cluster_id = cluster_id

    # Any complaint skipped from pairwise work still gets a stable singleton id.
    for c in all_complaints:
        if not c.incident_cluster_id:
            c.incident_cluster_id = c.complaint_id

    db.commit()
    return True


def cluster_members(db: Session, complaint: Complaint, include_self=False):
    cluster_id = complaint.incident_cluster_id or complaint.complaint_id
    q = db.query(Complaint).filter(Complaint.incident_cluster_id == cluster_id)
    if not include_self:
        q = q.filter(Complaint.complaint_id != complaint.complaint_id)
    return q.order_by(Complaint.created_at.asc(), Complaint.complaint_id.asc()).all()


def _reason_text(text):
    """Normalize wording without erasing the actual civic issue.

    Earlier code collapsed phrases such as ``drinking water`` and ``water supply``
    into the same generic token. That made water-quality complaints look similar
    to water-outage complaints. Keep the nouns and problem-state words separate.
    """
    t = re.sub(r"[^a-z0-9\s]", " ", (text or "").lower())
    t = re.sub(r"\s+", " ", t).strip()
    replacements = {
        "not clean": "dirty",
        "unclean": "dirty",
        "contaminated": "dirty",
        "polluted": "dirty",
        "foul smelling": "bad smell",
        "foul smell": "bad smell",
        "no water": "water outage",
        "no supply": "supply outage",
        "not coming": "supply outage",
        "not available": "supply outage",
        "low flow": "low pressure",
        "weak flow": "low pressure",
        "garbage": "waste",
        "rubbish": "waste",
        "trash": "waste",
    }
    for a, b in replacements.items():
        t = t.replace(a, b)
    return t


def related_reason(anchor: Complaint, member: Complaint):
    reasons = []
    a_text = _reason_text(anchor.translated_text or anchor.description)
    b_text = _reason_text(member.translated_text or member.description)
    sim = SequenceMatcher(None, a_text, b_text).ratio() if a_text and b_text else 0.0
    a_tokens, b_tokens = set(a_text.split()), set(b_text.split())
    overlap = len(a_tokens & b_tokens) / max(1, len(a_tokens | b_tokens))
    cheap_similarity = max(sim, overlap)
    if cheap_similarity >= 0.45:
        reasons.append(f"same/similar civic issue ({round(cheap_similarity*100)}% wording overlap)")
    if (anchor.pincode or "").strip() and (anchor.pincode or "").strip() == (member.pincode or "").strip():
        reasons.append(f"same pincode {anchor.pincode}")
    a_area = (anchor.area or "").strip().lower()
    b_area = (member.area or "").strip().lower()
    if a_area and b_area and (a_area == b_area or a_area in b_area or b_area in a_area):
        reasons.append("same locality/area")
    if (anchor.district or "").strip().lower() == (member.district or "").strip().lower():
        reasons.append(f"same district {anchor.district}")
    if not reasons:
        reasons.append("linked through the persisted high-confidence incident cluster")
    return "; ".join(reasons)


def incident_people_count(db: Session, cluster_id: int):
    reporters = {
        row[0] for row in db.query(Complaint.citizen_id)
        .filter(Complaint.incident_cluster_id == cluster_id)
        .distinct().all() if row[0] is not None
    }
    supporters = {
        row[0] for row in db.query(ComplaintSupport.citizen_id)
        .filter(ComplaintSupport.incident_cluster_id == cluster_id)
        .distinct().all() if row[0] is not None
    }
    return len(reporters | supporters)


def impact_from_counts(report_count: int, affected_count: int):
    """Build the community-impact signal from counts already in memory.

    Keeping this separate prevents endpoints that already loaded an incident from
    running the same COUNT/DISTINCT queries again.
    """
    if affected_count >= 10 or report_count >= 8:
        level = "Widespread"
    elif affected_count >= 4 or report_count >= 3:
        level = "Elevated"
    else:
        level = "Local"
    return {
        "level": level,
        "report_count": report_count,
        "affected_count": affected_count,
        "reason": f"{report_count} linked reports and {affected_count} affected citizens",
    }


def incident_impact(db: Session, cluster_id: int):
    """Operational community-impact signal kept separate from ML priority."""
    reports = db.query(Complaint).filter(Complaint.incident_cluster_id == cluster_id).count()
    affected = incident_people_count(db, cluster_id)
    return impact_from_counts(reports, affected)



# ---------------------------------------------------------------------------
# Sentence-BERT semantic similarity
# ---------------------------------------------------------------------------
_SBERT_MODEL = None
_SBERT_MODEL_LOCK = threading.Lock()
_SBERT_MODEL_NAME = os.getenv(
    "SBERT_MODEL_NAME",
    "sentence-transformers/all-MiniLM-L6-v2"
)
_SBERT_SIMILARITY_THRESHOLD = float(
    os.getenv("SBERT_SIMILARITY_THRESHOLD", "0.64")
)

# Permanent local copy after the first successful Hugging Face download.
# Future backend starts load from this folder and do not download again.
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_SBERT_LOCAL_DIR = Path(
    os.getenv(
        "SBERT_LOCAL_DIR",
        str(_BACKEND_ROOT / ".model_cache" / "all-MiniLM-L6-v2"),
    )
)

# Per-process embedding cache: complaint text -> normalized vector.
# This prevents repeated encoding when officers open the same complaints.
_SBERT_EMBEDDING_CACHE = {}
_SBERT_EMBEDDING_CACHE_MAX = int(
    os.getenv("SBERT_EMBEDDING_CACHE_MAX", "2000")
)


def _get_sbert_model():
    """Load Sentence-BERT once and reuse it.

    First run:
      Hugging Face model -> download -> save into backend/.model_cache/

    Later runs:
      backend/.model_cache/ -> local load only (no repeated model download)
    """
    global _SBERT_MODEL

    if _SBERT_MODEL is not None:
        return _SBERT_MODEL

    # Startup warming and a concurrent first request must not load/download
    # duplicate copies of the model.
    with _SBERT_MODEL_LOCK:
        if _SBERT_MODEL is not None:
            return _SBERT_MODEL
        try:
            from sentence_transformers import SentenceTransformer

            local_modules = _SBERT_LOCAL_DIR / "modules.json"
            if local_modules.exists():
                print(f"[SBERT] loading cached local model: {_SBERT_LOCAL_DIR}", flush=True)
                _SBERT_MODEL = SentenceTransformer(str(_SBERT_LOCAL_DIR), local_files_only=True)
                print("[SBERT] semantic model ready (local cache)", flush=True)
                return _SBERT_MODEL

            print(
                f"[SBERT] first-time setup: downloading {_SBERT_MODEL_NAME}. "
                "This happens once; CivicFlow will save a local copy afterwards.",
                flush=True,
            )
            _SBERT_MODEL = SentenceTransformer(_SBERT_MODEL_NAME)
            _SBERT_LOCAL_DIR.parent.mkdir(parents=True, exist_ok=True)
            _SBERT_MODEL.save(str(_SBERT_LOCAL_DIR))
            print(f"[SBERT] semantic model ready and saved locally: {_SBERT_LOCAL_DIR}", flush=True)
            return _SBERT_MODEL
        except Exception as exc:
            print(
                f"[SBERT] semantic similarity unavailable | "
                f"model={_SBERT_MODEL_NAME} | error={exc}",
                flush=True,
            )
            return None


def _normalized_text(text):
    return " ".join((text or "").split()).strip()


def _embedding_for_text(text):
    """Return cached normalized SBERT embedding for one complaint text."""
    cleaned = _normalized_text(text)
    if not cleaned:
        return None

    cached = _SBERT_EMBEDDING_CACHE.get(cleaned)
    if cached is not None:
        return cached

    model = _get_sbert_model()
    if model is None:
        return None

    try:
        embedding = model.encode(
            cleaned,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
    except Exception as exc:
        print(f"[SBERT] embedding failed | error={exc}", flush=True)
        return None

    if len(_SBERT_EMBEDDING_CACHE) >= _SBERT_EMBEDDING_CACHE_MAX:
        # Simple bounded FIFO-like eviction is enough for the current project size.
        _SBERT_EMBEDDING_CACHE.pop(next(iter(_SBERT_EMBEDDING_CACHE)))

    _SBERT_EMBEDDING_CACHE[cleaned] = embedding
    return embedding


def _semantic_issue_score(a, b):
    """Symmetric Sentence-BERT cosine similarity between two complaint texts."""
    a_embedding = _embedding_for_text(a)
    b_embedding = _embedding_for_text(b)
    if a_embedding is None or b_embedding is None:
        return 0.0

    try:
        score = float(a_embedding @ b_embedding)
        return max(-1.0, min(1.0, score))
    except Exception:
        return 0.0



_GENERIC_CIVIC_WORDS = {
    # Department / service nouns are too generic to be useful as explanations.
    "water","road","roads","electricity","power","garbage","waste","trash",
    "drain","drainage","sewer","streetlight","streetlights","light","lights",
    "complaint","issue","problem","area","locality","department","service",
}

_EXPLAIN_STOPWORDS = {
    "a","an","the","is","are","was","were","be","been","being","to","of","in","on",
    "at","for","from","with","and","or","but","our","my","your","their","this","that",
    "these","those","it","there","here","very","properly","please","kindly","near",
    "since","days","day","people","residents","citizens","we","i","has","have","had",
}


def _evidence_units(text: str):
    """Split a complaint into short evidence units for explanation.

    The SBERT match decision remains complaint-level. These units are used only
    to show officers *which exact statements* made the two complaints look alike.
    """
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return []

    # Split on sentence boundaries and common clause separators so explanations
    # can point to the actual reported condition rather than the whole paragraph.
    parts = re.split(
        r"(?<=[.!?])\s+|[;:\n]+|\s+(?:but|while|whereas|however)\s+",
        cleaned,
        flags=re.IGNORECASE,
    )

    units = []
    for part in parts:
        part = part.strip(" ,.-")
        if len(part) < 8:
            continue
        if len(part) > 180:
            # Keep explanations concise.
            part = part[:177].rstrip() + "..."
        units.append(part)

    return units[:12] or [cleaned[:180]]


def _specific_shared_terms(a_text: str, b_text: str):
    """Return non-generic exact terms shared by both complaints.

    This is explanation-only metadata. It does not affect similarity scoring.
    """
    def terms(text):
        normalized = re.sub(r"[^a-z0-9\s]", " ", (text or "").lower())
        tokens = [
            t for t in normalized.split()
            if len(t) > 2
            and t not in _EXPLAIN_STOPWORDS
            and t not in _GENERIC_CIVIC_WORDS
        ]
        return tokens

    a_terms = terms(a_text)
    b_set = set(terms(b_text))

    result = []
    seen = set()
    for term in a_terms:
        if term in b_set and term not in seen:
            seen.add(term)
            result.append(term)
        if len(result) >= 5:
            break

    return result


def _best_semantic_evidence_pair(a_text: str, b_text: str):
    """Find the most semantically aligned clauses using the same SBERT model."""
    model = _get_sbert_model()
    if model is None:
        return None

    a_units = _evidence_units(a_text)
    b_units = _evidence_units(b_text)
    if not a_units or not b_units:
        return None

    try:
        a_embeddings = model.encode(
            a_units,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        b_embeddings = model.encode(
            b_units,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        matrix = a_embeddings @ b_embeddings.T
        best_flat = int(matrix.argmax())
        row, col = divmod(best_flat, matrix.shape[1])
        return {
            "anchor_evidence": a_units[row],
            "candidate_evidence": b_units[col],
            "evidence_similarity": float(matrix[row, col]),
        }
    except Exception as exc:
        print(f"[SBERT] explanation evidence failed | error={exc}", flush=True)
        return None


def semantic_match_explanation(anchor: Complaint, candidate: Complaint, score: float):
    """Explain a direct SBERT match with concrete evidence from both complaints.

    The complaint-level Sentence-BERT score decides the match.
    This function does not use hand-written civic issue rules and does not alter
    the score. It simply identifies the closest pair of reported statements so
    the officer can understand the connection.
    """
    a_text = (anchor.translated_text or anchor.description or "").strip()
    b_text = (candidate.translated_text or candidate.description or "").strip()
    pct = round(float(score) * 100)

    evidence = _best_semantic_evidence_pair(a_text, b_text)
    specific_terms = _specific_shared_terms(a_text, b_text)

    if evidence:
        a_quote = evidence["anchor_evidence"]
        b_quote = evidence["candidate_evidence"]
        evidence_pct = round(evidence["evidence_similarity"] * 100)

        explanation = (
            f"Why this matches: the closest reported details are "
            f'“{a_quote}” and “{b_quote}”. '
            f"Those two statements express a very similar condition "
            f"({evidence_pct}% evidence similarity). "
        )

        if specific_terms:
            explanation += (
                "Specific shared details: "
                + ", ".join(f'"{term}"' for term in specific_terms[:4])
                + ". "
            )

        explanation += f"Overall complaint similarity: {pct}%."
        return explanation

    # Fallback when the explanation pass cannot run. Avoid generic service words.
    if specific_terms:
        return (
            "Why this matches: both complaints share specific details such as "
            + ", ".join(f'"{term}"' for term in specific_terms[:4])
            + f". Overall semantic similarity: {pct}%."
        )

    return (
        f"Why this matches: Sentence-BERT found the complete complaint meanings "
        f"to be closely aligned ({pct}% similarity), but no reliable short "
        f"evidence phrase could be extracted."
    )

def semantic_similar_complaints(
    db: Session,
    complaint: Complaint,
    threshold: float | None = None,
    limit: int = 50,
):
    """Return direct semantic matches efficiently.

    Performance rules:
    - anchor embedding is cached;
    - all uncached candidate texts are encoded in ONE batch;
    - encoded vectors are stored in the in-memory cache;
    - cosine scores are then cheap dot products.
    """
    threshold = (
        _SBERT_SIMILARITY_THRESHOLD
        if threshold is None
        else float(threshold)
    )

    anchor_text = (
        complaint.translated_text
        or complaint.description
        or ""
    ).strip()
    if not anchor_text:
        return []

    anchor_embedding = _embedding_for_text(anchor_text)
    if anchor_embedding is None:
        return []

    candidates = (
        db.query(Complaint)
        .filter(
            Complaint.department_id == complaint.department_id,
            Complaint.complaint_id != complaint.complaint_id,
        )
        .order_by(Complaint.created_at.desc())
        .limit(500)
        .all()
    )

    rows = []
    uncached_texts = []

    for candidate in candidates:
        text = (
            candidate.translated_text
            or candidate.description
            or ""
        ).strip()
        cleaned = _normalized_text(text)
        if not cleaned:
            continue

        rows.append((candidate, cleaned))

        if cleaned not in _SBERT_EMBEDDING_CACHE:
            uncached_texts.append(cleaned)

    # Encode every previously unseen complaint in one inference batch.
    if uncached_texts:
        model = _get_sbert_model()
        if model is None:
            return []

        # Preserve order while removing duplicates.
        uncached_texts = list(dict.fromkeys(uncached_texts))

        try:
            embeddings = model.encode(
                uncached_texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
                batch_size=32,
            )

            for cleaned, embedding in zip(uncached_texts, embeddings):
                if len(_SBERT_EMBEDDING_CACHE) >= _SBERT_EMBEDDING_CACHE_MAX:
                    _SBERT_EMBEDDING_CACHE.pop(next(iter(_SBERT_EMBEDDING_CACHE)))
                _SBERT_EMBEDDING_CACHE[cleaned] = embedding

        except Exception as exc:
            print(f"[SBERT] candidate batch encoding failed | error={exc}", flush=True)
            return []

    matches = []

    for candidate, cleaned in rows:
        candidate_embedding = _SBERT_EMBEDDING_CACHE.get(cleaned)
        if candidate_embedding is None:
            continue

        score = float(anchor_embedding @ candidate_embedding)
        if score < threshold:
            continue

        matches.append({
            "complaint": candidate,
            "similarity": round(score, 3),
            "method": "sentence-bert-cosine",
            "model": _SBERT_MODEL_NAME,
        })

    matches.sort(
        key=lambda item: (
            -item["similarity"],
            item["complaint"].complaint_id or 0,
        )
    )

    return matches[:limit]

