import logging
import io
import os
import enum

from abc import ABCMeta, abstractmethod
from typing import Iterable, List, Optional, Tuple, Union, Callable
from itertools import cycle
from dataclasses import dataclass

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
    """ Convert a XML coordinates into a list of points

    >>> _string_to_points_list("152,43 289,90")
    [(152.0, 43.0), (289.0, 90.0)]
    """
    return list([
            tuple(map(float, points.split(",")))
            for points in string.split()
        ])


def _points_list_to_string(points: List[Points]) -> str:
    """ Convert a list of points into coordinates for XML

    >>> _points_list_to_string([(152.0, 43.0), (289.0, 90.0)])
    '152,43 289,90'
    """
    return " ".join([
        f"{point[0]:.0f},{point[1]:.0f}"
        for point in points
    ])


@enum.unique
class Mode(enum.Enum):
    Filepath = 0
    String = 1


@dataclass
class Modifications:
    original: List[int]
    simplified: List[int]

    @property
    def percents(self) -> List[float]:
        """ % of points removed per element
        """
        return [1-sim/ori for sim, ori in zip(self.simplified, self.original)]

    @property
    def reduction(self) -> List[float]:
        return [ori-sim for sim, ori in zip(self.simplified, self.original)]


class Parsed(metaclass=ABCMeta):

    def __init__(self, content: str, namespace: Optional[str] = None, mode: Mode = Mode.Filepath):
        self._filepath: Optional[str] = content if mode is Mode.Filepath else None
        self._content: Optional[io.StringIO] = io.BytesIO(content.encode()) if mode is Mode.String else None

        self.mode = mode
        self.xml: ET.ElementTree = None
        self.reload()

    def reload(self) -> None:
        self.xml: ET.ElementTree = ET.parse(self._filepath) if self.mode is Mode.Filepath else ET.parse(self._content)

    @classmethod
    def from_file(cls, filepath: str, namespace: Optional[str] = None) -> "Parsed":
        return cls(content=filepath, namespace=namespace, mode=Mode.Filepath)

    @classmethod
    def from_string(cls, content: str, namespace: Optional[str] = None) -> "Parsed":
        return cls(content=content, namespace=namespace, mode=Mode.String)

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

    def simplify_lines(self, ratio: float = .10, **kwargs) -> Modifications:
        """ Take care of all lines

        :param ratio: Ratio of the line mask height we keep as maximum epsilon, .25 is a bit aggressive, .10
            seems better

        """
        original = []
        simplified = []
        for line_no, line in enumerate(self._lines_get()):
            orig_points: List[Points] = self._line_parse(line)
            if "epsilon" not in kwargs:
                kwargs["epsilon"]: float = ratio * self._line_height(line)
            points: List[Points] = simplify_line(orig_points, **kwargs)

            logger.info(f"Line {line_no}: Reduced number of points by {len(orig_points)-len(points)}")

            self._line_write(line, points)

            original.append(len(orig_points))
            simplified.append(len(points))

        return Modifications(original=original, simplified=simplified)

    @abstractmethod
    def get_image_path(self) -> str:
        pass

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

    def simplify_masks(self, ratio: float = .15, tolerance: float = None) -> Modifications:
        original = []
        simplified = []
        for mask_no, mask in enumerate(self._masks_get()):
            coords: List[Points] = self._mask_parse(mask)

            if not tolerance:
                tolerance: float = ratio * self._mask_height(mask)
            new_coords: List[Points] = simplify_mask(coords, tolerance=tolerance)

            logger.info(
                f"Mask {mask_no}: Reduced number of points ({len(new_coords)})"
                f" by {(len(coords)-len(new_coords))/len(coords)*100:.2f} %"
            )
            original.append(len(coords))
            simplified.append(len(new_coords))

            self._mask_write(mask, new_coords)
        return Modifications(original=original, simplified=simplified)

    def get_suffixed(self, suffix: str = "simple", filepath: Optional[str] = None) -> str:
        """

        """
        if filepath is None and self._filepath is None:
            raise ValueError("A filepath needs to be given to use this function")

        refs = (self._filepath or filepath).split(".")
        return ".".join([*refs[:-1], suffix, refs[-1]])

    def dump(self, filepath: Optional[str] = None) -> str:
        """ Get the written output of the current XML.
        Optionaly outputs its to a file if a file path is given.

        """
        string = ET.tostring(self.xml, encoding="utf-8", xml_declaration=True)

        if filepath:
            with open(filepath, "wb") as f:
                f.write(string)
        return string.decode()

    @staticmethod
    def _compute_height(mask: List[Points]) -> float:
        """ Computes the height of a mask given a list of points

        >>> Parsed._compute_height([(0, 10), (0, 20), (0, 30)])
        20

        """
        y = [x[1] for x in mask]
        bot, top = min(y), max(y)
        return top-bot

    def draw(self, image: Union[str, Image.Image] = None, output: Optional[str] = None, width: int = 4) -> Image.Image:
        """ Draws the masks and lines

        Inspired by a script of Kraken

        """
        if isinstance(image, str):
            image = Image.open(image)
        elif not isinstance(image, Image.Image):
            raise ValueError("Unable to find the image to draw with")

        im = image.convert('RGBA')
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
        if output:
            im.save(output, quality=60)
        return im

    def test_values(
            self,
            test_values: List[Tuple[float, float]],
            image: Union[Image.Image, str],
            basename_output: Optional[str] = None,
            draw_original: bool = True,
            callback: Callable[[], None] = None
    ) -> List[Tuple[Image.Image, Modifications, Modifications]]:
        """ Check different values of simplification on an image

        :param test_values: Tuple of ratio (<1.0) where the first ratio is applied to line, the second to mask
        :param image: Image to draw over
        :param basename_output: Optional path were to save the output (basename), e.g. ./myimage (no extension)
        :param draw_original: If set to false, does not draw the original mask
        :param callback: Callback, just to say that one output is ready
        eg.

        Usage:

        >>> page = PageXML.from_file("tests/data/simple.page.xml")
        >>> four_images = page.test_values([(.1, .1), (.15, .15), (.20, .20)],
        ...    image="tests/data/simple.png", basename_output="tests", draw_original=True)

        Will create 4 images:
        - tests.jpg which is the original image with the mask
        - test.line0.1-mask0.1.jpg which results from a simplification of 10%/10% (line/mask)
        - test.line0.15-mask0.15.jpg which results from a simplification of 15%/15% (line/mask)
        - test.line0.2-mask0.2.jpg which results from a simplification of 20%/20% (line/mask)

        It also outputs the image objects and the logs of modifications (See the Modification object)
        """
        data = []
        if draw_original:
            data.append((
                self.draw(image=image, output=basename_output+".jpg" if basename_output else None),
                Modifications([], []),
                Modifications([], [])
            ))
            if callback is not None:
                callback()

        for idx, (line_ratio, mask_ratio) in enumerate(test_values):
            if idx != 0:
                self.reload()

            line_logs = self.simplify_lines(ratio=line_ratio)
            mask_logs = self.simplify_masks(ratio=mask_ratio)

            image = self.draw(
                image=image,
                output=f"./{basename_output}.line{line_ratio}-mask{mask_ratio}.jpg" if basename_output else None
            )

            data.append((image, line_logs, mask_logs))
            if callback is not None:
                callback()
        return data


