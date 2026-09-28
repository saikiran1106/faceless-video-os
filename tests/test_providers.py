from faceless.providers import chunk_text, split_sentences


def test_chunks_keep_sentences_whole():
    text = "First sentence here. Second one is a bit longer than that. Third!"
    chunks = chunk_text(text, 40)
    assert all(len(c) <= 40 for c in chunks)
    assert " ".join(chunks) == " ".join(split_sentences(text))


def test_indic_danda_splits():
    assert len(split_sentences("पहला वाक्य। दूसरा वाक्य।")) == 2
