# import pandas as pd
# import joblib

# from sklearn.feature_extraction.text import TfidfVectorizer
# from sklearn.naive_bayes import MultinomialNB

# df=pd.read_csv("C:/Users/kandu/OneDrive/Desktop/CivicFlow-AI/dataset/department_dataset.csv")

# X=df["description"]
# y=df['department']

# vectorizer=TfidfVectorizer()
# X_vectorized=vectorizer.fit_transform(X)

# model=MultinomialNB()
# model.fit(X_vectorized,y)

# joblib.dump(model,"C:/Users/kandu/OneDrive/Desktop/CivicFlow-AI/models/department_model.pkl")
# joblib.dump(vectorizer,"C:/Users/kandu/OneDrive/Desktop/CivicFlow-AI/models/vectorizer.pkl")

# print("Department Model Trained Successfully!")

import pandas as pd
import joblib
from sklearn.model_selection import cross_val_score
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import confusion_matrix
import seaborn as sns
import matplotlib.pyplot as plt

from sklearn.naive_bayes import MultinomialNB
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.ensemble import RandomForestClassifier

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report
)

# ==========================================================
# LOAD DATASET
# ==========================================================

print("="*60)
print("Loading Dataset...")
print("="*60)

df = pd.read_csv(
    r"C:\Users\kandu\OneDrive\Desktop\CivicFlow-AI\dataset\department_dataset.csv"
)

# ==========================================================
# DATASET INFORMATION
# ==========================================================

print("\nFirst 5 Records\n")
print(df.head())

print("\nDataset Information\n")
print(df.info())

print("\nDataset Shape")
print(df.shape)

print("\nColumn Names")
print(df.columns.tolist())

print("\nMissing Values")
print(df.isnull().sum())

print("\nDuplicate Rows")
print(df.duplicated().sum())

print("\nDepartment Distribution\n")
print(df["department"].value_counts())

# ==========================================================
# REMOVE DUPLICATES
# ==========================================================

df = df.drop_duplicates()

print("\nDataset Shape After Removing Duplicates")
print(df.shape)

# ==========================================================
# FEATURES & LABELS
# ==========================================================

X = df["description"]

y = df["department"]

# ==========================================================
# TRAIN TEST SPLIT
# ==========================================================

X_train, X_test, y_train, y_test = train_test_split(

    X,
    y,

    test_size=0.20,

    random_state=42,

    stratify=y

)

print("\nTraining Samples :", len(X_train))
print("Testing Samples  :", len(X_test))

# ==========================================================
# TF-IDF VECTORIZATION
# ==========================================================

vectorizer = TfidfVectorizer(

    stop_words="english",

    lowercase=True,

    ngram_range=(1,2),
    min_df=2,
    max_df=0.90,
    sublinear_tf=True


)

X_train_vector = vectorizer.fit_transform(X_train)

X_test_vector = vectorizer.transform(X_test)

print("\nTF-IDF Vocabulary Size :", len(vectorizer.vocabulary_))

# ==========================================================
# MODELS
# ==========================================================

models = {

    "Naive Bayes": MultinomialNB(),

    "Logistic Regression": LogisticRegression(

        max_iter=1000,
        C=2,
        solver="lbfgs",
        class_weight="balanced",
        random_state=42

    ),

    "Linear SVM": LinearSVC(

        random_state=42

    ),

    "Random Forest": RandomForestClassifier(

        n_estimators=200,

        random_state=42

    )

}

best_model = None
best_model_name = ""
best_accuracy = 0

results = []

# ==========================================================
# TRAINING
# ==========================================================

print("\n")
print("="*60)
print("TRAINING MODELS")
print("="*60)

for name, model in models.items():

    print("\n")
    print("-"*60)
    print(name)
    print("-"*60)

    model.fit(X_train_vector, y_train)

    predictions = model.predict(X_test_vector)
    train_predictions = model.predict(X_train_vector)
    train_accuracy = accuracy_score(y_train, train_predictions)
    accuracy = accuracy_score(y_test, predictions)
    difference = train_accuracy - accuracy
    

    precision = precision_score(

        y_test,

        predictions,

        average="weighted"

    )

    recall = recall_score(

        y_test,

        predictions,

        average="weighted"

    )

    f1 = f1_score(

        y_test,

        predictions,

        average="weighted"

    )
    
    print(f"Difference        : {difference:.4f}")
    print(f"Training Accuracy : {train_accuracy:.4f}")
    print(f"Accuracy : {accuracy:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall   : {recall:.4f}")
    print(f"F1 Score : {f1:.4f}")

    

    scores = cross_val_score(
    model,
    X_train_vector,
    y_train,
    cv=5,
    scoring="accuracy"
    )

    print(scores)
    print("Average Accuracy:", scores.mean())
    

    print("\nClassification Report\n")

    print(

        classification_report(

            y_test,

            predictions

        )

    )

    results.append({

        "Model": name,

        "Accuracy": accuracy,

        "Precision": precision,

        "Recall": recall,

        "F1 Score": f1

    })

    if accuracy > best_accuracy:

        best_accuracy = accuracy

        best_model = model

        best_model_name = name



cm = confusion_matrix(y_test, predictions)

plt.figure(figsize=(8,6))
sns.heatmap(
    cm,
    annot=True,
    fmt="d",
    xticklabels=model.classes_,
    yticklabels=model.classes_
)
plt.xlabel("Predicted")
plt.ylabel("Actual")
plt.show()

# ==========================================================
# RESULTS
# ==========================================================

print("\n")
print("="*60)
print("MODEL COMPARISON")
print("="*60)

results_df = pd.DataFrame(results)

print(results_df)

# ==========================================================
# SAVE BEST MODEL
# ==========================================================

joblib.dump(

    best_model,

    r"C:\Users\kandu\OneDrive\Desktop\CivicFlow-AI\models\department_model.pkl"

)

joblib.dump(

    vectorizer,

    r"C:\Users\kandu\OneDrive\Desktop\CivicFlow-AI\models\vectorizer.pkl"

)

print("\n")
print("="*60)
print("BEST MODEL")
print("="*60)

print("Model    :", best_model_name)

print("Accuracy :", round(best_accuracy * 100, 2), "%")

print("\nBest model saved successfully!")

print("department_model.pkl")

print("vectorizer.pkl")

print("="*60)