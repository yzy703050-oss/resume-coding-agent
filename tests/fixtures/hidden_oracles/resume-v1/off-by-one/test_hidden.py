from app import values


def test_hidden_boundaries():
    assert values(0) == []
    assert values(1) == [0]
    assert values(5) == [0, 1, 2, 3, 4]
