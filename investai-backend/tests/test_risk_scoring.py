"""Tests for the risk-assessment instrument and its scoring.

These exist because the endpoint they cover was broken in two ways at once and
neither was visible: the request shape had drifted from what the mobile wizard
sends (every submission 422'd), and every option string in the scoring ladders
had stopped existing (so a matching shape would have scored 0/"Low" for
everyone). The tests below pin both halves — the payload the app actually sends,
and the property that an unrecognised answer *raises* instead of scoring zero.
"""
import pytest

from app.services import risk_scoring as rs
from app.services.risk_scoring import (
    AssessmentError,
    QUESTIONS,
    TOTAL_WEIGHT,
    category_for,
    question_bank,
    score_assessment,
)


# ── The instrument itself ────────────────────────────────────────────────────

def test_scored_weights_sum_to_100():
    """The score is a percentage; the weights have to add up to one."""
    assert TOTAL_WEIGHT == 100


def test_journey_is_ten_profile_and_five_knowledge_questions():
    bank = question_bank()
    profile = [q['id'] for q in bank if q['kind'] == 'profile']
    knowledge = [q['id'] for q in bank if q['kind'] == 'knowledge']
    assert profile == [1, 2, 3, 4, 5, 6, 7, 8, 10, 12]
    assert knowledge == [101, 102, 103, 104, 105]
    # Every served profile question is scored; the language question is gone.
    assert all(q['weight'] > 0 for q in bank if q['kind'] == 'profile')
    assert 14 not in profile


def test_knowledge_items_carry_a_valid_answer_and_explanation():
    for q in question_bank():
        if q['kind'] == 'knowledge':
            assert q['correct'] in q['options']
            assert q['explanation'].endswith('.')
            assert q['weight'] == 0
        else:
            assert 'correct' not in q


def test_every_scored_single_question_prices_all_its_options():
    """A missing fraction would raise KeyError at request time, not import."""
    for q in QUESTIONS:
        if q.scored and q.kind == 'single':
            assert set(q.fractions) == set(q.options), f'Q{q.id}'


def test_scored_fractions_are_within_unit_range():
    for q in QUESTIONS:
        for option, fraction in q.fractions.items():
            assert 0.0 <= fraction <= 1.0, f'Q{q.id} {option!r}'


def test_every_question_has_options_unless_slider():
    for q in QUESTIONS:
        if q.kind == 'slider':
            assert q.options == ()
        else:
            assert len(q.options) >= 2, f'Q{q.id}'


def test_question_bank_is_serialisable_and_complete():
    bank = question_bank()
    assert len(bank) == 15
    assert bank[0]['id'] == 1
    assert bank[0]['type'] == 'single'
    assert 'Retirement' in bank[0]['options']
    assert all(q['type'] == 'single' for q in bank)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _answers_at(index: int) -> dict:
    """Answer every scored question with the option at `index` (0-based)."""
    out = {}
    for q in QUESTIONS:
        if not q.scored:
            continue
        if q.kind == 'slider':
            out[str(q.id)] = [0, 34, 67, 100][index]
        else:
            out[str(q.id)] = q.options[index]
    return out


MOST_TOLERANT = {
    '1': 'Wealth Growth',
    '2': 'Very comfortable',
    '3': '5+ years',
    '4': 'Regularly',
    '5': 'Above 250,000',
    '6': 'More than 50%',
    '7': 'Yes, completely',   # descending ladder: best knowledge, top fraction
    '8': 'Buy more',
    '10': 'High risk / High reward',
    '12': 'Yes, daily',
}

LEAST_TOLERANT = {
    '1': 'Major Purchase (e.g., home)',
    '2': 'Not comfortable at all',
    '3': 'Less than 1 year',
    '4': 'Never',
    '5': 'Below 50,000',
    '6': 'Less than 10%',
    '7': 'No',
    '8': 'Sell everything',
    '10': 'Very safe (bonds/FDs)',
    '12': 'Never',
}


# ── Scoring behaviour ───────────────────────────────────────────────────────

def test_most_tolerant_answers_score_high():
    result = score_assessment(MOST_TOLERANT)
    assert result.score == 100
    assert result.category == 'High'
    assert result.answered_weight == TOTAL_WEIGHT


def test_least_tolerant_answers_score_low():
    result = score_assessment(LEAST_TOLERANT)
    # Q1's least-risk option is 0.15, not 0.0, so the floor is just above zero.
    assert result.score <= 2
    assert result.category == 'Low'


