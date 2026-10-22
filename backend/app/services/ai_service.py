from langdetect import detect, detect_langs
from deep_translator import MyMemoryTranslator
import requests
import time
import os
import logging
import joblib
from pathlib import Path
import re
from collections import Counter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger("civicflow.translation")

BASE_DIR = Path(__file__).resolve().parents[3]
model= joblib.load(BASE_DIR/ "models" / "department_model.pkl")
vectorizer=joblib.load(BASE_DIR / "models" / "vectorizer.pkl")

priority_model = joblib.load(BASE_DIR/ "models"/ "priority_model.pkl")
priority_vectorizer = joblib.load(BASE_DIR / "models" / "priority_vectorizer.pkl")


_FREE_GOOGLE_CACHE = {}
_FREE_GOOGLE_CACHE_MAX = 1200
_FREE_GOOGLE_FAILURES = 0
_FREE_GOOGLE_CIRCUIT_OPEN_UNTIL = 0.0
_GOOGLE_TRANSLATE_CACHE = {}
_GOOGLE_TRANSLATE_CACHE_MAX = 1200
_GOOGLE_TRANSLATE_FAILURES = 0
_GOOGLE_TRANSLATE_CIRCUIT_OPEN_UNTIL = 0.0
_FREE_GOOGLE_SESSION = requests.Session()
_FREE_GOOGLE_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 CivicFlow-AI/1.0",
    "Accept": "application/json,text/plain,*/*",
})


def google_translate_status():
    api_key_configured = bool((os.getenv("GOOGLE_TRANSLATE_API_KEY") or "").strip())
    return {
        "configured": api_key_configured,
        "api_key_configured": api_key_configured,
        "provider": "Google Cloud Translation API" if api_key_configured else "Google Translate Web (free fallback)",
        "target_language": "en",
        "timeout_seconds": int(os.getenv("FREE_GOOGLE_TRANSLATE_TIMEOUT_SECONDS", "8")),
        "cache_entries": len(_FREE_GOOGLE_CACHE) + len(_GOOGLE_TRANSLATE_CACHE),
        "mode": "cloud-api-with-free-fallback" if api_key_configured else "free-web-with-google-client-fallback",
    }



_BHASHINI_CACHE = {}
_BHASHINI_CACHE_MAX = 500

def bhashini_status():
    url = (os.getenv("BHASHINI_TRANSLATION_URL") or "").strip()
    api_key = (os.getenv("BHASHINI_API_KEY") or "").strip()
    user_id = (os.getenv("BHASHINI_USER_ID") or "").strip()
    pipeline_id = (os.getenv("BHASHINI_PIPELINE_ID") or "").strip()
    return {
        "configured": bool(api_key and user_id and (pipeline_id or url)),
        "endpoint_configured": bool(url),
        "api_key_configured": bool(api_key),
        "user_id_configured": bool(user_id),
        "pipeline_id_configured": bool(pipeline_id),
        "provider": "BHASHINI NMT",
        "target_language": "en",
        "timeout_seconds": int(os.getenv("BHASHINI_TIMEOUT_SECONDS", "10")),
        "cache_entries": len(_BHASHINI_CACHE),
    }

LANGUAGE_NAMES = {
    "en": "English",
    "as": "Assamese",
    "bn": "Bengali",
    "brx": "Bodo",
    "doi": "Dogri",
    "gu": "Gujarati",
    "hi": "Hindi",
    "kn": "Kannada",
    "ks": "Kashmiri",
    "kok": "Konkani",
    "mai": "Maithili",
    "ml": "Malayalam",
    "mni": "Manipuri",
    "mr": "Marathi",
    "ne": "Nepali",
    "or": "Odia",
    "pa": "Punjabi",
    "sa": "Sanskrit",
    "sat": "Santali",
    "sd": "Sindhi",
    "ta": "Tamil",
    "te": "Telugu",
    "ur": "Urdu",
    "af": "Afrikaans",
    "sq": "Albanian",
    "am": "Amharic",
    "ar": "Arabic",
    "hy": "Armenian",
    "az": "Azerbaijani",
    "eu": "Basque",
    "be": "Belarusian",
    "bs": "Bosnian",
    "bg": "Bulgarian",
    "ca": "Catalan",
    "zh-cn": "Chinese (Simplified)",
    "zh-tw": "Chinese (Traditional)",
    "hr": "Croatian",
    "cs": "Czech",
    "da": "Danish",
    "nl": "Dutch",
    "et": "Estonian",
    "fi": "Finnish",
    "fr": "French",
    "gl": "Galician",
    "ka": "Georgian",
    "de": "German",
    "el": "Greek",
    "he": "Hebrew",
    "hu": "Hungarian",
    "is": "Icelandic",
    "id": "Indonesian",
    "ga": "Irish",
    "it": "Italian",
    "ja": "Japanese",
    "kk": "Kazakh",
    "km": "Khmer",
    "ko": "Korean",
    "lo": "Lao",
    "lv": "Latvian",
    "lt": "Lithuanian",
    "mk": "Macedonian",
    "ms": "Malay",
    "mt": "Maltese",
    "mn": "Mongolian",
    "my": "Myanmar (Burmese)",
    "no": "Norwegian",
    "fa": "Persian",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "ru": "Russian",
    "sr": "Serbian",
    "si": "Sinhala",
    "sk": "Slovak",
    "sl": "Slovenian",
    "so": "Somali",
    "es": "Spanish",
    "sw": "Swahili",
    "sv": "Swedish",
    "tl": "Filipino",
    "th": "Thai",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "uz": "Uzbek",
    "vi": "Vietnamese",
    "cy": "Welsh",
    "zu": "Zulu",
    "unknown": "Unknown",
}


LANGUAGE_ALIASES = {
    **{name.lower(): code for code, name in LANGUAGE_NAMES.items()},
    "oriya": "or", "odia": "or",
    "punjabi": "pa", "panjabi": "pa",
    "assamese": "as", "bengali": "bn", "hindi": "hi",
    "marathi": "mr", "telugu": "te", "tamil": "ta",
    "kannada": "kn", "malayalam": "ml", "gujarati": "gu",
    "urdu": "ur", "nepali": "ne", "english": "en",
}

def normalize_language_code(value):
    if not value:
        return "unknown"
    raw = str(value).strip().lower().replace("_", "-")
    if raw in LANGUAGE_NAMES:
        return raw
    if raw in LANGUAGE_ALIASES:
        return LANGUAGE_ALIASES[raw]
    # langdetect / browser locales may include a region (e.g. hi-IN).
    base = raw.split("-")[0]
    if base in LANGUAGE_NAMES:
        return base
    return raw

SUPPORTED_INDIAN_LANGUAGE_CODES = {
    "as", "bn", "brx", "doi", "gu", "hi", "kn", "ks", "kok", "mai",
    "ml", "mni", "mr", "ne", "or", "pa", "sa", "sat", "sd", "ta",
    "te", "ur",
}

# Distinct Unicode scripts can be recognised deterministically. Some scheduled
# languages share a script (especially Devanagari), so those are resolved with
# langdetect when possible and the optional user language hint otherwise.
SCRIPT_RANGES = {
    "or": [(0x0B00, 0x0B7F)],       # Odia
    "te": [(0x0C00, 0x0C7F)],       # Telugu
    "ta": [(0x0B80, 0x0BFF)],       # Tamil
    "kn": [(0x0C80, 0x0CFF)],       # Kannada
    "ml": [(0x0D00, 0x0D7F)],       # Malayalam
    "gu": [(0x0A80, 0x0AFF)],       # Gujarati
    "pa": [(0x0A00, 0x0A7F)],       # Gurmukhi / Punjabi
    "sat": [(0x1C50, 0x1C7F)],      # Ol Chiki / Santali
    "mni": [(0xABC0, 0xABFF)],      # Meetei Mayek / Manipuri
}

