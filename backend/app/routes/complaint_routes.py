from app.utils.workflow_status import complaint_display_status
from app.utils.complaint_titles import title_needs_shortening, short_operational_title
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from fastapi import UploadFile, File, Form
from datetime import datetime, timezone
import os
import shutil
import uuid
import logging
import hashlib
import threading
import time
import pandas as pd
import requests
import json
from pathlib import Path

logger = logging.getLogger("civicflow.translation")



def _print_translation_provider(field_name, language, result):
    """Developer-only terminal trace; never exposed to frontend users."""
    result = result or {}
    print(
        f"[TRANSLATION] {field_name} | language={language} | "
        f"provider={result.get('provider') or 'none'} | "
        f"method={result.get('method') or 'unknown'} | "
        f"success={bool(result.get('success'))}",
        flush=True,
    )


from app.utils.auth import get_current_user
from app.utils.media import signed_media_url
from app.models.user import User
from app.database import SessionLocal
from app.models.complaint import Complaint
from app.models.complaint_assignment import ComplaintAssignment
from app.models.complaint_event import ComplaintEvent
from app.models.complaint_support import ComplaintSupport
from app.models.department import Department
from app.models.in_app_notification import InAppNotification
from app.services.in_app_notifications import create_notification
from app.models.translation_feedback import TranslationFeedback

from app.services.notification_service import send_email
from app.services.priority_engine import refresh_cluster, refresh_priorities, priority_breakdown, initial_state as priority_initial_state
from app.services.sla_service import set_resolution_target, assignment_deadline
from app.services.incident_service import assign_cluster_for_new_complaint, cluster_members, incident_people_count, incident_impact, impact_from_counts

from app.services.ai_service import (
    detect_language, translate_text, predict_priority_details, predict_department_details,
    summarize_complaint, get_department_id, suggest_reroute_department,
    get_language_name, find_duplicate, analyze_sentiment
)
UPLOAD_FOLDER = "uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

router=APIRouter()

def get_db():
    db=SessionLocal()
    try:
        yield db
    finally:
        db.close()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
COORDINATE_CSV = os.path.join(BASE_DIR, "dataset", "district_coordinates.csv")
COORDINATE_CACHE_FILE = Path(BASE_DIR) / "dataset" / "district_coordinate_cache.json"
ADDRESS_GEOCODE_CACHE_FILE = Path(BASE_DIR) / "dataset" / "address_geocode_cache.json"
_ADDRESS_GEOCODE_LOCK = threading.Lock()
_LAST_ADDRESS_GEOCODE_AT = 0.0


def _address_geocode_cache():
    try:
        if ADDRESS_GEOCODE_CACHE_FILE.exists():
            data = json.loads(ADDRESS_GEOCODE_CACHE_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning("Unable to read address geocode cache: %s", exc)
    return {}


def _save_address_geocode_cache(cache):
    try:
        ADDRESS_GEOCODE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = ADDRESS_GEOCODE_CACHE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(ADDRESS_GEOCODE_CACHE_FILE)
    except Exception as exc:
        logger.warning("Unable to save address geocode cache: %s", exc)



coordinates_df = pd.read_csv(COORDINATE_CSV)

# Normalize the static file once at import time instead of on every complaint.
coordinates_df["state_clean"] = (
    coordinates_df["state"].astype(str).str.strip().str.lower()
)
coordinates_df["district_clean"] = (
    coordinates_df["district"].astype(str).str.strip().str.lower()
)


def _coordinate_cache():
    try:
        if COORDINATE_CACHE_FILE.exists():
            data = json.loads(COORDINATE_CACHE_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning("Unable to read district coordinate cache: %s", exc)
    return {}


def _save_coordinate_cache(cache):
    try:
        COORDINATE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = COORDINATE_CACHE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(cache, indent=2), encoding="utf-8")
        tmp.replace(COORDINATE_CACHE_FILE)
    except Exception as exc:
        logger.warning("Unable to save district coordinate cache: %s", exc)


def _geocode_district_centroid(state: str, district: str):
    """Resolve an approximate district centre only when static data is absent.

    This is a fallback for map display. It is never treated as the citizen's
    exact GPS position.
    """
    query = f"{district} district, {state}, India"
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": query,
                "format": "jsonv2",
                "limit": 1,
                "countrycodes": "in",
            },
            headers={
                "User-Agent": "CivicFlow-AI/1.0 (district centroid resolver)"
            },
            timeout=5,
        )
        response.raise_for_status()
        results = response.json()
        if not results:
            return None

        lat = float(results[0]["lat"])
        lon = float(results[0]["lon"])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None
        return lat, lon
    except Exception as exc:
        logger.warning(
            "District centroid geocoding failed for %s, %s: %s",
            district,
            state,
            exc,
        )
        return None


def get_coordinates(state: str, district: str):
    """Return (latitude, longitude, source) for a district fallback location.

    Order:
      1. bundled static district coordinate dataset
      2. persistent local cache
      3. one-time OpenStreetMap/Nominatim lookup
      4. unavailable (never fake 0,0 coordinates)
    """
    state_clean = (state or "").strip().lower()
    district_clean = (district or "").strip().lower()

    match = coordinates_df[
        (coordinates_df["state_clean"] == state_clean)
        & (coordinates_df["district_clean"] == district_clean)
    ]

    if not match.empty:
        return (
            float(match.iloc[0]["latitude"]),
            float(match.iloc[0]["longitude"]),
            "district_centroid_static",
        )

    key = f"{state_clean}|{district_clean}"
    cache = _coordinate_cache()

    cached = cache.get(key)
    if isinstance(cached, dict) and "latitude" in cached and "longitude" in cached:
        return (
            float(cached["latitude"]),
            float(cached["longitude"]),
            "district_centroid_cached",
        )

    geocoded = _geocode_district_centroid(state, district)
    if geocoded:
        lat, lon = geocoded
        cache[key] = {
            "state": state,
            "district": district,
            "latitude": lat,
            "longitude": lon,
            "provider": "OpenStreetMap Nominatim",
        }
        _save_coordinate_cache(cache)
        print(
            f"[LOCATION] cached district centroid | {district}, {state} -> {lat}, {lon}",
            flush=True,
        )
        return lat, lon, "district_centroid_geocoded"

    print(
        f"[LOCATION] district centroid unavailable | {district}, {state}",
        flush=True,
    )
    return None, None, "unavailable"




