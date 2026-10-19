"""Store public Amrapali library facts with source and verification date.

Revision ID: 4a72bc16d903
Revises: 8c91d2a6f410
"""
from alembic import op
import sqlalchemy as sa
from datetime import date


revision = "4a72bc16d903"
down_revision = "8c91d2a6f410"
branch_labels = None
depends_on = None


LIBRARY_PAGE = "https://amrapali.ac.in/campus-life/library"
PROSPECTUS = "https://amrapali.ac.in/assets/frontend/pdf/prospectus-2025-26.pdf"
CHECKED_ON = date(2026, 10, 20)


def upgrade():
    op.create_table(
        "institutional_library_facts",
        sa.Column("fact_key", sa.String(length=120), primary_key=True),
        sa.Column("fact_value", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("source_checked_on", sa.Date(), nullable=False),
        sa.Column("source_note", sa.Text(), nullable=False, server_default=""),
    )
    facts = sa.table(
        "institutional_library_facts",
        sa.column("fact_key", sa.String()),
        sa.column("fact_value", sa.Text()),
        sa.column("source_url", sa.String()),
        sa.column("source_checked_on", sa.Date()),
        sa.column("source_note", sa.Text()),
    )
    op.bulk_insert(facts, [
        {
            "fact_key": "institution_name",
            "fact_value": "Amrapali University",
            "source_url": LIBRARY_PAGE,
            "source_checked_on": CHECKED_ON,
            "source_note": "Institution name shown on the official library page.",
        },
        {
            "fact_key": "library_address",
            "fact_value": "Shiksha Nagar, Lamachaur, Kaladhungi Road, Haldwani - 263139, Nainital, Uttarakhand",
            "source_url": LIBRARY_PAGE,
            "source_checked_on": CHECKED_ON,
            "source_note": "Public institutional address; confirm before using for official correspondence.",
        },
        {
            "fact_key": "catalog_titles_current_webpage",
            "fact_value": "14292",
            "source_url": LIBRARY_PAGE,
            "source_checked_on": CHECKED_ON,
            "source_note": "Aggregate figure published on the current official library webpage; not imported as local book records.",
        },
        {
            "fact_key": "catalog_volumes_current_webpage",
            "fact_value": "99083",
            "source_url": LIBRARY_PAGE,
            "source_checked_on": CHECKED_ON,
            "source_note": "Aggregate figure published on the current official library webpage; not imported as local copy records.",
        },
        {
            "fact_key": "print_journals_and_magazines_current_webpage",
            "fact_value": "209",
            "source_url": LIBRARY_PAGE,
            "source_checked_on": CHECKED_ON,
            "source_note": "The webpage describes this as print journals and magazines.",
        },
        {
            "fact_key": "resources_listed_current_webpage",
            "fact_value": "CDs and project reports; UBKS management lecture CDs/DVDs; NPTEL study material; national and regional newspapers; Indian and foreign text/reference books; e-library databases; DELNET; OPAC; multimedia section; encyclopaedias and map sets; documentation and newspaper-clippings section; reprographic facility; reading hall; online full-text e-journals.",
            "source_url": LIBRARY_PAGE,
            "source_checked_on": CHECKED_ON,
            "source_note": "Feature list transcribed from the official library resources section. Availability and access conditions may vary.",
        },
        {
            "fact_key": "catalog_titles_prospectus_2025_26",
            "fact_value": "11051",
            "source_url": PROSPECTUS,
            "source_checked_on": CHECKED_ON,
            "source_note": "Historical 2025-26 prospectus figure. It differs from the current webpage figure; verify directly with the library before operational use.",
        },
        {
            "fact_key": "catalog_volumes_prospectus_2025_26",
            "fact_value": "106067",
            "source_url": PROSPECTUS,
            "source_checked_on": CHECKED_ON,
            "source_note": "Historical 2025-26 prospectus figure. It differs from the current webpage figure; verify directly with the library before operational use.",
        },
        {
            "fact_key": "print_journals_and_magazines_prospectus_2025_26",
            "fact_value": "146",
            "source_url": PROSPECTUS,
            "source_checked_on": CHECKED_ON,
            "source_note": "Historical 2025-26 prospectus figure. It differs from the current webpage figure; verify directly with the library before operational use.",
        },
    ])


def downgrade():
    op.drop_table("institutional_library_facts")