DEVANAGARI_RANGE = (0x0900, 0x097F)
BENGALI_ASSAMESE_RANGE = (0x0980, 0x09FF)
ARABIC_RANGES = [(0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF)]


def _ratio_in_ranges(text, ranges):
    letters = [ch for ch in (text or "") if ch.isalpha()]
    if not letters:
        return 0.0
    count = sum(
        1 for ch in letters
        if any(start <= ord(ch) <= end for start, end in ranges)
    )
    return count / len(letters)


def _detect_distinct_script(text):
    for code, ranges in SCRIPT_RANGES.items():
        if _ratio_in_ranges(text, ranges) >= 0.35:
            return code
    return None


def _looks_assamese(text):
    # Assamese has a few commonly used characters that are highly informative
    # when present even though it shares the Bengali Unicode block.
    return any(ch in (text or "") for ch in "ৰৱ")


def detect_language(text, language_hint=None):
    """Detect the complaint language.

    Supports all 22 scheduled Indian languages through a hybrid strategy:
    * an optional user hint (used for script-sharing languages),
    * deterministic Unicode-script recognition for distinct scripts,
    * langdetect for languages it can distinguish,
    * conservative script fallbacks when automatic identification is ambiguous.

    A hint never changes the stored citizen text; it only disambiguates language
    identification. This is particularly useful for Devanagari languages such as
    Hindi, Marathi, Nepali, Sanskrit, Konkani, Dogri, Maithili and Bodo.
    """
    text = (text or "").strip()
    hint = normalize_language_code(language_hint) if language_hint else None

    if not text:
        return hint if hint in LANGUAGE_NAMES and hint != "unknown" else "unknown"

    # Distinct Indic scripts are stronger evidence than a manually selected hint.
    # This prevents selecting "English" for Telugu/Odia/Tamil/etc. from corrupting
    # the processing language and English translation fields.
    script_code = _detect_distinct_script(text)
    if script_code:
        return script_code

    try:
        candidates = detect_langs(text)
        detected = candidates[0].lang.lower() if candidates else "unknown"
        confidence = float(candidates[0].prob) if candidates else 0.0
    except Exception:
        detected = "unknown"
        confidence = 0.0

    # Afrikaans is not one of the reporting languages offered by CivicFlow and
    # short English civic phrases are often mislabeled as Afrikaans. Keep Auto
    # usable for these Latin-script reports; users can still explicitly choose
    # an available language when writing romanized text.
    if not hint and detected == "af" and _mostly_latin_text(text):
        return "en"

    # Short Latin-script civic text is frequently misidentified as Slovenian,
    # Afrikaans, etc. In Auto mode, use English as the safe processing default
    # when the detector is uncertain. Romanized non-English text should use a
    # language hint because its language cannot be inferred reliably from script.
    if not hint and _mostly_latin_text(text) and confidence < 0.80:
        return "en"

    # Bengali and Assamese share the same script. Prefer Assamese only when
    # characteristic Assamese letters are present; otherwise respect a useful
    # langdetect Bengali result.
    if _ratio_in_ranges(text, [BENGALI_ASSAMESE_RANGE]) >= 0.35:
        if hint in {"as", "bn"}:
            return hint
        if _looks_assamese(text):
            return "as"
        if detected in {"as", "bn"}:
            return detected
        return "bn"

    # Devanagari is shared by several scheduled languages. langdetect can
    # distinguish some of them; for the rest the UI language hint is the
    # reliable route. Without a hint, use the detector rather than pretending
    # certainty from script alone.
    if _ratio_in_ranges(text, [DEVANAGARI_RANGE]) >= 0.35:
        devanagari_codes = {"hi", "mr", "ne", "sa", "kok", "doi", "mai", "brx"}
        if hint in devanagari_codes:
            return hint
        if detected in {"hi", "mr", "ne"}:
            return detected
        return detected if detected != "unknown" else "hi"

    # Urdu, Kashmiri and Sindhi may all use Perso-Arabic script. langdetect
    # commonly identifies Urdu; the optional hint handles the ambiguous cases.
    if _ratio_in_ranges(text, ARABIC_RANGES) >= 0.35:
        if hint in {"ur", "ks", "sd", "ar", "fa"}:
            return hint
        if detected in {"ur", "ar", "fa"}:
            return "ur" if detected == "ur" else detected
        return "ur"

    # For Latin-script or otherwise ambiguous text, a compatible user hint can
    # disambiguate code-mixed/romanized input. Never let it override a distinct script.
    if hint in LANGUAGE_NAMES and hint != "unknown":
        return hint
    return detected


def get_language_name(code):
    """Return a human-readable language name for a stored language code."""
    if not code:
        return "Unknown"
    normalized = normalize_language_code(code)
    return LANGUAGE_NAMES.get(normalized, str(code).upper())


def _mostly_latin_text(text):
    letters = [ch for ch in (text or "") if ch.isalpha()]
    if not letters:
        return True
    latin = sum(1 for ch in letters if ("A" <= ch <= "Z") or ("a" <= ch <= "z"))
    return (latin / len(letters)) >= 0.80


def _usable_english_translation(original, translated):
    """Reject silent translation failures that simply echo Indic text back."""
    if not translated or not str(translated).strip():
        return False
    translated = str(translated).strip()
    if _mostly_latin_text(original):
        return True
    letters = [ch for ch in translated if ch.isalpha()]
    if not letters:
        return False
    latin = sum(1 for ch in letters if ("A" <= ch <= "Z") or ("a" <= ch <= "z"))
    # ML models are English-trained, so translated output must be predominantly Latin.
    return (latin / len(letters)) >= 0.65


def is_usable_english_translation(original, translated):
    """Public validator for stored/returned English processing copies."""
    return _usable_english_translation(original, translated)



