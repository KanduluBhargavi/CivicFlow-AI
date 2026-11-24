from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.metrics import (
    ConfusionMatrixDisplay, accuracy_score, classification_report,
    f1_score, precision_score, recall_score
)
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.multiclass import OneVsRestClassifier
from sklearn.svm import LinearSVC

ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = ROOT / 'dataset'
MODEL_DIR = ROOT / 'models'
REPORT_DIR = MODEL_DIR / 'reports'
MODEL_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)
RANDOM_STATE = 42


def _normalise(text: str) -> str:
    return re.sub(r'\W+', ' ', str(text).lower()).strip()


def _vectorizer(word_features: int, char_features: int):
    return FeatureUnion([
        ('word_tfidf', TfidfVectorizer(
            lowercase=True, stop_words='english', ngram_range=(1, 2), min_df=2,
            max_df=0.98, sublinear_tf=True, max_features=word_features,
            strip_accents='unicode')),
        ('char_tfidf', TfidfVectorizer(
            analyzer='char_wb', ngram_range=(3, 5), min_df=2,
            sublinear_tf=True, max_features=char_features)),
    ])


def _candidates():
    return {
        'ComplementNB': ComplementNB(alpha=0.35),
        'LogisticRegression': LogisticRegression(
            C=3.0, max_iter=1800, solver='lbfgs', class_weight='balanced',
            random_state=RANDOM_STATE),
        'LinearSVC': LinearSVC(
            C=1.2, class_weight='balanced', random_state=RANDOM_STATE),
        'SGDClassifier': SGDClassifier(
            loss='log_loss', alpha=1e-5, max_iter=2500, tol=1e-4,
            class_weight='balanced', random_state=RANDOM_STATE),
    }


def _benchmark(X_train, y_train, word_features, char_features, task_name):
    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=RANDOM_STATE)
    rows = []
    for name, classifier in _candidates().items():
        pipe = Pipeline([
            ('features', _vectorizer(word_features, char_features)),
            ('classifier', classifier),
        ])
        scores = cross_validate(
            pipe, X_train, y_train, cv=cv,
            scoring={'accuracy':'accuracy', 'macro_f1':'f1_macro', 'weighted_f1':'f1_weighted'},
            n_jobs=1, return_train_score=False
        )
        rows.append({
            'model': name,
            'cv_accuracy_mean': float(np.mean(scores['test_accuracy'])),
            'cv_accuracy_std': float(np.std(scores['test_accuracy'])),
            'cv_macro_f1_mean': float(np.mean(scores['test_macro_f1'])),
            'cv_macro_f1_std': float(np.std(scores['test_macro_f1'])),
            'cv_weighted_f1_mean': float(np.mean(scores['test_weighted_f1'])),
        })
    result = pd.DataFrame(rows).sort_values(
        ['cv_macro_f1_mean', 'cv_accuracy_mean'], ascending=False
    ).reset_index(drop=True)
    result.to_csv(REPORT_DIR / f'{task_name}_model_comparison.csv', index=False)
    return result


def _fit_selected(name, X_train, y_train, word_features, char_features):
    vectorizer = _vectorizer(word_features, char_features)
    Xv = vectorizer.fit_transform(X_train)
    base = _candidates()[name]
    # LinearSVC normally has no probabilities. Calibrate only the deployed winner,
    # preserving a strong text classifier while allowing honest confidence scores.
    if name == 'LinearSVC':
        classifier = CalibratedClassifierCV(base, method='sigmoid', cv=3)
    else:
        classifier = base
    classifier.fit(Xv, y_train)
    return vectorizer, classifier, Xv.shape[1]


def _heldout(task_name, model, vectorizer, X_test, y_test, feature_count):
    Xt = vectorizer.transform(X_test)
    pred = model.predict(Xt)
    classes = list(model.classes_)
    metrics = {
        'accuracy': float(accuracy_score(y_test, pred)),
        'macro_f1': float(f1_score(y_test, pred, average='macro')),
        'weighted_f1': float(f1_score(y_test, pred, average='weighted')),
        'macro_precision': float(precision_score(y_test, pred, average='macro', zero_division=0)),
        'macro_recall': float(recall_score(y_test, pred, average='macro', zero_division=0)),
        'classification_report': classification_report(y_test, pred, output_dict=True, zero_division=0),
        'classes': classes,
        'test_rows': int(len(X_test)),
        'feature_count': int(feature_count),
    }
    fig, ax = plt.subplots(figsize=(9, 7))
    ConfusionMatrixDisplay.from_predictions(
        y_test, pred, labels=classes, xticks_rotation=45, cmap='Blues', ax=ax, colorbar=False
    )
    ax.set_title(f'{task_name.title()} - Final Held-out Confusion Matrix')
    fig.tight_layout()
    fig.savefig(REPORT_DIR / f'{task_name}_confusion_matrix.png', dpi=160)
    plt.close(fig)
    return metrics


