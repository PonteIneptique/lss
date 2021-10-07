from unittest import TestCase
import os.path
from lss.parsers import PageXML


def elements_equal(e1, e2):
    return \
        e1.tag == e2.tag and \
        e1.text == e2.text and \
        e1.tail == e2.tail and \
        e1.attrib == e2.attrib and \
        len(e1) == len(e2) and \
        all(elements_equal(c1, c2) for c1, c2 in zip(e1, e2))


class TestPage(TestCase):
    def setUp(self) -> None:
        self.xml_path = "./tests/data/simple.page.xml"
        with open(self.xml_path) as f:
            self.xml = f.read()

    def test_parsing(self):
        from_filepath = PageXML.from_file(self.xml_path)
        from_string = PageXML.from_string(self.xml)
        self.assertEqual(from_string.dump(), from_filepath.dump(), "XML should be the same once parsed")

    def test_simplifying(self):
        page = PageXML.from_string(self.xml)
        modifications = page.simplify_lines(.10)
        self.assertEqual(modifications.percents, [.40], "2 points over 5 are removed on the single line")
        modifications = page.simplify_masks(.20)
        self.assertEqual(modifications.original, [9], "There were 9 points on the mask")
        self.assertEqual(modifications.simplified, [6], "Only 6 remains")
        self.assertEqual(modifications.percents, [1-6/9], "Which makes it a 33% reduction")
        self.assertEqual(
            page.dump(),
            """<?xml version='1.0' encoding='utf-8'?>
<PcGts xmlns="http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15">
    <Page imageFilename="simple.png" imageWidth="200" imageHeight="200">
        <TextRegion>
            <Coords points="5,5 5,195 195,195 195,5"/>
            <TextLine>
                <Coords points="5,10 100,10 100,50 40,50 50,10 5,10"/>
                <Baseline points="5,10 15,10 25,30"/>
            </TextLine>
        </TextRegion>
    </Page>
</PcGts>""")

    def test_ensure_find_namespace_work(self):
        """ Ensure that find_namespaces work """
        page = PageXML.from_file(self.xml_path, namespace="stupid")
        page.find_namespace()
        modifications = page.simplify_lines(.10)
        self.assertEqual(modifications.percents, [.40])

    def test_draw(self):
        """ No better idea how to test that yet """
        page = PageXML.from_file(self.xml_path, namespace="stupid")
        page.find_namespace()
        modifications = page.simplify_lines(.10)
        image = page.draw(image="./tests/data/simple.png")
        self.assertEqual(image.width, 200)
        image = page.draw(image="./tests/data/simple.png", output="./test.jpg")
        self.assertEqual(image.width, 200)

