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


def test_upload_mode_spelling_corrections_reach_captions():
    from faceless.captions import caption_words

    heard = words_from("the olimpic sailed on for years.")
    transcript = {"words": heard}
    corrected = {"source": "transcript", "narration": "the Olympic sailed on for years."}
    assert [w["text"] for w in caption_words(transcript, corrected)][1] == "Olympic"
    rewritten = {"source": "transcript", "narration": "a completely different sentence entirely now."}
    assert caption_words(transcript, rewritten)[1]["text"] == "olimpic"  # rewrites never override the recording


def test_script_only_words_are_kept_and_timed():
    heard = words_from("her twin sister the olympic sailed on.")
    aligned = align_script_words("Her twin sister, the RMS Olympic, sailed on.", heard)
    texts = [w["text"] for w in aligned]
    assert texts == ["Her", "twin", "sister,", "the", "RMS", "Olympic,", "sailed", "on."]
    rms = aligned[4]
    assert aligned[3]["end"] <= rms["start"] + 1e-6 and rms["end"] <= aligned[5]["start"] + 1e-6