def _offline_civic_semantic_translation(text, lang):
    """Last-resort offline semantic interpretation for common civic complaints.

    This is intentionally conservative: it only returns an English processing
    sentence when recognizable civic-domain signals are present. It is NOT
    presented as a literal translation. The original citizen text remains
    preserved in the database/UI.
    """
    raw = str(text or "").strip()
    if not raw:
        return None

    # Common Odia civic-service vocabulary.  The phrases cover the eight
    # departments used by CivicFlow and the most common safety/urgency cues.
    if lang == "or":
        groups = {
            "Water Supply": ["ପାଣି", "ଜଳ", "ପିଇବା ପାଣି", "ପାଇପ", "ପାଇପଲାଇନ", "ଜଳ ଯୋଗାଣ", "ପାଣି ସପ୍ଲାଇ", "ଦୁଷିତ", "ମଲିନ ପାଣି", "ଦୁର୍ଗନ୍ଧ"],
            "Electricity": ["ବିଦ୍ୟୁତ", "କରେଣ୍ଟ", "ଟ୍ରାନ୍ସଫର୍ମର", "ତାର", "ବିଦ୍ୟୁତ ଖୁଟି", "ଲାଇଟ", "ବିଦ୍ୟୁତ ସରବରାହ"],
            "Roads & Transport": ["ରାସ୍ତା", "ସଡ଼କ", "ଗଡ଼ଢା", "ପୋଥୋଲ", "ପୁଲ", "ଟ୍ରାଫିକ", "ବସ"],
            "Sanitation": ["ଆବର୍ଜନା", "କଚରା", "ନାଳା", "ନର୍ଦ୍ଦମା", "ମଳ", "ସଫା", "ସିୱେଜ"],
            "Healthcare": ["ହସ୍ପିଟାଲ", "ଡାକ୍ତର", "ଔଷଧ", "ଚିକିତ୍ସା", "ରୋଗୀ", "ଆମ୍ବୁଲାନ୍ସ", "ଅସୁସ୍ଥ"],
            "Police": ["ପୋଲିସ", "ଚୋରି", "ମାରପିଟ", "ହିଂସା", "ଧମକ", "ଅପରାଧ", "ସୁରକ୍ଷା"],
            "Education": ["ସ୍କୁଲ", "ବିଦ୍ୟାଳୟ", "ଶିକ୍ଷକ", "ଛାତ୍ର", "କଲେଜ", "ଶିକ୍ଷା"],
            "Municipal Corporation": ["ଷ୍ଟ୍ରିଟ ଲାଇଟ", "ରାସ୍ତା ଆଲୋକ", "ପାର୍କ", "ବଜାର", "ନଗର", "ମ୍ୟୁନିସିପାଲ"],
        }
        scores = {dept: sum(1 for kw in kws if kw in raw) for dept, kws in groups.items()}
        dept, score = max(scores.items(), key=lambda kv: kv[1])
        if score <= 0:
            return None

        danger = any(k in raw for k in ["ବିପଦ", "ଜୀବନ", "ଆଗୁନ", "ସ୍ପାର୍କ", "ଖୋଲା ତାର", "ଦୁଷିତ", "ଅସୁସ୍ଥ", "ଜରୁରୀ", "ଶୀଘ୍ର"])
        templates = {
            "Water Supply": "Citizen reports a drinking water or water-supply problem in the local area",
            "Electricity": "Citizen reports an electricity supply or electrical infrastructure problem in the local area",
            "Roads & Transport": "Citizen reports a road, bridge, traffic, or transport-related problem in the local area",
            "Sanitation": "Citizen reports a sanitation, drainage, sewage, or waste-management problem in the local area",
            "Healthcare": "Citizen reports a healthcare or medical-service problem in the local area",
            "Police": "Citizen reports a police, safety, or public-security problem in the local area",
            "Education": "Citizen reports an education or school-related problem in the local area",
            "Municipal Corporation": "Citizen reports a municipal civic-service problem in the local area",
        }
        msg = templates[dept]
        if dept == "Water Supply" and any(k in raw for k in ["ଦୁଷିତ", "ମଲିନ", "ଦୁର୍ଗନ୍ଧ", "ଅସୁସ୍ଥ"]):
            msg = "Citizen reports contaminated or dirty drinking water with a possible health risk in the local area"
        if danger:
            msg += " and requests urgent attention"
        return msg + "."

    return None

def _extract_translation_from_payload(payload):
    """Best-effort extraction across BHASHINI/Udyat response wrappers."""
    if isinstance(payload, str):
        return payload.strip()
    if isinstance(payload, list):
        for item in payload:
            value = _extract_translation_from_payload(item)
            if value:
                return value
        return None
    if isinstance(payload, dict):
        preferred = (
            "translatedText", "translated_text", "translation", "target",
            "targetText", "outputText", "text"
        )
        for key in preferred:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for key in ("output", "outputs", "data", "result", "pipelineResponse"):
            if key in payload:
                value = _extract_translation_from_payload(payload[key])
                if value:
                    return value
    return None


def _free_google_translate(text, source_language=None):
    """Best-effort no-cost Google Translate web fallback.

    This uses Google's public web translation endpoint without an API key. It
    is wrapped with timeout, retry/backoff, cache, validation and a short
    circuit breaker so translation failures do not repeatedly block complaint
    submission.
    """
    global _FREE_GOOGLE_FAILURES, _FREE_GOOGLE_CIRCUIT_OPEN_UNTIL

    original = str(text or "").strip()
    if not original:
        return None

    now = time.time()
    if _FREE_GOOGLE_CIRCUIT_OPEN_UNTIL > now:
        return None

    lang = normalize_language_code(source_language or "auto")
    cache_key = (lang, "en", original)
    cached = _FREE_GOOGLE_CACHE.get(cache_key)
    if cached:
        return cached

    timeout = max(3, int(os.getenv("FREE_GOOGLE_TRANSLATE_TIMEOUT_SECONDS", "8")))
    max_retries = max(0, min(2, int(os.getenv("FREE_GOOGLE_TRANSLATE_MAX_RETRIES", "2"))))
    endpoint = "https://translate.googleapis.com/translate_a/single"
    params = {"client": "gtx", "sl": "auto", "tl": "en", "dt": "t", "q": original}

    for attempt in range(max_retries + 1):
        try:
            response = _FREE_GOOGLE_SESSION.get(endpoint, params=params, timeout=timeout)
            if response.status_code == 200:
                payload = response.json()
                pieces = payload[0] if isinstance(payload, list) and payload else []
                translated = "".join(
                    str(piece[0]) for piece in pieces
                    if isinstance(piece, list) and piece and piece[0]
                ).strip()
                if _usable_english_translation(original, translated):
                    _FREE_GOOGLE_FAILURES = 0
                    _FREE_GOOGLE_CIRCUIT_OPEN_UNTIL = 0.0
                    if len(_FREE_GOOGLE_CACHE) >= _FREE_GOOGLE_CACHE_MAX:
                        _FREE_GOOGLE_CACHE.pop(next(iter(_FREE_GOOGLE_CACHE)))
                    _FREE_GOOGLE_CACHE[cache_key] = translated
                    return translated
                logger.warning("Google web translation returned unusable output (HTTP 200).")
                return None
            if response.status_code not in {429, 500, 502, 503, 504}:
                logger.warning("Google web translation rejected a request (HTTP %s).", response.status_code)
                _FREE_GOOGLE_FAILURES += 1
                break
        except requests.RequestException as exc:
            if attempt >= max_retries:
                logger.warning("Google web translation failed after retries (%s).", type(exc).__name__)
        except Exception as exc:
            logger.warning("Google web translation response could not be read (%s).", type(exc).__name__)
            break

        if attempt < max_retries:
            time.sleep(0.5 * (2 ** attempt))

    logger.warning("Google web translation provider exhausted its configured retries.")
    _FREE_GOOGLE_FAILURES += 1
    if _FREE_GOOGLE_FAILURES >= 3:
        _FREE_GOOGLE_CIRCUIT_OPEN_UNTIL = time.time() + 60
    return None


