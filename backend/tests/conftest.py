import os
import sys
from pathlib import Path

# Ensure offline + deterministic embeddings in tests
os.environ.setdefault("LLM_PROVIDER", "offline")
os.environ.setdefault("EMBEDDINGS_FAKE", "1")

# Backend on sys.path for `from app...` imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
