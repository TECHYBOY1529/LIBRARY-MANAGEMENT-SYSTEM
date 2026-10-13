# Academic project report outline

## Title
Library Management System Using Total Quality Management Practices

## Abstract
Summarize the library service problem, the Flask/SQLite solution, role-based workflows, TQM methods, test approach, measured results, and the prototype's limitations. Report only results reproduced from the demo database or tests.

## 1. Introduction
- Role of academic libraries in teaching and research.
- Service quality, reliable collections, and feedback loops.
- Scope of a practical library management system.

## 2. Problem Statement
- Manual or fragmented circulation and inventory records can cause inconsistent availability and overdue tracking.
- Complaints and feedback may not be categorized or linked to corrective action.
- Without measured follow-up, process improvements are difficult to verify.

## 3. Objectives
- Build a role-based catalog, circulation and member workflow.
- Maintain copy-level inventory and transactional issue/return procedures.
- Collect member ratings and categorized complaints.
- Implement root-cause, corrective-action, and PDCA records.
- Calculate transparent service KPIs from application records.
- Verify critical workflows with automated tests.

## 4. Existing System
Describe the institution's current library process based on local interviews or observation. This section should be completed with the student's own findings; do not present the fictional demo data as a study of a real institution.

## 5. Proposed System
- Flask web application with HTML5, CSS3, JavaScript, Bootstrap 5, Chart.js, and SQLite.
- Three roles: Admin/Librarian, Member/Student, and Quality Manager.
- Individual book copies, reservations, loans, fines, feedback, complaints, notifications, reports, and quality records.

## 6. Methodology
- Requirements elicitation and role-based use cases.
- Relational schema design and constraints.
- Iterative implementation with validation, transaction boundaries, and audit records.
- PDCA as the quality-improvement method.
- Pytest unit, integration, and workflow tests.

## 7. System Requirements
- Python 3.10 or newer, pip, SQLite, and a modern browser.
- Functional requirements by user role.
- Nonfunctional requirements: usability, maintainability, security, accessibility, and data integrity.

## 8. Database Design
Explain normalized users, books, copies, loans, reservations, fines, feedback, complaints, RCAs, actions, PDCA, audit, notification, and inventory-audit tables. Include primary keys, foreign keys, constraints, and indexes from `DATABASE_SCHEMA.md`.

## 9. Module Descriptions
- Authentication and role authorization.
- Catalog and metadata management.
- Members, circulation, reservations, returns, and fines.
- Feedback, complaints, and notifications.
- TQM analytics, Pareto, fishbone/5 Whys, actions, PDCA, and inventory audits.
- Reports and CSV exports.

## 10. Implementation
Describe the blueprint structure, SQLAlchemy models, service layer, sessions, password hashing, CSRF protection, environment configuration, transaction rollback, frontend, and Chart.js dashboards.

## 11. Testing
Summarize `python -m pytest -v`, the covered role and circulation workflows, invalid input handling, KPI edge cases, and rollback behavior. Include actual pass/fail output from the run being reported.

## 12. Results
Present verified application screenshots and measured outputs produced from the clearly labeled fictional seed data. Include the KPI formulas and reporting periods; distinguish the demo dataset from real institutional evidence.

## 13. Limitations
- No live email/SMS delivery; notifications are in-app.
- No barcode scanner or payment gateway integration.
- Issue-operation duration measures server-side workflow time, not a physical service queue.
- Control charts are withheld until consistent subgroup data is collected.
- Local SQLite and academic demo account are not a multi-branch production deployment.

## 14. Conclusion
Summarize achieved workflows and explain how feedback, measured review, root-cause analysis, and PDCA support continuous improvement. Propose institution-specific pilot evaluation as future work.