class ResolutionConfirmation(BaseModel):
    confirmed: bool
    note: str | None = None


class TranslationFeedbackCreate(BaseModel):
    issue_type: str = Field(default="translation", max_length=40)
    note: str = Field(min_length=8, max_length=1500)
    suggested_english: str | None = Field(default=None, max_length=10000)

class AddressGeocodeRequest(BaseModel):
    state: str = Field(min_length=2, max_length=100)
    district: str = Field(min_length=2, max_length=100)
    area: str = Field(default="", max_length=200)
    address: str = Field(min_length=3, max_length=500)
    landmark: str = Field(default="", max_length=200)
    pincode: str = Field(default="", max_length=12)


@router.post("/complaints/geocode-address")
def geocode_complaint_address(
    payload: AddressGeocodeRequest,
    current_user: User = Depends(get_current_user),
):
    """Resolve a user-requested address to a candidate point; never silently submit it."""
    parts = [payload.address, payload.area, payload.landmark, payload.district, payload.state, payload.pincode, "India"]
    query = ", ".join(part.strip() for part in parts if part and part.strip())
    normalized = " ".join(query.casefold().split())
    cache_key = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    cache = _address_geocode_cache()
    cached = cache.get(cache_key)
    if isinstance(cached, dict) and cached.get("latitude") is not None and cached.get("longitude") is not None:
        result = dict(cached)
        result["cached"] = True
        return {"success": True, "result": result}

    # Try the original address first; translating a proper place name can change
    # its meaning. Only ask the translation providers if that original query has
    # no match, and keep the original address untouched in the complaint.
    original_location_text = ", ".join(
        part.strip() for part in (payload.address, payload.area, payload.landmark)
        if part and part.strip()
    )
    has_non_latin_letters = any(
        ch.isalpha() and not ("A" <= ch <= "Z" or "a" <= ch <= "z")
        for ch in original_location_text
    )
    # Finally retry using standardized locality identifiers. A misspelled
    # local-script place name must not poison the postal/district lookup.
    locality_parts = ([payload.pincode, payload.district, payload.state, "India"]
                      if payload.pincode else [payload.area, payload.district, payload.state, "India"])
    locality_query = ", ".join(part.strip() for part in locality_parts if part and part.strip())
    global _LAST_ADDRESS_GEOCODE_AT

    def search_nominatim(search_query):
        """Make one rate-limited lookup without holding the lock during translation."""
        global _LAST_ADDRESS_GEOCODE_AT
        with _ADDRESS_GEOCODE_LOCK:
            wait_for = 1.05 - (time.monotonic() - _LAST_ADDRESS_GEOCODE_AT)
            if wait_for > 0:
                time.sleep(wait_for)
            response = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": search_query, "format": "jsonv2", "addressdetails": 1,
                        "limit": 1, "countrycodes": "in"},
                headers={"User-Agent": "CivicFlow-AI/1.0 (address geocoding for citizen-submitted complaints)",
                         "Accept-Language": "en"},
                timeout=8,
            )
            _LAST_ADDRESS_GEOCODE_AT = time.monotonic()
        response.raise_for_status()
        return response.json()

    results = []
    match_source = "original"
    provider_error = None
    try:
        results = search_nominatim(query)
    except requests.RequestException as exc:
        provider_error = exc
        logger.warning("Original address geocoding failed (%s).", type(exc).__name__)

    # A typo in the free-text street/address field should not suppress usable
    # locality detail the citizen entered separately. Retry those structured
    # fields before translating the address or falling all the way back to a
    # postcode/district centroid.
    structured_parts = [
        payload.landmark, payload.area, payload.district, payload.state,
        payload.pincode, "India",
    ]
    structured_query = ", ".join(
        part.strip() for part in structured_parts if part and part.strip()
    )
    if not results and payload.area and structured_query.casefold() != query.casefold():
        try:
            results = search_nominatim(structured_query)
            if results:
                match_source = "structured_locality"
        except requests.RequestException as exc:
            provider_error = exc
            logger.warning("Structured locality geocoding failed (%s).", type(exc).__name__)

    if not results and original_location_text and has_non_latin_letters:
        location_language = detect_language(original_location_text)
        location_translation = translate_text(
            original_location_text, location_language, return_status=True
        )
        if location_translation.get("success") and location_translation.get("text"):
            translated_parts = [
                location_translation["text"], payload.district, payload.state,
                payload.pincode, "India",
            ]
            translated_query = ", ".join(
                part.strip() for part in translated_parts if part and part.strip()
            )
            if translated_query.casefold() != query.casefold():
                try:
                    results = search_nominatim(translated_query)
                    if results:
                        match_source = "translated"
                except requests.RequestException as exc:
                    provider_error = exc
                    logger.warning("Translated address geocoding failed (%s).", type(exc).__name__)

    if not results and locality_query and locality_query.casefold() != query.casefold():
        try:
            results = search_nominatim(locality_query)
            if results:
                match_source = "locality"
        except requests.RequestException as exc:
            provider_error = exc
            logger.warning("Locality geocoding fallback failed (%s).", type(exc).__name__)

    if not results and provider_error:
        raise HTTPException(status_code=502, detail="Address lookup is temporarily unavailable. You can still submit the complaint without a resolved map point.")

    if not results:
        return {"success": False, "message": "No reliable map match was found. Check the address or use your current location instead."}

    candidate = results[0]
    try:
        lat, lon = float(candidate["lat"]), float(candidate["lon"])
    except (KeyError, TypeError, ValueError):
        return {"success": False, "message": "The map service returned an invalid location. Please try again or use your current location."}
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return {"success": False, "message": "The map service returned an invalid location."}

    address_parts = candidate.get("address") or {}
    result_type = (candidate.get("addresstype") or candidate.get("type") or "unknown").lower()
    precise_types = {"house", "building", "residential", "address", "apartments", "road"}
    locality_types = {"neighbourhood", "suburb", "quarter", "village", "hamlet", "town", "city", "municipality"}
    if result_type in precise_types:
        match_level = "address_or_road"
    elif result_type in locality_types:
        match_level = "locality_approximate"
    else:
        match_level = "area_approximate"
    if match_source != "original":
        match_level = "locality_approximate"

    resolved_state = address_parts.get("state") or ""
    resolved_district = address_parts.get("state_district") or address_parts.get("county") or address_parts.get("district") or ""
    warnings = []
    if match_source == "translated":
        warnings.append("The original-language address had no exact match. This approximate point came from its English translation; verify or move the pin to the incident location.")
    elif match_source == "locality":
        warnings.append("The exact address spelling was not found. This broader locality/pincode match is approximate; verify or move the pin to the incident location.")
    elif match_source == "structured_locality":
        warnings.append("The street/address text did not match, so this point uses your separate locality and landmark fields. It may be approximate; zoom in and move the pin to the incident location.")
    if resolved_state and payload.state.strip().casefold() not in resolved_state.casefold() and resolved_state.casefold() not in payload.state.strip().casefold():
        warnings.append("The result's state name differs from the selected state. Verify it before using this point.")
    if resolved_district and payload.district.strip().casefold() not in resolved_district.casefold() and resolved_district.casefold() not in payload.district.strip().casefold():
        warnings.append("The result's district name differs from the selected district. Verify it before using this point.")

    result = {
        "latitude": lat,
        "longitude": lon,
        "display_name": candidate.get("display_name") or query,
        "match_level": match_level,
        "result_type": result_type,
        "resolved_state": resolved_state,
        "resolved_district": resolved_district,
        "warnings": warnings,
        "provider": "OpenStreetMap Nominatim",
        "cached": False,
    }
    # Cache positive results to avoid repeatedly querying the public geocoder.
    cache[cache_key] = result
    _save_address_geocode_cache(cache)
    return {"success": True, "result": result}


