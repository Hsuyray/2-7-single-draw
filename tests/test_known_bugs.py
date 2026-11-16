"""
Known engine bugs, recorded as strict expected failures.

Each test asserts the CORRECT behaviour and is marked xfail(strict=True):
it fails today as expected; once the bug is fixed it passes, strict
mode turns that into a failure, and the marker must be removed and the
test moved to tests/test_regression_fixed_bugs.py.

No known engine bugs are open (day70). The all-in round bug
(docs/proposals/ENGINE-all-in-round.md) was fixed on day70; its
tests now live in tests/test_regression_fixed_bugs.py.
"""
