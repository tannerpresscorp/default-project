"""Durable agent-run lifecycle with database-enforced transitions."""

import sqlalchemy as sa
from alembic import op

revision = "0002_agent_run_state"
down_revision = "0001_platform"
branch_labels = None
depends_on = None

RUN_STATUSES = (
    "PENDING",
    "RUNNING",
    "WAITING_FOR_TOOL",
    "WAITING_FOR_APPROVAL",
    "RETRYING",
    "SUCCEEDED",
    "FAILED",
    "CANCELLED",
    "TIMED_OUT",
)
TERMINAL_STATUSES = ("SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT")

ALLOWED_TRANSITIONS = (
    ("PENDING", "RUNNING"),
    ("PENDING", "FAILED"),
    ("PENDING", "CANCELLED"),
    ("PENDING", "TIMED_OUT"),
    ("RUNNING", "WAITING_FOR_TOOL"),
    ("RUNNING", "WAITING_FOR_APPROVAL"),
    ("RUNNING", "RETRYING"),
    ("RUNNING", "SUCCEEDED"),
    ("RUNNING", "FAILED"),
    ("RUNNING", "CANCELLED"),
    ("RUNNING", "TIMED_OUT"),
    ("WAITING_FOR_TOOL", "RUNNING"),
    ("WAITING_FOR_TOOL", "WAITING_FOR_APPROVAL"),
    ("WAITING_FOR_TOOL", "RETRYING"),
    ("WAITING_FOR_TOOL", "FAILED"),
    ("WAITING_FOR_TOOL", "CANCELLED"),
    ("WAITING_FOR_TOOL", "TIMED_OUT"),
    ("WAITING_FOR_APPROVAL", "RUNNING"),
    ("WAITING_FOR_APPROVAL", "FAILED"),
    ("WAITING_FOR_APPROVAL", "CANCELLED"),
    ("WAITING_FOR_APPROVAL", "TIMED_OUT"),
    ("RETRYING", "RUNNING"),
    ("RETRYING", "FAILED"),
    ("RETRYING", "CANCELLED"),
    ("RETRYING", "TIMED_OUT"),
)


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _transition_pairs() -> str:
    pairs = (f"('{source}', '{target}')" for source, target in ALLOWED_TRANSITIONS)
    return ",\n                ".join(pairs)


def upgrade():
    op.add_column(
        "agent_runs",
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.add_column("agent_runs", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("agent_runs", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True))
    # Forced RLS hides existing rows from the migration role, so the backfill
    # must run as the table owner with FORCE temporarily lifted.
    op.execute("ALTER TABLE agent_runs NO FORCE ROW LEVEL SECURITY")
    op.execute("UPDATE agent_runs SET updated_at = created_at")
    op.execute(
        f"UPDATE agent_runs SET finished_at = created_at "
        f"WHERE status IN ({_quoted(TERMINAL_STATUSES)}) AND finished_at IS NULL"
    )
    op.execute("ALTER TABLE agent_runs FORCE ROW LEVEL SECURITY")
    op.create_check_constraint(
        "ck_agent_runs_status", "agent_runs", f"status IN ({_quoted(RUN_STATUSES)})"
    )
    op.create_check_constraint(
        "ck_agent_runs_terminal_finished_at",
        "agent_runs",
        f"(status IN ({_quoted(TERMINAL_STATUSES)})) = (finished_at IS NOT NULL)",
    )
    op.create_index("ix_agent_runs_tenant_id_status", "agent_runs", ["tenant_id", "status"])
    op.execute(
        f"""CREATE FUNCTION validate_agent_run_transition()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM (VALUES
                {_transition_pairs()}
                ) AS allowed(from_status, to_status)
                WHERE allowed.from_status = OLD.status
                  AND allowed.to_status = NEW.status
            ) THEN
                RAISE EXCEPTION 'invalid agent run transition from % to %',
                    OLD.status, NEW.status;
            END IF;
            RETURN NEW;
        END $$"""
    )
    op.execute(
        """CREATE TRIGGER valid_agent_run_transition
        BEFORE UPDATE OF status ON agent_runs
        FOR EACH ROW WHEN (OLD.status IS DISTINCT FROM NEW.status)
        EXECUTE FUNCTION validate_agent_run_transition()"""
    )


def downgrade():
    op.execute("DROP TRIGGER valid_agent_run_transition ON agent_runs")
    op.execute("DROP FUNCTION validate_agent_run_transition()")
    op.drop_index("ix_agent_runs_tenant_id_status", table_name="agent_runs")
    op.drop_constraint("ck_agent_runs_terminal_finished_at", "agent_runs", type_="check")
    op.drop_constraint("ck_agent_runs_status", "agent_runs", type_="check")
    op.drop_column("agent_runs", "finished_at")
    op.drop_column("agent_runs", "started_at")
    op.drop_column("agent_runs", "updated_at")