def train_department():
    df = pd.read_csv(DATASET_DIR / 'department_dataset.csv').dropna(subset=['description','department']).copy()
    df['description'] = df['description'].astype(str).str.replace(r'\s+', ' ', regex=True).str.strip()
    df['norm'] = df['description'].map(_normalise)
    counts = df.groupby('norm')['department'].nunique()
    contradictory = set(counts[counts > 1].index)
    df = df[~df['norm'].isin(contradictory)].drop_duplicates('norm').reset_index(drop=True)

    X_train, X_test, y_train, y_test = train_test_split(
        df['description'], df['department'], test_size=0.20,
        random_state=RANDOM_STATE, stratify=df['department'])

    comparison = _benchmark(X_train, y_train, 30000, 25000, 'department')
    winner = comparison.iloc[0]['model']
    vectorizer, model, feature_count = _fit_selected(winner, X_train, y_train, 30000, 25000)
    metrics = _heldout('department', model, vectorizer, X_test, y_test, feature_count)
    metrics.update({
        'selected_model': winner,
        'selection_metric': '3-fold stratified CV macro-F1',
        'cv_macro_f1_mean': float(comparison.iloc[0]['cv_macro_f1_mean']),
        'cv_macro_f1_std': float(comparison.iloc[0]['cv_macro_f1_std']),
        'clean_rows': int(len(df)),
        'train_rows': int(len(X_train)),
        'removed_contradictory_texts': int(len(contradictory)),
        'candidate_models': comparison.to_dict(orient='records'),
        'probability_support': bool(hasattr(model, 'predict_proba')),
    })
    joblib.dump(model, MODEL_DIR / 'department_model.pkl')
    joblib.dump(vectorizer, MODEL_DIR / 'vectorizer.pkl')
    return metrics


CATEGORY_TO_DEPARTMENT = {
    'Road & Transportation': 'Roads & Transport',
    'Waste Management': 'Sanitation',
    'Electricity': 'Electricity',
    'Health & Sanitation': 'Healthcare',
    'Water Leakage': 'Water Supply',
    'Public Safety': 'Police',
    'Encroachment & Illegal Construction': 'Municipal Corporation',
    'Others': 'Municipal Corporation',
}


def priority_input(text: str, department: str | None = None) -> str:
    """Legacy helper kept for the old CivicComp benchmark script (not used in production)."""
    dept = re.sub(r'\W+', '_', (department or 'unknown').lower()).strip('_') or 'unknown'
    return f'department_{dept} {str(text).strip()}'


# ---------------------------------------------------------------------------
# Priority model (production)
# ---------------------------------------------------------------------------
# Production priority is trained on CivicFlow's own human-written complaint
# priorities (priority_dataset.csv). The CivicComp/BBMP corpus was evaluated as
# extra training data and *reduced* in-domain accuracy (its labels are derived
# from keyword rules on Bengaluru complaints), so it is no longer mixed in.
_PREFIX_RE = re.compile(r'^\s*(urgent|emergency|immediate attention|please help|asap)\s*[:!-]*\s*', re.I)


def _priority_group_key(text: str) -> str:
    """Key shared by a complaint and its 'URGENT:'/'EMERGENCY:'/ALL-CAPS variants.

    Used to keep near-duplicates in the same CV/test fold so metrics are not
    inflated by leakage between templated variants of one complaint.
    """
    return re.sub(r'\W+', ' ', _PREFIX_RE.sub('', str(text)).lower()).strip()


