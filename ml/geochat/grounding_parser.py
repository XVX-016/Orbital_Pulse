"""Re-export shim for grounding_parser in ml/geochat."""
import sys
import os

SATQUERY_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "satquery-service"))
if SATQUERY_PATH not in sys.path:
    sys.path.insert(0, SATQUERY_PATH)

from grounding_parser import parse_geochat_grounding
