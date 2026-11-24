"""DeepSeek endpoint only. Credentials are read from the operator's external environment."""
import os
from dotenv import dotenv_values

env_file = os.getenv('PRIAGENT_ENV_FILE')
values = dotenv_values(env_file, interpolate=False) if env_file else {}
def setting(key, default=None):
    return os.getenv(key) or values.get(key) or default

LLM_BASE_URL = 'https://api.deepseek.com/anthropic'
LLM_MODEL = setting('LLM_MODEL', 'deepseek-flash')
if LLM_MODEL not in ('deepseek-flash','deepseek-v4-flash','deepseek-v4-pro'):
    raise ValueError('Select DeepSeek Flash or Pro')
# Select the credential source before selecting the provider's key alias.
# An explicitly selected account must not fall through to a different billed account.
credentials = values if env_file else os.environ
key_names = ('DEEPSEEK_API_KEY', 'ANTHROPIC_API_KEY', 'LLM_API_KEY')
key_name = next((name for name in key_names if credentials.get(name)), None)
LLM_API_KEY = credentials.get(key_name) if key_name else None
LLM_KEY_SOURCE = ('PRIAGENT_ENV_FILE' if env_file else 'process environment') + (f' ({key_name})' if key_name else '')
LLM_THINKING = False
LLM_THINKING_BUDGET_TOKENS = 1024
LLM_TEMPERATURE = 0
LLM_MAX_TOKENS = 4096
LLM_TIMEOUT_SECONDS = 120
LLM_MAX_RETRIES = 2
