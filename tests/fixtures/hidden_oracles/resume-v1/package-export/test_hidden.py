from textutil import slugify


def test_hidden_public_slugify():
    assert slugify("  Hello,   World!  ") == "hello-world"
    assert slugify("Already--Slugged") == "already-slugged"
    assert slugify("***") == ""
