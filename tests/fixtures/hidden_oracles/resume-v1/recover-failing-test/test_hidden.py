from counter import count_words


def test_hidden_whitespace_counting():
    assert count_words("") == 0
    assert count_words("one\ttwo\nthree") == 3
    assert count_words("  padded  words ") == 2
