from app.core.policy_engine import evaluate_policy


def test_policy_passes_small_delta_with_high_coverage():
    result = evaluate_policy(
        monthly={"delta": 25.0},
        annual={"delta": 300.0},
        summary={"total_resources": 4, "exact_resources": 3, "unestimated_resources": 0},
        findings=[],
    )

    assert result["status"] == "pass"
    assert result["blocking_reasons"] == []
    assert result["warnings"] == []


def test_policy_fails_large_monthly_delta():
    result = evaluate_policy(
        monthly={"delta": 750.0},
        annual={"delta": 9000.0},
        summary={"total_resources": 2, "exact_resources": 2, "unestimated_resources": 0},
        findings=[],
    )

    assert result["status"] == "fail"
    assert any("Monthly cost increase" in reason for reason in result["blocking_reasons"])
    assert any("Annual cost increase" in reason for reason in result["blocking_reasons"])


def test_policy_warns_on_low_exact_coverage():
    result = evaluate_policy(
        monthly={"delta": 0.0},
        annual={"delta": 0.0},
        summary={"total_resources": 10, "exact_resources": 2, "unestimated_resources": 0},
        findings=[],
    )

    assert result["status"] == "warn"
    assert any("exact pricing" in warning for warning in result["warnings"])


def test_policy_fails_on_critical_finding():
    result = evaluate_policy(
        monthly={"delta": 0.0},
        annual={"delta": 0.0},
        summary={"total_resources": 1, "exact_resources": 1, "unestimated_resources": 0},
        findings=[
            {
                "resource_address": "aws_instance.root",
                "severity": "critical",
                "evidence": "Critical cost control violation.",
            }
        ],
    )

    assert result["status"] == "fail"
    assert any("aws_instance.root" in reason for reason in result["blocking_reasons"])


def test_policy_accepts_custom_threshold_override():
    result = evaluate_policy(
        monthly={"delta": 750.0},
        annual={"delta": 9000.0},
        summary={"total_resources": 2, "exact_resources": 2, "unestimated_resources": 0},
        findings=[],
        policy={
            "monthly_delta_threshold_usd": 1000.0,
            "annual_delta_threshold_usd": 12000.0,
        },
    )

    assert result["status"] == "pass"


def test_policy_warns_when_unestimated_resource_limit_is_exceeded():
    result = evaluate_policy(
        monthly={"delta": 0.0},
        annual={"delta": 0.0},
        summary={"total_resources": 12, "exact_resources": 10, "unestimated_resources": 6},
        findings=[],
    )

    assert result["status"] == "warn"
    assert any("could not be priced" in warning for warning in result["warnings"])