def _load_priority_frame() -> pd.DataFrame:
    df = pd.read_csv(DATASET_DIR / 'priority_dataset.csv').dropna(subset=['description', 'priority']).copy()
    df['description'] = df['description'].astype(str).str.replace(r'\s+', ' ', regex=True).str.strip()
    df['priority'] = df['priority'].astype(str).str.strip().str.title()
    df = df[df['priority'].isin(['Low', 'Medium', 'High'])]
    df['group'] = df['description'].map(_priority_group_key)
    # Identical complaints with conflicting labels are resolved by majority vote.
    majority = df.groupby('group')['priority'].agg(lambda s: s.value_counts().index[0])
    df['priority'] = df['group'].map(majority)
    return df.reset_index(drop=True)


def _load_priority_external() -> pd.DataFrame:
    """Load real labeled urgency/severity corpora as bounded training-only data.

    CivicDex urgency and CivicComp annotated severity are normalized to the
    application's Low/Medium/High labels. The larger annotated corpus is
    stratified-downsampled to 500 rows so it cannot overwhelm in-domain data.
    """
    civicdex = pd.read_csv(DATASET_DIR / 'civicdex_adapted.csv').dropna(
        subset=['english_gloss', 'urgency']).copy()
    civicdex['description'] = civicdex['english_gloss'].astype(str).str.replace(
        r'\s+', ' ', regex=True).str.strip()
    civicdex['priority'] = civicdex['urgency'].astype(str).str.strip().str.title()
    civicdex['source'] = 'civicdex'
    civicdex = civicdex[civicdex['priority'].isin(['Low', 'Medium', 'High'])]
    civicdex = civicdex[['description', 'priority', 'source']]

    annotated = pd.read_csv(DATASET_DIR / 'annotated_complaints_with_severity.csv').dropna(
        subset=['text_en', 'severity']).copy()
    title = annotated['complaint_title'].fillna('').astype(str).str.strip()
    body = annotated['text_en'].astype(str).str.strip()
    annotated['description'] = (title + '. ' + body).str.replace(
        r'\s+', ' ', regex=True).str.strip(' .')
    annotated['priority'] = annotated['severity'].astype(str).str.strip().str.title()
    annotated['source'] = 'annotated_severity'
    annotated = annotated[annotated['priority'].isin(['Low', 'Medium', 'High'])]
    # Preserve the in-domain class proportions while sampling deterministically.
    target_counts = _load_priority_frame()['priority'].value_counts(normalize=True)
    cap = 500
    annotated = pd.concat([
        group.sample(n=min(len(group), max(1, round(cap * target_counts.get(label, 0)))),
                     random_state=RANDOM_STATE)
        for label, group in annotated.groupby('priority')
    ], ignore_index=True)
    annotated = annotated[['description', 'priority', 'source']]

    feedback_path = DATASET_DIR / 'priority_supplement.csv'
    if feedback_path.exists():
        feedback = pd.read_csv(feedback_path)
        if {'description', 'priority', 'source'}.issubset(feedback.columns):
            feedback = feedback[feedback['source'].astype(str).eq('user_feedback')].copy()
            feedback['priority'] = feedback['priority'].astype(str).str.strip().str.title()
            feedback = feedback[feedback['priority'].isin(['Low', 'Medium', 'High'])]
            feedback = feedback[['description', 'priority']].assign(source='user_feedback')
        else:
            feedback = pd.DataFrame(columns=['description', 'priority', 'source'])
    else:
        feedback = pd.DataFrame(columns=['description', 'priority', 'source'])

    external = pd.concat([civicdex, annotated, feedback], ignore_index=True)
    external = external[external['description'].astype(str).str.len() >= 3].copy()
    external['group'] = external['description'].map(_priority_group_key)
    # Remove duplicates across external corpora; keep one row per text group.
    external = external.drop_duplicates('group').reset_index(drop=True)
    return external


def _priority_vectorizer():
    return FeatureUnion([
        ('word_tfidf', TfidfVectorizer(
            lowercase=True, ngram_range=(1, 3), sublinear_tf=True, strip_accents='unicode')),
        ('char_tfidf', TfidfVectorizer(
            analyzer='char_wb', ngram_range=(3, 5), min_df=2, sublinear_tf=True)),
    ])


def _priority_features(vectorizer, texts, fit=False):
    from scipy import sparse
    from app.services.urgency_features import matrix as urgency_matrix
    sparse_part = vectorizer.fit_transform(texts) if fit else vectorizer.transform(texts)
    return sparse.hstack([sparse_part, sparse.csr_matrix(urgency_matrix(texts))]).tocsr()


