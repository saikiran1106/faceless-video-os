from conftest import words_from
from faceless.captions import align_script_words, build_pages, to_srt


def test_script_spelling_with_transcript_timing():
    heard = words_from("the olimpic sailed on for years.")
    aligned = align_script_words("The Olympic sailed on for years.", heard)
    assert [w["text"] for w in aligned] == ["The", "Olympic", "sailed", "on", "for", "years."]
    assert aligned[1]["start"] == heard[1]["start"]


def test_pages_respect_limits_and_sentence_ends():
    words = words_from("One two three four five. Six seven.")
    pages = build_pages(words, max_words=3, max_chars=40)
    assert all(len(p["words"]) <= 3 for p in pages)
    assert pages[1]["words"][-1]["text"] == "five."


def test_srt_format():
    srt = to_srt(build_pages(words_from("Hello world."), 3, 40))
    assert srt.startswith("1\n00:00:00,000 --> ")
