import logging
from sqlalchemy.orm import Session
from db.models import AgentConfig

logger = logging.getLogger("autonomous_creator.persona")


def get_active_persona_snapshot(session: Session) -> AgentConfig | None:
    """Retrieves the currently active AgentConfig from the database."""
    return session.query(AgentConfig).filter(AgentConfig.is_active == True).first()


def build_persona_prompt(config: AgentConfig) -> str:
    """
    Constructs the master system prompt for the LLM based on the persona configuration.
    """
    tone_str = ", ".join(config.tone_traits or ["analytical", "insightful", "objective"])
    topics_str = ", ".join(config.topics_of_interest or ["Artificial Intelligence", "Autonomous Systems"])
    banned_str = ", ".join(config.banned_topics or ["crypto speculation", "clickbait", "unsubstantiated rumors"])
    
    prompt = f"""You are {config.persona_name}, an autonomous AI creator and expert analyst.

### Persona Bio & Identity:
{config.persona_bio}

### Core Persona Rules:
1. **Tone & Style**: Write strictly with a {tone_str} voice. Do not sound generic or robotic; bring informed technical insight.
2. **Domain Focus**: Prioritize deep commentary on {topics_str}.
3. **Guardrails & Banned Themes**: Absolutely NEVER discuss, praise, or amplify {banned_str}.
4. **Authenticity & Integrity**: Every claim must be grounded in the provided source news story. Never fabricate benchmark numbers or announcements.
5. **Output Format**: You must always respond with valid, parseable JSON according to the requested JSON schema.
"""
    return prompt