def test_answers_are_ordered_least_to_most_tolerant():
    """Picking the n-th option throughout must score monotonically upward.

    This is the check the replaced implementation could never have passed: its
    ladders pointed at option strings that no longer existed, so every rung
    scored the same zero.
    """
    scores = [score_assessment(_answers_at(i)).score for i in range(4)]
    assert scores == sorted(scores), scores
    assert scores[0] < scores[-1]


def test_knowledge_questions_score_in_reverse():
    """Q7 and Q12 list their best answer first, so the ladder must descend."""
    knows = dict(MOST_TOLERANT, **{'7': 'Yes, completely', '12': 'Yes, daily'})
    does_not = dict(MOST_TOLERANT, **{'7': 'No', '12': 'Never'})
    assert score_assessment(knows).score > score_assessment(does_not).score


def test_legacy_answers_from_older_clients_are_accepted_but_unscored():
    base = score_assessment(MOST_TOLERANT).score
    old = score_assessment(dict(MOST_TOLERANT, **{'11': 0, '14': 'Sinhala'}))
    assert old.score == base
    assert old.answers['11'] == 0
    assert old.knowledge_score is None


def test_unscored_answers_do_not_move_the_score():
    base = score_assessment(MOST_TOLERANT).score
    with_extras = score_assessment(dict(
        MOST_TOLERANT,
        **{'9': 'Daily', '11': 0, '13': ['Technology', 'Healthcare'], '14': 'Sinhala',
           '15': 'University', '101': 'A loan you gave the company'},
    ))
    assert with_extras.score == base


def test_preferred_language_and_sectors_are_surfaced():
    result = score_assessment(dict(
        MOST_TOLERANT,
        **{'13': ['Technology', 'Energy'], '14': 'Tamil'},
    ))
    assert result.preferred_language == 'Tamil'
    assert result.sectors == ['Technology', 'Energy']
    # And they are retained for storage.
    assert result.answers['14'] == 'Tamil'


def test_missing_optional_answers_are_absent_not_null():
    result = score_assessment(MOST_TOLERANT)
    assert result.preferred_language is None
    assert result.sectors == []


# ── Rejection behaviour: the point of the rewrite ────────────────────────────

def test_unknown_option_raises_instead_of_scoring_zero():
    bad = dict(MOST_TOLERANT, **{'2': 'Growth (Aggressive)'})
    with pytest.raises(AssessmentError) as exc:
        score_assessment(bad)
    # The message has to name the question, or the app cannot explain itself.
    assert 'Q2' in str(exc.value)


def test_legacy_four_field_payload_is_rejected_loudly():
    """The shape the old endpoint expected must now fail with a clear error."""
    with pytest.raises(AssessmentError):
        score_assessment({
            'goal': 'Wealth Growth',
            'risk': 'Speculative',
            'experience': 'Expert Investor',
            'savings': '> Rs. 100,000',
        })


def test_unknown_question_id_is_rejected():
    with pytest.raises(AssessmentError) as exc:
        score_assessment(dict(MOST_TOLERANT, **{'99': 'anything'}))
    assert '99' in str(exc.value)


def test_empty_submission_is_rejected():
    with pytest.raises(AssessmentError):
        score_assessment({})


def test_thin_submission_is_rejected():
    """Two answers renormalised to 100 would look like a confident score."""
    with pytest.raises(AssessmentError) as exc:
        score_assessment({'2': 'Very comfortable', '8': 'Buy more'})
    assert 'Not enough' in str(exc.value)


@pytest.mark.parametrize('value', [-1, 101, '50', True, None])
def test_slider_rejects_out_of_range_and_wrong_types(value):
    payload = dict(MOST_TOLERANT)
    payload['11'] = value
    if value is None:
        # None means "left blank"; the legacy slider carries no weight.
        assert score_assessment(payload).answered_weight == TOTAL_WEIGHT
        return
    with pytest.raises(AssessmentError):
        score_assessment(payload)


def test_multi_question_rejects_a_bare_string():
    with pytest.raises(AssessmentError):
        score_assessment(dict(MOST_TOLERANT, **{'13': 'Technology'}))


def test_multi_question_rejects_an_unknown_sector():
    with pytest.raises(AssessmentError):
        score_assessment(dict(MOST_TOLERANT, **{'13': ['Crypto']}))


def test_single_question_rejects_a_list():
    with pytest.raises(AssessmentError):
        score_assessment(dict(MOST_TOLERANT, **{'2': ['Very comfortable']}))


