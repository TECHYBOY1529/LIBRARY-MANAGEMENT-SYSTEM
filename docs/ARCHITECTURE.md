# Application architecture

```mermaid
flowchart LR
  Browser[Browser: HTML5 / CSS3 / Bootstrap 5 / JavaScript / Chart.js] --> Flask[Flask application]
  Flask --> Auth["Auth blueprint<br/>Flask sessions + password hash + CSRF"]
  Flask --> Library[Catalog and circulation blueprint]
  Flask --> Quality[Feedback, complaints and TQM blueprint]
  Flask --> Reports[Reports and CSV blueprint]
  Auth --> Services[Reusable service layer]
  Library --> Services
  Quality --> Services
  Reports --> ORM[Flask-SQLAlchemy ORM]
  Services --> ORM
  ORM --> SQLite[(SQLite database)]
  Services --> Audit[Audit log and notifications]
  Audit --> ORM
```

## Issue / return workflow

```mermaid
sequenceDiagram
  actor Staff as Librarian
  participant UI as Loan screen
  participant Service as Transaction service
  participant DB as SQLite
  participant Member as Member account
  Staff->>UI: Select member and title
  UI->>Service: Validate issue request
  Service->>DB: Begin transaction and verify member, duplicate, copy
  alt Eligible copy found
    Service->>DB: Copy available → loaned; insert loan, audit, due notification
    DB-->>Service: Commit
    Service-->>UI: Confirm issue and due date
  else Invalid / unavailable
    Service->>DB: Roll back
    Service-->>UI: Explain validation failure
  end
  Staff->>UI: Scan/process active loan return
  UI->>Service: Validate active loan
  Service->>DB: Set returned; assess configured fine; release or allocate copy
  alt Waiting member exists
    Service->>DB: Mark reservation ready and notify member
  else No waiting member
    Service->>DB: Copy status → available
  end
  Service->>DB: Write audit record and commit transaction
  Service-->>UI: Confirm return and fine (if any)
```
