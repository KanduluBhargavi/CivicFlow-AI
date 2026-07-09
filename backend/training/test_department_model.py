import joblib

model=joblib.load("C:/Users/kandu/OneDrive/Desktop/CivicFlow-AI/models/department_model.pkl")
vectorizer=joblib.load("C:/Users/kandu/OneDrive/Desktop/CivicFlow-AI/models/vectorizer.pkl")

complaint="Water appears in almost every complaint, so it's not very useful."

complaint_vector=vectorizer.transform([complaint])

prediction=model.predict(complaint_vector)

print("Predicted Department:", prediction[0])