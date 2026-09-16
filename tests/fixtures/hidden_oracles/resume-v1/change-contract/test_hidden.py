from app import greet


def test_hidden_names():
    assert greet("Ada Lovelace") == "Hello ADA LOVELACE"
    assert greet("aLiCe") == "Hello ALICE"
    assert greet("") == "Hello "
