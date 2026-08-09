"""Demo seed script: pre-warms database and demonstrates autonomous cycle execution."""
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
from datetime import datetime, timezone
from db.database import init_db, get_session
from api.schemas import AgentConfigRequest
from services.agent_service import init_agent, run_cycle, get_active_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("demo_seed")


def run_demo_seed():
    logger.info("Initializing SQLite database...")
    init_db()
    
    with get_session() as session:
        active = get_active_config(session)
        if not active:
            logger.info("Configuring sample agent persona: 'Dr. Nova Sterling'...")
            config_req = AgentConfigRequest(
                persona_name="Dr. Nova Sterling",
                persona_bio="Autonomous Principal AI Researcher specializing in reasoning models, autonomous agentic loops, and open-weights intelligence.",
                topics_of_interest=["LLMs", "Autonomous Agents", "Robotics", "AI Safety", "Open Source AI"],
                posting_interval_minutes=15,
                tone_traits=["analytical", "authoritative", "forward-looking", "rigorous"],
                banned_topics=["crypto speculation", "clickbait", "unverified rumors"],
                daily_post_cap=12,
                force_restart=True
            )
            init_agent(config_req, session)
        else:
            logger.info(f"Existing persona active: {active.persona_name}")

        logger.info("Executing initial autonomous cycle...")
        result = run_cycle(session)
        logger.info(f"Cycle execution result: {result}")
        
    logger.info("Demo seeding completed! Visit http://localhost:8000 to view the live dashboard.")


if __name__ == "__main__":
    run_demo_seed()