@router.post("/complaints")
def create_complaint(

    background_tasks: BackgroundTasks,

    title: str = Form(""),

    description: str = Form(""),

    language_hint: str = Form("auto"),

    state: str = Form(...),

    district: str = Form(...),

    area: str = Form(...),

    address: str = Form(...),

    landmark: str = Form(""),

    pincode: str = Form(...),

    latitude: float = Form(None),

    longitude: float = Form(None),

    location_source_input: str = Form("unresolved", alias="location_source"),

    file: UploadFile = File(None),

    current_user: User = Depends(get_current_user),

    db: Session = Depends(get_db)

):

    try:
        title = (title or "").strip()
        description = (description or "").strip()
        has_media = bool(file and file.filename)
        if len(title) < 3:
            raise HTTPException(status_code=422, detail="Add a short title or caption of at least 3 characters so the complaint can be routed correctly.")
        if len(title) > 100:
            raise HTTPException(status_code=422, detail="Keep the complaint title within 100 characters and put full details in the description.")
        # A citizen may submit a video-first report with a short caption. The
        # caption is the text used for translation, routing and priority; the
        # video itself is displayed for staff review, not silently AI-decoded.
        if not description and has_media:
            description = title
        if not description:
            raise HTTPException(status_code=422, detail="Describe the issue, or attach media and add a short title/caption.")

        # Retry-safe guard: detect recently submitted identical complaint content
        # BEFORE any expensive translation, model calls or upload processing.
        from datetime import timedelta
        normalized_title = title.strip()
        normalized_description = description.strip()
        recently_saved = db.query(Complaint).filter(
            Complaint.citizen_id == current_user.user_id,
            Complaint.title == normalized_title,
            Complaint.description == normalized_description,
            Complaint.state == state,
            Complaint.district == district,
            Complaint.created_at >= datetime.now(timezone.utc) - timedelta(minutes=2),
        ).order_by(Complaint.complaint_id.desc()).first()
        if recently_saved:
            raise HTTPException(status_code=409, detail=f"This complaint was already submitted recently (#{recently_saved.complaint_id}). Check My Complaints before submitting again.")


        # =========================
        # CLEAN LOCATION DATA
        # =========================

        state = " ".join(state.strip().split()).title()

        district = " ".join(
            district.strip().split()
        ).title()


        # =========================
        # AI PROCESSING
        # =========================

        # Description is the primary language signal because titles are often very
        # short (or typo-heavy) and can confuse statistical language detectors.
        # The optional user hint remains available for script-sharing languages.
        selected_language = None if language_hint in {"", "auto"} else language_hint
        language = detect_language(description, selected_language)
        if language == "unknown":
            language = detect_language(title, selected_language)

        # Translate the description using the detected/selected language and
        # VERIFY that usable English was produced. Never send untranslated Indic
        # text into the English-trained department/priority classifiers.
        description_translation = translate_text(
            description, language, return_status=True
        )
        if not description_translation["success"]:
            translation_failure = (
                "Bodo translation is temporarily unavailable because the Bodo translation pipeline is not configured or could not be reached. "
                "Your complaint was not submitted, and your form is still filled in. Please contact the site administrator or try again shortly."
                if language == "brx"
                else (
                    f"We couldn't translate this {get_language_name(language)} complaint after retrying the available translation services. "
                    "It was not submitted, and your form is still filled in. Please try again shortly."
                )
            )
            raise HTTPException(
                status_code=422,
                detail=translation_failure,
            )
        translated_text = description_translation["text"]
        _print_translation_provider("description", language, description_translation)

        # Internal diagnostics only — never returned in the citizen/officer UI.
        logger.info(
            "[TRANSLATION] description | language=%s | provider=%s | method=%s",
            language,
            description_translation.get("provider") or "none",
            description_translation.get("method") or "unknown",
        )

        # Keep short Latin-script titles as entered; otherwise translate them too.
        title_language = detect_language(title, selected_language)
        title_translation = translate_text(
            title, title_language, return_status=True
        )
        translated_title_candidate = title_translation["text"] if title_translation["success"] else ""
        needs_shortening = title_needs_shortening(title) or title_needs_shortening(translated_title_candidate)
        _print_translation_provider("title", title_language, title_translation)

        logger.info(
            "[TRANSLATION] title | language=%s | provider=%s | method=%s",
            title_language,
            title_translation.get("provider") or "none",
            title_translation.get("method") or "fallback-original",
        )

        def _translate_operational_field(value, field_name):
            """Translate free-text operational fields without blocking submission.

            Original citizen text remains stored. If translation fails, the original
            value is kept as a temporary fallback and can be retried lazily later.
            """
            raw = (value or "").strip()
            if not raw:
                return None

            field_language = detect_language(raw, selected_language)
            if field_language in {"en", "english"}:
                return raw

            result = translate_text(raw, field_language, return_status=True)
            _print_translation_provider(field_name, field_language, result)

            if result.get("success") and result.get("text"):
                return result["text"].strip()
            return None

        translated_area = _translate_operational_field(area, "area")
        translated_address = _translate_operational_field(address, "address")
        translated_landmark = (
            _translate_operational_field(landmark, "landmark")
            if landmark else None
        )

        # The verified description is the source of truth. Long sentence-like
        # titles may contain contradictory wording/negation, so exclude them
        # from ML input and replace only the operational display title below.
        ml_text = (
            translated_text.strip()
            if needs_shortening
            else f"{translated_text}. {translated_title_candidate}".strip(" .")
        )

        department_result = predict_department_details(ml_text)
        predicted_department = department_result["department"]
        translated_title = None if not title_translation["success"] else (
            short_operational_title(predicted_department, translated_text)
            if translated_text and needs_shortening else translated_title_candidate
        )

        department_id = get_department_id(predicted_department, db)
        if department_id is None:
            raise HTTPException(
                status_code=409,
                detail=f"The {predicted_department} department is not configured or active. Please contact the site administrator.",
            )

        priority_result = predict_priority_details(ml_text, predicted_department)
        priority = priority_result["priority"]

        summary = summarize_complaint(translated_text)

        # =========================
        # SENTIMENT ANALYSIS
        # =========================
        # Detect visible frustration as a separate citizen-experience signal.
        # Sentiment does not automatically increase operational priority.

        sentiment_result = analyze_sentiment(ml_text)


        # =========================
        # LOCATION + GEO-AWARE DUPLICATE DETECTION
        # =========================
        # Browser GPS is trusted for proximity scoring. District-centroid
        # fallback coordinates are retained for map display but are NOT
        # treated as exact complaint locations.

        if latitude is not None and longitude is not None:
            final_latitude, final_longitude = latitude, longitude
            requested_source = (location_source_input or "unresolved").strip().lower()
            allowed_sources = {"gps", "user_confirmed_map_pin", "osm_address_or_road", "osm_locality_approximate", "osm_area_approximate"}
            location_source = requested_source if requested_source in allowed_sources else "gps"
        else:
            final_latitude, final_longitude, location_source = get_coordinates(
                state,
                district,
            )

        open_complaints = (
            db.query(Complaint)
            .filter(
                Complaint.department_id == department_id,
                Complaint.district == district,
                Complaint.status != "Resolved"
            )
            .all()
        )

        duplicate_candidates = [
            {
                "complaint_id": c.complaint_id,
                "text": c.translated_text or c.description,
                "area": c.area,
                "pincode": c.pincode,
                "landmark": c.landmark,
                "latitude": c.latitude,
                "longitude": c.longitude,
                "location_source": c.location_source,
                "created_at": c.created_at,
            }
            for c in open_complaints
        ]

        duplicate_result = find_duplicate(
            translated_text,
            duplicate_candidates,
            {
                "area": area,
                "pincode": pincode,
                "landmark": landmark,
                "latitude": final_latitude,
                "longitude": final_longitude,
                "location_source": location_source,
            }
        )

        # Only HIGH-confidence matches are auto-grouped. Possible matches
        # are stored for officer review but remain independent complaints.
        final_duplicate_of_id = duplicate_result["duplicate_of"]
        if final_duplicate_of_id:
            matched_complaint = next(
                (c for c in open_complaints if c.complaint_id == final_duplicate_of_id),
                None
            )
            if matched_complaint and matched_complaint.duplicate_of_id:
                final_duplicate_of_id = matched_complaint.duplicate_of_id


        # =========================
        # FILE UPLOAD
        # =========================

        media_path = None

        if file and file.filename:

            allowed_extensions = [".jpg", ".jpeg", ".png", ".mp4", ".mov", ".avi"]
            allowed_content_types = {
                "image/jpeg", "image/png",
                "video/mp4", "video/quicktime", "video/x-msvideo"
            }
            max_upload_bytes = 50 * 1024 * 1024

            extension = os.path.splitext(file.filename)[1].lower()

            if extension not in allowed_extensions or file.content_type not in allowed_content_types:
                raise HTTPException(
                    status_code=400,
                    detail="Only JPG, PNG, MP4, MOV and AVI files are allowed."
                )

            # Read a bounded payload so oversized uploads are rejected before
            # writing arbitrary data to disk.
            upload_bytes = file.file.read(max_upload_bytes + 1)
            if len(upload_bytes) > max_upload_bytes:
                raise HTTPException(
                    status_code=413,
                    detail="Upload is too large. Maximum allowed size is 50 MB."
                )

            if extension in {".jpg", ".jpeg", ".png"}:
                # File extension/MIME alone can be spoofed. Verify actual image
                # format and size before saving to the uploads directory.
                from PIL import Image, UnidentifiedImageError
                from io import BytesIO
                try:
                    with Image.open(BytesIO(upload_bytes)) as img:
                        if img.format not in {"JPEG", "PNG"} or img.width * img.height > 24_000_000:
                            raise ValueError("Unsupported image or excessive dimensions")
                        img.verify()
                except (UnidentifiedImageError, ValueError, OSError):
                    raise HTTPException(status_code=400, detail="Invalid photo. Upload a genuine JPG/PNG image of the reported issue, up to 24 megapixels.")
            elif extension in {".mp4", ".mov"} and not (len(upload_bytes) > 12 and b"ftyp" in upload_bytes[4:32]):
                raise HTTPException(status_code=400, detail="This does not appear to be a valid MP4/MOV video. Choose a playable video file.")
            elif extension == ".avi" and not (len(upload_bytes) > 12 and upload_bytes[:4] == b"RIFF" and upload_bytes[8:12] == b"AVI "):
                raise HTTPException(status_code=400, detail="This does not appear to be a valid AVI video. Choose a playable video file.")

            unique_filename = (

                f"{uuid.uuid4()}{extension}"

            )


            media_path = os.path.join(

                UPLOAD_FOLDER,

                unique_filename

            )


            with open(media_path, "wb") as buffer:
                buffer.write(upload_bytes)


        # =========================
        # CREATE COMPLAINT
        # =========================

        new_complaint = Complaint(

            citizen_id=current_user.user_id,

            department_id=department_id,

            title=title,

            description=description,

            state=state,

            district=district,

            area=area,

            address=address,

            landmark=landmark,

            pincode=pincode,

            latitude=final_latitude,

            longitude=final_longitude,

            language=language,

            translated_text=translated_text,
            translated_title=translated_title,
            translated_area=translated_area,
            translated_address=translated_address,
            translated_landmark=translated_landmark,

            predicted_department=predicted_department,
            department_confidence=department_result.get("confidence"),

            priority=priority,
            base_priority=priority_result.get("base_priority"),
            priority_factors=priority_initial_state(priority_result),
            priority_confidence=priority_result.get("confidence"),
            priority_reason=(
                "Critical safety override: " + ", ".join(priority_result.get("critical_reasons", []))
                if priority_result.get("critical_override")
                else f"ML severity prediction ({priority_result.get('base_priority')})"
            ),

            ai_summary=summary,

            sentiment=sentiment_result["sentiment"],

            is_duplicate=duplicate_result["is_duplicate"],

            duplicate_of_id=final_duplicate_of_id,
            duplicate_match_id=duplicate_result["match_id"],
            duplicate_confidence=duplicate_result["confidence"],
            duplicate_similarity=duplicate_result["similarity"],
            duplicate_classification=duplicate_result["classification"],
            duplicate_reason=duplicate_result["reason"],
            location_source=location_source,

            media_path=media_path,

            status="Assigned",

            assigned_at=datetime.now(timezone.utc)

        )


        db.add(new_complaint)
        db.flush()

        matched_for_cluster = None
        if duplicate_result.get("is_duplicate") and duplicate_result.get("match_id"):
            matched_for_cluster = next(
                (c for c in open_complaints if c.complaint_id == duplicate_result.get("match_id")),
                None
            )
        assign_cluster_for_new_complaint(db, new_complaint, matched_for_cluster)

        # Dynamic priority: combine the ML result with incident size (a
        # duplicate joins an existing incident), essential service, health
        # risk, etc. Also re-scores the earlier complaints of the incident.
        refresh_cluster(db, new_complaint, commit=False)
        priority = new_complaint.priority
        set_resolution_target(db, new_complaint)
        new_complaint.officer_assignment_due_at = assignment_deadline(
            new_complaint.assigned_at or new_complaint.created_at, priority
        )

        db.add(ComplaintEvent(
            complaint_id=new_complaint.complaint_id,
            event_type="created",
            title="Complaint submitted and assigned",
            detail=f"AI routed this complaint to {predicted_department} with {priority} priority.",
            actor="CivicFlow AI"
        ))
        if duplicate_result["classification"] != "none":
            db.add(ComplaintEvent(
                complaint_id=new_complaint.complaint_id,
                event_type="duplicate_check",
                title=("High-confidence duplicate grouped" if duplicate_result["is_duplicate"] else "Possible duplicate flagged"),
                detail=f"Matched complaint #{duplicate_result['match_id']} at {round(duplicate_result['confidence']*100)}% confidence: {duplicate_result['reason']}",
                actor="CivicFlow AI"
            ))

        db.commit()
        db.refresh(new_complaint)


        # =========================
        # SEND CONFIRMATION EMAIL
        # =========================

        email_message = f"""

        <div style="
            font-family: Arial, sans-serif;
            padding: 20px;
        ">

            <h2 style="color:#2563eb;">
                Complaint Successfully Submitted ✅
            </h2>

            <p>
                Hello <strong>{current_user.full_name}</strong>,
            </p>

            <p>
                Thank you for submitting your complaint through
                <strong>CivicFlow AI</strong>.
            </p>

            <p>
                Your complaint has been successfully registered
                and routed to the appropriate department.
            </p>

            <hr>

            <p>
                <strong>Complaint ID:</strong>
                #{new_complaint.complaint_id}
            </p>

            <p>
                <strong>Complaint Title:</strong>
                {new_complaint.title}
            </p>

            <p>
                <strong>Assigned Department:</strong>
                {predicted_department}
            </p>

            <p>
                <strong>Priority:</strong>
                {priority}
            </p>

            <hr>

            <p>
                📢 We will notify you whenever your complaint
                status changes.
            </p>

            <p>
                You can also log in to CivicFlow AI anytime
                to track your complaint.
            </p>

            <br>

            <p>
                Regards,<br>
                <strong>CivicFlow AI Support Team</strong>
            </p>

        </div>

        """


        background_tasks.add_task(

            send_email,

            current_user.email,

            "CivicFlow AI - Complaint Successfully Submitted",

            email_message

        )


        return {

            "message":
            "Complaint submitted successfully",

            "complaint_id":
            new_complaint.complaint_id,

            "department":
            predicted_department,

            "priority":
            priority,

            "language":
            get_language_name(language),

            "is_duplicate":
            duplicate_result["is_duplicate"],

            "duplicate_of":
            duplicate_result["duplicate_of"]

        }


    except HTTPException:

        raise


    except Exception as e:

        db.rollback()
        logger.exception("Complaint creation error")

        raise HTTPException(
            status_code=500,
            detail="Unable to submit complaint."
        )

