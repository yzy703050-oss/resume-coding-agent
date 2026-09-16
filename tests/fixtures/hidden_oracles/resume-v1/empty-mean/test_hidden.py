import pytest
from statsutil import mean


def test_hidden_mean_contract():
    assert mean([1]) == 1
    assert mean([-2, 2]) == 0
    with pytest.raises(ValueError, match="values must not be empty"):
        mean([])