def _google_cloud_translate(text, source_language=None):
    """Translate text using the official Google Cloud Translation Basic v2 API.

    The API key stays server-side. Source language is intentionally omitted by
    default so Google can auto-detect broadly supported languages and we avoid
    rejecting a complaint merely because CivicFlow's local detector returned a
    language code that Google does not accept.

    Reliability controls:
    - bounded timeout
    - small in-memory cache
    - retry on 429/5xx only
    - short circuit breaker after repeated failures
    - output validation before English text reaches the ML pipeline
    """
    global _GOOGLE_TRANSLATE_FAILURES, _GOOGLE_TRANSLATE_CIRCUIT_OPEN_UNTIL

    api_key = (os.getenv("GOOGLE_TRANSLATE_API_KEY") or "").strip()
    if not api_key:
        return None

    original = str(text or "").strip()
    if not original:
        return None

    now = time.time()
    if _GOOGLE_TRANSLATE_CIRCUIT_OPEN_UNTIL > now:
        return None

    lang = normalize_language_code(source_language or "auto")
    cache_key = (lang, "en", original)
    cached = _GOOGLE_TRANSLATE_CACHE.get(cache_key)
    if cached:
        return cached

    endpoint = "https://translation.googleapis.com/language/translate/v2"
    timeout = max(3, int(os.getenv("GOOGLE_TRANSLATE_TIMEOUT_SECONDS", "10")))
    max_retries = max(0, min(3, int(os.getenv("GOOGLE_TRANSLATE_MAX_RETRIES", "2"))))

    payload = {
        "q": original,
        "target": "en",
        "format": "text",
    }

    # Auto-detection is the safest default for broad language coverage.
    # Optional explicit-source mode can be enabled later if required.
    if (
        os.getenv("GOOGLE_TRANSLATE_USE_EXPLICIT_SOURCE", "false").lower() == "true"
        and lang not in {"", "auto", "unknown", "en"}
    ):
        payload["source"] = lang

    for attempt in range(max_retries + 1):
        try:
            response = requests.post(
                endpoint,
                params={"key": api_key},
                json=payload,
                timeout=timeout,
            )

            if response.status_code == 200:
                body = response.json()
                translations = (
                    body.get("data", {}).get("translations", [])
                    if isinstance(body, dict)
                    else []
                )
                translated = (
                    translations[0].get("translatedText")
                    if translations and isinstance(translations[0], dict)
                    else None
                )

                # Google may HTML-escape some characters in v2 output.
                if translated:
                    import html as html_lib
                    translated = html_lib.unescape(str(translated)).strip()

                if _usable_english_translation(original, translated):
                    _GOOGLE_TRANSLATE_FAILURES = 0
                    _GOOGLE_TRANSLATE_CIRCUIT_OPEN_UNTIL = 0.0

                    if len(_GOOGLE_TRANSLATE_CACHE) >= _GOOGLE_TRANSLATE_CACHE_MAX:
                        _GOOGLE_TRANSLATE_CACHE.pop(next(iter(_GOOGLE_TRANSLATE_CACHE)))
                    _GOOGLE_TRANSLATE_CACHE[cache_key] = translated
                    return translated

                logger.warning("Google Cloud Translation returned unusable output (HTTP 200).")
                return None

            # Retry only temporary provider/rate-limit failures.
            if response.status_code not in {429, 500, 502, 503, 504}:
                logger.warning("Google Cloud Translation rejected a request (HTTP %s).", response.status_code)
                _GOOGLE_TRANSLATE_FAILURES += 1
                break

        except requests.RequestException as exc:
            if attempt >= max_retries:
                logger.warning("Google Cloud Translation failed after retries (%s).", type(exc).__name__)
        except Exception as exc:
            logger.warning("Google Cloud Translation response could not be read (%s).", type(exc).__name__)
            break

        if attempt < max_retries:
            time.sleep(0.5 * (2 ** attempt))

    _GOOGLE_TRANSLATE_FAILURES += 1

    # Avoid repeatedly stalling complaint submissions when Google is unavailable.
    if _GOOGLE_TRANSLATE_FAILURES >= 3:
        _GOOGLE_TRANSLATE_CIRCUIT_OPEN_UNTIL = time.time() + 60

    return None


def _google_html_translate(text, source_language=None):
    """Bounded HTML-client fallback matching the previous GoogleTranslator path."""
    original = str(text or "").strip()
    if not original:
        return None
    lang = normalize_language_code(source_language or "auto")
    cache_key = (lang, "en", original)
    cached = _FREE_GOOGLE_CACHE.get(cache_key)
    if cached:
        return cached

    try:
        from bs4 import BeautifulSoup
        response = _FREE_GOOGLE_SESSION.get(
            "https://translate.google.com/m",
            params={"sl": "auto", "tl": "en", "q": original},
            timeout=max(3, int(os.getenv("GOOGLE_TRANSLATE_WEB_TIMEOUT_SECONDS", "8"))),
        )
        if response.status_code != 200:
            logger.warning("Google HTML translation rejected a request (HTTP %s).", response.status_code)
            return None
        soup = BeautifulSoup(response.text, "html.parser")
        element = soup.select_one(".t0, .result-container")
        translated = element.get_text(strip=True) if element else None
        if not _usable_english_translation(original, translated):
            logger.warning("Google HTML translation returned no usable English result.")
            return None
        translated = str(translated).strip()
        if len(_FREE_GOOGLE_CACHE) >= _FREE_GOOGLE_CACHE_MAX:
            _FREE_GOOGLE_CACHE.pop(next(iter(_FREE_GOOGLE_CACHE)))
        _FREE_GOOGLE_CACHE[cache_key] = translated
        return translated
    except requests.RequestException as exc:
        logger.warning("Google HTML translation failed (%s).", type(exc).__name__)
    except Exception as exc:
        logger.warning("Google HTML translation response could not be read (%s).", type(exc).__name__)
    return None


def _bhashini_translate(text, source_language):
    """Call configured BHASHINI NMT with timeout, cache and safe validation.

    CivicFlow never exposes BHASHINI credentials to the browser. The provider
    is enabled only when the server-side environment contains the approved
    endpoint/API key.
    """
    url = (os.getenv("BHASHINI_TRANSLATION_URL") or "").strip()
    pipeline_id = (os.getenv("BHASHINI_PIPELINE_ID") or "").strip()
    api_key = (os.getenv("BHASHINI_API_KEY") or "").strip()
    user_id = (os.getenv("BHASHINI_USER_ID") or "").strip()
    if not api_key or not user_id or (not pipeline_id and not url):
        return None

    src = normalize_language_code(source_language or "auto")
    cache_key = (src, "en", str(text).strip())
    cached = _BHASHINI_CACHE.get(cache_key)
    if cached:
        return cached

    timeout = int(os.getenv("BHASHINI_TIMEOUT_SECONDS", "10"))
    try:
        headers = {
            "Content-Type": "application/json",
            "ulcaApiKey": api_key,
            "userID": user_id,
        }
        if pipeline_id:
            # Standard ULCA flow: request a translation service for this exact
            # language pair, then call the inference endpoint returned by it.
            config_url = (os.getenv(
                "BHASHINI_CONFIG_URL",
                "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline",
            ) or "").strip()
            config_response = requests.post(
                config_url,
                json={
                    "pipelineId": pipeline_id,
                    "taskType": ["translation"],
                    "config": {"language": {"sourceLanguage": src, "targetLanguage": "en"}},
                },
                headers=headers,
                timeout=timeout,
            )
            if not config_response.ok:
                logger.warning("BHASHINI pipeline config rejected a request (HTTP %s).", config_response.status_code)
                return None
            config_body = config_response.json()
            task_configs = config_body.get("pipelineResponseConfig") or config_body.get("pipelineTasks") or []
            translation_task = next(
                (item for item in task_configs if item.get("taskType") == "translation"),
                None,
            )
            services = (translation_task or {}).get("config") or []
            if isinstance(services, dict):
                services = [services]
            service = next((item for item in services if item.get("serviceId")), None)
            endpoint = config_body.get("pipelineInferenceAPIEndPoint") or {}
            compute_url = url or endpoint.get("callbackUrl") or endpoint.get("callbackURL")
            if not service or not compute_url:
                logger.warning("BHASHINI pipeline config lacks a translation service or compute endpoint.")
                return None
            inference_key = endpoint.get("inferenceApiKey") or {}
            compute_headers = {"Content-Type": "application/json"}
            if inference_key.get("name") and inference_key.get("value"):
                compute_headers[inference_key["name"]] = inference_key["value"]
            else:
                compute_headers.update(headers)
            compute_payload = {
                "pipelineTasks": [{"taskType": "translation", "config": service}],
                "inputData": {"input": [{"source": text}]},
            }
            response = requests.post(compute_url, json=compute_payload, headers=compute_headers, timeout=timeout)
        else:
            # Retain compatibility with deployments using a direct BHASHINI
            # adapter endpoint instead of the standard ULCA pipeline flow.
            response = requests.post(
                url,
                json={"sourceLanguage": src, "targetLanguage": "en", "input": [{"source": text}], "text": text},
                headers=headers,
                timeout=timeout,
            )
        if not response.ok:
            logger.warning("BHASHINI translation rejected a request (HTTP %s).", response.status_code)
            return None
        translated = _extract_translation_from_payload(response.json())
        if not _usable_english_translation(text, translated):
            return None

        translated = str(translated).strip()
        if len(_BHASHINI_CACHE) >= _BHASHINI_CACHE_MAX:
            # Small FIFO-like eviction is sufficient for local/single-node use.
            _BHASHINI_CACHE.pop(next(iter(_BHASHINI_CACHE)))
        _BHASHINI_CACHE[cache_key] = translated
        return translated
    except Exception as exc:
        logger.warning("BHASHINI translation failed (%s).", type(exc).__name__)
        return None