def _priority_candidates():
    return {
        'ComplementNB': ComplementNB(alpha=0.35),
        'LogisticRegression': LogisticRegression(
            C=3.0, max_iter=3000, class_weight='balanced', random_state=RANDOM_STATE),
        'LinearSVC': CalibratedClassifierCV(
            LinearSVC(C=0.5, class_weight='balanced', random_state=RANDOM_STATE), method='sigmoid', cv=3),
        'SGDClassifier': SGDClassifier(
            loss='log_loss', alpha=1e-4, max_iter=3000, tol=1e-4,
            class_weight='balanced', random_state=RANDOM_STATE),
    }


def train_priority():
    """Benchmark four families with leak-free grouped CV, then deploy the winner.

    1. 5-fold StratifiedGroupKFold (groups = complaint text without urgency prefix)
       on the full cleaned dataset selects the model family by macro-F1.
    2. A separate grouped 80/20 split reports an untouched held-out score.
    3. The deployed model is refit on 100% of the data.
    """
    from sklearn.model_selection import StratifiedGroupKFold, GroupShuffleSplit
    import sys
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / 'backend'))

    df = _load_priority_frame()
    external = _load_priority_external()
    X, y, groups = df['description'].values, df['priority'].values, df['group'].values
    X_external = external['description'].astype(str).values
    y_external = external['priority'].astype(str).values
    external_groups = external['group'].astype(str).values

    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    folds = list(cv.split(X, y, groups))
    rows = []
    for name in _priority_candidates():
        pred = np.empty(len(df), dtype=object)
        for tr, te in folds:
            vec = _priority_vectorizer()
            # Keep external duplicates of this validation fold out of training.
            test_groups = set(groups[te])
            keep_external = np.array([g not in test_groups for g in external_groups])
            fit_x = np.concatenate([X[tr], X_external[keep_external]])
            fit_y = np.concatenate([y[tr], y_external[keep_external]])
            A = _priority_features(vec, fit_x, fit=True)
            B = _priority_features(vec, X[te])
            pred[te] = _priority_candidates()[name].fit(A, fit_y).predict(B)
        rows.append({
            'model': name,
            'cv_accuracy': float(accuracy_score(y, pred)),
            'cv_macro_f1': float(f1_score(y, pred, average='macro')),
            'cv_weighted_f1': float(f1_score(y, pred, average='weighted')),
        })
    comparison = pd.DataFrame(rows).sort_values(
        ['cv_macro_f1', 'cv_accuracy'], ascending=False).reset_index(drop=True)
    comparison.to_csv(REPORT_DIR / 'priority_model_comparison.csv', index=False)
    winner = str(comparison.iloc[0]['model'])

    # Untouched grouped hold-out for the reported headline numbers.
    tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=RANDOM_STATE).split(X, y, groups))
    vec = _priority_vectorizer()
    holdout_groups = set(groups[te])
    keep_external = np.array([g not in holdout_groups for g in external_groups])
    holdout_fit_x = np.concatenate([X[tr], X_external[keep_external]])
    holdout_fit_y = np.concatenate([y[tr], y_external[keep_external]])
    A = _priority_features(vec, holdout_fit_x, fit=True)
    B = _priority_features(vec, X[te])
    held = _priority_candidates()[winner].fit(A, holdout_fit_y)
    pred = held.predict(B)
    classes = list(held.classes_)

    # Deployed model: refit on all data.
    vectorizer = _priority_vectorizer()
    final_fit_x = np.concatenate([X, X_external])
    final_fit_y = np.concatenate([y, y_external])
    Xall = _priority_features(vectorizer, final_fit_x, fit=True)
    model = _priority_candidates()[winner].fit(Xall, final_fit_y)

    from app.services.urgency_features import FEATURE_VERSION, NAMES
    metrics = {
        'selected_model': winner,
        'selection_metric': '5-fold grouped (leak-free) CV macro-F1 across four model families',
        'cv_macro_f1': float(comparison.iloc[0]['cv_macro_f1']),
        'cv_accuracy': float(comparison.iloc[0]['cv_accuracy']),
        'accuracy': float(accuracy_score(y[te], pred)),
        'macro_f1': float(f1_score(y[te], pred, average='macro')),
        'weighted_f1': float(f1_score(y[te], pred, average='weighted')),
        'macro_precision': float(precision_score(y[te], pred, average='macro', zero_division=0)),
        'macro_recall': float(recall_score(y[te], pred, average='macro', zero_division=0)),
        'classification_report': classification_report(y[te], pred, output_dict=True, zero_division=0),
        'classes': classes,
        'clean_rows': int(len(df)),
        'external_training_rows': int(len(external)),
        'external_training_sources': {k: int(v) for k, v in external['source'].value_counts().items()},
        'external_training_distribution': {k: int(v) for k, v in external['priority'].value_counts().items()},
        'unique_complaint_groups': int(df['group'].nunique()),
        'train_rows': int(len(tr)),
        'test_rows': int(len(te)),
        'feature_count': int(Xall.shape[1]),
        'urgency_feature_version': FEATURE_VERSION,
        'urgency_feature_names': NAMES,
        'class_distribution': {k: int(v) for k, v in df['priority'].value_counts().items()},
        'candidate_models': comparison.to_dict(orient='records'),
        'probability_support': bool(hasattr(model, 'predict_proba')),
        'source_columns_used': ['priority_dataset.description', 'priority_dataset.priority', 'civicdex_adapted.english_gloss', 'civicdex_adapted.urgency', 'annotated_complaints_with_severity.complaint_title', 'annotated_complaints_with_severity.text_en', 'annotated_complaints_with_severity.severity'],
        'note': 'External CivicDex and annotated severity rows are training-only, label-mapped to Low/Medium/High, deduplicated, bounded, and excluded from matching held-out groups. Features = word(1-3)+char(3-5) TF-IDF plus urgency features.',
    }
    fig, ax = plt.subplots(figsize=(8, 6))
    ConfusionMatrixDisplay.from_predictions(
        y[te], pred, labels=classes, xticks_rotation=45, cmap='Blues', ax=ax, colorbar=False)
    ax.set_title('Priority - Grouped Held-out Confusion Matrix')
    fig.tight_layout()
    fig.savefig(REPORT_DIR / 'priority_confusion_matrix.png', dpi=160)
    plt.close(fig)
    joblib.dump(model, MODEL_DIR / 'priority_model.pkl')
    joblib.dump(vectorizer, MODEL_DIR / 'priority_vectorizer.pkl')
    with open(REPORT_DIR / 'priority_metrics.json', 'w', encoding='utf-8') as f:
        json.dump(metrics, f, indent=2)
    return metrics

