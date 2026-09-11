import pytest

from now_eval.metrics.classification import (
    accuracy,
    confusion_counts,
    multilabel_precision_recall,
)


def test_accuracy_hand_computed():
    # 8 of 10 correct -> 0.8. Exactly the type-classification gate shape
    # (>=0.95 in production; this is just proving the arithmetic).
    predictions = {f"a{i}": "eat" for i in range(8)}
    predictions.update({"a8": "stay", "a9": "editorial"})
    labels = {f"a{i}": "eat" for i in range(10)}
    assert accuracy(predictions, labels) == pytest.approx(0.8)


def test_accuracy_commercial_guarantee_case():
    # The specific failure §17 exists to catch: a hotel (stay)
    # misclassified as editorial. Still just arithmetic here -- 1 wrong
    # of 4 -> 0.75 -- but named to document why the gate exists.
    predictions = {"hotel1": "editorial", "eat1": "eat", "stay1": "stay", "do1": "do"}
    labels = {"hotel1": "stay", "eat1": "eat", "stay1": "stay", "do1": "do"}
    assert accuracy(predictions, labels) == pytest.approx(0.75)


def test_accuracy_perfect_and_zero():
    assert accuracy({"a": "x"}, {"a": "x"}) == 1.0
    assert accuracy({"a": "y"}, {"a": "x"}) == 0.0


def test_accuracy_raises_on_empty_overlap():
    with pytest.raises(ValueError):
        accuracy({"a": "x"}, {"b": "x"})


def test_confusion_counts_hand_computed():
    # item "1": true=eat,  pred=eat  -> confusion[eat][eat]  += 1
    # item "2": true=stay, pred=eat  -> confusion[stay][eat] += 1
    # item "3": true=stay, pred=stay -> confusion[stay][stay]+= 1
    predictions = {"1": "eat", "2": "eat", "3": "stay"}
    labels = {"1": "eat", "2": "stay", "3": "stay"}
    table = confusion_counts(predictions, labels)
    assert table == {"eat": {"eat": 1}, "stay": {"eat": 1, "stay": 1}}


def test_multilabel_precision_recall_hand_computed():
    # item1: predicted {a,b,c}, true {a,b}      -> tp=2 fp=1 fn=0
    # item2: predicted {a},     true {a,d}      -> tp=1 fp=0 fn=1
    # totals: tp=3 fp=1 fn=1
    # precision = 3/4 = 0.75, recall = 3/4 = 0.75
    predicted = {"item1": {"a", "b", "c"}, "item2": {"a"}}
    true = {"item1": {"a", "b"}, "item2": {"a", "d"}}
    precision, recall = multilabel_precision_recall(predicted, true)
    assert precision == pytest.approx(0.75)
    assert recall == pytest.approx(0.75)


def test_multilabel_precision_recall_perfect_match():
    predicted = {"item1": {"a", "b"}}
    true = {"item1": {"a", "b"}}
    precision, recall = multilabel_precision_recall(predicted, true)
    assert precision == 1.0
    assert recall == 1.0


def test_multilabel_precision_recall_no_predictions_is_zero_not_error():
    predicted: dict[str, set[str]] = {}
    true = {"item1": {"a"}}
    precision, recall = multilabel_precision_recall(predicted, true)
    assert precision == 0.0
    assert recall == 0.0


def test_multilabel_precision_recall_empty_true_is_zero_precision_not_div_by_zero():
    predicted = {"item1": {"a"}}
    true: dict[str, set[str]] = {}
    precision, recall = multilabel_precision_recall(predicted, true)
    assert precision == 0.0
    assert recall == 0.0
