"""Initial schema"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20240320_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("role", sa.String(length=50), nullable=False, server_default="user"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "part_analog_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "part_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "equipment_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "colleagues",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "counterparties",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("contact_person", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=100), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("driver_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=255), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
    )

    op.create_table(
        "parts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sku", sa.String(length=255), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("min_qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("price", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("part_categories.id", ondelete="SET NULL")),
        sa.Column("analog_group_id", sa.Integer(), sa.ForeignKey("part_analog_groups.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_unique_constraint("uq_parts_name_sku", "parts", ["name", "sku"])
    op.create_index("ix_parts_category_id", "parts", ["category_id"])
    op.create_index("ix_parts_analog_group_id", "parts", ["analog_group_id"])

    op.create_table(
        "equipment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sku", sa.String(length=255), nullable=True),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("equipment_categories.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("equipment.id", ondelete="CASCADE"), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_unique_constraint("uq_equipment_name", "equipment", ["name"])
    op.create_index("ix_equipment_category_id", "equipment", ["category_id"])

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("counterparty_id", sa.Integer(), sa.ForeignKey("counterparties.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("invoice_no", sa.String(length=255), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("delivery_date", sa.Date(), nullable=False),
        sa.Column("delivery_address", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="создан"),
        sa.Column("driver_notified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "equipment_parts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("equipment_id", sa.Integer(), sa.ForeignKey("equipment.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("part_id", sa.Integer(), sa.ForeignKey("parts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("installed_qty", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("last_replacement_override", sa.Text(), nullable=True),
        sa.Column("requires_replacement", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_unique_constraint("uq_equipment_parts_equipment_part", "equipment_parts", ["equipment_id", "part_id"])
    op.create_index("ix_equipment_parts_part_id", "equipment_parts", ["part_id"])

    op.create_table(
        "periodic_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("equipment_id", sa.Integer(), sa.ForeignKey("equipment.id", ondelete="SET NULL")),
        sa.Column("equipment_part_id", sa.Integer(), sa.ForeignKey("equipment_parts.id", ondelete="SET NULL")),
        sa.Column("period_days", sa.Integer(), nullable=False),
        sa.Column("last_completed_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_periodic_tasks_due_idx", "periodic_tasks", ["period_days", "last_completed_date"])

    op.create_table(
        "counterparty_addresses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("counterparty_id", sa.Integer(), sa.ForeignKey("counterparties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_counterparty_addresses_counterparty_id", "counterparty_addresses", ["counterparty_id"])

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="средний"),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("assignee_id", sa.Integer(), sa.ForeignKey("colleagues.id", ondelete="SET NULL")),
        sa.Column("equipment_id", sa.Integer(), sa.ForeignKey("equipment.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="в работе"),
        sa.Column("is_replacement", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_tasks_status_priority_due_date", "tasks", ["status", "priority", "due_date"])

    op.create_table(
        "complex_components",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("equipment_part_id", sa.Integer(), sa.ForeignKey("equipment_parts.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("equipment_id", sa.Integer(), sa.ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "replacements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("equipment_id", sa.Integer(), sa.ForeignKey("equipment.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("part_id", sa.Integer(), sa.ForeignKey("parts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("part_id", sa.Integer(), sa.ForeignKey("parts.id", ondelete="SET NULL")),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sku", sa.String(length=255), nullable=True),
        sa.Column("qty", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("price", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "task_parts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("equipment_part_id", sa.Integer(), sa.ForeignKey("equipment_parts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("part_id", sa.Integer(), sa.ForeignKey("parts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_task_parts_task_id", "task_parts", ["task_id"])
    op.create_index("ix_task_parts_equipment_part_id", "task_parts", ["equipment_part_id"])

    op.create_table(
        "knife_tracking",
        sa.Column("part_id", sa.Integer(), sa.ForeignKey("parts.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="наточен"),
        sa.Column("sharp_state", sa.String(length=20), nullable=False, server_default="заточен"),
        sa.Column("installation_state", sa.String(length=20), nullable=False, server_default="снят"),
        sa.Column("last_sharpen_date", sa.Date(), nullable=True),
        sa.Column("work_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_interval_days", sa.Integer(), nullable=True),
        sa.Column("total_sharpenings", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_knife_tracking_status", "knife_tracking", ["status"])

    op.create_table(
        "knife_status_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("part_id", sa.Integer(), sa.ForeignKey("knife_tracking.part_id", ondelete="CASCADE"), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_knife_status_log_part_id", "knife_status_log", ["part_id", "changed_at"])

    op.create_table(
        "knife_sharpen_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("part_id", sa.Integer(), sa.ForeignKey("knife_tracking.part_id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_knife_sharpen_log_part_id", "knife_sharpen_log", ["part_id", "date"])

def downgrade() -> None:
    op.drop_index("ix_knife_sharpen_log_part_id", table_name="knife_sharpen_log")
    op.drop_table("knife_sharpen_log")
    op.drop_index("ix_knife_status_log_part_id", table_name="knife_status_log")
    op.drop_table("knife_status_log")
    op.drop_index("ix_knife_tracking_status", table_name="knife_tracking")
    op.drop_table("knife_tracking")
    op.drop_index("ix_task_parts_equipment_part_id", table_name="task_parts")
    op.drop_index("ix_task_parts_task_id", table_name="task_parts")
    op.drop_table("task_parts")
    op.drop_table("order_items")
    op.drop_table("replacements")
    op.drop_table("complex_components")
    op.drop_index("ix_tasks_status_priority_due_date", table_name="tasks")
    op.drop_table("tasks")
    op.drop_index("ix_counterparty_addresses_counterparty_id", table_name="counterparty_addresses")
    op.drop_table("counterparty_addresses")
    op.drop_index("ix_periodic_tasks_due_idx", table_name="periodic_tasks")
    op.drop_table("periodic_tasks")
    op.drop_index("ix_equipment_parts_part_id", table_name="equipment_parts")
    op.drop_table("equipment_parts")
    op.drop_table("orders")
    op.drop_index("ix_equipment_category_id", table_name="equipment")
    op.drop_table("equipment")
    op.drop_index("ix_parts_analog_group_id", table_name="parts")
    op.drop_index("ix_parts_category_id", table_name="parts")
    op.drop_constraint("uq_parts_name_sku", "parts", type_="unique")
    op.drop_table("parts")
    op.drop_table("app_settings")
    op.drop_table("counterparties")
    op.drop_table("colleagues")
    op.drop_table("equipment_categories")
    op.drop_table("part_categories")
    op.drop_table("part_analog_groups")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
