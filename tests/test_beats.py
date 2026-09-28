from conftest import words_from
from faceless.beats import build_beats

PACING = {"min_s": 1.6, "target_s": 3.0, "max_s": 5.0, "max_hold_s": 6.0}


def test_beats_cover_audio_continuously():
    text = "One two three four. Five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen. Short. End of the story here."
    words = words_from(text)
    duration = words[-1]["end"] + 0.8
    beats = build_beats(words, duration, PACING)
    assert beats[0]["start_s"] == 0
    assert beats[-1]["end_s"] == round(duration, 3)
    for a, b in zip(beats, beats[1:]):
        assert a["end_s"] == b["start_s"]
    assert len({b["keyframe_id"] for b in beats}) == len(beats)


def test_long_sentence_is_split_under_max():
    words = words_from(" ".join(f"w{i}," if i % 6 == 5 else f"w{i}" for i in range(40)) + " end.")
    beats = build_beats(words, words[-1]["end"], PACING)
    assert len(beats) > 1
    assert max(b["end_s"] - b["start_s"] for b in beats) <= PACING["max_s"] * 1.3


def test_tiny_sentence_is_merged():
    words = words_from("Wow. This is a much longer sentence that follows it here.")
    beats = build_beats(words, words[-1]["end"], PACING)
    assert beats[0]["text"].startswith("Wow.")
    assert beats[0]["end_s"] - beats[0]["start_s"] >= PACING["min_s"]


def test_keep_directions_rebinds_only_unchanged_lines():
    from faceless.beats import carry_directions

    first = "Alpha beta gamma delta epsilon zeta eta."
    old_words = words_from(f"{first} Theta iota kappa lambda mu nu xi.")
    old = build_beats(old_words, old_words[-1]["end"], PACING)
    assert len(old) == 2
    for b in old:
        b["visual_objective"] = f"show {b['text']}"
    new_words = words_from(f"{first} Something else entirely was said here instead.", per_word=0.45)
    new = build_beats(new_words, new_words[-1]["end"], PACING)
    result = carry_directions(new, old)
    assert new[0]["keyframe_id"] == old[0]["keyframe_id"] and new[0]["visual_objective"]
    assert new[-1]["keyframe_id"] not in {b["keyframe_id"] for b in old}
    assert result["new_needing_direction"] == [new[-1]["beat_id"]]
