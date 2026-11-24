# ML datasets used by CivicFlow

## `department_dataset.csv`
Original CivicFlow eight-department labelled complaint dataset. It remains the production source for department-routing training because its labels match the exact departments implemented by the application.

## `annotated_complaints_with_severity.csv`
CivicComp multilingual civic complaint data provided for this project. Priority training uses English complaint title/text and the annotated severity label (mapped to Low/Medium/High). A deterministic, class-stratified sample capped at 500 rows is used as training-only augmentation to limit source imbalance. Target-derived scores/keywords and category fields are excluded.

Source page supplied during development:
`https://www.kaggle.com/datasets/shyamtripathi373/civiccomp-hien-hindienglish-civic-complaints`

The source page indicates CC BY-SA 4.0. Preserve source attribution and verify the current dataset license before redistributing outside the project/repository.

## `civicdex_adapted.csv`
Used as training-only priority augmentation through `english_gloss` and `urgency` (mapped to Low/Medium/High). All 660 labeled rows are eligible; duplicates of held-out in-domain complaint groups are excluded in each fold. Its category/department fields are not used for priority.

## Important
`train.csv` and `test.csv` from CivicComp were not additionally merged into the full annotated CSV because those records originate from the same dataset and doing so can duplicate samples / cause leakage.


Priority evaluation remains on the grouped held-out split of `priority_dataset.csv`; CivicDex and annotated rows are used only for training and never as evaluation examples. Synthetic priority examples are not used by the training pipeline.

Only the two manually labeled user_feedback examples in priority_supplement.csv are included; curated_synthetic rows are excluded.
