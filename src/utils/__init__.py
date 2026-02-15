"""
Utility modules for the GOA LLM application.
"""

import warnings

# Silence known LangChain warning on Python 3.14+; functionality still works for this app flow.
warnings.filterwarnings(
    "ignore",
    message=r"Core Pydantic V1 functionality isn't compatible with Python 3\.14 or greater\.",
    category=UserWarning,
)

from . import crm_utils
from . import doc_filler
from . import llm_handler
from . import pdf_utils
from . import schemas
from . import template_utils
from . import few_shot_learning