def main():
    dep = train_department()
    pri = train_priority()
    metadata = {
        'trained_at_utc': datetime.now(timezone.utc).isoformat(),
        'random_state': RANDOM_STATE,
        'scikit_learn_runtime': __import__('sklearn').__version__,
        'model_selection_protocol': 'Department: 4 candidates with 3-fold stratified CV. Priority: 4 candidates with 5-fold grouped (leak-free) CV on the CivicFlow labelled priority dataset, plus an untouched grouped hold-out.',
        'candidate_algorithms': list(_candidates().keys()),
        'department': dep,
        'priority': pri,
        'notes': {
            'critical_priority': 'Critical is produced by a transparent emergency safety layer because CivicComp has no genuine Critical training class.',
            'calibration': 'If LinearSVC wins, the deployed classifier is wrapped in CalibratedClassifierCV(sigmoid, cv=3) so the API can expose probability/confidence values.',
            'random_forest': 'Not benchmarked because tree ensembles are a poor fit for extremely high-dimensional sparse TF-IDF compared with linear text classifiers; SGD provides a scalable fourth baseline.'
        }
    }
    with open(REPORT_DIR / 'ml_metrics.json','w',encoding='utf-8') as f:
        json.dump(metadata,f,indent=2)
    with open(REPORT_DIR / 'ml_metrics_summary.json','w',encoding='utf-8') as f:
        json.dump({
            'department': {k:dep[k] for k in ['selected_model','accuracy','macro_f1','weighted_f1','cv_macro_f1_mean']},
            'priority': {k:pri[k] for k in ['selected_model','accuracy','macro_f1','weighted_f1','cv_macro_f1']}
        },f,indent=2)
    print(json.dumps({
        'department': {k:dep[k] for k in ['selected_model','accuracy','macro_f1','cv_macro_f1_mean']},
        'priority': {k:pri[k] for k in ['selected_model','accuracy','macro_f1','cv_macro_f1']}
    }, indent=2))

if __name__ == '__main__':
    main()
