LSS (Layout Segmentation Simplifier)
====================================


## Install

`pip install https://github.com/PonteIneptique/lss/archive/refs/heads/main.zip`

## Use

```python
from lss.parsers import PageXML

file = PageXML(
    # Path to your file
    "0029_Main_frame.xml",
    # Optional: set-up the namespace, as they tend to change a lot
    namespace="http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15" 
)
# Simplify your baseline: things within 10% of your line height will be discarded (Seems to be a good number)
file.simplify_lines(epsilon_ratio=.10)
# Simplify your baseline: things within 15% of your mask height will be discarded (Seems to be a good number)
file.simplify_masks(ratio=.15)
# Write the new file
file.write(suffix="simple")
# A new file named 00029_Main_frame.simple.xml is born
# You can also retrieve the modified xml in
file.xml
```