"""Train the production priority/severity model from CivicComp.
Run from anywhere: python backend/training/train_priority_model.py
"""
from train_ml_models import train_priority

if __name__ == "__main__":
    metrics = train_priority()
    print(f"Priority accuracy: {metrics['accuracy']:.4f}")
    print(f"Priority macro-F1: {metrics['macro_f1']:.4f}")
