"""Train the production department-routing model.
Run from anywhere: python backend/training/train_department_model.py
"""
from train_ml_models import train_department

if __name__ == "__main__":
    metrics = train_department()
    print(f"Department accuracy: {metrics['accuracy']:.4f}")
    print(f"Department macro-F1: {metrics['macro_f1']:.4f}")
