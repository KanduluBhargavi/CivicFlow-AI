"""Conservative issue-specific compatibility gate for duplicate matching."""
import re

def issue_type(text):
    text = (text or "").lower()
    water = bool(re.search(r"\b(water|tap|pipeline|drinking|supply|paani|jal)\b", text))
    if not water:
        return None
    quality = bool(re.search(r"\b(dirty|polluted|contaminat\w*|impur\w*|smell\w*|stink\w*|muddy|yellow|brown|unsafe|foul|quality)\b", text))
    outage = bool(re.search(r"\b(no water|not coming|not available|not getting|no supply|no flow|dry tap|dry taps|supply stopped|water outage|shortage|interruption|low pressure|no pressure|irregular supply)\b", text))
    if quality and not outage: return "water_quality"
    if outage and not quality: return "water_supply"
    return None

def incompatible_issues(a, b):
    x, y = issue_type(a), issue_type(b)
    return bool(x and y and x != y)
