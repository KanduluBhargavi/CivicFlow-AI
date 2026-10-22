"""Hand-built urgency signals that complement TF-IDF for priority prediction.

Dependency-free (re + numpy) so the exact same code is used at training time
and at inference time. Changing anything here changes the feature layout, so
bump ``FEATURE_VERSION`` and retrain with ``python backend/training/train_priority_model.py``.
"""
import re
import numpy as np

FEATURE_VERSION = 1
GROUPS = {
 'safety':   r"danger|dangerous|hazard|unsafe|risk|injur|accident|collision|fatal|death|died|electrocut|shock|spark|fire|smoke|burn|explos|gas leak|collapse|cave[- ]?in|sinkhole|open manhole|exposed|live wire|toxic|poison|snake|assault|violence|attack|threat|weapon|knife|harass|stalk|abus|rape|molest|kidnap|robbery|theft|stolen|extort|bully|ragging",
 'health':   r"disease|dengue|malaria|cholera|typhoid|epidemic|outbreak|infection|contaminat|polluted|unsafe water|sewage|stench|rats|mosquito|ambulance|emergency|patient|surgery|medicine|doctor|hospital|clinic|vaccine|oxygen|unhygienic|unclean|dirty water",
 'vulnerable': r"child|children|kid|student|pupil|school|infant|baby|elderly|senior|old age|disab|wheelchair|blind|pregnan|women|woman|girl|patient",
 'outage':   r"no (?:drinking )?water|no electricity|no power|power cut|outage|blackout|not coming|not receiving|not supplied|without (?:water|power|electricity)|supply (?:stopped|disrupted|cut|failure)|shortage|dry taps?|water main|burst|flood|waterlog|overflow|blocked|clogged|stagnant",
 'urgent':   r"urgent|emergency|immediately|asap|at once|critical|serious|severe|severely|life[- ]threatening|right now|please help|dire|extremely|very bad|unbearable|worst",
 'duration': r"for (?:\w+ ){0,2}(?:days|weeks|months|years)|since (?:\w+ ){0,2}(?:days|weeks|months|years|last|yesterday|morning)|several (?:days|weeks|months)|\d+ (?:days|weeks|months|years)|two (?:days|weeks|months)|again and again|repeated|repeatedly|multiple (?:times|complaints|occasions)|despite|no response|not (?:been )?(?:acted|resolved|addressed|responded)|still not|ignored|no action|every (?:day|night|evening|morning)|daily",
 'scale':    r"entire|whole|all (?:the )?(?:residents|houses|areas?|streets?|colony|locality)|many|several|hundreds|multiple|everyone|residents|locality|neighbou?rhood|colony|main road|highway|market|junction|busy|crowd|public",
 'mitigate': r"\b(?:small|minor|slight|slightly|little|tiny|cosmetic|occasionally|sometimes|once|just|only|mild|not urgent|no rush|whenever|bit)\b|certificate|application|reimburse|refund|bill|tax|fee|fees|renewal|permit|licence|license|document|id card|ration card|aadhaar|name change|update(?:d)? my|noise|barking|graffiti|parking|parked|rude|staff behaviou?r|delay(?:ed)?|suggestion|request(?:ing)? (?:for|to)|kindly|replace|replacement|paint|bench|signboard",
 'access':   r"road|bridge|signal|traffic|junction|crossing|footpath|pavement|sidewalk|manhole|drain|pothole|streetlight|street light|pitch black|dark",
}
_RX = {k: re.compile(v, re.I) for k, v in GROUPS.items()}
NAMES = list(GROUPS)+['n_words','exclaim','caps_ratio','urgent_prefix']
def features(text):
    t=str(text or ''); low=t.lower()
    f=[min(len(_RX[k].findall(low)),3)/3.0 for k in GROUPS]
    letters=[c for c in t if c.isalpha()]
    caps=sum(c.isupper() for c in letters)/len(letters) if letters else 0
    f+= [min(len(low.split()),60)/60.0, min(t.count('!'),3)/3.0, caps if caps>0.6 else 0.0,
         1.0 if re.match(r'\s*(urgent|emergency)\b',low) else 0.0]
    return f
def matrix(texts): return np.array([features(t) for t in texts])
