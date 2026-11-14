"""CRR credit scoring: points per ScoreDetail field from the ScoreMatrix table."""
from collections import defaultdict
from decimal import Decimal


def matrix_by_attribute(rows):
    """Group ScoreMatrix rows by score_attr, keeping their order (scr_index)."""
    grouped = defaultdict(list)
    for row in rows:
        grouped[row.score_attr].append(row)
    return grouped


def field_points(value, rows):
    """
    Points for one field: the first row whose range holds the value. A row with
    value_from == value_to matches that exact value. No matching row, or no
    value, scores 0. A value of 0 is a real value and is scored.
    """
    if value is None:
        return Decimal(0)
    for row in rows:
        if row.value_from == row.value_to:
            if value == row.value_to:
                return row.adjusted_score
        elif row.value_from is not None and row.value_to is not None \
                and row.value_from <= value <= row.value_to:
            return row.adjusted_score
    return Decimal(0)


def score(values, matrix_rows):
    """
    Total score and points per field for a dict of {field name: value}.
    Fields without ScoreMatrix rows score 0.
    """
    matrix = matrix_by_attribute(matrix_rows)
    points = {name: field_points(value, matrix.get(name, [])) for name, value in values.items()}
    return sum(points.values(), Decimal(0)), points
