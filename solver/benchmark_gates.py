"""
A2 benchmark gates (approved day48, Q4 revised day49).

A pure function of an evaluate_checkpoint report dict, so any
saved report can be re-gated without rerunning it. Bump
GATES_VERSION whenever a gate or threshold changes.

Hard gates (correctness): if one fails, no other number in the
report can be trusted.

Quality gates: thresholds from docs/A2_DESIGN.md section 10.

Q4 is a necessary condition for an equilibrium, not a measure
of strength: in this two-player zero-sum game, played in the
duplicate (seat-swapped) format, a Nash equilibrium strategy
earns at least the game value, 0, against every opponent
strategy. The fixed opponents use only actions inside the
solver's abstraction, so the guarantee applies to them. A
significant loss therefore proves the profile is exploitable;
a win, however large, says little about how close it is to
equilibrium. The margin is reported as information only.

The SBR proxy is reported but not gated (see A2_DESIGN 11).
"""

GATES_VERSION = 1

BENCHMARK_PRESET = "standard"

ZERO_SUM_TOLERANCE = 1e-9

COVERAGE_OVERALL_MIN = 0.97
COVERAGE_PHASE_MIN = 0.95
DEALS_WITH_MISS_MAX = 0.10
NEAR_UNIFORM_PLAYED_MAX = 0.10
NOT_LOSE_STANDARD_ERRORS = 2.0

PASS = "pass"
FAIL = "fail"
NOT_APPLICABLE = "n/a"
MISSING = "missing"
EXTERNAL = "external"


def evaluate_gates(
    report: dict,
) -> dict:
    gates = [
        _invalid_strategies(report),
        _action_space(report),
        _zero_sum(report),
        {
            "id": "H4",
            "kind": "hard",
            "description": (
                "Same checkpoint and arguments "
                "give an identical report"
            ),
            "status": EXTERNAL,
            "detail": (
                "checked by evaluate_checkpoint "
                "--compare on two runs"
            ),
        },
        _coverage(report),
        _deals_with_miss(report),
        _near_uniform_played(report),
        _baselines(report),
        _previous(report),
    ]

    parameters = report.get(
        "parameters",
        {},
    )

    benchmark_run = (
        parameters.get("preset")
        == BENCHMARK_PRESET
        and not parameters.get(
            "overridden"
        )
    )

    statuses = [
        gate["status"]
        for gate in gates
    ]

    if MISSING in statuses:
        verdict = "INCOMPLETE"
    elif FAIL in statuses:
        verdict = "FAIL"
    else:
        verdict = "PASS"

    return {
        "gates_version": GATES_VERSION,
        "benchmark_run": benchmark_run,
        "verdict": verdict,
        "note": (
            None
            if benchmark_run
            else (
                "Not a benchmark run (preset "
                f"must be {BENCHMARK_PRESET!r} "
                "with no overrides); the verdict "
                "is indicative only."
            )
        ),
        "gates": gates,
    }


def _gate(
    gate_id: str,
    kind: str,
    description: str,
    status: str,
    **detail,
) -> dict:
    return {
        "id": gate_id,
        "kind": kind,
        "description": description,
        "status": status,
    } | detail


def _status(
    ok: bool,
) -> str:
    return PASS if ok else FAIL


def _invalid_strategies(
    report: dict,
) -> dict:
    description = (
        "No NaN, inf, negative or "
        "non-normalized stored strategy"
    )

    static = report.get("static")

    if static is None:
        return _gate(
            "H1",
            "hard",
            description,
            MISSING,
        )

    value = static["invalid_strategies"]

    return _gate(
        "H1",
        "hard",
        description,
        _status(value == 0),
        value=value,
        threshold="== 0",
    )


def _action_space(
    report: dict,
) -> dict:
    description = (
        "Stored action sets equal the rebuilt "
        "legal actions at every played state"
    )

    coverage = report.get("coverage")

    if coverage is None:
        return _gate(
            "H2",
            "hard",
            description,
            MISSING,
        )

    value = coverage[
        "action_space_mismatches"
    ]

    return _gate(
        "H2",
        "hard",
        description,
        _status(value == 0),
        value=value,
        threshold="== 0",
    )


def _zero_sum(
    report: dict,
) -> dict:
    description = (
        "Every simulated deal is zero-sum"
    )

    errors = []

    coverage = report.get("coverage")

    if coverage is not None:
        errors.append(
            coverage["self_play"][
                "max_zero_sum_error"
            ]
        )

    for match in report.get(
        "baselines",
        {},
    ).get(
        "opponents",
        {},
    ).values():
        errors.append(
            match["max_zero_sum_error"]
        )

    head_to_head = report.get(
        "previous",
        {},
    ).get("head_to_head")

    if head_to_head is not None:
        errors.append(
            head_to_head[
                "max_zero_sum_error"
            ]
        )

    if not errors:
        return _gate(
            "H3",
            "hard",
            description,
            MISSING,
        )

    value = max(errors)

    return _gate(
        "H3",
        "hard",
        description,
        _status(
            value <= ZERO_SUM_TOLERANCE
        ),
        value=value,
        threshold=f"<= {ZERO_SUM_TOLERANCE:g}",
    )


