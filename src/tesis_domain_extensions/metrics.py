from __future__ import annotations

import math

from tesis_domain_extensions.contracts.common import large_non_negative_integer
from tesis_domain_extensions.contracts.results import ExactFraction


def unrestricted_undirected_path_count(n: int) -> int:
    """Count physical Hamiltonian paths of K_n, identifying reverse order."""

    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError("n must be a positive integer")
    if n == 1:
        return 1
    return math.factorial(n) // 2


def exact_fraction(numerator: int, denominator: int) -> ExactFraction:
    if numerator < 0 or denominator <= 0:
        raise ValueError("fraction requires a non-negative numerator and positive denominator")
    divisor = math.gcd(numerator, denominator)
    return ExactFraction(
        numerator=large_non_negative_integer(numerator // divisor),
        denominator=large_non_negative_integer(denominator // divisor),
    )
