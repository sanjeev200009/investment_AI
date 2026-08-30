"""Canonical risk-assessment instrument and its scoring rules.

Why this module exists
----------------------
``POST /me/risk-profile`` used to accept four fields — ``goal``, ``risk``,
``experience``, ``savings`` — and score them by comparing each against a
hard-coded string such as ``'Growth (Aggressive)'`` or ``'> Rs. 100,000'``.

The mobile wizard it was meant to serve no longer asks those questions. It asks
fifteen, and posts them keyed by question id (``{"1": "Retirement", ...}``). Two
separate failures followed from that drift:

1.  Every submission was rejected with HTTP 422, because ``goal``/``risk``/
    ``experience``/``savings`` were all missing. No risk profile was ever saved,
    so ``_risk_context()`` in app/services/agent/memory.py never had a risk
    tolerance to inject and FR-2's personalisation silently did nothing.
2.  Even had the shape matched, *none* of the wizard's option strings appear in
    the old scoring ladders. Every comparison would have fallen through to
    ``score += 0``, producing score 0 / category "Low" for every user
    regardless of their answers — a wrong number rather than an error.

The lesson from (2) drives the design here: a mismatch between the app's
options and the server's must **fail loudly**, never score zero. Unknown
question ids and unrecognised option strings raise :class:`AssessmentError`,
which the router turns into a 422 the app surfaces to the user.

The question bank below is the single source of truth for the instrument. It is
also served over ``GET /me/assessment/questions`` so the app can be driven from
it, and so the instrument is documentable for the evaluation chapter.

Scoring model
-------------
Each question carries a weight; the weights of the scored questions sum to 100
(asserted in tests). Each answer maps to a fraction in ``[0.0, 1.0]`` of that
weight, where 1.0 is the most risk-tolerant response. The final score is the
weighted mean over *answered* scored questions, rescaled to 0-100, so a partial
response is still comparable to a complete one.

Questions 9, 13, 14 and 15 carry weight 0. They are collected for other
purposes — Q13 sector interest and Q14 language preference feed recommendation
and multilingual behaviour — but they are not risk indicators, and Q9
(monitoring frequency) points in no clean direction: frequent checking can mean
either anxiety or active trading.

Option strings are matched after light normalisation — Unicode dashes folded to
``-``, whitespace collapsed, case ignored — so a transcoding accident to the en
dashes in "1–3 years" cannot break scoring. Anything that still fails to match
is reported, not scored as zero, and the canonical spelling is what gets stored.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

# Fraction ladders for monotonically ordered four-option questions.
_ASC4 = (0.0, 0.34, 0.67, 1.0)
_DESC4 = (1.0, 0.67, 0.34, 0.0)

# En dash, em dash and minus sign all show up in hand-edited option lists.
_DASHES = str.maketrans({'–': '-', '—': '-', '−': '-'})


def _norm(value: str) -> str:
    """Fold an option string to a form that survives editor transcoding."""
    return ' '.join(value.translate(_DASHES).split()).casefold()


class AssessmentError(ValueError):
    """Raised when a submission does not match the canonical instrument."""


@dataclass(frozen=True)
class Question:
    id: int
    text: str
    kind: str  # 'single' | 'multi' | 'slider'
    options: tuple[str, ...] = ()
    weight: int = 0
    # option -> fraction of `weight`, only for scored 'single' questions.
    fractions: Mapping[str, float] = field(default_factory=dict)

    @property
    def scored(self) -> bool:
        return self.weight > 0


def _single(
    qid: int,
    text: str,
    options: Sequence[str],
    weight: int = 0,
    ladder: Sequence[float] | None = None,
    fractions: Mapping[str, float] | None = None,
) -> Question:
    """Build a single-choice question.

    Pass ``ladder`` for a monotonic question (fractions align with option
    order) or ``fractions`` for one whose options have no natural order.
    """
    opts = tuple(options)
    if weight and fractions is None:
        if ladder is None or len(ladder) != len(opts):
            raise AssertionError(f'Q{qid}: ladder must cover every option')
        fractions = dict(zip(opts, ladder))
    return Question(
        id=qid,
        text=text,
        kind='single',
        options=opts,
        weight=weight,
        fractions=dict(fractions or {}),
    )


QUESTIONS: tuple[Question, ...] = (
    # Investment objective. Not monotonic, so the fractions are explicit: a
    # dated liability (a house deposit) has the least capacity for risk, open
    # ended wealth growth the most.
    _single(
        1,
        'What is your primary investment goal?',
        ('Retirement', 'Wealth Growth', 'Major Purchase (e.g., home)', 'Income Generation'),
        weight=5,
        fractions={
            'Wealth Growth': 1.0,
            'Retirement': 0.6,
            'Income Generation': 0.35,
            'Major Purchase (e.g., home)': 0.15,
        },
    ),
    _single(
        2,
        'How comfortable are you with potential short-term fluctuations in your investment value?',
        (
            'Not comfortable at all',
            'Slightly comfortable',
            'Moderately comfortable',
            'Very comfortable',
        ),
        weight=12,
        ladder=_ASC4,
    ),
    _single(
        3,
        'How long do you plan to keep your investments?',
        ('Less than 1 year', '1–3 years', '3–5 years', '5+ years'),
        weight=12,
        ladder=_ASC4,
    ),
    _single(
        4,
        'Have you invested in stocks before?',
        ('Never', 'Once or twice', 'Occasionally', 'Regularly'),
        weight=8,
        ladder=_ASC4,
    ),
    _single(
        5,
        'What is your monthly income range (LKR)?',
        (
            'Below 50,000',
            '50,000–100,000',
            '100,000–250,000',
            'Above 250,000',
        ),
        weight=8,
        ladder=_ASC4,
    ),
    _single(
        6,
        'How much of your savings are you willing to invest?',
        ('Less than 10%', '10–25%', '25–50%', 'More than 50%'),
        weight=10,
        ladder=_ASC4,
    ),
    # Knowledge check. Options run best-understanding first, so the ladder
    # descends — the bug this module replaces got exactly this kind of
    # direction wrong and no one could see it.
    _single(
        7,
        'Do you understand what a P/E ratio is?',
        ('Yes, completely', 'Somewhat', "I've heard of it", 'No'),
        weight=4,
        ladder=_DESC4,
    ),
    # Behavioural reaction to a drawdown: the strongest single predictor of
    # real risk tolerance, hence the heaviest weight.
    _single(
        8,
        'How would you react if your portfolio dropped 20% in one month?',
        ('Sell everything', 'Sell some', 'Hold', 'Buy more'),
        weight=15,
        ladder=_ASC4,
    ),
    # Monitoring frequency is collected but not scored: checking hourly can
    # signal either anxiety (low tolerance) or active trading (high).
    _single(
        9,
        'How often do you want to check your investments?',
        ('Multiple times a day', 'Daily', 'Weekly', 'Monthly'),
    ),
    _single(
        10,
        'What is your preferred investment style?',
        (
            'Very safe (bonds/FDs)',
            'Balanced',
            'Growth-focused',
            'High risk / High reward',
        ),
        weight=12,
        ladder=_ASC4,
    ),
    Question(
        id=11,
        text='What is your risk tolerance?',
        kind='slider',
        weight=10,
    ),
    _single(
        12,
        'Do you follow financial news regularly?',
        ('Yes, daily', 'Few times a week', 'Rarely', 'Never'),
        weight=4,
        ladder=_DESC4,
    ),
    Question(
        id=13,
        text='Which sectors interest you most?',
        kind='multi',
        options=(
            'Banking & Finance',
            'Technology',
            'Healthcare',
            'Energy',
            'Consumer Goods',
        ),
    ),
    Question(
        id=14,
        text='What is your preferred language for investment guidance?',
        kind='single',
        options=('English', 'Sinhala', 'Tamil'),
    ),
    Question(
        id=15,
        text='How did you hear about InvestAI?',
        kind='single',
        options=('Social Media', 'Friend/Family', 'University', 'Other'),
    ),
)

_BY_ID: dict[int, Question] = {q.id: q for q in QUESTIONS}

# qid -> {normalised option: canonical option}. Built once so lookups are exact
# on the normalised form while what we store stays the canonical spelling.
_CANONICAL: dict[int, dict[str, str]] = {
    q.id: {_norm(opt): opt for opt in q.options} for q in QUESTIONS
}

TOTAL_WEIGHT: int = sum(q.weight for q in QUESTIONS)

# A submission covering less than this share of the scored weight is rejected:
# renormalising over a handful of answers produces a confident-looking score
# from almost no evidence.
MIN_ANSWERED_WEIGHT_RATIO = 0.6

# Category thresholds. Deliberately conservative — a respondent who picks the
# third of four options throughout lands at ~67 and is classed Medium, not
# High. Under-stating risk tolerance is the safer error for a tool aimed at
# first-time investors.
HIGH_THRESHOLD = 70
MEDIUM_THRESHOLD = 40


@dataclass(frozen=True)
class ScoredAssessment:
    score: int
    category: str
    answered_weight: int
    total_weight: int
    # Normalised answers, keyed by question id as a string, safe to store.
    answers: dict[str, Any]
    preferred_language: str | None
    sectors: list[str]


def category_for(score: int) -> str:
    if score >= HIGH_THRESHOLD:
        return 'High'
    if score >= MEDIUM_THRESHOLD:
        return 'Medium'
    return 'Low'


def _parse_qid(raw: Any) -> int:
    try:
        qid = int(raw)
    except (TypeError, ValueError):
        raise AssessmentError(f'Question key {raw!r} is not a question number.')
    if qid not in _BY_ID:
        raise AssessmentError(
            f'Unknown question id {qid}. Valid ids are 1-{max(_BY_ID)}.'
        )
    return qid


def _canonical_option(q: Question, answer: Any) -> str:
    """Resolve `answer` to one of `q.options`, or raise."""
    if not isinstance(answer, str):
        raise AssessmentError(
            f'Q{q.id} expects one of its option strings, got {answer!r}.'
        )
    canonical = _CANONICAL[q.id].get(_norm(answer))
    if canonical is None:
        raise AssessmentError(
            f'Q{q.id}: {answer!r} is not one of the options for this question.'
        )
    return canonical


def _fraction_for(q: Question, answer: Any) -> tuple[float, Any]:
    """(fraction of `q.weight` earned, canonical answer to store)."""
    if q.kind == 'slider':
        if isinstance(answer, bool) or not isinstance(answer, (int, float)):
            raise AssessmentError(
                f'Q{q.id} expects a number between 0 and 100, got {answer!r}.'
            )
        if not 0 <= answer <= 100:
            raise AssessmentError(
                f'Q{q.id} must be between 0 and 100, got {answer!r}.'
            )
        return float(answer) / 100.0, answer

    canonical = _canonical_option(q, answer)
    return q.fractions[canonical], canonical


def _validate_unscored(q: Question, answer: Any) -> Any:
    """Check an unscored answer is still a legitimate option; return it."""
    if q.kind == 'multi':
        if not isinstance(answer, list):
            raise AssessmentError(f'Q{q.id} expects a list of options.')
        return [_canonical_option(q, a) for a in answer]
    if q.kind == 'single':
        return _canonical_option(q, answer)
    return answer


def score_assessment(raw_answers: Mapping[Any, Any]) -> ScoredAssessment:
    """Validate and score a wizard submission.

    Raises :class:`AssessmentError` on any answer that does not belong to the
    canonical instrument, or when too little of the scored weight is covered.
    Never silently contributes zero for an answer it does not recognise.
    """
    if not isinstance(raw_answers, Mapping) or not raw_answers:
        raise AssessmentError('No assessment answers were submitted.')

    normalised: dict[str, Any] = {}
    earned = 0.0
    answered_weight = 0

    for raw_key, answer in raw_answers.items():
        qid = _parse_qid(raw_key)
        q = _BY_ID[qid]
        if answer is None or (isinstance(answer, (str, list)) and len(answer) == 0):
            continue  # left blank; ignore rather than reject
        if q.scored:
            fraction, canonical = _fraction_for(q, answer)
            earned += fraction * q.weight
            answered_weight += q.weight
            normalised[str(qid)] = canonical
        else:
            normalised[str(qid)] = _validate_unscored(q, answer)

    if answered_weight < TOTAL_WEIGHT * MIN_ANSWERED_WEIGHT_RATIO:
        raise AssessmentError(
            'Not enough of the assessment was answered to produce a reliable '
            f'risk score ({answered_weight} of {TOTAL_WEIGHT} points covered). '
            'Please answer the remaining questions.'
        )

    score = round(earned / answered_weight * 100)
    score = min(max(score, 0), 100)

    sectors = normalised.get('13') or []
    return ScoredAssessment(
        score=score,
        category=category_for(score),
        answered_weight=answered_weight,
        total_weight=TOTAL_WEIGHT,
        answers=normalised,
        preferred_language=normalised.get('14'),
        sectors=list(sectors),
    )


def question_bank() -> list[dict[str, Any]]:
    """The instrument as plain data, for ``GET /me/assessment/questions``."""
    return [
        {
            'id': q.id,
            'text': q.text,
            'type': q.kind,
            'options': list(q.options),
            'weight': q.weight,
        }
        for q in QUESTIONS
    ]