class Alto(Parsed):
    """ Implementation that deals with ALTO files

    """
    def __init__(self, content: str, namespace: Optional[str] = None, **kwargs):
        super(Alto, self).__init__(content, namespace=namespace, **kwargs)
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
    """ Deals with PageXML based content

    >>> import os
    >>> file = PageXML.from_file("./tests/data/simple.page.xml")
    >>> file.simplify_lines()
    Modifications(original=[5], simplified=[3])
    >>> new_xml = file.dump(filepath="./unittest.doctest.xml")
    >>> os.path.exists("./unittest.doctest.xml")
    True
    >>> open("./unittest.doctest.xml").read() == new_xml
    True
    """
    def __init__(self, content: str, namespace: Optional[str] = None, **kwargs):
        super(PageXML, self).__init__(content, namespace=namespace, **kwargs)
        self.ns = {"page": namespace or "http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15"}

    def get_image_path(self, basedir: Optional[str] = None) -> str:
        """ Retrieve the image path from the XML

        >>> file = PageXML.from_file("./tests/data/simple.page.xml")
        >>> file.get_image_path()
        'simple.png'
        >>> import os.path
        >>> file.get_image_path(basedir=os.path.dirname("./tests/data/simple.page.xml"))
        './tests/data/simple.png'
        """
        image = self.xml.xpath("//page:Page/@imageFilename", namespaces=self.ns)
        if image:
            image = str(image[0])
            if basedir:
                return os.path.join(basedir, image)
            return image
        raise ValueError("No image path found")

    def find_namespace(self):
        for value in self.xml.getroot().nsmap.values():
            if "/PAGE/gts/" in value:
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
