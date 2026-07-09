from langdetect import detect
from deep_translator import GoogleTranslator
import joblib
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
model= joblib.load(BASE_DIR/ "models" / "department_model.pkl")
vectorizer=joblib.load(BASE_DIR / "models" / "vectorizer.pkl")

priority_model = joblib.load(BASE_DIR/ "models"/ "priority_model.pkl")
priority_vectorizer = joblib.load(BASE_DIR / "models" / "priority_vectorizer.pkl")

def detect_language(text):
    try:
        return detect(text)
    except:
        return "unknown"
    

def translate_text(text):
    try:
        return GoogleTranslator(source='auto',target='en').translate(text)
    except:
       return text

def predict_department(text):
    text_vector = vectorizer.transform([text])
    prediction = model.predict(text_vector)
    return prediction[0]

def predict_priority(text):
    text_vector=priority_vectorizer.transform([text])
    prediction=priority_model.predict(text_vector)
    return prediction[0]

def summarize_complaint(text):
    return text[:100]

def get_department_id(department: str):
    department_map = {
        "Water Supply": 1,
        "Electricity": 2,
        "Roads & Transport": 3,
        "Sanitation": 4,
        "Police": 5,
        "Healthcare": 6,
        "Education": 7,
        "Municipal Corporation": 8
    }

    return department_map.get(department, 8)

