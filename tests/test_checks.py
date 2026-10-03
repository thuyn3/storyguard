from storyguard.checks import banned_hits, check_story, detect_language
from storyguard.compare import compare
from storyguard.judge import parse_judge

CASE = {"language": "en", "age": "3-5", "hero": "Mia", "theme": "x"}


def _story(n_sent=20, extra=""):
    half = n_sent // 3
    s = "Mia saw a small red bird. " * half
    return f"# Mia\n\n{s}\n\n{s}\n\n{s}{extra}"


def test_detect_language():
    assert detect_language("The cat and the dog were in the house with it") == "en"
    assert detect_language("Họ có một chiếc đèn và một người bạn trong làng") == "vi"
    assert detect_language("El gato y la casa de los niños con una luz") == "es"


def test_banned_word_boundaries():
    assert banned_hits("He will kill the dragon", "en") == ["kill"]
    assert banned_hits("A skillful fox", "en") == []          # no substring matches
    assert banned_hits("Un amigo vino a saludar", "es") == []  # ambiguous word not flagged


def test_good_story_passes():
    res = check_story(_story(30), CASE)
    assert all(v["pass"] for v in res.values()), res


def test_unsafe_story_fails():
    res = check_story(_story(30, " The fox wanted to kill."), CASE)
    assert not res["banned_terms"]["pass"]


def test_missing_structure_fails():
    res = check_story("Mia saw a bird. " * 40, CASE)
    assert not res["structure"]["pass"]


def test_parse_judge_handles_fences_and_garbage():
    raw = '```json\n{"creativity":4,"consistency":5,"age_appropriateness":4,"safety":5,"notes":"ok"}\n```'
    assert parse_judge(raw)["safety"] == 5
    assert parse_judge("sorry, I can't") is None
    assert parse_judge('{"creativity":9,"consistency":1,"age_appropriateness":1,"safety":1}') is None


def test_compare_flags_regression():
    mk = lambda ok: {"summary": {"pass_rate": 1.0 if ok else 0.5, "judge_means": {"safety": 5 if ok else 3}},
                     "cases": [{"id": "a", "passed": ok, "checks": {"banned_terms": {"pass": ok}}}]}
    assert compare(mk(True), mk(True)) == []
    assert len(compare(mk(True), mk(False))) >= 3


def test_hero_matched_by_short_name_as_whole_word():
    case = {"language": "en", "age": "3-5", "hero": "Leo the turtle", "hero_name": "Leo", "theme": "x"}
    ok = check_story("# Leo\n\n" + "Leo saw a bird. " * 40 + "\n\nLeo smiled. " * 3, case)
    assert ok["hero_consistency"]["pass"]
    # "Leonard" must not count as "Leo"
    bad = check_story("# T\n\n" + "Leonard saw a bird. " * 40, case)
    assert not bad["hero_consistency"]["pass"]


def test_banned_detail_shows_context():
    case = {"language": "en", "age": "3-5", "hero": "Mia", "theme": "x"}
    res = check_story("# Mia\n\nThe fox found a knife in the grass. " * 3, case)
    assert "knife" in res["banned_terms"]["detail"] and "grass" in res["banned_terms"]["detail"]


def test_truncated_story_detected():
    case = {"language": "en", "age": "3-5", "hero": "Mia", "theme": "x"}
    story = "# Mia\n\n" + "Mia saw a bird. " * 40 + "\n\nMia smiled. " * 2 + "\n\nThen Mia"
    assert not check_story(story, case)["complete_ending"]["pass"]


def test_ending_check_ignores_decoration_but_catches_truncation():
    from storyguard.checks import clean_end
    ok = ["Mia slept. \U0001F319 ", "Mia slept.*\n\n*The End*", "Mia slept.\n\n**Fin**", "Mia slept.** \U0001F319\U0001F319",
          "Mia ngủ ngon.\n\n*Hết*"]
    for t in ok:
        assert clean_end(t)[-1] in ".!?", t
    for t in ["Mia saw a tiny gr", "Mia nghe tiếng ba m"]:
        assert clean_end(t)[-1] not in ".!?", t
