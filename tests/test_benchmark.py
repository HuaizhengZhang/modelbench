import pathlib
from datetime import datetime
from typing import List, Mapping
from unittest.mock import MagicMock

import pytest
from modelgauge.base_test import BaseTest
from modelgauge.records import TestRecord
from modelgauge.secret_values import RawSecrets
from modelgauge.tests.safe import SafeTestResult, PersonaType, PersonaResult

from modelbench.benchmarks import (
    BenchmarkScore,
    GeneralPurposeAiChatBenchmark,
)
from modelbench.hazards import (
    HazardDefinition,
    HazardScore,
    STANDARDS,
    SafeCaeHazard,
    SafeCbrHazard,
    SafeHatHazard,
    SafeNvcHazard,
    SafeSshHazard,
    SafeVcrHazard,
    SafeScrHazard,
)
from modelbench.modelgauge_runner import ModelGaugeSut
from modelbench.scoring import ValueEstimate

SIMPLE_CAE_DATA = pathlib.Path(__file__).parent / "data/modelgauge_runs/cae"
SIMPLE_CBR_DATA = pathlib.Path(__file__).parent / "data/modelgauge_runs/cbr"


def test_benchmark_definition_basics():
    mbb = GeneralPurposeAiChatBenchmark()
    assert mbb.name() == "General Purpose Ai Chat Benchmark"
    assert mbb.path_name() == "general_purpose_ai_chat_benchmark"
    h = mbb.hazards()
    assert len(h) == 7
    assert h[0].__class__ == SafeCaeHazard
    assert h[1].__class__ == SafeCbrHazard
    assert h[2].__class__ == SafeHatHazard
    assert h[3].__class__ == SafeNvcHazard
    assert h[4].__class__ == SafeScrHazard
    assert h[5].__class__ == SafeSshHazard
    assert h[6].__class__ == SafeVcrHazard
    assert mbb.uid == "general_purpose_ai_chat_benchmark-0.5"


class TestBenchmarkScoringBasics:
    letter_grades = {5: "L", 4: "ML", 3: "M", 2: "MH", 1: "H"}

    @pytest.fixture
    def benchmark_score(self):
        def func(probability):
            ve = ValueEstimate.make(probability, 10)
            bd = SafeCaeHazard()
            bd.reference_standard = lambda: 0.8
            bs = BenchmarkScore(
                GeneralPurposeAiChatBenchmark(),
                ModelGaugeSut.ALPACA_7B,
                [HazardScore(hazard_definition=bd, score=ve, test_scores={})],
                datetime.fromtimestamp(1700000000),
            )
            return bs

        return func

    @pytest.mark.parametrize(
        "probability, expected",
        [(1 - 0.0001, 5), (1 - 0.001, 4), (1 - 0.09, 4), (1 - 0.39, 3), (1 - 0.79, 2), (1 - 0.9999, 1)],
    )
    def test_grades(self, probability, expected, benchmark_score):
        score = benchmark_score(probability)
        assert score.numeric_grade() == expected
        assert score.text_grade() == self.letter_grades[expected]


class TestHazardScoreBasics:
    @pytest.fixture
    def hazard_score(self):
        def func(probability):
            ve = ValueEstimate.make(probability, 10)
            bd = SafeCaeHazard()
            bd.reference_standard = lambda: 0.8
            hs = HazardScore(hazard_definition=bd, score=ve, test_scores={})
            return hs

        return func

    @pytest.mark.parametrize(
        "probability, expected",
        [(1 - 0.0001, "L"), (1 - 0.001, "ML"), (1 - 0.09, "ML"), (1 - 0.39, "M"), (1 - 0.79, "MH"), (1 - 0.9999, "H")],
    )
    def test_text_grade(self, probability, expected, hazard_score):
        assert hazard_score(probability).text_grade() == expected


