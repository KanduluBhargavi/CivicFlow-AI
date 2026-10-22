"""DEPRECATED: legacy CivicComp benchmark. It overwrites the priority reports with
results from the old BBMP-only approach. Use train_priority_model.py instead."""
raise SystemExit("benchmark_priority_fast.py is deprecated; run train_priority_model.py")
from pathlib import Path
import json
import joblib, pandas as pd, matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, classification_report, ConfusionMatrixDisplay
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.svm import LinearSVC
from sklearn.naive_bayes import ComplementNB
from sklearn.calibration import CalibratedClassifierCV
from sklearn.multiclass import OneVsRestClassifier
from train_ml_models import _normalise, CATEGORY_TO_DEPARTMENT, priority_input, RANDOM_STATE, DATASET_DIR, MODEL_DIR, REPORT_DIR

df=pd.read_csv(DATASET_DIR/'annotated_complaints_with_severity.csv').dropna(subset=['severity']).copy()
df['severity']=df['severity'].astype(str).str.title(); df=df[df['severity'].isin(['Low','Medium','High'])]
df['text']=(df['complaint_title'].fillna('').astype(str).str.strip()+' '+df['text_en'].fillna('').astype(str).str.strip()).str.replace(r'\s+',' ',regex=True).str.strip()
df=df[df['text'].str.len()>5].copy(); df['norm']=df['text'].map(_normalise); df=df.drop_duplicates('norm').reset_index(drop=True)
df['department']=df['category_primary'].map(CATEGORY_TO_DEPARTMENT).fillna('Municipal Corporation'); df['model_input']=[priority_input(t,d) for t,d in zip(df['text'],df['department'])]
X_dev,X_test,y_dev,y_test=train_test_split(df['model_input'],df['severity'],test_size=.20,random_state=RANDOM_STATE,stratify=df['severity'])
X_train,X_val,y_train,y_val=train_test_split(X_dev,y_dev,test_size=.20,random_state=RANDOM_STATE,stratify=y_dev)

def make_vec(): return TfidfVectorizer(lowercase=True,stop_words='english',ngram_range=(1,2),min_df=2,max_df=.98,sublinear_tf=True,max_features=45000,strip_accents='unicode')
vec=make_vec(); Xt=vec.fit_transform(X_train); Xv=vec.transform(X_val)
cands={'ComplementNB':ComplementNB(alpha=.35),'LogisticRegression':OneVsRestClassifier(LogisticRegression(C=2,max_iter=700,solver='liblinear',class_weight='balanced',random_state=RANDOM_STATE)),'LinearSVC':LinearSVC(C=1.2,class_weight='balanced',random_state=RANDOM_STATE),'SGDClassifier':SGDClassifier(loss='log_loss',alpha=1e-5,max_iter=1800,tol=1e-4,class_weight='balanced',random_state=RANDOM_STATE)}
rows=[]
for name,m in cands.items():
 m.fit(Xt,y_train); p=m.predict(Xv); rows.append({'model':name,'validation_accuracy':float(accuracy_score(y_val,p)),'validation_macro_f1':float(f1_score(y_val,p,average='macro')),'validation_weighted_f1':float(f1_score(y_val,p,average='weighted'))})
comp=pd.DataFrame(rows).sort_values(['validation_macro_f1','validation_accuracy'],ascending=False).reset_index(drop=True); comp.to_csv(REPORT_DIR/'priority_model_comparison.csv',index=False); winner=comp.iloc[0]['model']
vec2=make_vec(); Xd=vec2.fit_transform(X_dev); Xte=vec2.transform(X_test); base=cands[winner]; model=CalibratedClassifierCV(base,method='sigmoid',cv=3) if winner=='LinearSVC' else base; model.fit(Xd,y_dev); pred=model.predict(Xte)
metrics={'selected_model':winner,'selection_metric':'stratified validation macro-F1','validation_macro_f1':float(comp.iloc[0]['validation_macro_f1']),'accuracy':float(accuracy_score(y_test,pred)),'macro_f1':float(f1_score(y_test,pred,average='macro')),'weighted_f1':float(f1_score(y_test,pred,average='weighted')),'macro_precision':float(precision_score(y_test,pred,average='macro',zero_division=0)),'macro_recall':float(recall_score(y_test,pred,average='macro',zero_division=0)),'classification_report':classification_report(y_test,pred,output_dict=True,zero_division=0),'classes':list(model.classes_),'clean_rows':int(len(df)),'train_validation_rows':int(len(X_dev)),'test_rows':int(len(X_test)),'feature_count':int(Xd.shape[1]),'class_distribution':{k:int(v) for k,v in df['severity'].value_counts().items()},'candidate_models':comp.to_dict(orient='records'),'probability_support':hasattr(model,'predict_proba'),'feature_representation':'word TF-IDF unigrams+bigrams, max 45k features','source_columns_used':['complaint_title','text_en','category_primary','severity'],'excluded_leakage_columns':['severity_score','high_keywords_matched','medium_keywords_matched']}
fig,ax=plt.subplots(figsize=(8,6)); ConfusionMatrixDisplay.from_predictions(y_test,pred,labels=list(model.classes_),xticks_rotation=45,cmap='Blues',ax=ax,colorbar=False); ax.set_title('Priority - Final Held-out Confusion Matrix'); fig.tight_layout(); fig.savefig(REPORT_DIR/'priority_confusion_matrix.png',dpi=160); plt.close(fig)
joblib.dump(model,MODEL_DIR/'priority_model.pkl'); joblib.dump(vec2,MODEL_DIR/'priority_vectorizer.pkl'); json.dump(metrics,open(REPORT_DIR/'priority_metrics.json','w'),indent=2)
print(comp.to_string(index=False)); print(json.dumps({k:metrics[k] for k in ['selected_model','validation_macro_f1','accuracy','macro_f1','weighted_f1']},indent=2))
