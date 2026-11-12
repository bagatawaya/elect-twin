"""Trusted text-only provider specifications; no network or credentials at import.

Official endpoint documentation checked 2026-11-10. Live account/model compatibility
and billing have not been tested. The requested output limit is NOT a spend cap.
"""
SOURCES = {
    'openrouter': 'https://openrouter.ai/docs/api-reference/chat-completion',
    'gemini': 'https://aistudio.google.com/docs/openai',
    'mistral': 'https://docs.mistral.ai/api',
    'groq': 'https://console.groq.com/docs/api-reference#chat-create',
}
ENDPOINTS = {
    'openrouter': ('OPENROUTER_API_KEY', 'https://openrouter.ai/api/v1/chat/completions', 'max_tokens'),
    'gemini': ('GEMINI_API_KEY', 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions', 'max_tokens'),
    'mistral': ('MISTRAL_API_KEY', 'https://api.mistral.ai/v1/chat/completions', 'max_tokens'),
    'groq': ('GROQ_API_KEY', 'https://api.groq.com/openai/v1/chat/completions', 'max_completion_tokens'),
}

def _headers(key):
    return {'Authorization': 'Bearer ' + key}

def _answer(data):
    content = data['choices'][0]['message']['content']
    if isinstance(content, str):
        return content
    # Mistral can return typed content chunks; do not display hidden reasoning
    # or interpret non-text/tool content as an executable action.
    if isinstance(content, list):
        return '\n'.join(x['text'] for x in content if isinstance(x, dict) and x.get('type') == 'text' and isinstance(x.get('text'), str))
    return ''

def _payload_factory(system_prompt, token_field):
    def payload(model, context):
        return {
            'model': model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': context},
            ],
            token_field: 2048,
        }
    return payload

def build_extra_providers(system_prompt):
    """Return a registry compatible with twin.PROVIDERS, retaining exact system text."""
    return {
        provider: {
            'env': env,
            'url': url,
            'headers': _headers,
            'payload': _payload_factory(system_prompt, token_field),
            'answer': _answer,
            'docs': SOURCES[provider],
        }
        for provider, (env, url, token_field) in ENDPOINTS.items()
    }
