LSS (Layout Segmentation Simplifier)
====================================


## Install

`pip install https://github.com/PonteIneptique/lss/archive/refs/heads/main.zip`

or 

`pip install layouts-segmentation-simplifier`
## Use

### Generic use

```python
from lss.parsers import PageXML

file = PageXML(
    # Path to your file
    "data/0029_Main_frame.xml",
    # Optional: set-up the namespace, as they tend to change a lot
    namespace="http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15" 
)
# Simplify your baseline: things within 10% of your line height will be discarded (Seems to be a good number)
file.simplify_lines(ratio=.10)
# Simplify your baseline: things within 15% of your mask height will be discarded (Seems to be a good number)
file.simplify_masks(ratio=.15)
# Write the new file
file.write(suffix="simple")
# A new file named 00029_Main_frame.simple.xml is born
# You can also retrieve the modified xml in
file.xml
```

### Qualitatively search for best parameters

You can also get it to make multiple simulation, to chose the best value (highest ratio = bigger simplification)

```python
from lss.parsers import PageXML

page = PageXML("./data/0002_Main_frame.xml")
page.find_namespace()
page.test_values([(.05, .05), (.1, .1), (.15, .15), (.20, .20)], image_path="./data/0002_Main_frame.jpg")
```

In this context, lines will be simplified by a ratio of 0.05, 0.10, 0.15 and 0.20. Mask will be as well. 
Few files will be saved. Each test will create test files with overlays (cf. folder [data](./data) for all examples):

Original            |  15% ratio on both line and masks
:-------------------------:|:-------------------------:
![Original Mask](./data/0002_Main_frame.jpg.original.jpg)  |  ![Original Mask](./data/0002_Main_frame.jpg.line0.15-mask0.15.jpg)

10%            |  20%
:-------------------------:|:-------------------------:
![Original Mask](./data/0002_Main_frame.jpg.line0.1-mask0.1.jpg)  |  ![Original Mask](./data/0002_Main_frame.jpg.line0.2-mask0.2.jpg)


