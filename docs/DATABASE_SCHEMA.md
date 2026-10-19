# Database schema

The application uses SQLite through Flask-SQLAlchemy. Foreign keys are enabled on SQLite connections. SQLAlchemy models provide primary keys, foreign keys, unique constraints, status/rating/amount checks, and indexes on lookup and reporting fields. Physical inventory is represented by one `book_copies` row per copy; availability is derived from the status of those rows.

## Entity relationships

```mermaid
erDiagram
  USERS ||--o{ LOANS : borrows
  USERS ||--o{ RESERVATIONS : requests
  USERS ||--o{ FEEDBACK : submits
  USERS ||--o{ COMPLAINTS : submits
  USERS ||--o{ IMPROVEMENT_ACTIONS : owns
  USERS ||--o{ PDCA_CYCLES : leads
  USERS ||--o{ AUDIT_LOGS : performs
  USERS ||--o{ NOTIFICATIONS : receives
  AUTHORS ||--o{ BOOKS : writes
  CATEGORIES ||--o{ BOOKS : groups
  COURSES ||--o{ BOOKS : classifies
  PUBLISHERS ||--o{ BOOKS : publishes
  USERS o|--o{ SYSTEM_SETTINGS : updates
  BOOKS ||--|{ BOOK_COPIES : contains
  BOOKS ||--o{ RESERVATIONS : requested_as
  BOOK_COPIES ||--o{ LOANS : loaned_in
  LOANS ||--o| FINES : may_assess
  COMPLAINTS ||--o{ ROOTCAUSEANALYSES : investigated_by

  USERS {
    int id PK
    string full_name
    string email UK
    string password_hash
    int auth_version
    string role
    bool active
  }
  AUTHORS {
    int id PK
    string name UK
  }
  CATEGORIES {
    int id PK
    string name UK
  }
  COURSES {
    int id PK
    string name UK
  }
  PUBLISHERS {
    int id PK
    string name UK
  }
  INSTITUTIONAL_LIBRARY_FACTS {
    string fact_key PK
    text fact_value
    string source_url
    date source_checked_on
    text source_note
  }
  SYSTEM_SETTINGS {
    string key PK
    string value
    int updated_by_id FK
    datetime updated_at
  }
  BOOKS {
    int id PK
    string isbn UK
    string title
    int author_id FK
    int category_id FK
    int course_id FK
    int publisher_id FK
    int publication_year
    int semester
  }
  BOOK_COPIES {
    int id PK
    int book_id FK
    string barcode UK
    string status
    date acquired_at
  }
  LOANS {
    int id PK
    int copy_id FK
    int member_id FK
    int issued_by_id FK
    date due_date
    datetime issued_at
    datetime returned_at
    string status
  }
  RESERVATIONS {
    int id PK
    int book_id FK
    int member_id FK
    bool available_at_request
    string status
    datetime created_at
  }
  FINES {
    int id PK
    int loan_id FK
    decimal amount
    bool paid
  }
  FEEDBACK {
    int id PK
    int member_id FK
    string category
    int rating
    datetime created_at
  }
  COMPLAINTS {
    int id PK
    int member_id FK
    string category
    string status
    datetime resolved_at
  }
  ROOTCAUSEANALYSES {
    int id PK
    int complaint_id FK
    text six_fishbone_factors
    text whys_json
    text root_cause
  }
  IMPROVEMENT_ACTIONS {
    int id PK
    int owner_id FK
    date deadline
    string status
    datetime completed_at
  }
  PDCA_CYCLES {
    int id PK
    string phase
    text plan
    text do_notes
    text check_result
    text act_decision
    text outcome
  }
  AUDIT_LOGS {
    int id PK
    int user_id FK
    string action
    string entity_type
    int entity_id
    datetime created_at
  }
  NOTIFICATIONS {
    int id PK
    int user_id FK
    string kind
    string reference_key UK
    datetime read_at
  }
  INVENTORY_AUDITS {
    int id PK
    int checked_copies
    int matching_copies
    datetime created_at
  }
```

## Important consistency rules

- `users.role` is constrained to `admin`, `member`, or `quality_manager`; public registration always creates a `member`.
- ISBNs, emails, copy barcodes, and notification reference keys are unique.
- A partial unique index prevents two active loans for one physical copy. The issue service also checks for another active loan for the same member and title.
- A book's total/available copy count is derived from its copy rows. An active loan changes one copy from `available` to `loaned`; return changes it to `available` or `reserved` for the next waiting member.
- A partial unique index prevents duplicate active reservations for the same member and title.
- Rating, role, status, fine amount, and inventory audit counts have database checks in addition to request validation.
- Issue and return update the loan, copy, fine, reservation, audit, and notification records within one SQLAlchemy transaction. Exceptions roll the transaction back.
- `inventory_audits` holds physical spot-check samples. The accuracy KPI is based on these samples rather than assuming the database is correct.

The schema is initialized with the repeatable `flask --app run.py init-db` command. For an academic local demonstration this uses `create_all`; changes to an already deployed schema should be managed with a migration tool and a backup, not by resetting a database containing user data.
