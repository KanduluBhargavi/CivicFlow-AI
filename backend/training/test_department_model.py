# import joblib

# model=joblib.load("C:/Users/kandu/OneDrive/Desktop/CivicFlow-AI/models/department_model.pkl")
# vectorizer=joblib.load("C:/Users/kandu/OneDrive/Desktop/CivicFlow-AI/models/vectorizer.pkl")

# complaint="Water appears in almost every complaint, so it's not very useful."

# complaint_vector=vectorizer.transform([complaint])

# prediction=model.predict(complaint_vector)

# print("Predicted Department:", prediction[0])

import joblib

# Load trained model
model = joblib.load(
    r"C:\Users\kandu\OneDrive\Desktop\CivicFlow-AI\models\department_model.pkl"
)

vectorizer = joblib.load(
    r"C:\Users\kandu\OneDrive\Desktop\CivicFlow-AI\models\vectorizer.pkl"
)

complaints = [

    

    "Power cut for 6 hours",
    "Frequent voltage fluctuations are damaging household appliances in our neighborhood.",

    "Drainage water overflowing",
"Unknown persons stole the electrical cables supplying power to our village.",
    "Police are not responding to complaints",
    "Rainwater remains stagnant on our street because the stormwater drain has collapsed.",

    "Hospital has no doctors available",
    "We have submitted all documents for the trade licence renewal, but the municipal office has not processed the application even after 45 days."

]

print("=" * 60)
print("Department Prediction Results")
print("=" * 60)

for complaint in complaints:

    complaint_vector = vectorizer.transform([complaint])

    prediction = model.predict(complaint_vector)

    print(f"\nComplaint : {complaint}")
    print(f"Department: {prediction[0]}")