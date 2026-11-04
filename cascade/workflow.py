"""Rendering helpers for the consumer GitHub Actions workflow."""

from importlib.resources import files

from cascade import __version__


def render_workflow() -> str:
    text = files("cascade").joinpath("templates/github-cascade.yml").read_text()
    rendered = text.replace("__CASCADE_VERSION__", __version__)
    if "__CASCADE_VERSION__" in rendered:
        raise ValueError("unrendered Cascade version in workflow")
    return rendered
