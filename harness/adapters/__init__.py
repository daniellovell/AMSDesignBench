"""
Adapter module for LLM integrations.
"""

import importlib
from typing import Dict, Any

ADAPTERS: Dict[str, Any] = {}


def get_adapter(name: str, **kwargs):
    """
    Get an LLM adapter by name.
    
    Args:
        name: Adapter name ('dummy', 'openai', 'anthropic', 'openrouter', 'gpt-4', 'claude-3.5-sonnet', etc.)
        **kwargs: Additional arguments to pass to the adapter
    
    Returns:
        Adapter instance
    """
    global ADAPTERS
    
    # Map common model names to adapters
    model_to_adapter = {
        'gpt-4': ('openai', {'model': 'gpt-4'}),
        'gpt-4o': ('openai', {'model': 'gpt-4o'}),
        'gpt-4o-mini': ('openai', {'model': 'gpt-4o-mini'}),
        'gpt-3.5-turbo': ('openai', {'model': 'gpt-3.5-turbo'}),
        'claude-3-5-sonnet': ('anthropic', {'model': 'claude-3-5-sonnet-20241022'}),
        'claude-3.5-sonnet': ('anthropic', {'model': 'claude-3-5-sonnet-20241022'}),
        'claude-3-opus': ('anthropic', {'model': 'claude-3-opus-20240229'}),
        'claude-3-sonnet': ('anthropic', {'model': 'claude-3-sonnet-20240229'}),
    }
    
    # Check if name is a model shorthand
    if name in model_to_adapter:
        adapter_name, model_kwargs = model_to_adapter[name]
        kwargs = {**model_kwargs, **kwargs}
        name = adapter_name
    
    # Lazy load adapters
    if not ADAPTERS:
        # Dummy adapter (always available)
        try:
            mod = importlib.import_module("harness.adapters.dummy")
            ADAPTERS["dummy"] = getattr(mod, "build")
        except Exception:
            from .dummy import build as build_dummy
            ADAPTERS["dummy"] = build_dummy
        
        # OpenAI adapter (optional)
        try:
            mod = importlib.import_module("harness.adapters.openai")
            ADAPTERS["openai"] = getattr(mod, "build")
        except Exception:
            try:
                from .openai import build as build_openai
                ADAPTERS["openai"] = build_openai
            except Exception:
                pass
        
        # Anthropic adapter (optional)
        try:
            mod = importlib.import_module("harness.adapters.anthropic")
            ADAPTERS["anthropic"] = getattr(mod, "build")
        except Exception:
            try:
                from .anthropic import build as build_anthropic
                ADAPTERS["anthropic"] = build_anthropic
            except Exception:
                pass
        
        # OpenRouter adapter (optional)
        try:
            mod = importlib.import_module("harness.adapters.openrouter")
            ADAPTERS["openrouter"] = getattr(mod, "build")
        except Exception:
            try:
                from .openrouter import build as build_openrouter
                ADAPTERS["openrouter"] = build_openrouter
            except Exception:
                pass
    
    if name not in ADAPTERS:
        available = ', '.join(ADAPTERS.keys())
        raise ValueError(f"Unknown adapter: {name}. Available: {available}")
    
    build_fn = ADAPTERS[name]
    try:
        return build_fn(**kwargs)
    except TypeError:
        # Back-compat for builders without kwargs signature
        return build_fn()


__all__ = ['get_adapter']
