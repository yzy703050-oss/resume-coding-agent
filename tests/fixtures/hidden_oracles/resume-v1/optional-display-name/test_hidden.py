from names import display_name


def test_hidden_display_names():
    assert display_name("") == "Guest"
    assert display_name("   ") == "Guest"
    assert display_name(" Ada ") == " Ada "
