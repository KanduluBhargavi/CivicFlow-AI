"""Safe operational title helpers for complaint displays and ML inputs."""
import re

def title_needs_shortening(value: str) -> bool:
    value = re.sub(r"\s+", " ", (value or "")).strip()
    words = re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*", value)
    return len(value) > 90 or len(words) > 11 or (len(words) > 7 and value.endswith((".", "!", "?")))

def short_operational_title(department: str, translated_description: str) -> str:
    """Return a concise neutral title without changing the stored citizen text."""
    dept = (department or "").strip().lower()
    text = (translated_description or "").lower()
    if "electric" in dept or re.search(r"\b(electricity|power cut|power supply|transformer|live wire)\b", text):
        return "Electricity service complaint"
    if "water" in dept or re.search(r"\b(water supply|drinking water|water pipeline)\b", text):
        return "Water supply complaint"
    if "sanitation" in dept or re.search(r"\b(garbage|waste collection|sewage|drainage|sanitation)\b", text):
        return "Sanitation complaint"
    if "road" in dept or "transport" in dept or re.search(r"\b(pothole|road damage|street damage|traffic)\b", text):
        return "Roads and transport complaint"
    if "health" in dept or "medical" in dept:
        return "Healthcare service complaint"
    if "police" in dept:
        return "Police service complaint"
    if "education" in dept:
        return "Education service complaint"
    if "municipal" in dept:
        return "Municipal service complaint"
    return "Public service complaint"

def display_operational_title(title: str, department: str, translated_description: str) -> str:
    candidate = (title or "").strip()
    if title_needs_shortening(candidate):
        return short_operational_title(department, translated_description)
    return candidate or short_operational_title(department, translated_description)
