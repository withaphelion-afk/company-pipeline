from app.core.config import get_settings
from app.services.llm.base import LLMProvider
from app.services.llm.ollama import OllamaProvider
from app.services.llm.template import TemplateProvider


def get_provider() -> LLMProvider:
    return OllamaProvider() if get_settings().LLM_PROVIDER == "ollama" else TemplateProvider()
