from typing import List
import os
import click
import tqdm

from lss.parsers import PageXML, Alto


@click.group("lss")
def main():
    """ LSS is a tool to deal with mask and baseline simplification
    """
    pass


@main.command("test-values")
@click.argument("files", nargs=-1, type=click.Path(exists=True, dir_okay=False, file_okay=True))
@click.option("-n", "--namespace", default="page", type=click.Choice(["alto", "page"]),
              help="Format in which the files are written", show_default=True)
@click.option("-b", "--basedir", default=None, type=click.Path(exists=True, dir_okay=True, file_okay=False),
              help="Directory where the images are stored, if different from the files")
@click.option("-o", "--outdir", default="./", type=click.Path(exists=True, dir_okay=True, file_okay=False),
              show_default=True,
              help="Directory where images will be saved")
@click.option("-v", "--value", default=None, type=float, multiple=True,
              help="Height ratio to use to remove points in baseline and masks")
def test_values(files: List[str], namespace: str, basedir: str, outdir : str, value: List[float] = None):
    """ Test different ratio for mask and baseline simplification using one or multiple FILES"""
    cls = PageXML if namespace == "page" else Alto

    if not value:
        value = [(.10, .10), (.05, .05), (.15, .15), (.20, .20)]
    else:
        value = [(val, val) for val in value]

    for file in tqdm.tqdm(files, desc="Files processed"):
        with tqdm.tqdm(total=len(value)+1, desc="Values tested") as pbar:
            content = PageXML.from_file(filepath=file)
            content.find_namespace()
            content.test_values(
                test_values=value,
                image=content.get_image_path(basedir=basedir if basedir is not None else os.path.dirname(file)),
                basename_output=os.path.join(outdir, os.path.basename(file)),
                callback=lambda: pbar.update(1)
            )


if __name__ == "__main__":
    main()
