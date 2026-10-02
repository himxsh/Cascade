"""In-tree PEP 517 backend: setuptools, then a short pip-install next-steps notice."""

from __future__ import annotations

from setuptools.build_meta import *  # noqa: F403
from setuptools.build_meta import build_editable as _build_editable
from setuptools.build_meta import build_wheel as _build_wheel

from cascade.pip_notice import emit_install_notice


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    wheel = _build_wheel(wheel_directory, config_settings, metadata_directory)
    emit_install_notice()
    return wheel


def build_editable(wheel_directory, config_settings=None, metadata_directory=None):
    wheel = _build_editable(wheel_directory, config_settings, metadata_directory)
    emit_install_notice()
    return wheel
