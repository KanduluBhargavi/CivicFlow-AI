# ML datasets used by CivicFlow

## `department_dataset.csv`
Original CivicFlow eight-department labelled complaint dataset. It remains the production source for department-routing training because its labels match the exact departments implemented by the application.

## `annotated_complaints_with_severity.csv`
CivicComp multilingual civic complaint data provided for this project. CivicFlow uses its complaint title, English text, primary civic category and severity label for severity training. Target-derived fields (`severity_score`, matched severity keywords) are excluded from model features to reduce leakage.

Source page supplied during development:
`https://www.kaggle.com/datasets/shyamtripathi373/civiccomp-hien-hindienglish-civic-complaints`

The source page indicates CC BY-SA 4.0. Preserve source attribution and verify the current dataset license before redistributing outside the project/repository.

## `civicdex_adapted.csv`
Retained as a secondary multilingual/urgency research dataset. It is not blindly merged into the production classifiers because its department taxonomy and labelling policy differ from CivicFlow's canonical department labels.

## Important
`train.csv` and `test.csv` from CivicComp were not additionally merged into the full annotated CSV because those records originate from the same dataset and doing so can duplicate samples / cause leakage.
