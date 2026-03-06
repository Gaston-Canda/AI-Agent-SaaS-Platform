"""Application initialization and setup."""
from sqlalchemy import inspect, text
from app.db.database import engine
from app.tools import ToolRegistry, register_builtin_tools
from app.monitoring.logging import StructuredLogger
from app.services.billing_service import BillingService
from app.db.database import SessionLocal

logger = StructuredLogger(__name__)


def initialize_application():
    """
    Initialize application components.

    Called on app startup to:
    - Register built-in tools
    - Set up registries
    - Validate configurations
    """
    try:
        _apply_optional_schema_upgrades()

        # Register built-in tools
        register_builtin_tools(ToolRegistry)
        logger.log_execution(
            "Built-in tools registered",
            {"tools": ToolRegistry.list_tools()}
        )

        db = SessionLocal()
        try:
            BillingService.ensure_default_plans(db)
            logger.log_execution(
                "Default subscription plans ensured",
                {"status": "ok"},
            )
        finally:
            db.close()

    except Exception as e:
        logger.log_error(
            f"Failed to initialize application: {str(e)}",
            {"exception": type(e).__name__}
        )
        raise


def _apply_optional_schema_upgrades() -> None:
    """Apply safe additive schema upgrades for optional platform features."""

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    with engine.begin() as connection:

        # ----------------------------------------------------------------
        # Agent Memories Table
        # ----------------------------------------------------------------

        if "agent_memories" not in tables:
            connection.execute(
                text(
                    """
                    CREATE TABLE agent_memories (
                        id VARCHAR(36) PRIMARY KEY,
                        tenant_id VARCHAR(36) NOT NULL,
                        agent_id VARCHAR(36) NOT NULL,
                        content TEXT NOT NULL,
                        embedding JSON NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE NOT NULL
                    )
                    """
                )
            )
            logger.log_execution(
                "Schema upgrade applied",
                {"status": "created_table", "table": "agent_memories"},
            )

        # ----------------------------------------------------------------
        # Audit Logs Table
        # ----------------------------------------------------------------

        if "audit_logs" not in tables:
            connection.execute(
                text(
                    """
                    CREATE TABLE audit_logs (
                        id VARCHAR(36) PRIMARY KEY,
                        timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                        tenant_id VARCHAR(36),
                        user_id VARCHAR(36),
                        action VARCHAR(120) NOT NULL,
                        metadata JSON NOT NULL
                    )
                    """
                )
            )
            logger.log_execution(
                "Schema upgrade applied",
                {"status": "created_table", "table": "audit_logs"},
            )

        # ----------------------------------------------------------------
        # Subscription Plans Table
        # ----------------------------------------------------------------

        if "subscription_plans" not in tables:
            connection.execute(
                text(
                    """
                    CREATE TABLE subscription_plans (
                        id VARCHAR(36) PRIMARY KEY,
                        plan_name VARCHAR(50) NOT NULL UNIQUE,
                        price FLOAT NOT NULL DEFAULT 0.0,
                        currency VARCHAR(8) NOT NULL DEFAULT 'USD',
                        billing_interval VARCHAR(20) NOT NULL DEFAULT 'monthly',
                        max_agents INTEGER NOT NULL DEFAULT 3,
                        max_executions_month INTEGER NOT NULL DEFAULT 1000,
                        max_tokens_month INTEGER NOT NULL DEFAULT 100000,
                        max_tool_calls INTEGER NOT NULL DEFAULT 500,
                        concurrent_executions INTEGER NOT NULL DEFAULT 2,
                        stripe_price_id VARCHAR(255),
                        is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TIMESTAMP WITH TIME ZONE NOT NULL
                    )
                    """
                )
            )
            logger.log_execution(
                "Schema upgrade applied",
                {"status": "created_table", "table": "subscription_plans"},
            )

        # ----------------------------------------------------------------
        # Execution Logs Upgrade
        # ----------------------------------------------------------------

        if "execution_logs" in tables:

            existing_columns = {
                col["name"] for col in inspector.get_columns("execution_logs")
            }

            additions = {
                "tokens_used": "INTEGER NOT NULL DEFAULT 0",
                "llm_latency_ms": "INTEGER NOT NULL DEFAULT 0",
                "tool_latency_ms": "INTEGER NOT NULL DEFAULT 0",
                "total_execution_time_ms": "INTEGER NOT NULL DEFAULT 0",
            }

            for column_name, column_type in additions.items():

                if column_name in existing_columns:
                    continue

                connection.execute(
                    text(
                        f"ALTER TABLE execution_logs ADD COLUMN {column_name} {column_type}"
                    )
                )

                logger.log_execution(
                    "Schema upgrade applied",
                    {
                        "status": "added_column",
                        "table": "execution_logs",
                        "column": column_name,
                    },
                )

        # ----------------------------------------------------------------
        # Tenant Subscriptions Upgrade
        # ----------------------------------------------------------------

        if "tenant_subscriptions" in tables:

            existing_columns = {
                col["name"] for col in inspector.get_columns("tenant_subscriptions")
            }

            additions = {
                "plan_id": "VARCHAR(36)",
                "status": "VARCHAR(30) NOT NULL DEFAULT 'active'",
                "current_period_start": "TIMESTAMP WITH TIME ZONE",
                "current_period_end": "TIMESTAMP WITH TIME ZONE",
                "cancel_at_period_end": "BOOLEAN NOT NULL DEFAULT FALSE",
                "trial_start": "TIMESTAMP WITH TIME ZONE",
                "trial_end": "TIMESTAMP WITH TIME ZONE",
                "trial_active": "BOOLEAN NOT NULL DEFAULT TRUE",
                "stripe_customer_id": "VARCHAR(255)",
                "stripe_subscription_id": "VARCHAR(255)",
                "max_executions_month": "INTEGER NOT NULL DEFAULT 1000",
                "max_agents": "INTEGER NOT NULL DEFAULT 3",
                "max_tool_calls": "INTEGER NOT NULL DEFAULT 500",
            }

            for column_name, column_type in additions.items():

                if column_name in existing_columns:
                    continue

                connection.execute(
                    text(
                        f"ALTER TABLE tenant_subscriptions ADD COLUMN {column_name} {column_type}"
                    )
                )

                logger.log_execution(
                    "Schema upgrade applied",
                    {
                        "status": "added_column",
                        "table": "tenant_subscriptions",
                        "column": column_name,
                    },
                )


def initialize_worker():
    """
    Initialize Celery worker.

    Called when a worker starts to:
    - Register tools
    - Set up async context
    """

    try:

        register_builtin_tools(ToolRegistry)

        logger.log_execution(
            "Worker initialized with tools",
            {"tools": ToolRegistry.list_tools()}
        )

    except Exception as e:

        logger.log_error(
            f"Failed to initialize worker: {str(e)}",
            {"exception": type(e).__name__}
        )

        raise