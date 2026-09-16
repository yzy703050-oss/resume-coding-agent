from ordering import order_by_priority


def test_hidden_stable_priority():
    tied = [{"name": "z", "priority": 2}, {"name": "a", "priority": 2}]
    assert order_by_priority(tied) == tied
    mixed = [{"name": "low", "priority": 1}, {"name": "high", "priority": 3}]
    assert [item["name"] for item in order_by_priority(mixed)] == ["high", "low"]
    assert order_by_priority([]) == []
