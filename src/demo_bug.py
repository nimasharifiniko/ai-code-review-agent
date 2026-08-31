"""
Intentional demo bug for AI Code Review Agent evaluation.

This function always divides by zero, regardless of the caller's
input. It exists solely to produce a real, verifiable bug for a
controlled Pull Request evaluation — it is not part of the review
engine and is not meant to be fixed as part of this task.
"""


def divide(a: float, b: float) -> float:
    return a / 0