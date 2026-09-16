import pytest
from ports import parse_port


def test_hidden_valid_ports():
    assert parse_port(1) == 1
    assert parse_port("65535") == 65535


@pytest.mark.parametrize("value", [True, 3.5, "http", "0", 65536])
def test_hidden_invalid_ports(value):
    with pytest.raises(ValueError):
        parse_port(value)
