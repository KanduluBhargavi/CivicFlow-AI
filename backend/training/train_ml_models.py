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
    from sklearn.model_selection import GroupShuffleSplit, StratifiedGroupKFold
    df = pd.read_csv(DATASET_DIR / 'department_dataset.csv').dropna(subset=['description','department']).copy()
    df['description'] = df['description'].astype(str).str.replace(r'\s+', ' ', regex=True).str.strip()
    df['norm'] = df['description'].map(_normalise)
    counts = df.groupby('norm')['department'].nunique()
    contradictory = set(counts[counts > 1].index)
    df = df[~df['norm'].isin(contradictory)].drop_duplicates('norm').reset_index(drop=True)

    df = df.drop_duplicates('norm').reset_index(drop=True)
    df['group'] = df['norm']

    # The Hugging Face file has 25 labels, while CivicFlow currently routes to
    # eight operational departments. Use only categories with a reviewed,
    # defensible mapping; leave the other 16 categories for a future routing
    # taxonomy decision instead of silently assigning them to unrelated teams.
    hf_department_map = {
        'Roads and Public Works': 'Roads & Transport',
        'Electricity and Street Lighting': 'Electricity',
        'Public Transport': 'Roads & Transport',
        'Municipal Services': 'Municipal Corporation',
        'Sanitation and Solid Waste': 'Sanitation',
        'Water Supply and Irrigation': 'Water Supply',
        'Public Health and Hospitals': 'Healthcare',
        'Education and Scholarships': 'Education',
        'Police and Public Safety': 'Police',
    }
    hf_path = DATASET_DIR / 'hf_public_grievance_candidate.csv'
    hf = pd.DataFrame(columns=['description', 'department', 'group'])
    if hf_path.exists():
        raw_hf = pd.read_csv(hf_path).dropna(subset=['grievance_text', 'category']).copy()
        raw_hf['department'] = raw_hf['category'].map(hf_department_map)
        raw_hf = raw_hf.dropna(subset=['department'])
        hf['description'] = raw_hf['grievance_text'].astype(str).str.replace(
            r'\s+', ' ', regex=True
        ).str.strip()
        hf['department'] = raw_hf['department'].astype(str)
        hf['group'] = hf['description'].map(_normalise)
        hf = hf.drop_duplicates('group').reset_index(drop=True)

    tr, te = next(GroupShuffleSplit(
        n_splits=1, test_size=0.20, random_state=RANDOM_STATE
    ).split(df['description'], df['department'], df['group']))
    train_df, test_df = df.iloc[tr].copy(), df.iloc[te].copy()
    # Exclude any exact HF-text duplicate of a CivicFlow holdout complaint.
    holdout_groups = set(test_df['group'])
    hf = hf[~hf['group'].isin(holdout_groups)].reset_index(drop=True)

    vectorizer_factory = lambda: TfidfVectorizer(
        lowercase=True, ngram_range=(1, 2), min_df=2,
        max_features=150_000, sublinear_tf=True, strip_accents='unicode',
    )
    weight_options = (0.0, 0.025, 0.05, 0.10, 0.25, 0.50, 1.0) if len(hf) else (0.0,)
    cv = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=43)
    folds = list(cv.split(train_df['description'], train_df['department'], train_df['group']))
    weight_results = []
    for hf_weight in weight_options:
        fold_scores = []
        for fold_tr, fold_va in folds:
            local = train_df.iloc[fold_tr]
            valid = train_df.iloc[fold_va]
            if hf_weight:
                fit_text = pd.concat([local['description'], hf['description']], ignore_index=True)
                fit_y = pd.concat([local['department'], hf['department']], ignore_index=True)
                sample_weight = np.concatenate([
                    np.ones(len(local)),
                    np.full(len(hf), hf_weight * len(local) / len(hf)),
                ])
            else:
                fit_text, fit_y, sample_weight = local['description'], local['department'], None
            vec = vectorizer_factory()
            fit_X = vec.fit_transform(fit_text)
            valid_X = vec.transform(valid['description'])
            clf = LogisticRegression(
                max_iter=2000, class_weight='balanced', random_state=RANDOM_STATE
            )
            clf.fit(fit_X, fit_y, sample_weight=sample_weight)
            fold_scores.append(float(f1_score(
                valid['department'], clf.predict(valid_X), average='macro'
            )))
        weight_results.append({
            'hf_total_weight_vs_civicflow': float(hf_weight),
            'grouped_cv_macro_f1_mean': float(np.mean(fold_scores)),
            'grouped_cv_macro_f1_std': float(np.std(fold_scores)),
        })
    selected = max(weight_results, key=lambda row: (
        row['grouped_cv_macro_f1_mean'], -row['hf_total_weight_vs_civicflow']
    ))
    hf_weight = selected['hf_total_weight_vs_civicflow']

    # Score the selected candidate on an untouched CivicFlow-only grouped holdout.
    if hf_weight:
        fit_text = pd.concat([train_df['description'], hf['description']], ignore_index=True)
        fit_y = pd.concat([train_df['department'], hf['department']], ignore_index=True)
        sample_weight = np.concatenate([
            np.ones(len(train_df)), np.full(len(hf), hf_weight * len(train_df) / len(hf))
        ])
    else:
        fit_text, fit_y, sample_weight = train_df['description'], train_df['department'], None
    vectorizer = vectorizer_factory()
    fit_X = vectorizer.fit_transform(fit_text)
    heldout_model = LogisticRegression(
        max_iter=2000, class_weight='balanced', random_state=RANDOM_STATE
    )
    heldout_model.fit(fit_X, fit_y, sample_weight=sample_weight)
    metrics = _heldout(
        'department', heldout_model, vectorizer,
        test_df['description'], test_df['department'], fit_X.shape[1],
    )
    metrics.update({
        'selected_model': 'LogisticRegression',
        'selection_metric': '3-fold StratifiedGroupKFold macro-F1; source weight selected only on CivicFlow training rows',
        'cv_macro_f1_mean': float(selected['grouped_cv_macro_f1_mean']),
        'cv_macro_f1_std': float(selected['grouped_cv_macro_f1_std']),
        'clean_rows': int(len(df)),
        'train_rows': int(len(train_df)),
        'test_rows': int(len(test_df)),
        'removed_contradictory_texts': int(len(contradictory)),
        'hf_rows_used': int(len(hf)),
        'hf_source_weight_vs_civicflow': float(hf_weight),
        'hf_mapped_categories': hf_department_map,
        'source_weight_candidates': weight_results,
        'probability_support': True,
        'training_data_note': 'Only the nine HF categories mapped above are used; the model still predicts CivicFlow\'s existing eight operational departments.',
    })
    comparison = pd.DataFrame(weight_results).sort_values(
        'hf_total_weight_vs_civicflow'
    ).reset_index(drop=True)
    comparison.to_csv(REPORT_DIR / 'department_model_comparison.csv', index=False)

    # Refit the selected model on all CivicFlow labels plus the mapped HF rows
    # for inference. The reported metrics above remain from the untouched holdout.
    if hf_weight:
        all_text = pd.concat([df['description'], hf['description']], ignore_index=True)
        all_y = pd.concat([df['department'], hf['department']], ignore_index=True)
        all_weight = np.concatenate([
            np.ones(len(df)), np.full(len(hf), hf_weight * len(df) / len(hf))
        ])
    else:
        all_text, all_y, all_weight = df['description'], df['department'], None
    final_vectorizer = vectorizer_factory()
    all_X = final_vectorizer.fit_transform(all_text)
    final_model = LogisticRegression(
        max_iter=2000, class_weight='balanced', random_state=RANDOM_STATE
    )
    final_model.fit(all_X, all_y, sample_weight=all_weight)
    joblib.dump(final_model, MODEL_DIR / 'department_model.pkl')
    joblib.dump(final_vectorizer, MODEL_DIR / 'vectorizer.pkl')
    with open(REPORT_DIR / 'department_metrics.json', 'w', encoding='utf-8') as f:
        json.dump(metrics, f, indent=2)
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
            fit_source = np.concatenate([
                np.repeat('priority_dataset', len(tr)),
                external.loc[keep_external, 'source'].astype(str).values,
            ])
            fit_weights = np.where((fit_source == 'user_feedback') & (fit_y == 'Low'), 5.0, 1.0)
            A = _priority_features(vec, fit_x, fit=True)
            B = _priority_features(vec, X[te])
            pred[te] = _priority_candidates()[name].fit(
                A, fit_y, sample_weight=fit_weights
            ).predict(B)
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
    holdout_sources = np.concatenate([
        np.repeat('priority_dataset', len(tr)),
        external.loc[keep_external, 'source'].astype(str).values,
    ])
    holdout_weights = np.where((holdout_sources == 'user_feedback') & (holdout_fit_y == 'Low'), 5.0, 1.0)
    A = _priority_features(vec, holdout_fit_x, fit=True)
    B = _priority_features(vec, X[te])
    held = _priority_candidates()[winner].fit(A, holdout_fit_y, sample_weight=holdout_weights)
    pred = held.predict(B)
    classes = list(held.classes_)

    # Deployed model: refit on all data.
    vectorizer = _priority_vectorizer()
    final_fit_x = np.concatenate([X, X_external])
    final_fit_y = np.concatenate([y, y_external])
    final_sources = np.concatenate([
        np.repeat('priority_dataset', len(X)), external['source'].astype(str).values,
    ])
    final_weights = np.where((final_sources == 'user_feedback') & (final_fit_y == 'Low'), 5.0, 1.0)
    Xall = _priority_features(vectorizer, final_fit_x, fit=True)
    model = _priority_candidates()[winner].fit(Xall, final_fit_y, sample_weight=final_weights)

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
