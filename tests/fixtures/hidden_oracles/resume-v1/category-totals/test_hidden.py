from totals import category_totals


def test_hidden_category_totals():
    assert category_totals([]) == {}
    assert category_totals([("a", 1), ("b", 2), ("a", 4)]) == {"a": 5, "b": 2}
    assert category_totals([("x", -2), ("x", 3)]) == {"x": 1}
