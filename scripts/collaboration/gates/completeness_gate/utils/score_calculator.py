"""Score calculation utilities for completeness gate."""


def calculate_alignment_score(required: int, implemented: int) -> float:
    """
    Calculate alignment score as implemented/required ratio.

    Args:
        required: Number of required elements
        implemented: Number of implemented elements

    Returns:
        Score between 0.0 and 1.0
    """
    if required == 0:
        return 1.0  # Nothing required, perfect alignment

    if implemented < 0 or required < 0:
        return 0.0

    # Cap at 1.0 even if implemented > required
    return min(1.0, implemented / required)


def calculate_coverage_score(planned: int, implemented: int) -> float:
    """
    Calculate test coverage score as implemented/planned ratio.

    Args:
        planned: Number of planned test cases
        implemented: Number of implemented test cases

    Returns:
        Score between 0.0 and 1.0
    """
    if planned == 0:
        return 1.0  # Nothing planned, perfect coverage

    if implemented < 0 or planned < 0:
        return 0.0

    return min(1.0, implemented / planned)


def calculate_error_handling_score(total_ops: int, protected_ops: int) -> float:
    """
    Calculate error handling score as protected/total ratio.

    Args:
        total_ops: Total number of risky operations
        protected_ops: Number of protected operations

    Returns:
        Score between 0.0 and 1.0
    """
    if total_ops == 0:
        return 1.0  # No risky operations, perfect score

    if protected_ops < 0 or total_ops < 0:
        return 0.0

    return min(1.0, protected_ops / total_ops)


def calculate_security_score(required: int, found: int) -> float:
    """
    Calculate security feature score as found/required ratio.

    Args:
        required: Number of required security features
        found: Number of found security features

    Returns:
        Score between 0.0 and 1.0
    """
    if required == 0:
        return 1.0  # Nothing required, perfect score

    if found < 0 or required < 0:
        return 0.0

    return min(1.0, found / required)


def weighted_average(scores: list[float], weights: list[float] | None = None) -> float:
    """
    Calculate weighted average of scores.

    Args:
        scores: List of score values (0.0-1.0)
        weights: Optional list of weights (must sum to 1.0)

    Returns:
        Weighted average score
    """
    if not scores:
        return 0.0

    if weights is None:
        # Equal weights
        return sum(scores) / len(scores)

    if len(scores) != len(weights):
        raise ValueError("Scores and weights must have same length")

    if abs(sum(weights) - 1.0) > 0.001:
        raise ValueError("Weights must sum to 1.0")

    return sum(s * w for s, w in zip(scores, weights))
