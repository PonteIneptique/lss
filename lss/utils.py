import enum
from typing import List, Optional, Sequence
# https://martinfleischmann.net/line-simplification-algorithms/
from simplification.cutil import (
    simplify_coords as _dp,  # this is Douglas-Peucker
    simplify_coords_vw as _vw,  # this is Visvalingam-Whyatt
)
from shapely.geometry import Polygon

Points = Sequence[float]


@enum.unique
class LineSimplificator(enum.Enum):
    DouglasPeucker = 0
    VisvalingamWhyatt = 1


def simplify_line(
        points: List[Points],
        algo: LineSimplificator = LineSimplificator.DouglasPeucker,
        epsilon: Optional[float] = None
) -> List[Points]:
    """ Given a list of points, returns a simplified line

    >>> simplify_line([[0.0, 0.0], [5.0, 4.0], [11.0, 5.5], [17.3, 3.2], [27.8, 0.1]])
    [[0.0, 0.0], [5.0, 4.0], [11.0, 5.5], [27.8, 0.1]

    >>> simplify_line(
    ...     [[0.0, 0.0], [5.0, 4.0], [11.0, 5.5], [17.3, 3.2], [27.8, 0.1]],
    ...     algo=LineSimplificator.VisvalingamWhyatt
    ... )
    [[5.0, 2.0], [7.0, 25.0], [10.0, 10.0]]
    """
    if algo == LineSimplificator.DouglasPeucker:
        return _dp(points, epsilon or 1.0)
    return _vw(points, epsilon or 30.0)


def simplify_mask(mask: List[Points], tolerance: float) -> List[Points]:
    poly = Polygon(mask)
    poly = poly.simplify(tolerance=tolerance, preserve_topology=True)
    return [tuple(coords) for coords in poly.exterior.coords]
