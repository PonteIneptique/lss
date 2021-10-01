from abc import ABCMeta, abstractmethod
from typing import Iterable, List, Optional, Tuple
import logging
import os
from itertools import cycle

import lxml.etree as ET
from PIL import Image, ImageDraw

from lss.utils import Points, simplify_line, simplify_mask


cmap = cycle([(230, 25, 75, 127),
              (60, 180, 75, 127),
              (255, 225, 25, 127),
              (0, 130, 200, 127),
              (245, 130, 48, 127),
              (145, 30, 180, 127),
              (70, 240, 240, 127)])


def _get_circle(points: Points, width: int = 5) -> Tuple[int, int, int, int]:
    return (points[0]-width, points[1]-width, points[0]+width, points[1]+width)


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

    def reload(self) -> None:
        self.xml: ET.ElementTree = ET.parse(self._filepath)

    @abstractmethod
    def find_namespace(self):
        pass

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

    def simplify_lines(self, ratio: float = .10, **kwargs):
        """ Take care of all lines

        :param epsilon_ratio: Ratio of the line mask height we keep as maximum epsilon, .25 is a bit aggressive, .10
            seems better

        """
        for line_no, line in enumerate(self._lines_get()):
            orig_points: List[Points] = self._line_parse(line)
            if "epsilon" not in kwargs:
                kwargs["epsilon"]: float = ratio * self._line_height(line)
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

    def draw(self, image_path: str = None, output_path: str = None, width: int = 4):
        im = Image.open(image_path)
        im = im.convert('RGBA')
        tmp = Image.new('RGBA', im.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(tmp)
        for line in self._lines_get():
            points = self._line_parse(line)
            draw.line(points, width=width, fill="red")
            for circle in [_get_circle(cross, width=width) for cross in points]:
                draw.ellipse(circle, fill="white")

        tmp2 = Image.new('RGBA', im.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(tmp2)
        for mask in self._masks_get():
            points = self._mask_parse(mask)
            draw.polygon(points, fill=next(cmap))
            for circle in [_get_circle(cross, width=width) for cross in points]:
                draw.ellipse(circle, fill="white")

        tmp = Image.alpha_composite(tmp2, tmp)
        im = Image.alpha_composite(im, tmp)
        im = im.convert('RGB')
        if not output_path:
            output_path = '{}.segmented.jpg'.format(os.path.basename(image_path))
        im.save(output_path, quality=60)

    def test_values(self, test_values: List[Tuple[float, float]], image_path: str = None):
        """ Check different values of simplification on an image

        :param test_values: Tuple of ratio (<1.0) where the first ratio is applied to line, the second to mask
        eg.
        >>> page = PageXML("somexml.xml")
        >>> page.test_values([(.1, .1), (.15, .15), (.20, .20)], image_path)
        """
        basename = os.path.basename(image_path)
        self.draw(image_path=image_path, output_path=f"./{basename}.original.jpg")

        for idx, (line_ratio, mask_ratio) in enumerate(test_values):
            if idx != 0:
                self.reload()
            self.simplify_lines(ratio=line_ratio)
            self.simplify_masks(ratio=mask_ratio)
            self.draw(image_path=image_path, output_path=f"./{basename}.line{line_ratio}-mask{mask_ratio}.jpg")


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

    def find_namespace(self):
        for value in self.xml.getroot().nsmap.values():
            if "alto" in value:
                self.ns = {"alto": value}


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

    def find_namespace(self):
        for value in self.xml.getroot().nsmap.values():
            if "/PAGE/gts/"in value:
                self.ns = {"page": value}

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
