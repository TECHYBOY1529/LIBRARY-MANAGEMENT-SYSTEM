"""Add course and semester classification to catalog books.

Revision ID: 8c91d2a6f410
Revises: 2152e5fbbe38
"""
from alembic import op
import sqlalchemy as sa


revision = "8c91d2a6f410"
down_revision = "2152e5fbbe38"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "courses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.UniqueConstraint("name", name="uq_courses_name"),
    )
    op.bulk_insert(
        sa.table("courses", sa.column("id", sa.Integer()), sa.column("name", sa.String())),
        [
            {"id": 1, "name": "B.Tech Computer Science"},
            {"id": 2, "name": "BA English"},
            {"id": 3, "name": "B.Sc Mathematics"},
            {"id": 4, "name": "BA History"},
            {"id": 5, "name": "B.Sc Natural Sciences"},
            {"id": 6, "name": "BBA Business Administration"},
            {"id": 7, "name": "General Studies"},
        ],
    )
    with op.batch_alter_table("books") as batch_op:
        batch_op.add_column(sa.Column("course_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("semester", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_books_course_id_courses", "courses", ["course_id"], ["id"], ondelete="SET NULL"
        )
        batch_op.create_check_constraint(
            "ck_book_semester_range", "semester IS NULL OR semester BETWEEN 1 AND 12"
        )
        batch_op.create_index("ix_books_course_id", ["course_id"])

    # The known fictional demo ISBN range can be classified safely. Real catalog
    # records keep NULL until a librarian assigns their course and semester.
    op.execute(sa.text("""
        UPDATE books
        SET course_id = (
            SELECT courses.id
            FROM categories
            JOIN courses ON courses.name = CASE categories.name
                WHEN 'Computer Science' THEN 'B.Tech Computer Science'
                WHEN 'Literature' THEN 'BA English'
                WHEN 'Mathematics' THEN 'B.Sc Mathematics'
                WHEN 'History' THEN 'BA History'
                WHEN 'Science' THEN 'B.Sc Natural Sciences'
                WHEN 'Business' THEN 'BBA Business Administration'
                ELSE 'General Studies'
            END
            WHERE categories.id = books.category_id
        ),
        semester = ((id - 1) % 8) + 1
        WHERE isbn LIKE '978000%'
          AND EXISTS (
              SELECT 1 FROM book_copies
              WHERE book_copies.book_id = books.id AND book_copies.barcode LIKE 'DEMO-%'
          )
    """))


def downgrade():
    with op.batch_alter_table("books") as batch_op:
        batch_op.drop_index("ix_books_course_id")
        batch_op.drop_constraint("ck_book_semester_range", type_="check")
        batch_op.drop_constraint("fk_books_course_id_courses", type_="foreignkey")
        batch_op.drop_column("semester")
        batch_op.drop_column("course_id")
    op.drop_table("courses")