def translate_text(text, source_language=None, return_status=False):
    """Translate citizen text to English safely.

    Use configured Google Cloud credentials first, followed by bounded free
    Google endpoints and configured BHASHINI. Reject output that simply echoes
    Indic text; only a verified English result reaches the classifier.
    """
    if not text or not str(text).strip():
        result = {"text": text, "success": True, "method": "empty"}
        return result if return_status else text

    original = str(text).strip()
    lang = normalize_language_code(source_language or "auto")

    # Genuine English / Latin text does not need translation.
    if lang == "en" and _mostly_latin_text(original):
        result = {"text": original, "success": True, "method": "original_english"}
        return result if return_status else original

    # If metadata says English but the script is Indic, ignore the bad metadata.
    if lang == "en" and not _mostly_latin_text(original):
        detected_actual = detect_language(original)
        lang = detected_actual if detected_actual not in {"unknown", "en"} else "auto"

    # Bodo is absent from Google's published Cloud Translation language list.
    # Route it directly to an explicitly configured BHASHINI pipeline instead
    # of wasting time on Google endpoints that cannot serve this language.
    if lang == "brx":
        bodo_text = _bhashini_translate(original, lang)
        if bodo_text:
            result = {
                "text": bodo_text,
                "success": True,
                "method": "bhashini-udyat",
                "provider": "bhashini",
            }
            return result if return_status else result["text"]
        result = {
            "text": None,
            "success": False,
            "method": "bhashini-unavailable",
            "provider": "bhashini",
            "error_code": "bhashini_not_configured_or_unavailable",
        }
        return result if return_status else None

    # Prefer the official API when the operator configured its server-side key.
    cloud_text = _google_cloud_translate(original, lang)
    if cloud_text:
        result = {"text": cloud_text, "success": True, "method": "google-cloud-v2", "provider": "google-cloud"}
        return result if return_status else result["text"]

    # Provider 1: no-cost Google Translate web endpoint.
    # Auto-detection gives broader language coverage without an API key.
    free_google_text = _free_google_translate(original, lang)
    if free_google_text:
        result = {
            "text": free_google_text,
            "success": True,
            "method": "google-free-web",
            "provider": "google-free-web",
        }
        return result if return_status else result["text"]

    # Provider 2: BHASHINI NMT for Indian languages once approved/configured.
    bhashini_text = _bhashini_translate(original, lang)
    if bhashini_text:
        result = {
            "text": bhashini_text,
            "success": True,
            "method": "bhashini-udyat",
            "provider": "bhashini",
        }
        return result if return_status else result["text"]

    # Provider 3: bounded HTML client matching CivicFlow's earlier Google
    # translation flow. Keep it enabled as recovery when the gtx endpoint is
    # rate-limited; operators may disable it.
    if os.getenv("ENABLE_UNOFFICIAL_TRANSLATION_FALLBACK", "true").lower() == "true":
        translated = _google_html_translate(original, lang)
        if translated:
            result = {
                "text": translated,
                "success": True,
                "method": "google-html-fallback",
                "provider": "google-html-fallback",
            }
            return result if return_status else result["text"]

    # MyMemory is a separate public service. Only send complaint text to it when
    # an operator explicitly enables that additional provider.
    if os.getenv("ENABLE_MYMEMORY_TRANSLATION_FALLBACK", "false").lower() == "true":
        fallback_sources = []
        if lang not in {"", "auto", "unknown", "en"}:
            fallback_sources.append(lang)
            language_name = LANGUAGE_NAMES.get(lang)
            if language_name:
                fallback_sources.append(language_name.lower())
        fallback_sources.append("auto")

        seen_fallback = set()
        for source in fallback_sources:
            if source in seen_fallback:
                continue
            seen_fallback.add(source)
            try:
                translated = MyMemoryTranslator(source=source, target="en").translate(original)
                if _usable_english_translation(original, translated):
                    result = {
                        "text": str(translated).strip(),
                        "success": True,
                        "method": f"mymemory:{source}",
                        "provider": "mymemory",
                    }
                    return result if return_status else result["text"]
            except Exception:
                continue

    # Provider 4: conservative offline civic-domain interpretation.  This keeps
    # a mentor/demo flow functional even when public translation services are
    # rate-limited. It only succeeds for recognizable civic-domain language.
    offline_text = _offline_civic_semantic_translation(original, lang)
    if offline_text and _usable_english_translation(original, offline_text):
        result = {
            "text": offline_text,
            "success": True,
            "method": f"offline-civic:{lang}",
            "provider": "offline-civic",
            "approximate": True,
        }
        return result if return_status else result["text"]

    result = {
        "text": None,
        "success": False,
        "method": "providers_unavailable",
        "provider": None,
    }
    return result if return_status else original


def _probability_payload(classifier, features):
    """Return top prediction and calibrated/native class probabilities when available."""
    prediction = classifier.predict(features)[0]
    probabilities = {}
    confidence = None
    if hasattr(classifier, "predict_proba"):
        probs = classifier.predict_proba(features)[0]
        probabilities = {
            str(label): round(float(prob), 4)
            for label, prob in zip(classifier.classes_, probs)
        }
        confidence = float(max(probs))
    return prediction, confidence, probabilities


DEPARTMENT_GUARD_PATTERNS = {
    "Electricity": [r"\blive wire\b", r"\belectric(?:al)? (?:wire|cable|pole|transformer)\b", r"\bpower transformer\b"],
    "Water Supply": [
        r"\bno water(?: supply)?\b", r"\bwater supply\b", r"\bwater pipeline\b",
        r"\bwater pipe(?: leak| leakage| broken)?\b", r"\bdrinking water\b",
        r"\btap water\b", r"\bwater shortage\b", r"\bwater leak(?:age)?\b",
        r"\bwater (?:is )?(?:dirty|unclean|contaminated|unsafe|not clean)\b",
    ],
    "Roads & Transport": [r"\bpothole\b", r"\broad damage\b", r"\bbroken road\b", r"\btraffic signal\b"],
    "Sanitation": [r"\bgarbage\b", r"\bwaste collection\b", r"\bdumping waste\b", r"\btrash\b"],
    "Police": [r"\btheft\b", r"\brobbery\b", r"\bassault\b", r"\bharassment\b"],
    "Healthcare": [r"\bhospital\b.*\b(?:doctor|medicine|treatment)\b", r"\bhealth centre\b", r"\bambulance\b"],
    "Education": [r"\bteacher shortage\b", r"\bschool teacher\b", r"\bclassroom\b"],
    "Municipal Corporation": [r"\billegal construction\b", r"\bencroachment\b", r"\bproperty tax\b"],
}


def _department_guard(text):
    lowered = (text or "").lower()
    matches = []
    for department, patterns in DEPARTMENT_GUARD_PATTERNS.items():
        if any(re.search(pattern, lowered) for pattern in patterns):
            matches.append(department)
    return matches[0] if len(matches) == 1 else None


