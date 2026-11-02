import contextlib
import io
import json
import os
import shutil
import unittest
from pathlib import Path
from unittest import mock

from cascade.agent import _call_llm

FIXTURE = Path(__file__).resolve().parents[1] / "demo" / "fixtures" / "demo_graph.json"
MODELS_DIR = Path(__file__).resolve().parents[1] / "examples" / "models"
RAW_URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.raw_orders,PROD)"
FCT_URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.fct_orders,PROD)"




if __name__ == "__main__":
    unittest.main()
