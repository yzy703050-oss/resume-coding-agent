from payloads import omit_none


def test_hidden_nested_payloads():
    assert omit_none({"outer": {"drop": None, "keep": 1}}) == {"outer": {"keep": 1}}
    assert omit_none({"rows": [{"x": None, "y": 2}, None]}) == {"rows": [{"y": 2}, None]}
    assert omit_none({}) == {}
