"""Local stand-ins for the SQS/EventBridge-triggered Lambdas. Production
decouples these via a queue and a scheduler; locally there's no queue to
stand up, so the same side effects run as a FastAPI BackgroundTask (signup)
and a periodic asyncio task (digest) instead. Behavior (what gets logged,
when) matches welcome-notifier and signup-digest; only the trigger changes.
"""

import asyncio
import logging
import os

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models
from .database import SessionLocal

logger = logging.getLogger("foodie")

SIGNUP_DIGEST_INTERVAL_SECONDS = int(os.getenv("SIGNUP_DIGEST_INTERVAL_SECONDS", str(24 * 60 * 60)))


def welcome_notifier(name: str, email: str) -> None:
    """Same message welcome-notifier logs when it drains the SQS message
    auth-login publishes on signup."""
    logger.info(f"Welcome email queued for {name} <{email}> (user id: {email})")


async def signup_digest_loop() -> None:
    """Same query signup-digest runs on its daily EventBridge schedule."""
    while True:
        await asyncio.sleep(SIGNUP_DIGEST_INTERVAL_SECONDS)
        db: Session = SessionLocal()
        try:
            count = db.query(func.count(models.User.email)).scalar()
            logger.info(f"Signup digest: {count} total users registered so far.")
        finally:
            db.close()
