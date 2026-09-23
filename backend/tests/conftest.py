"""Test-wide settings: the suite never calls the real LLM provider.

The repo-root .env may hold a Gemini key for live demos; an empty environment variable overrides
it, so every test runs the offline paths unless it injects a fake client itself.
"""

import os

os.environ["GEMINI_API_KEY"] = ""
