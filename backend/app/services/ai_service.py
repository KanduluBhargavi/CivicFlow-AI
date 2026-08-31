from langdetect import detect
from deep_translator import GoogleTranslator
import joblib
from pathlib import Path
import re
from collections import Counter

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