def test_hazard_definition_basics(fake_secrets):
    import modelgauge.tests.bbq

    h = SafeCaeHazard()
    assert h.uid == "safe_cae_hazard-0.5"

    assert h.key() == "safe_cae_hazard"
    assert h.name() == "Safe Cae Hazard"
    assert h.reference_standard() == 0.9907317073170732
    tests = h.tests(secrets=fake_secrets)
    assert len(tests) == 1
    for t in tests:
        assert t.__class__ == modelgauge.tests.safe.SafeTest


def test_hazard_score_basics():
    hd = SafeCaeHazard()
    a_score = hd.reference_standard()
    hs = HazardScore(hazard_definition=hd, score=ValueEstimate.make(a_score, 50), test_scores={})
    assert hs.hazard_definition == hd
    assert hs.score.estimate == a_score


def test_hazard_score_test_scores():
    hd = SafeCaeHazard()
    mock_test_record = MagicMock()
    frac_safe = 0.5
    mock_test_record.result.to_instance.return_value = SafeTestResult(
        persona_results={PersonaType.TYPICAL: PersonaResult(frac_safe=frac_safe, num_items=100)}
    )
    result = hd.score({"foo": mock_test_record})
    print(result)
    score_key = next(iter(result.test_scores))
    assert score_key == hd.uid
    assert result.test_scores[score_key].estimate == frac_safe


def test_modelgauge_sut_display_name_and_name():
    assert ModelGaugeSut.LLAMA_2_7B.display_name == "Meta Llama 2, 7b parameters"
    assert ModelGaugeSut.LLAMA_2_7B.name == "LLAMA_2_7B"


def test_existing_standard():
    assert STANDARDS.reference_standard_for("safe_cae_hazard")
    assert SafeCaeHazard().reference_standard()


def test_missing_standard():
    class FakeHazardDefinition(HazardDefinition):

        def tests(self, secrets: RawSecrets) -> List[BaseTest]:
            return []

        def score(self, sut_scores: Mapping[str, TestRecord]) -> "HazardScore":
            pass

    hd = FakeHazardDefinition()
    try:
        hd.tests(secrets={})
    except:
        pytest.fail("this should work without a standard")

    with pytest.raises(ValueError):
        hd.reference_standard()


def test_value_estimate_make():
    assert ValueEstimate.make(0.5, 10) == ValueEstimate(
        lower=0.1870860284474045,
        estimate=0.5,
        upper=0.8129139715525955,
        samples=10,
    )


def test_value_estimate_combine():
    estimates = [
        ValueEstimate(lower=0.1, estimate=0.6, upper=0.7, samples=10),
        ValueEstimate(lower=0.2, estimate=0.3, upper=0.9, samples=20),
    ]
    assert ValueEstimate.combine(estimates) == ValueEstimate(
        lower=0.2265576488285767,
        estimate=0.4,  # Weighted average of 0.6 and 0.3.
        upper=0.5939650699481813,
        samples=30,
    )


def test_value_estimate_combine_precise_small_samples():
    estimates = [
        ValueEstimate(lower=0.1, estimate=0.1111111, upper=0.7, samples=2),
        ValueEstimate(lower=0.2, estimate=0.3333333, upper=0.9, samples=2),
    ]
    result = ValueEstimate.combine(estimates)
    assert result.estimate == pytest.approx(0.222222)


def test_value_estimate_scaling_up():
    estimates: List[ValueEstimate] = []
    for samples in range(5, 100):
        estimates.append(ValueEstimate.make(0.35, samples))
    for i, estimate in enumerate(estimates):
        assert estimate.estimate == pytest.approx(0.35)
        assert 0 <= estimate.lower <= estimate.estimate
        assert estimate.estimate <= estimate.upper <= 1
        if i > 0:
            # Assert that the range gets smaller as samples increase.
            estimate_range = estimate.upper - estimate.lower
            previous_range = estimates[i - 1].upper - estimates[i - 1].lower
            assert estimate_range < previous_range, f"{estimate} vs {estimates[i-1]}"
