from datetime import date, datetime, timedelta
from decimal import Decimal

from .extensions import db
from .models import (Author, Book, BookCopy, Category, Complaint, Feedback, Fine,
                     ImprovementAction, InventoryAudit, Loan, Notification, PdcaCycle, Publisher,
                     Reservation, RootCauseAnalysis, User, utcnow)

DEMO_ADMIN_EMAIL = "admin@library.demo"
DEMO_ADMIN_PASSWORD = "LibraryDemo!2026"


def reset_demo():
    db.drop_all()
    db.create_all()
    seed_demo()


def seed_demo():
    db.create_all()
    if User.query.filter_by(email=DEMO_ADMIN_EMAIL).first():
        return

    admin = User(full_name="Avery Morgan (Demo Librarian)", email=DEMO_ADMIN_EMAIL, role="admin")
    admin.set_password(DEMO_ADMIN_PASSWORD)
    quality = User(full_name="Jordan Lee (Demo Quality Manager)", email="quality@library.demo", role="quality_manager")
    quality.set_password("QualityDemo!2026")
    db.session.add_all([admin, quality])
    members = []
    for index in range(1, 13):
        user = User(full_name=f"Student {index:02d}", email=f"student{index:02d}@library.demo", role="member")
        user.set_password("StudentDemo!2026")
        members.append(user)
    db.session.add_all(members)
    categories = [Category(name=n) for n in ["Computer Science", "Literature", "Mathematics", "History", "Science", "Business"]]
    authors = [Author(name=n) for n in ["Mira Sen", "Arun Das", "Leah Carter", "Samir Rao", "Nora Patel", "Ishaan Mehta", "Ella Green", "Dev Malik", "Ruth James", "Noah Kim"]]
    publishers = [Publisher(name=n) for n in ["Campus Press", "Northstar Academic", "Riverbend Books", "Open Shelf Publishing"]]
    db.session.add_all(categories + authors + publishers)
    db.session.flush()

    titles = [
        "Foundations of Computing", "Data Structures in Practice", "Networks and Society", "Secure Systems Primer", "Human Computer Interaction",
        "The Quiet Observatory", "Monsoon Letters", "Stories from the Coast", "A Map of Small Things", "The Last Paper Crane",
        "Calculus for Curious Minds", "Linear Algebra Workbook", "Statistics and Evidence", "Discrete Models", "Applied Probability",
        "World History: Shared Paths", "The City Through Time", "Archives and Memory", "Trade Routes of Asia", "Ideas that Changed Us",
        "Ecology in Everyday Life", "Physics at Work", "Chemistry Around Us", "The Living Cell", "Climate Systems Explained",
        "Principles of Management", "Ethics at Work", "Social Enterprise Toolkit", "Accounting Basics", "Project Teams that Learn",
    ]
    books = []
    for i, title in enumerate(titles):
        book = Book(isbn=f"978000{i + 1:07d}", title=title, author_id=authors[i % len(authors)].id,
                    category_id=categories[i // 5].id, publisher_id=publishers[i % len(publishers)].id,
                    publication_year=2016 + i % 10)
        db.session.add(book)
        books.append(book)
    db.session.flush()
    copies_by_book = {}
    for i, book in enumerate(books):
        count = 1 + (i % 3)
        copies = []
        for c in range(count):
            copy = BookCopy(book_id=book.id, barcode=f"DEMO-{i + 1:03d}-{c + 1:02d}")
            db.session.add(copy)
            copies.append(copy)
        copies_by_book[book.id] = copies
    db.session.flush()

    # Fictional service records span recent months so charts have visible trends.
    for index in range(14):
        member = members[index % len(members)]
        book = books[index]
        copy = copies_by_book[book.id][0]
        issued = utcnow() - timedelta(days=(index * 5 + 2) % 80)
        if index < 8:
            due = date.today() + timedelta(days=(index % 4) - 2)
            copy.status = "loaned"
            db.session.add(Loan(copy_id=copy.id, member_id=member.id, issued_by_id=admin.id,
                                issued_at=issued, due_date=due, status="active", issue_seconds=320 + index * 85))
        else:
            late = 4 if index in (8, 11) else 0
            due = (issued.date() - timedelta(days=late))
            returned = issued + timedelta(days=10 + late)
            db.session.add(Loan(copy_id=copy.id, member_id=member.id, issued_by_id=admin.id,
                                returned_to_id=admin.id, issued_at=issued, due_date=due,
                                returned_at=returned, status="returned", issue_seconds=420 + index * 55))
            if late:
                db.session.flush()
                loan = Loan.query.filter_by(copy_id=copy.id).one()
                db.session.add(Fine(loan_id=loan.id, amount=Decimal(late), paid=(index == 8), assessed_at=returned))

    fb_categories = list({"book_availability": 0, "staff_service": 0, "waiting_time": 0, "cleanliness": 0, "digital_access": 0, "other": 0})
    ratings = [5, 4, 4, 3, 5, 2, 4, 5, 3, 4, 5, 3, 4, 2, 5, 4, 3, 5]
    for i, rating in enumerate(ratings):
        created = utcnow() - timedelta(days=8 + (i * 4) % 83)
        db.session.add(Feedback(member_id=members[i % len(members)].id, category=fb_categories[i % len(fb_categories)],
                                rating=rating, comments=f"Fictional demo feedback entry {i + 1}.", created_at=created))

    complaint_categories = ["waiting_time", "book_availability", "digital_access", "staff_service", "cleanliness", "other"]
    complaints = []
    for i, category in enumerate(complaint_categories * 2):
        created = utcnow() - timedelta(days=4 + i * 6)
        status = "resolved" if i < 8 else "open"
        row = Complaint(member_id=members[i % len(members)].id, category=category,
                        subject=f"Demo service concern {i + 1}",
                        description=f"Fictional example report about {category.replace('_', ' ')}.",
                        status=status, created_at=created,
                        resolved_at=created + timedelta(days=2 + i % 5) if status == "resolved" else None)
        db.session.add(row)
        complaints.append(row)
    db.session.flush()

    db.session.add_all([
        RootCauseAnalysis(complaint_id=complaints[0].id, problem_statement="Peak hour queue exceeds service target.",
                          people="One service desk is staffed at lunch.", processes="Returns and new issues share a single queue.",
                          technology="No self check in available.", materials_resources="Only one scanner is in use.",
                          environment="Class change creates a short arrival peak.", policies="All transactions require a desk check.",
                          whys_json='["Students arrive between classes", "The queue shares one line", "Tasks are not separated", "No peak schedule exists", "Demand data is not reviewed"]',
                          root_cause="Service capacity is not scheduled against observed peak demand.", created_by_id=quality.id),
        RootCauseAnalysis(complaint_id=complaints[2].id, problem_statement="Digital catalog searches occasionally time out.",
                          technology="Search index is rebuilt manually.", processes="No recurring maintenance check.",
                          whys_json='["Requests time out", "Index refresh is delayed", "No job is scheduled", "Ownership is unclear", "There is no service checklist"]',
                          root_cause="The search index lacks an assigned automated maintenance process.", created_by_id=quality.id),
    ])

    db.session.add_all([
        ImprovementAction(problem="Reduce the mid-day service queue", root_cause="Staffing does not follow demand peaks.",
                          corrective_action="Pilot a second service desk for the 12:00–14:00 peak and log wait samples weekly.", owner_id=admin.id,
                          deadline=date.today() + timedelta(days=20), status="in_progress", created_by_id=quality.id),
        ImprovementAction(problem="Improve catalog search reliability", root_cause="Index refresh is manual and ownership is unclear.",
                          corrective_action="Assign a weekly index check and document the recovery procedure.", owner_id=quality.id,
                          deadline=date.today() + timedelta(days=10), status="pending", created_by_id=quality.id),
        ImprovementAction(problem="Clarify book reservation status", root_cause="Members cannot see queue status.",
                          corrective_action="Send a notification when a reserved copy is ready and add status tracking.", owner_id=admin.id,
                          deadline=date.today() - timedelta(days=5), status="completed", completed_at=utcnow() - timedelta(days=8), created_by_id=quality.id),
    ])

    db.session.add_all([
        PdcaCycle(title="Peak-hour service pilot", problem="Median issue queue exceeds 8 minutes at lunch.",
                  measurable_target="Reduce median queue time to 5 minutes within 8 weeks.", baseline="Baseline: 8.6 minutes from 24 fictional observations.",
                  plan="Add a second desk during lunch for four weeks; sample queue times weekly.", do_notes="Second desk piloted Monday–Thursday, 12:00–14:00.",
                  check_result="Pilot sample median was 5.4 minutes; target was not fully met.", act_decision="Continue the pilot and adjust staffing on the two busiest days.",
                  phase="complete", owner_id=quality.id, started_at=utcnow() - timedelta(days=45), completed_at=utcnow() - timedelta(days=5),
                  outcome="Improved, target partially met; another cycle is recommended."),
        PdcaCycle(title="Reservation pickup notifications", problem="Members miss ready-to-pick-up reservations.",
                  measurable_target="Notify 95% of members within one minute of copy release.", baseline="Baseline: no automated notification.",
                  plan="Introduce an application notification when a return allocates to the next reservation.",
                  do_notes="Workflow implemented in the demo application.", phase="check", owner_id=admin.id, started_at=utcnow() - timedelta(days=12)),
        PdcaCycle(title="Catalog index checks", problem="Search results may be stale.", measurable_target="Weekly checks completed for 8 consecutive weeks.",
                  baseline="Baseline: no recorded checks.", plan="Assign a weekly search index checklist and record exceptions.", phase="plan", owner_id=quality.id),
    ])

    db.session.add_all([
        Reservation(book_id=books[0].id, member_id=members[9].id, status="waiting", available_at_request=False),
        Reservation(book_id=books[1].id, member_id=members[10].id, status="fulfilled", available_at_request=True, fulfilled_at=utcnow() - timedelta(days=5)),
    ])
    db.session.add_all([
        InventoryAudit(checked_copies=48, matching_copies=46, notes="Fictional demo shelf sample A.", audited_by_id=quality.id, created_at=utcnow() - timedelta(days=40)),
        InventoryAudit(checked_copies=52, matching_copies=51, notes="Fictional demo shelf sample B.", audited_by_id=quality.id, created_at=utcnow() - timedelta(days=12)),
    ])
    for member in members[:5]:
        db.session.add(Notification(user_id=member.id, title="Welcome to the demo library", message="This is fictional seed data for demonstration purposes.", kind="general"))
    db.session.commit()