@router.get("/my-complaints")
def my_complaints(
    limit: int = 200, offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    

    complaints = (
        db.query(Complaint)
        .filter(Complaint.citizen_id == current_user.user_id)
        .order_by(Complaint.created_at.desc())
        .offset(max(0, offset)).limit(max(1, min(limit, 1000))).all()
    )

    data = []
    complaint_ids = [c.complaint_id for c in complaints]
    assignments = (
        db.query(ComplaintAssignment.complaint_id, ComplaintAssignment.officer_id, ComplaintAssignment.assigned_at, User.full_name)
        .join(User, User.user_id == ComplaintAssignment.officer_id)
        .filter(ComplaintAssignment.complaint_id.in_(complaint_ids))
        .all() if complaint_ids else []
    )
    assignment_map = {row.complaint_id: row for row in assignments}

    for c in complaints:
        assignment = assignment_map.get(c.complaint_id)
        data.append({
            "complaint_id": c.complaint_id,
            "title": c.title,
            "department": c.predicted_department,
            "status": c.status,
            "display_status": complaint_display_status(c.status, assignment is not None),
            "assigned_officer": assignment.full_name if assignment else None,
            "priority": c.priority,
            "created_at": c.created_at,
            "summary": c.ai_summary
        })

    return data

@router.get("/complaints/{complaint_id}")
def complaint_details(
    complaint_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    complaint = (
        db.query(Complaint)
        .filter(
            Complaint.complaint_id == complaint_id,
            Complaint.citizen_id == current_user.user_id
        )
        .first()
    )

    if not complaint:
        return {"message": "Complaint not found"}

    translation_feedback = db.query(TranslationFeedback).filter(
        TranslationFeedback.complaint_id == complaint.complaint_id,
        TranslationFeedback.citizen_id == current_user.user_id,
    ).order_by(TranslationFeedback.created_at.desc()).all()

    members = cluster_members(db, complaint, include_self=True)
    cluster_id = complaint.incident_cluster_id or complaint.complaint_id
    reporter_ids = {m.citizen_id for m in members if m.citizen_id is not None}
    user_supported = db.query(ComplaintSupport).filter(
        ComplaintSupport.incident_cluster_id == cluster_id,
        ComplaintSupport.citizen_id == current_user.user_id
    ).first() is not None
    assignment = (
        db.query(ComplaintAssignment, User)
        .join(User, User.user_id == ComplaintAssignment.officer_id)
        .filter(ComplaintAssignment.complaint_id == complaint.complaint_id)
        .first()
    )
    affected_count = incident_people_count(db, cluster_id)

    return {
    "complaint_id": complaint.complaint_id,
    "title": complaint.title,
    "description": complaint.description,

    # AI Analysis
    "language": get_language_name(complaint.language),
    "translated_text": complaint.translated_text,
    "translation_feedback": [{
        "feedback_id": item.feedback_id,
        "note": item.note,
        "suggested_english": item.suggested_english,
        "status": item.status,
        "review_note": item.review_note,
        "created_at": item.created_at,
    } for item in translation_feedback],
    "department": complaint.predicted_department,
    "priority": complaint.priority,
    "summary": complaint.ai_summary,
    "sentiment": complaint.sentiment,
    "is_duplicate": complaint.is_duplicate,
    "duplicate_of": complaint.duplicate_of_id,
    "incident_cluster_id": cluster_id,
    "incident_report_count": len(members),
    "priority_analysis": priority_breakdown(complaint),
    "incident_affected_count": affected_count,
    "incident_impact": impact_from_counts(len(members), affected_count),
    "incident_user_already_reported": current_user.user_id in reporter_ids,
    "incident_user_supported": user_supported,

    # Complaint Information
    "state": complaint.state,
    "district": complaint.district,
    "area": complaint.area,

    # Status
    "status": complaint.status,
    "display_status": complaint_display_status(complaint.status, assignment is not None),
    "assigned_officer": ({"name": assignment[1].full_name, "email": assignment[1].email} if assignment else None),
    "officer_assigned_at": (assignment[0].assigned_at if assignment else None),

    # Dates
    "created_at": complaint.created_at,
    "assigned_at": complaint.assigned_at,
    "in_progress_at": complaint.in_progress_at,
    "resolved_at": complaint.resolved_at,
    "resolution_proof_path": complaint.resolution_proof_path,
    "resolution_proof_url": signed_media_url(complaint.resolution_proof_path),
    "resolution_note": complaint.resolution_note,
    "citizen_resolution_status": complaint.citizen_resolution_status,
    "resolution_disputes_used": db.query(ComplaintEvent).filter(ComplaintEvent.complaint_id == complaint.complaint_id, ComplaintEvent.event_type == "citizen_reopen").count(),
    "citizen_resolution_note": complaint.citizen_resolution_note,
    "citizen_confirmed_at": complaint.citizen_confirmed_at
}


@router.post("/complaints/{complaint_id}/translation-feedback")
def submit_translation_feedback(
    complaint_id: int,
    payload: TranslationFeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    complaint = db.query(Complaint).filter(
        Complaint.complaint_id == complaint_id,
        Complaint.citizen_id == current_user.user_id,
    ).first()
    if complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found")
    feedback = TranslationFeedback(
        complaint_id=complaint_id,
        citizen_id=current_user.user_id,
        issue_type=payload.issue_type.strip() or "translation",
        note=payload.note.strip(),
        suggested_english=(payload.suggested_english or "").strip() or None,
        status="Open",
    )
    db.add(feedback)
    db.flush()
    assignment = db.query(ComplaintAssignment).filter(ComplaintAssignment.complaint_id == complaint_id).first()
    if assignment:
        create_notification(
            db, notification_type="translation_feedback", title="Citizen reported a translation issue",
            message=f"Review the citizen's translation feedback for complaint #{complaint_id}.",
            complaint_id=complaint_id, recipient_user_id=assignment.officer_id,
            dedupe_key=f"translation-feedback:officer:{assignment.officer_id}:{feedback.feedback_id}",
        )
    if complaint.department_id:
        create_notification(
            db, notification_type="translation_feedback", title="Citizen reported a translation issue",
            message=f"Review the citizen's translation feedback for complaint #{complaint_id}.",
            complaint_id=complaint_id, recipient_department_id=complaint.department_id,
            dedupe_key=f"translation-feedback:department:{complaint.department_id}:{feedback.feedback_id}",
        )
    db.add(ComplaintEvent(
        complaint_id=complaint_id, event_type="translation_feedback",
        title="Citizen reported a translation issue",
        detail="The citizen asked the department to review the English processing translation.",
        actor=current_user.full_name,
    ))
    db.commit()
    return {"message": "Translation feedback sent to the department for review.", "feedback_id": feedback.feedback_id}


@router.get("/community/incidents")
def community_incidents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Active persisted incidents near the citizen, loaded in batches.

    This avoids the old N+1 pattern that issued several SQL queries for every
    incident card on the dashboard.
    """
    active_q = db.query(Complaint.incident_cluster_id, Complaint.complaint_id).filter(
        Complaint.status != "Resolved"
    )
    if current_user.state:
        active_q = active_q.filter(Complaint.state == current_user.state)
    if current_user.district:
        active_q = active_q.filter(Complaint.district == current_user.district)

    active_rows = active_q.all()
    active_cluster_ids = {cluster_id or complaint_id for cluster_id, complaint_id in active_rows}
    if not active_cluster_ids:
        return []

    # One query for every report in all visible incidents.
    reports = (
        db.query(Complaint)
        .filter(Complaint.incident_cluster_id.in_(active_cluster_ids))
        .order_by(Complaint.created_at.asc(), Complaint.complaint_id.asc())
        .all()
    )
    by_cluster = {}
    for complaint in reports:
        cluster_id = complaint.incident_cluster_id or complaint.complaint_id
        by_cluster.setdefault(cluster_id, []).append(complaint)

    # One support query for the whole set, not one per incident.
    support_rows = (
        db.query(ComplaintSupport.incident_cluster_id, ComplaintSupport.citizen_id)
        .filter(ComplaintSupport.incident_cluster_id.in_(active_cluster_ids))
        .all()
    )
    supporters_by_cluster = {}
    for cluster_id, citizen_id in support_rows:
        supporters_by_cluster.setdefault(cluster_id, set()).add(citizen_id)

    result = []
    for cluster_id in active_cluster_ids:
        cluster_reports = by_cluster.get(cluster_id, [])
        if not cluster_reports:
            # Compatibility for a rare singleton legacy row.
            singleton = db.query(Complaint).filter(Complaint.complaint_id == cluster_id).first()
            cluster_reports = [singleton] if singleton else []
        if not cluster_reports:
            continue

        representative = cluster_reports[0]
        reporter_ids = {c.citizen_id for c in cluster_reports if c.citizen_id is not None}
        supporter_ids = supporters_by_cluster.get(cluster_id, set())
        affected_count = len(reporter_ids | supporter_ids)
        unresolved_count = sum(1 for c in cluster_reports if c.status != "Resolved")
        report_count = len(cluster_reports)

        result.append({
            "incident_cluster_id": cluster_id,
            "representative_complaint_id": representative.complaint_id,
            "title": representative.title,
            "department": representative.predicted_department,
            "priority": representative.priority,
            "area": representative.area,
            "district": representative.district,
            "pincode": representative.pincode,
            "report_count": report_count,
            "unresolved_count": unresolved_count,
            "affected_count": affected_count,
            "impact": impact_from_counts(report_count, affected_count),
            "already_reported": current_user.user_id in reporter_ids,
            "supported": current_user.user_id in supporter_ids,
        })

    result.sort(
        key=lambda x: (x["unresolved_count"], x["report_count"], x["affected_count"]),
        reverse=True,
    )
    return result[:20]


@router.get("/incidents/{cluster_id}")
def incident_details(
    cluster_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Citizen-facing incident view built from the persisted incident cluster."""
    reports = (
        db.query(Complaint)
        .filter(Complaint.incident_cluster_id == cluster_id)
        .order_by(Complaint.created_at.asc(), Complaint.complaint_id.asc())
        .all()
    )
    if not reports:
        legacy_report = db.query(Complaint).filter(Complaint.complaint_id == cluster_id).first()
        if legacy_report and not legacy_report.incident_cluster_id:
            reports = [legacy_report]
    if not reports:
        raise HTTPException(status_code=404, detail="Incident not found")

    reporter_ids = {c.citizen_id for c in reports if c.citizen_id is not None}
    # A citizen can always view an incident that includes their own complaint,
    # even if an older cluster's representative report has stale location data.
    representative = reports[0]
    is_reporter = current_user.user_id in reporter_ids
    if not is_reporter and current_user.state and representative.state and current_user.state != representative.state:
        raise HTTPException(status_code=403, detail="Incident is outside your jurisdiction")
    if not is_reporter and current_user.district and representative.district and current_user.district != representative.district:
        raise HTTPException(status_code=403, detail="Incident is outside your district")

    supported = db.query(ComplaintSupport).filter(
        ComplaintSupport.incident_cluster_id == cluster_id,
        ComplaintSupport.citizen_id == current_user.user_id
    ).first() is not None

    status_counts = {}
    for c in reports:
        status_counts[c.status] = status_counts.get(c.status, 0) + 1

    incident_affected = incident_people_count(db, cluster_id)

    # Citizen incident pages must remain usable even when an incident has
    # hundreds of reports. Show a compact recent preview and always include
    # the logged-in citizen's own report if it falls outside that window.
    recent_reports = sorted(
        reports,
        key=lambda c: (c.created_at or datetime.min, c.complaint_id),
        reverse=True
    )[:5]

    mine = next((c for c in reports if c.citizen_id == current_user.user_id), None)
    preview_reports = list(recent_reports)
    if mine and all(c.complaint_id != mine.complaint_id for c in preview_reports):
        preview_reports.append(mine)

    active_count = sum(1 for c in reports if c.status != "Resolved")
    resolved_count = sum(1 for c in reports if c.status == "Resolved")

    return {
        "incident_cluster_id": cluster_id,
        "title": representative.title,
        "department": representative.predicted_department,
        "area": representative.area,
        "district": representative.district,
        "state": representative.state,
        "pincode": representative.pincode,
        "impact": impact_from_counts(len(reports), incident_affected),
        "status_counts": status_counts,
        "total_reports": len(reports),
        "active_reports": active_count,
        "resolved_reports": resolved_count,
        "preview_limit": 5,
        "already_reported": current_user.user_id in reporter_ids,
        "supported": supported or current_user.user_id in reporter_ids,
        "participation_message": "Submitting a complaint automatically counts you as affected; no extra support click is required." if current_user.user_id in reporter_ids else "You may mark yourself affected if this incident impacts you.",
        "reports": [
            {
                "complaint_id": c.complaint_id,
                "title": c.title,
                "priority": c.priority,
                "status": c.status,
                "display_status": complaint_display_status(
                    c.status,
                    db.query(ComplaintAssignment).filter(
                        ComplaintAssignment.complaint_id == c.complaint_id
                    ).first() is not None
                ),
                "created_at": c.created_at,
                "is_mine": c.citizen_id == current_user.user_id,
            }
            for c in preview_reports
        ],
    }


@router.post("/incidents/{cluster_id}/support")
def support_incident(
    cluster_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    reports = db.query(Complaint).filter(Complaint.incident_cluster_id == cluster_id).all()
    if not reports:
        raise HTTPException(status_code=404, detail="Incident not found")

    if any(c.citizen_id == current_user.user_id for c in reports):
        return {
            "message": "Your complaint is already part of this incident.",
            "supported": False,
            "already_reported": True,
            "affected_count": incident_people_count(db, cluster_id),
        }

    existing = db.query(ComplaintSupport).filter(
        ComplaintSupport.incident_cluster_id == cluster_id,
        ComplaintSupport.citizen_id == current_user.user_id,
    ).first()
    if not existing:
        db.add(ComplaintSupport(incident_cluster_id=cluster_id, citizen_id=current_user.user_id))
        db.commit()
        # "I'm affected" raises the affected-people count -> re-score the incident.
        refresh_cluster(db, reports[0])

    return {
        "message": "You are marked as affected by this incident.",
        "supported": True,
        "already_reported": False,
        "affected_count": incident_people_count(db, cluster_id),
    }


@router.post("/complaints/{complaint_id}/resolution-confirmation")
def confirm_resolution(
    complaint_id: int,
    payload: ResolutionConfirmation,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    complaint = db.query(Complaint).filter(
        Complaint.complaint_id == complaint_id,
        Complaint.citizen_id == current_user.user_id
    ).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    if complaint.status != "Resolved":
        raise HTTPException(status_code=400, detail="Only resolved complaints can be confirmed")
    # Count persisted reopen events, surviving application restarts.
    reopen_count = db.query(ComplaintEvent).filter(
        ComplaintEvent.complaint_id == complaint_id,
        ComplaintEvent.event_type == "citizen_reopen"
    ).count()
    if not payload.confirmed and reopen_count >= 3:
        raise HTTPException(status_code=409, detail="Three resolution disputes have already been used. You can accept the resolution or contact an administrator for independent review.")

    from datetime import datetime, timezone
    complaint.citizen_resolution_note = (payload.note or "").strip() or None
    complaint.citizen_confirmed_at = datetime.now(timezone.utc)
    if payload.confirmed:
        complaint.citizen_resolution_status = "Confirmed"
        db.add(ComplaintEvent(
            complaint_id=complaint.complaint_id, event_type="citizen_confirmation",
            title="Citizen confirmed resolution", detail=complaint.citizen_resolution_note or "Citizen confirmed that the issue is resolved.",
            actor=current_user.full_name
        ))
    else:
        complaint.citizen_resolution_status = "Reopened"
        complaint.status = "In Progress"
        complaint.resolved_at = None
        db.add(ComplaintEvent(
            complaint_id=complaint.complaint_id, event_type="citizen_reopen",
            title="Citizen reported issue still exists", detail=complaint.citizen_resolution_note or "Citizen rejected the resolution and the complaint was reopened.",
            actor=current_user.full_name
        ))
    assignment = db.query(ComplaintAssignment).filter(
        ComplaintAssignment.complaint_id == complaint.complaint_id
    ).first()
    event_type = "citizen_confirmation" if payload.confirmed else "citizen_reopen"
    event_title = "Citizen confirmed resolution" if payload.confirmed else "Citizen reopened complaint"
    event_message = (
        f"Citizen confirmed that complaint #{complaint.complaint_id} is resolved."
        if payload.confirmed else
        f"Citizen says complaint #{complaint.complaint_id} is still unresolved. Review the new note and follow up."
    )
    if assignment:
        create_notification(
            db, notification_type=event_type, title=event_title, message=event_message,
            complaint_id=complaint.complaint_id, recipient_user_id=assignment.officer_id,
        )
    if complaint.department_id:
        create_notification(
            db, notification_type=event_type, title=event_title, message=event_message,
            complaint_id=complaint.complaint_id, recipient_department_id=complaint.department_id,
        )
    db.commit()
    if not payload.confirmed:
        refresh_priorities(db, [complaint])   # reopen => failed repair, priority rises
    return {"message": "Resolution confirmation recorded", "status": complaint.status, "citizen_resolution_status": complaint.citizen_resolution_status, "disputes_used": reopen_count + (0 if payload.confirmed else 1), "dispute_limit": 3}

# NOTE: reroute-suggestion + apply-reroute moved to app/routes/department_routes.py
# so they are properly scoped to the logged-in department (see get_current_department).
