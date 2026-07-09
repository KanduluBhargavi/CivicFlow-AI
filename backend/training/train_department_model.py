import pandas as pd
import joblib

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB

df=pd.read_csv("C:/Users/kandu/OneDrive/Desktop/CivicFlow-AI/dataset/department_dataset.csv")

X=df["description"]
y=df['department']

vectorizer=TfidfVectorizer()
X_vectorized=vectorizer.fit_transform(X)

model=MultinomialNB()
model.fit(X_vectorized,y)

joblib.dump(model,"C:/Users/kandu/OneDrive/Desktop/CivicFlow-AI/models/department_model.pkl")
joblib.dump(vectorizer,"C:/Users/kandu/OneDrive/Desktop/CivicFlow-AI/models/vectorizer.pkl")

print("Department Model Trained Successfully!")