def predict_department_details(text):
    text_vector = vectorizer.transform([text])
    prediction, confidence, probabilities = _probability_payload(model, text_vector)
    guard_department = _department_guard(text)
    # Domain guards are deliberately high-precision civic phrases. If exactly one
    # strong domain signal is present, prefer it even when the statistical model is
    # over-confident. This prevents obvious cases such as "drinking water is not
    # clean" being routed to a generic municipal class.
    guard_applied = bool(guard_department and guard_department != prediction)
    final_department = guard_department if guard_applied else prediction
    model_confidence = round(confidence, 4) if confidence is not None else None
    # The classifier's confidence belongs to its own prediction, not to a
    # guard-overridden label. Keep it explicitly named and avoid implying that
    # it is calibrated confidence in the final routed department.
    return {
        "department": final_department,
        "model_department": prediction,
        "confidence": model_confidence if not guard_applied else None,
        "model_confidence": model_confidence,
        "probabilities": probabilities,
        "confidence_scope": "final_department_model_prediction" if not guard_applied else "model_department_only_guard_overrode_final_department",
        "guard_applied": guard_applied,
        "guard_department": guard_department if guard_applied else None,
        "guard_reason": (f"Explicit {guard_department} domain signal overrode the statistical model prediction." if guard_applied else None),
        "needs_human_review": bool((confidence is not None and confidence < 0.55) or guard_applied),
    }


def predict_department(text):
    return predict_department_details(text)["department"]


def _priority_features(text):
    """TF-IDF + hand-built urgency features, identical to the training layout."""
    from scipy import sparse
    from app.services.urgency_features import matrix as urgency_matrix
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    return sparse.hstack([
        priority_vectorizer.transform([clean]),
        sparse.csr_matrix(urgency_matrix([clean])),
    ]).tocsr()


CRITICAL_PATTERNS = {
    "live electrical hazard": [r"\blive wire\b", r"\bfallen (?:electric|electrical|power) (?:wire|cable)\b", r"\belectrocution\b"],
    "fire or explosion": [r"\bmajor fire\b", r"\bexplosion\b", r"\bexploded\b", r"\bgas leak\b"],
    "structural collapse": [r"\bbuilding collapse", r"\bbridge collapse", r"\bcollapsed (?:building|bridge|wall)\b"],
    "immediate life threat": [r"\bperson trapped\b", r"\bpeople trapped\b", r"\bdrowning\b", r"\bunconscious\b", r"\blife[- ]threatening\b"],
    "severe flood emergency": [r"\bflash flood\b", r"\bsevere flooding\b.*\btrapped\b", r"\bflood(?:ing)?\b.*\bevacuate"],
}

VULNERABLE_LOCATION_PATTERNS = [r"\bschool\b", r"\bhospital\b", r"\bclinic\b", r"\bchildren\b", r"\belderly\b"]
HAZARD_PATTERNS = [r"\blive wire\b", r"\bopen manhole\b", r"\btoxic\b", r"\bfire\b", r"\bgas leak\b", r"\bcollapse\b"]


_NEGATION_WORDS = re.compile(
    r"\b(?:no|not|never|without|isn't|aren't|wasn't|weren't|doesn't|didn't|hasn't|haven't|hadn't|cannot|can't|isnt|arent|wasnt|werent)\b",
    re.I,
)
_HISTORICAL_RESOLUTION = re.compile(
    r"\b(?:was|were|has been|had been|already)\s+(?:fully\s+)?(?:extinguished|put out|contained|resolved|repaired|fixed|cleared|removed)\b|"
    r"\b(?:last month|last week|yesterday|previously|earlier today)\b",
    re.I,
)


def _active_pattern_match(text, pattern):
    """Match an active hazard, rejecting nearby negation and resolved history.

    This is intentionally conservative and rule-based; it is not a substitute for
    human review. Negation is checked within the same clause and a short word
    window so unrelated earlier sentences do not cancel a real hazard.
    """
    source = str(text or "")
    for match in re.finditer(pattern, source, re.I):
        start, end = match.span()
        # Some patterns include the verb/adjective after the hazard noun (for
        # example "transformer is not sparking"), so check negation inside the
        # matched phrase as well as immediately before it.
        matched_text = match.group(0)
        if _NEGATION_WORDS.search(matched_text) and not re.search(r"\bnot\s+only\b", matched_text, re.I):
            continue
        # Keep only the current clause before the match (sentence/comma/semicolon
        # boundaries) and the local phrase after it.
        left = re.split(r"[.!?;\n]", source[:start])[-1]
        left_words = re.findall(r"[\w']+", left.lower())
        if left_words and _NEGATION_WORDS.search(" ".join(left_words[-5:])):
            # Avoid false cancellation in constructions like "not only ... but".
            tail = source[end:end + 35]
            if not re.match(r"\s+only\b", tail, re.I):
                continue
        right = re.split(r"[.!?;\n]", source[end:])[0][:100]
        if _HISTORICAL_RESOLUTION.search(right):
            continue
        return True
    return False


def assess_critical_risk(text):
    """Transparent safety override for Critical, excluding clearly negated or resolved hazards."""
    source = str(text or "")
    reasons = []
    for label, patterns in CRITICAL_PATTERNS.items():
        if any(_active_pattern_match(source, pattern) for pattern in patterns):
            reasons.append(label)

    vulnerable = any(_active_pattern_match(source, pattern) for pattern in VULNERABLE_LOCATION_PATTERNS)
    hazard = any(_active_pattern_match(source, pattern) for pattern in HAZARD_PATTERNS)
    if vulnerable and hazard:
        reasons.append("hazard near a vulnerable/critical location")

    # Critical is reserved for active explicit-risk signals, not emotional wording.
    return {"is_critical": bool(reasons), "reasons": sorted(set(reasons))}



HIGH_RISK_PATTERNS = {
    "electrical equipment hazard": [
        r"\btransformer\b.*\b(?:spark|sparking|smoke|burning|fire)\b",
        r"\b(?:spark|sparking|smoke|burning)\b.*\btransformer\b",
        r"\bexposed (?:electric|electrical|power) (?:wire|cable)\b",
        r"\bdamaged electric pole\b",
    ],
    "dangerous road/infrastructure defect": [
        r"\bopen manhole\b", r"\broad cave[- ]?in\b", r"\bsinkhole\b",
        r"\bbridge (?:crack|damage|damaged)\b",
    ],
    "serious sanitation/water hazard": [
        r"\bsewage (?:overflow|overflowing)\b",
        r"\bcontaminated (?:drinking )?water\b",
        r"\bwater main (?:burst|broken)\b",
    ],
}

def assess_high_risk(text):
    """Safety floor for active serious hazards, excluding clear negations/history."""
    source = str(text or "")
    reasons = []
    for label, patterns in HIGH_RISK_PATTERNS.items():
        if any(_active_pattern_match(source, pattern) for pattern in patterns):
            reasons.append(label)
    return {"is_high_risk": bool(reasons), "reasons": sorted(set(reasons))}

def predict_priority_details(text, department=None):
    # ``department`` is accepted for API compatibility; the priority model is
    # trained on complaint text alone (department context did not help).
    text_vector = _priority_features(text)
    base_priority, confidence, probabilities = _probability_payload(priority_model, text_vector)
    critical = assess_critical_risk(text)
    high_risk = assess_high_risk(text)
    if critical["is_critical"]:
        final_priority = "Critical"
    elif high_risk["is_high_risk"] and base_priority in {"Low", "Medium"}:
        final_priority = "High"
    else:
        final_priority = base_priority
    return {
        "priority": final_priority,
        "base_priority": base_priority,
        "confidence": round(confidence, 4) if confidence is not None else None,
        "probabilities": probabilities,
        "critical_override": critical["is_critical"],
        "critical_reasons": critical["reasons"],
        "high_risk_override": bool(high_risk["is_high_risk"] and not critical["is_critical"] and base_priority in {"Low", "Medium"}),
        "high_risk_reasons": high_risk["reasons"],
        "needs_human_review": bool(confidence is not None and confidence < 0.50 and not critical["is_critical"]),
    }


def predict_priority(text, department=None):
    return predict_priority_details(text, department)["priority"]

