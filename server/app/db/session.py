"""Database session — DynamoDB client provider.

Replaces the previous MySQL/SQLAlchemy setup.
Provides get_db() for FastAPI dependency injection (returns dynamo client module).
SessionLocal() for background tasks.
"""
import app.dynamo.client as dynamo_client


def get_db():
    """FastAPI dependency — yields the DynamoDB client module.

    Usage in endpoints: db = Depends(get_db)
    Then: db.get_table("orders"), db.next_id("orders"), etc.
    """
    yield dynamo_client


def SessionLocal():
    """For background tasks that need their own 'session'.

    Returns the dynamo client module directly (DynamoDB is stateless,
    no session management needed like SQLAlchemy).
    """
    return dynamo_client
