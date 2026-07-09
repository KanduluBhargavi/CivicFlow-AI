import pandas as pd
import joblib

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB

df=pd.read_csv("C:/Users/kandu/OneDrive/Desktop/CivicFlow-AI/dataset/priority_dataset.csv")

X=df["description"]
y=df["priority"]

vectorizer=TfidfVectorizer()
X_vectorized=vectorizer.fit_transform(X)

model=MultinomialNB()
model.fit(X_vectorized,y)

joblib.dump(model, "C:/Users/kandu/OneDrive/Desktop/CivicFlow-AI/models/priority_model.pkl")
joblib.dump(vectorizer, "C:/Users/kandu/OneDrive/Desktop/CivicFlow-AI/models/priority_vectorizer.pkl")

print("Priority Model Trained Successfully!")

