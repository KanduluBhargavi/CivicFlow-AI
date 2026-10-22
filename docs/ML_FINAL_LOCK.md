# ML Final Lock

CivicFlow's ML base has been finalized for the current project cycle.

## Frozen components
1. Department routing classifier
2. Priority/severity classifier
3. Critical safety escalation
4. Duplicate intelligence scoring
5. Language detection/translation pipeline
6. Extractive complaint summarization
7. Confidence + human-review flags

## Why no further retraining is required now
- Department model already exceeds 0.93 held-out Macro-F1.
- Priority model was rebuilt on the larger CivicComp corpus and benchmarked honestly under class imbalance.
- Four candidate algorithms were compared before selecting the deployed classifiers.
- Preprocessing, leakage controls, stratified validation, confusion matrices, metrics, and model documentation are present.
- The remaining gains would require better/new labelled severity data or a larger multilingual transformer experiment, which is future work rather than a Review-2 requirement.

## Next development phase
Freeze the current `models/` artifacts. Focus only on product features, workflow, testing, UI, and demo reliability.

## Runtime safety guard
- High-priority safety floor prevents explicit serious hazards (e.g. transformer sparking, exposed electrical cables, open manholes, contaminated drinking water) from remaining Low/Medium due to short or sparse text.
- Critical remains reserved for explicit immediate life-safety emergencies.
