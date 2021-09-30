from abc import ABCMeta, abstractmethod
from typing import Iterable, List, Optional
import logging

from lss.utils import Points, simplify_line, simplify_mask
import lxml.etree as ET


logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _string_to_points_list(string: str) -> List[Points]:
    return list([
            tuple(map(float, points.split(",")))
            for points in string.split()
        ])


def _points_list_to_string(points: List[Points]) -> str:
    return " ".join([
        f"{point[0]:.0f},{point[1]:.0f}"
        for point in points
    ])


class Parsed(metaclass=ABCMeta):
    def __init__(self, filepath: str, namespace: Optional[str] = None):
        self._filepath = filepath
        self.xml: ET.ElementTree = ET.parse(filepath)

    @abstractmethod
    def _lines_get(self) -> Iterable[ET.Element]:
        pass

    @abstractmethod
    def _line_parse(self, line: ET.Element) -> List[Points]:
        pass

    @abstractmethod
    def _line_height(self, line: ET.Element) -> float:
        pass

    @abstractmethod
    def _line_write(self, line: ET.Element, points: List[Points]) -> None:
        pass

    def simplify_lines(self, epsilon_ratio: float = .10, **kwargs):
        """ Take care of all lines

        :param epsilon_ratio: Ratio of the line mask height we keep as maximum epsilon, .25 is a bit aggressive, .10
            seems better

        """
        for line_no, line in enumerate(self._lines_get()):
            orig_points: List[Points] = self._line_parse(line)
            if "epsilon" not in kwargs:
                kwargs["epsilon"]: float = epsilon_ratio * self._line_height(line)
            points: List[Points] = simplify_line(orig_points, **kwargs)

            logger.info(f"Line {line_no}: Reduced number of points by {len(orig_points)-len(points)}")

            self._line_write(line, points)

    @abstractmethod
    def _masks_get(self) -> Iterable[ET.Element]:
        pass

    @abstractmethod
    def _mask_parse(self, mask: ET.Element) -> List[Points]:
        pass

    @abstractmethod
    def _mask_height(self, mask: ET.Element) -> float:
        pass

    @abstractmethod
    def _mask_write(self, mask: ET.Element, points: List[Points]) -> None:
        pass

    def simplify_masks(self, ratio: float = .15, tolerance: float = None):
        for mask_no, mask in enumerate(self._masks_get()):
            coords: List[Points] = self._mask_parse(mask)

            if not tolerance:
                tolerance: float = ratio * self._mask_height(mask)
            new_coords: List[Points] = simplify_mask(coords, tolerance=tolerance)

            logger.info(
                f"Mask {mask_no}: Reduced number of points ({len(new_coords)})"
                f" by {(len(coords)-len(new_coords))/len(coords)*100:.2f} %"
            )

            self._mask_write(mask, new_coords)

    def write(self, suffix: str = "simple"):
        filepath = self._filepath
        if suffix:
            refs = self._filepath.split(".")
            filepath = ".".join([*refs[:-1], suffix, refs[-1]])
        with open(filepath, "w") as f:
            f.write(ET.tounicode(self.xml))

    def _compute_height(self, mask: List[Points]) -> float:
        y = [x[1] for x in mask]
        bot, top = min(y), max(y)
        return top-bot


class Alto(Parsed):
    """

    >>> from lss.utils import LineSimplificator
    >>> file = Alto("./tests/data/dictionary.xml")
    >>> file.simplify_lines()
    >>> file.write(suffix="simplified")
    """
    def __init__(self, filepath: str, namespace: Optional[str] = None):
        super(Alto, self).__init__(filepath)
        self.ns = {"alto": namespace or "http://www.loc.gov/standards/alto/ns-v4#"}

    def _lines_get(self) -> Iterable[ET.Element]:
        yield from self.xml.xpath(".//alto:TextLine", namespaces=self.ns)

    def _line_height(self, line: ET.Element) -> float:
        return float(line.attrib["HEIGHT"])

    def _line_parse(self, line: ET.Element) -> List[Points]:
        return _string_to_points_list(line.attrib["BASELINE"])

    def _line_write(self, line: ET.Element, points: List[Points]) -> None:
        line.attrib["BASELINE"] = _points_list_to_string(points)


class PageXML(Parsed):
    """

    >>> from lss.utils import LineSimplificator
    >>> file = PageXML("./tests/data/page.xml")
    >>> file.simplify_lines()
    >>> file.write(suffix="simplified")
    """
    def __init__(self, filepath: str, namespace: Optional[str] = None):
        super(PageXML, self).__init__(filepath)
        self.ns = {"page": namespace or "http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15"}

    def _lines_get(self) -> Iterable[ET.Element]:
        yield from self.xml.xpath(".//page:TextLine", namespaces=self.ns)

    def _line_height(self, line: ET.Element) -> float:
        mask = _string_to_points_list(line.xpath("./page:Coords", namespaces=self.ns)[0].attrib["points"])
        return self._compute_height(mask)

    def _line_parse(self, line: ET.Element) -> List[Points]:
        return _string_to_points_list(line.xpath("./page:Baseline", namespaces=self.ns)[0].attrib["points"])

    def _line_write(self, line: ET.Element, points: List[Points]) -> None:
        line.xpath("./page:Baseline", namespaces=self.ns)[0].attrib["points"] = _points_list_to_string(points)

    def _masks_get(self) -> Iterable[ET.Element]:
        yield from self.xml.xpath(".//page:TextLine/page:Coords", namespaces=self.ns)

    def _mask_height(self, mask: ET.Element) -> float:
        return self._compute_height(_string_to_points_list(mask.attrib["points"]))

    def _mask_parse(self, mask: ET.Element) -> List[Points]:
        return _string_to_points_list(mask.attrib["points"])

    def _mask_write(self, mask: ET.Element, points: List[Points]) -> None:
        mask.attrib["points"] = _points_list_to_string(points)
