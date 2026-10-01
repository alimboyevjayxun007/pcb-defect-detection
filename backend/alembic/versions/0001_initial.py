"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspection_mode = postgresql.ENUM("single", "live", name="inspection_mode")
    verdict_enum = postgresql.ENUM("OK", "NOK", name="verdict")
    inspection_mode.create(op.get_bind(), checkfirst=True)
    verdict_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "inspections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("image_path", sa.String(500), nullable=True),
        sa.Column(
            "mode",
            postgresql.ENUM("single", "live", name="inspection_mode", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "verdict",
            postgresql.ENUM("OK", "NOK", name="verdict", create_type=False),
            nullable=False,
        ),
        sa.Column("inference_ms", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_inspections_created_at", "inspections", ["created_at"])

    op.create_table(
        "detections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "inspection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inspections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("defect_type", sa.String(50), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("bbox_x", sa.Float(), nullable=False),
        sa.Column("bbox_y", sa.Float(), nullable=False),
        sa.Column("bbox_w", sa.Float(), nullable=False),
        sa.Column("bbox_h", sa.Float(), nullable=False),
    )
    op.create_index("ix_detections_inspection_id", "detections", ["inspection_id"])

    op.create_table(
        "defect_types",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("description", sa.String(500), nullable=True),
    )

    defect_types_table = sa.table(
        "defect_types",
        sa.column("name", sa.String),
        sa.column("description", sa.String),
    )
    op.bulk_insert(
        defect_types_table,
        [
            {"name": "mouse_bite", "description": "Mis yo'lakchasi chetida kemirilgandek nuqson"},
            {"name": "missing_hole", "description": "Teshik yo'qligi (drill hole yetishmaydi)"},
            {"name": "spurious_copper", "description": "Keraksiz mis qoldig'i"},
            {"name": "spur", "description": "Yo'lakchadan tashqariga chiqqan mis bo'rtig'i"},
            {"name": "open_circuit", "description": "Uzilgan zanjir (yo'lakcha узilgan)"},
            {"name": "short", "description": "Qisqa tutashuv"},
        ],
    )


def downgrade() -> None:
    op.drop_table("defect_types")
    op.drop_index("ix_detections_inspection_id", table_name="detections")
    op.drop_table("detections")
    op.drop_index("ix_inspections_created_at", table_name="inspections")
    op.drop_table("inspections")

    postgresql.ENUM(name="inspection_mode").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="verdict").drop(op.get_bind(), checkfirst=True)