# ── Robustness of option matching ────────────────────────────────────────────

def test_dash_variants_still_match():
    """An en dash mangled to a hyphen must not silently change the score."""
    canonical = score_assessment(dict(MOST_TOLERANT, **{'3': '1–3 years'}))
    hyphenated = score_assessment(dict(MOST_TOLERANT, **{'3': '1-3 years'}))
    assert canonical.score == hyphenated.score
    # Whichever spelling arrives, the canonical one is what gets stored.
    assert hyphenated.answers['3'] == '1–3 years'


def test_case_and_whitespace_are_tolerated():
    result = score_assessment(dict(MOST_TOLERANT, **{'4': '  regularly '}))
    assert result.answers['4'] == 'Regularly'


def test_blank_answers_are_skipped_not_rejected():
    payload = dict(MOST_TOLERANT)
    payload['12'] = ''      # empty string
    payload['13'] = []      # empty multi-select
    result = score_assessment(payload)
    assert '12' not in result.answers
    assert result.answered_weight == TOTAL_WEIGHT - 6  # Q12's weight


def test_integer_question_keys_are_accepted():
    """JSON always gives string keys, but a Python caller may pass ints."""
    payload = {int(k): v for k, v in MOST_TOLERANT.items()}
    result = score_assessment(payload)
    assert result.score == 100
    assert set(result.answers) == set(MOST_TOLERANT)


# ── Category boundaries ─────────────────────────────────────────────────────

@pytest.mark.parametrize('score,expected', [
    (0, 'Low'), (39, 'Low'), (40, 'Medium'), (69, 'Medium'),
    (70, 'High'), (100, 'High'),
])
def test_category_boundaries(score, expected):
    assert category_for(score) == expected


def test_category_values_match_the_database_constraint():
    """risk_profiles has CHECK (category IN ('Low','Medium','High'))."""
    allowed = {'Low', 'Medium', 'High'}
    assert {category_for(s) for s in range(0, 101)} <= allowed


def test_score_never_leaves_zero_to_one_hundred():
    for i in range(4):
        score = score_assessment(_answers_at(i)).score
        assert 0 <= score <= 100


def test_min_coverage_boundary_is_enforced_not_approximated():
    """Exactly at the threshold must pass; one point under must not."""
    threshold = TOTAL_WEIGHT * rs.MIN_ANSWERED_WEIGHT_RATIO
    # Q2(13) + Q3(13) + Q8(17) + Q10(13) + Q12(6) = 62 >= 60
    ok = {'2': 'Very comfortable', '3': '5+ years', '8': 'Buy more',
          '10': 'High risk / High reward', '12': 'Yes, daily'}
    assert score_assessment(ok).answered_weight >= threshold
    # Drop Q12 (6 points) -> 56, under the floor.
    del ok['12']
    with pytest.raises(AssessmentError):
        score_assessment(ok)


# ── Knowledge checks ────────────────────────────────────────────────────────

RIGHT = {str(q.id): q.correct for q in rs.KNOWLEDGE}
WRONG = {str(q.id): next(o for o in q.options if o != q.correct) for q in rs.KNOWLEDGE}


def test_knowledge_score_is_marked_server_side():
    assert rs.KNOWLEDGE_TOTAL == 5
    assert score_assessment(dict(MOST_TOLERANT, **RIGHT)).knowledge_score == 5
    assert score_assessment(dict(MOST_TOLERANT, **WRONG)).knowledge_score == 0
    mixed = {**MOST_TOLERANT, **RIGHT, '104': WRONG['104'], '105': WRONG['105']}
    result = score_assessment(mixed)
    assert (result.knowledge_score, result.knowledge_total) == (3, 5)
    assert result.answers['104'] == WRONG['104']


def test_knowledge_answers_never_move_the_risk_score():
    base = score_assessment(MOST_TOLERANT).score
    assert score_assessment(dict(MOST_TOLERANT, **RIGHT)).score == base
    assert score_assessment(dict(LEAST_TOLERANT, **WRONG)).score == score_assessment(LEAST_TOLERANT).score


def test_knowledge_answer_must_be_one_of_its_options():
    with pytest.raises(AssessmentError) as exc:
        score_assessment(dict(MOST_TOLERANT, **{'102': 'correct'}))
    assert 'Q102' in str(exc.value)


def test_knowledge_only_submission_is_too_thin_for_a_risk_score():
    with pytest.raises(AssessmentError):
        score_assessment(RIGHT)
