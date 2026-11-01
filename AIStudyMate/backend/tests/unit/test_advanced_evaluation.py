import json
from pathlib import Path
from evaluation.evaluate import evaluate
def test_reproducible_advanced_learning_evaluation_contract():
    root=Path(__file__).resolve().parents[2]/"evaluation";data=json.loads((root/"advanced_learning_dataset.json").read_text());result=evaluate(data)
    assert result["dataset"]["documents"]==1;assert result["dataset"]["pages"]==2
    assert all(value is not None and 0<=value<=1 for value in result["metrics"].values())
