from tags import normalize_tags


def test_hidden_normalization_contract():
    assert normalize_tags([]) == []
    assert normalize_tags([" AI", "ai ", "", " Python "]) == ["ai", "python"]
    assert normalize_tags(["b", "A", "B", "a"]) == ["b", "a"]