def _coverage(
    report: dict,
) -> dict:
    description = (
        "Self-play coverage (button 0): "
        f"overall >= {COVERAGE_OVERALL_MIN:.0%}, "
        f"every phase >= {COVERAGE_PHASE_MIN:.0%}"
    )

    coverage = report.get("coverage")

    if coverage is None:
        return _gate(
            "Q1",
            "quality",
            description,
            MISSING,
        )

    overall = coverage["overall"]["rate"]

    phases = {
        phase: stats["rate"]
        for phase, stats in coverage[
            "by_phase"
        ].items()
    }

    failing = [
        phase
        for phase, rate in phases.items()
        if rate is None
        or rate < COVERAGE_PHASE_MIN
    ]

    ok = (
        overall is not None
        and overall >= COVERAGE_OVERALL_MIN
        and not failing
    )

    return _gate(
        "Q1",
        "quality",
        description,
        _status(ok),
        value={
            "overall": overall,
            "by_phase": phases,
        },
        failing_phases=failing,
    )


def _deals_with_miss(
    report: dict,
) -> dict:
    description = (
        "Deals with any missing decision "
        f"<= {DEALS_WITH_MISS_MAX:.0%}"
    )

    coverage = report.get("coverage")

    if coverage is None:
        return _gate(
            "Q2",
            "quality",
            description,
            MISSING,
        )

    value = coverage["first_miss"]["rate"]

    return _gate(
        "Q2",
        "quality",
        description,
        _status(
            value is not None
            and value <= DEALS_WITH_MISS_MAX
        ),
        value=value,
    )


def _near_uniform_played(
    report: dict,
) -> dict:
    description = (
        "Played decisions using a near-uniform "
        "stored strategy, every phase "
        f"<= {NEAR_UNIFORM_PLAYED_MAX:.0%}"
    )

    coverage = report.get("coverage")

    if coverage is None:
        return _gate(
            "Q3",
            "quality",
            description,
            MISSING,
        )

    phases = {
        phase: stats.get(
            "near_uniform_played"
        )
        for phase, stats in coverage[
            "by_phase"
        ].items()
    }

    failing = [
        phase
        for phase, rate in phases.items()
        if rate is None
        or rate > NEAR_UNIFORM_PLAYED_MAX
    ]

    return _gate(
        "Q3",
        "quality",
        description,
        _status(not failing),
        value=phases,
        failing_phases=failing,
    )


def _baselines(
    report: dict,
) -> dict:
    description = (
        "Does not lose to any fixed opponent "
        f"(utility >= -{NOT_LOSE_STANDARD_ERRORS:g} SE). "
        "Necessary for equilibrium; the "
        "winning margin is information only"
    )

    baselines = report.get("baselines")

    if baselines is None:
        return _gate(
            "Q4",
            "quality",
            description,
            MISSING,
        )

    values = {}
    failing = []

    for (
        name,
        match,
    ) in baselines["opponents"].items():
        lower = (
            -NOT_LOSE_STANDARD_ERRORS
            * match["standard_error"]
        )

        values[name] = {
            "utility": match["utility"],
            "standard_error": (
                match["standard_error"]
            ),
        }

        if match["utility"] < lower:
            failing.append(name)

    return _gate(
        "Q4",
        "quality",
        description,
        _status(not failing),
        value=values,
        failing_opponents=failing,
    )


def _previous(
    report: dict,
) -> dict:
    description = (
        "Does not lose to the previous "
        "compatible checkpoint "
        f"(utility >= -{NOT_LOSE_STANDARD_ERRORS:g} SE)"
    )

    previous = report.get("previous")

    if previous is None:
        return _gate(
            "Q5",
            "quality",
            description,
            NOT_APPLICABLE,
            detail="no --previous given",
        )

    if not previous["compatible"]:
        return _gate(
            "Q5",
            "quality",
            description,
            NOT_APPLICABLE,
            detail=(
                "previous checkpoint has a "
                "different game config"
            ),
        )

    match = previous["head_to_head"]

    return _gate(
        "Q5",
        "quality",
        description,
        _status(
            match["utility"]
            >= -NOT_LOSE_STANDARD_ERRORS
            * match["standard_error"]
        ),
        value={
            "utility": match["utility"],
            "standard_error": (
                match["standard_error"]
            ),
        },
    )


def render_gates(
    gates: dict,
) -> list[str]:
    lines = [
        f"GATES v{gates['gates_version']}: "
        f"{gates['verdict']}",
    ]

    if gates["note"]:
        lines.append(
            f"  ({gates['note']})"
        )

    for gate in gates["gates"]:
        extra = ""

        for key in (
            "failing_phases",
            "failing_opponents",
        ):
            if gate.get(key):
                extra = (
                    "  failing: "
                    + ", ".join(gate[key])
                )

        lines.append(
            f"  {gate['id']:<3} "
            f"{gate['status'].upper():<8} "
            f"{gate['description']}{extra}"
        )

    return lines
