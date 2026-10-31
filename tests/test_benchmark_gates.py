import pytest
import copy

from solver.benchmark_gates import (
    evaluate_gates,
    render_gates,
)


def passing_report() -> dict:
    phase = {
        "rate": 0.99,
        "near_uniform_played": 0.05,
    }

    match = {
        "utility": 0.5,
        "standard_error": 0.1,
        "max_zero_sum_error": 0.0,
    }

    return {
        "parameters": {
            "preset": "standard",
            "overridden": [],
        },
        "static": {
            "invalid_strategies": 0,
        },
        "coverage": {
            "action_space_mismatches": 0,
            "overall": {"rate": 0.98},
            "by_phase": {
                "predraw_betting": dict(phase),
                "draw": dict(phase),
                "postdraw_betting": dict(phase),
            },
            "first_miss": {"rate": 0.05},
            "self_play": {
                "max_zero_sum_error": 1e-15,
            },
        },
        "baselines": {
            "opponents": {
                "uniform": dict(match),
                "call_station": dict(match),
            },
        },
        "sbr": {
            "grouping": "coarse",
            "runs": {
                "seat_0": [
                    {"gain": 0.1, "gain_standard_error": 0.3},
                    {"gain": 0.3, "gain_standard_error": 0.3},
                ],
                "seat_1": [
                    {"gain": 0.2, "gain_standard_error": 0.3},
                    {"gain": 0.2, "gain_standard_error": 0.3},
                ],
            },
        },
    }


def statuses(
    report: dict,
) -> dict:
    return {
        gate["id"]: gate["status"]
        for gate in evaluate_gates(report)[
            "gates"
        ]
    }


def test_passing_report_passes() -> None:
    gates = evaluate_gates(
        passing_report()
    )

    assert gates["verdict"] == "PASS"
    assert gates["benchmark_run"] is True
    assert statuses(passing_report())["Q5"] == "n/a"
    assert render_gates(gates)[0].endswith("PASS")


def test_each_hard_gate_fails_the_verdict() -> None:
    for mutate, gate_id in (
        (
            lambda r: r["static"].update(
                invalid_strategies=1
            ),
            "H1",
        ),
        (
            lambda r: r["coverage"].update(
                action_space_mismatches=3
            ),
            "H2",
        ),
        (
            lambda r: r["baselines"]["opponents"][
                "uniform"
            ].update(max_zero_sum_error=1e-6),
            "H3",
        ),
    ):
        report = passing_report()
        mutate(report)

        assert statuses(report)[gate_id] == "fail"
        assert evaluate_gates(report)[
            "verdict"
        ] == "FAIL"


def test_quality_thresholds() -> None:
    report = passing_report()
    report["coverage"]["by_phase"]["draw"][
        "rate"
    ] = 0.949
    assert statuses(report)["Q1"] == "fail"

    report = passing_report()
    report["coverage"]["first_miss"]["rate"] = 0.11
    assert statuses(report)["Q2"] == "fail"

    report = passing_report()
    report["coverage"]["by_phase"]["draw"][
        "near_uniform_played"
    ] = 0.2
    gate = [
        gate
        for gate in evaluate_gates(report)["gates"]
        if gate["id"] == "Q3"
    ][0]
    assert gate["status"] == "fail"
    assert gate["failing_phases"] == ["draw"]


def test_q4_is_a_not_lose_gate() -> None:
    # A small win, or a loss inside 2 SE, passes:
    # an equilibrium only guarantees >= 0.
    report = passing_report()
    report["baselines"]["opponents"]["call_station"][
        "utility"
    ] = -0.19
    assert statuses(report)["Q4"] == "pass"

    report["baselines"]["opponents"]["call_station"][
        "utility"
    ] = -0.21
    assert statuses(report)["Q4"] == "fail"


def test_previous_gate() -> None:
    report = passing_report()
    report["previous"] = {
        "compatible": False,
    }
    assert statuses(report)["Q5"] == "n/a"

    report["previous"] = {
        "compatible": True,
        "head_to_head": {
            "utility": -0.5,
            "standard_error": 0.1,
            "max_zero_sum_error": 0.0,
        },
    }
    assert statuses(report)["Q5"] == "fail"


def test_missing_section_is_incomplete_and_quick_is_not_benchmark() -> None:
    report = passing_report()
    del report["static"]
    assert evaluate_gates(report)[
        "verdict"
    ] == "INCOMPLETE"

    report = copy.deepcopy(passing_report())
    report["parameters"]["preset"] = "quick"
    gates = evaluate_gates(report)
    assert gates["benchmark_run"] is False
    assert gates["note"]


def test_q6_sbr_gate() -> None:
    report = passing_report()

    gate = [
        gate
        for gate in evaluate_gates(report)["gates"]
        if gate["id"] == "Q6"
    ][0]

    assert gate["status"] == "pass"
    assert gate["value"]["mean_gain"] == pytest.approx(0.2)
    assert gate["value"]["lower_bound"] == pytest.approx(-0.4)

    # v1-like numbers: 1.57 - 2 * 0.37 > 0.2.
    for runs in report["sbr"]["runs"].values():
        for run in runs:
            run["gain"] = 1.57
            run["gain_standard_error"] = 0.37

    assert statuses(report)["Q6"] == "fail"
    assert evaluate_gates(report)["verdict"] == "FAIL"

    # Just at the tolerance passes.
    for runs in report["sbr"]["runs"].values():
        for run in runs:
            run["gain"] = 0.94
            run["gain_standard_error"] = 0.37

    assert statuses(report)["Q6"] == "pass"


def test_q6_not_applicable_to_per_state_sbr() -> None:
    report = passing_report()
    report["sbr"]["grouping"] = "none"
    assert statuses(report)["Q6"] == "n/a"

    del report["sbr"]["grouping"]
    assert statuses(report)["Q6"] == "n/a"

    del report["sbr"]
    assert statuses(report)["Q6"] == "missing"