def summarize_complaint(text):
    """
    General extractive NLP summarization using
    word frequency and sentence scoring.
    """

    if not text or not isinstance(text, str):
        return ""

    # Clean text
    text = re.sub(r'\s+', ' ', text).strip()

    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)

    # Remove empty sentences
    sentences = [sentence.strip() for sentence in sentences if sentence.strip()]

    # For short complaints, return original text
    if len(sentences) <= 2:
        return text

    # Extract words
    words = re.findall(r'\b[a-zA-Z]+\b', text.lower())

    # General English stop words
    stop_words = {
        "a", "an", "the", "and", "or", "but", "if", "because",
        "as", "while", "of", "at", "by", "for", "with", "about",
        "against", "between", "into", "through", "during", "before",
        "after", "above", "below", "to", "from", "up", "down",
        "in", "out", "on", "off", "over", "under", "again",
        "further", "then", "once", "here", "there", "when",
        "where", "why", "how", "all", "any", "both", "each",
        "few", "more", "most", "other", "some", "such", "no",
        "nor", "not", "only", "own", "same", "so", "than",
        "too", "very", "can", "will", "just", "should", "now",
        "is", "am", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did",
        "i", "me", "my", "we", "our", "you", "your",
        "he", "she", "it", "they", "them", "their"
    }

    # Remove stop words
    filtered_words = [
        word for word in words
        if word not in stop_words and len(word) > 2
    ]

    # If no meaningful words exist
    if not filtered_words:
        return sentences[0]

    # Calculate frequency of important words
    word_frequency = Counter(filtered_words)

    # Normalize word frequencies
    max_frequency = max(word_frequency.values())

    for word in word_frequency:
        word_frequency[word] = (
            word_frequency[word] / max_frequency
        )

    sentence_scores = {}

    # Score every sentence
    for index, sentence in enumerate(sentences):

        sentence_words = re.findall(
            r'\b[a-zA-Z]+\b',
            sentence.lower()
        )

        # Only meaningful words
        meaningful_words = [
            word for word in sentence_words
            if word in word_frequency
        ]

        if not meaningful_words:
            sentence_scores[index] = 0
            continue

        # Average importance of words in sentence
        score = sum(
            word_frequency[word]
            for word in meaningful_words
        ) / len(meaningful_words)

        # Slight positional importance
        # Main issue is often introduced early
        position_bonus = 1 - (index / (len(sentences) * 10))

        sentence_scores[index] = score * position_bonus

    # Number of sentences for summary
    summary_length = max(1, min(2, len(sentences) // 2))

    # Select highest scoring sentences
    top_indexes = sorted(
        sentence_scores,
        key=sentence_scores.get,
        reverse=True
    )[:summary_length]

    # Put selected sentences back in original order
    top_indexes.sort()

    summary = " ".join(
        sentences[index]
        for index in top_indexes
    )

    return summary

FRUSTRATION_LEXICON = {
    # strong frustration / neglect indicators
    "nobody came": 3, "no one came": 3, "no one showed up": 3,
    "still not resolved": 3, "not resolved": 2, "again and again": 3,
    "fed up": 3, "sick of": 3, "tired of": 2, "no use": 2,
    "no response": 2, "not responding": 2, "no action": 2,
    "useless": 2, "pathetic": 2, "shameful": 2, "disgraceful": 2,
    "unacceptable": 2, "disappointed": 2, "frustrated": 3,
    "frustrating": 3, "angry": 2, "furious": 3, "ignored": 2,
    "ignoring": 2, "neglected": 2, "worthless": 2, "waste of time": 2,
    "months": 1, "weeks": 1, "several times": 2, "many times": 2,
    "repeatedly": 2, "no help": 2, "not working": 1, "broken promise": 2,
    "still waiting": 2, "no update": 1, "harassment": 2, "disgusted": 2,
}

POSITIVE_LEXICON = {
    "thank you": -2, "thanks": -2, "appreciate": -2, "good job": -2,
    "great work": -2, "resolved quickly": -2, "satisfied": -2, "happy": -1,
}


def analyze_sentiment(text):
    """
    Feature: Sentiment Analysis (frustration detection).

    A lightweight lexicon-based detector that flags complaints written
    with visible frustration/anger - e.g. "We have complained for six
    months but nobody came." - independent of the ML-predicted
    department/priority. This lets a department officer instantly spot
    the most upset citizens, and lets the system slightly increase a
    complaint's priority when real frustration is detected.

    Returns: {
        "sentiment": "Frustrated" | "Negative" | "Neutral" | "Positive",
        "frustration_score": float,   # 0.0 - 1.0
        "priority_boost": bool        # True => bump priority one level
    }
    """

    if not text or not isinstance(text, str):
        return {"sentiment": "Neutral", "frustration_score": 0.0, "priority_boost": False}

    lowered = text.lower()
    score = 0

    for phrase, weight in FRUSTRATION_LEXICON.items():
        if phrase in lowered:
            score += weight

    for phrase, weight in POSITIVE_LEXICON.items():
        if phrase in lowered:
            score += weight  # already negative

    # Repeated exclamation marks / shouted (ALL-CAPS) words add a small nudge
    score += min(text.count("!"), 3)
    shouted_words = re.findall(r"\b[A-Z]{4,}\b", text)
    score += min(len(shouted_words), 2)

    frustration_score = max(0.0, min(1.0, score / 8))

    if score >= 4:
        sentiment = "Frustrated"
    elif score >= 2:
        sentiment = "Negative"
    elif score <= -2:
        sentiment = "Positive"
    else:
        sentiment = "Neutral"

    return {
        "sentiment": sentiment,
        "frustration_score": round(frustration_score, 2),
        "priority_boost": sentiment == "Frustrated"
    }


def apply_sentiment_priority_boost(priority, sentiment_result):
    """
    Nudges the ML-predicted priority one level up when the complaint text
    shows real frustration (see analyze_sentiment), so a citizen who has
    been ignored for months doesn't keep sitting at "Low"/"Medium".
    High priority is left unchanged - it's already the ceiling.
    """
    if not sentiment_result or not sentiment_result.get("priority_boost"):
        return priority

    order = ["Low", "Medium", "High"]

    if priority not in order:
        return priority

    index = order.index(priority)
    return order[min(index + 1, len(order) - 1)]


def get_department_id(department: str, db):
    """Resolve the model's department label against the live department table.

    Department IDs are database-generated and must never be inferred from row
    order. Returning None lets callers stop safely when the matching department
    has not been configured or has been deactivated.
    """
    from sqlalchemy import func
    from app.models.department import Department

    name = (department or "").strip()
    if not name:
        return None
    row = (
        db.query(Department.department_id)
        .filter(
            func.lower(Department.department_name) == name.lower(),
            Department.is_active.is_(True),
        )
        .order_by(Department.department_id)
        .first()
    )
    return row[0] if row else None

def suggest_reroute_department(complaint_text, current_department):
    """
    Suggests a different department if the complaint appears
    to belong to another department.
    """

    predicted_department = predict_department(complaint_text)

    # If AI predicts the same department, no rerouting is required
    if predicted_department.strip().lower() == current_department.strip().lower():
        return {
            "reroute_required": False,
            "suggested_department": current_department,
            "reason": "AI analysis indicates that the complaint belongs to the current department."
        }

    return {
        "reroute_required": True,
        "suggested_department": predicted_department,
        "reason": (
            f"AI analysis suggests that this complaint is more relevant "
            f"to the {predicted_department} department."
        )
    }


DUPLICATE_HIGH_THRESHOLD = 0.68
DUPLICATE_POSSIBLE_THRESHOLD = 0.60


def _norm_place(value):
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def _place_similarity(a, b):
    """Fuzzy locality similarity for harmless spelling variations."""
    from difflib import SequenceMatcher
    a, b = _norm_place(a), _norm_place(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def _canonical_issue_text(text):
    """
    Convert common civic phrasings into a compact issue signature.
    This makes semantically equivalent complaints such as
    'drinking water not clean' / 'dirty drinking water' /
    'contaminated water' compare strongly without requiring an LLM.
    """
    t = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    if not t:
        return ""

    # Water family
    if any(k in t for k in ("water", "drinking water", "water supply", "pipeline")):
        if any(k in t for k in (
            "dirty", "unclean", "not clean", "contaminated", "unsafe", "bad smell",
            "foul smell", "smell", "impure", "polluted", "health risk"
        )):
            return "water drinking quality contaminated dirty unsafe"
        if any(k in t for k in ("no water", "not coming", "no supply", "supply stopped", "shortage")):
            return "water supply outage shortage"
        if any(k in t for k in ("leak", "leakage", "burst", "broken pipe", "pipe burst")):
            return "water pipeline leak burst"
        return "water drinking supply problem"

    # Electricity family
    if any(k in t for k in ("electricity", "power", "transformer", "wire", "cable")):
        if any(k in t for k in ("sparking", "spark", "live wire", "exposed", "shock")):
            return "electricity dangerous exposed wire sparking"
        if any(k in t for k in ("no power", "power cut", "outage", "blackout")):
            return "electricity power outage"
        return "electricity service problem"

    # Road family
    if any(k in t for k in ("road", "pothole", "street", "bridge")):
        if any(k in t for k in ("pothole", "broken", "damaged", "crack")):
            return "road damaged pothole"
        return "road infrastructure problem"

    # Sanitation family
    if any(k in t for k in ("garbage", "waste", "sewage", "drain", "sanitation")):
        if any(k in t for k in ("sewage", "drain", "overflow")):
            return "sanitation sewage drain overflow"
        return "sanitation garbage waste"

    return t


def _haversine_m(lat1, lon1, lat2, lon2):
    """Distance between two GPS points in metres."""
    from math import radians, sin, cos, sqrt, atan2
    try:
        lat1, lon1, lat2, lon2 = map(float, (lat1, lon1, lat2, lon2))
    except (TypeError, ValueError):
        return None
    r = 6371000.0
    p1, p2 = radians(lat1), radians(lat2)
    dp = radians(lat2 - lat1)
    dl = radians(lon2 - lon1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * r * atan2(sqrt(a), sqrt(1 - a))


def _tfidf_pair_score(a, b):
    scores = []
    for kwargs in (
        {"stop_words": "english", "ngram_range": (1, 2)},
        {"analyzer": "char_wb", "ngram_range": (3, 5)},
    ):
        try:
            v = TfidfVectorizer(**kwargs)
            m = v.fit_transform([a, b])
            scores.append(float(cosine_similarity(m[0], m[1])[0][0]))
        except ValueError:
            scores.append(0.0)
    return 0.65 * scores[0] + 0.35 * scores[1]


def _pair_text_similarity(a, b):
    """Hybrid lexical + civic issue-signature similarity."""
    if not a or not b:
        return 0.0
    raw = _tfidf_pair_score(str(a), str(b))
    ca, cb = _canonical_issue_text(a), _canonical_issue_text(b)
    canonical = _tfidf_pair_score(ca, cb) if ca and cb else 0.0
    # Exact canonical issue match is especially meaningful for short reports.
    if ca and ca == cb:
        canonical = 1.0

    # If one report is only a generic wording of the same civic family
    # (for example, "water-supply problem") while another is more
    # specific ("dirty drinking water"), keep a strong floor. This is
    # especially useful for multilingual/offline fallback summaries.
    family_a = ca.split()[0] if ca else ""
    family_b = cb.split()[0] if cb else ""
    generic_a = ca.endswith("problem") if ca else False
    generic_b = cb.endswith("problem") if cb else False
    family_floor = 0.78 if family_a and family_a == family_b and (generic_a or generic_b) else 0.0
    return max(raw, canonical, family_floor)


def _locality_score(new_meta, old_meta):
    score = 0.0
    new_pin, old_pin = _norm_place(new_meta.get("pincode")), _norm_place(old_meta.get("pincode"))
    if new_pin and new_pin == old_pin:
        score += 0.45

    area_sim = _place_similarity(new_meta.get("area"), old_meta.get("area"))
    if area_sim >= 0.82:
        score += 0.40
    elif area_sim >= 0.65:
        score += 0.25

    landmark_sim = _place_similarity(new_meta.get("landmark"), old_meta.get("landmark"))
    if landmark_sim >= 0.82:
        score += 0.15
    return min(score, 1.0)


def _recency_score(created_at):
    if not created_at:
        return 0.5
    from datetime import datetime, timezone
    try:
        now = datetime.now(timezone.utc)
        dt = created_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        hours = max(0.0, (now - dt).total_seconds() / 3600)
    except Exception:
        return 0.5
    if hours <= 24:
        return 1.0
    if hours <= 72:
        return 0.75
    if hours <= 168:
        return 0.45
    return 0.20


from app.services.issue_types import incompatible_issues

def find_duplicate(new_text, candidates, new_meta=None):
    """Geo/locality-aware duplicate detection for civic complaints."""
    if not new_text or not candidates:
        return {"is_duplicate": False, "duplicate_of": None, "match_id": None,
                "similarity": 0.0, "confidence": 0.0, "classification": "none",
                "reason": "No comparable complaints found.", "distance_m": None}

    new_meta = new_meta or {}
    best = None

    for raw in candidates:
        if isinstance(raw, dict):
            cid = raw.get("complaint_id")
            text = raw.get("text")
            old = raw
        else:
            cid, text = raw
            old = {"complaint_id": cid, "text": text}
        if not text or not str(text).strip():
            continue
        if incompatible_issues(new_text, text):
            continue  # same department/location but different underlying problem

        text_score = _pair_text_similarity(new_text, text)
        locality = _locality_score(new_meta, old)
        recency = _recency_score(old.get("created_at"))

        distance = None
        geo_score = None
        trusted_geo = new_meta.get("location_source") == "gps" and old.get("location_source") == "gps"
        if trusted_geo:
            distance = _haversine_m(new_meta.get("latitude"), new_meta.get("longitude"),
                                    old.get("latitude"), old.get("longitude"))
            if distance is not None:
                if distance <= 100: geo_score = 1.0
                elif distance <= 250: geo_score = 0.85
                elif distance <= 500: geo_score = 0.65
                elif distance <= 1000: geo_score = 0.30
                else: geo_score = 0.0

        if geo_score is not None:
            confidence = 0.62 * text_score + 0.23 * geo_score + 0.10 * locality + 0.05 * recency
        else:
            confidence = 0.68 * text_score + 0.22 * locality + 0.10 * recency

        strong_locality = locality >= 0.40
        strong_geo = distance is not None and distance <= 500
        high = confidence >= DUPLICATE_HIGH_THRESHOLD and text_score >= 0.58 and (strong_geo or strong_locality)
        possible = not high and confidence >= DUPLICATE_POSSIBLE_THRESHOLD and text_score >= 0.40 and (strong_geo or strong_locality)
        classification = "high" if high else ("possible" if possible else "none")

        reasons = [f"issue similarity {round(text_score*100)}%"]
        if distance is not None:
            reasons.append(f"{round(distance)} m away")
        if locality >= 0.40:
            reasons.append("same/local matching area")
        reasons.append(f"recency {round(recency*100)}%")

        result = {
            "is_duplicate": high,
            "duplicate_of": cid if high else None,
            "match_id": cid if classification != "none" else None,
            "similarity": round(text_score, 3),
            "confidence": round(confidence, 3),
            "classification": classification,
            "reason": ", ".join(reasons),
            "distance_m": round(distance, 1) if distance is not None else None,
        }
        if best is None or result["confidence"] > best["confidence"]:
            best = result

    return best or {"is_duplicate": False, "duplicate_of": None, "match_id": None,
                    "similarity": 0.0, "confidence": 0.0, "classification": "none",
                    "reason": "No usable complaint text found.", "distance_m": None}
