from snoc_agent.api import create_app
from snoc_agent.config import load_settings

settings = load_settings()
app = create_app(settings)
