# Demonstration guide

All data in this local walkthrough is fictional seed data. Do not treat it as a real library dataset.

## Start the application

1. Install dependencies and copy `.env.example` to `.env` (see the README).
2. Initialize and seed: `python -m flask --app run.py reset-demo`.
3. Start the current checkout with `python -m flask --app run.py run --host 127.0.0.1 --port 5002`; open `http://127.0.0.1:5002`. If another server is already using that port, leave it running and choose a free port, then open that port instead.
4. Use the demo accounts below. Change demo passwords with the hidden-prompt CLI before sharing a local machine.

At `/login`, choose **Student** for member accounts or **Library management** for Admin/Librarian and Quality Manager accounts. The server checks the selected account type before signing in and directs each role to its own dashboard.

## Example workflows

### Member experience

1. Sign in as `student01@library.demo` using the shared demo password.
2. Browse the catalog and search by title, ISBN, or author; try the availability filter.
3. Place a reservation on a title. If a copy is available, it is held and becomes ready; otherwise the request enters the waiting list.
4. Submit a 1–5 rating and categorized feedback. Submit a concern, then check its status and notifications.
5. Review due dates, history, reservations, and personal fines.

### Librarian circulation

1. Sign in as the demo admin and open **Loans & returns**.
2. Issue a title to an active member. The system selects an available copy, records its barcode, sets a due date, and audits the change.
3. Try to issue the same title to that member again; verify the duplicate-loan validation.
4. Return the active loan. The copy becomes available or is held for the oldest waiting reservation. Late returns receive a configured fine.
5. Check the copy inventory, loan history, fine register, and CSV exports.

### TQM cycle

1. Sign in as the Quality Manager and review the satisfaction, borrowing, complaint category, KPI, Pareto, and PDCA charts.
2. Inspect the feedback and complaint registers. Update a complaint and confirm the member notification.
3. Complete an Ishikawa form across six dimensions and a 5 Whys chain.
4. Assign an improvement action to a staff owner with a deadline and update its status.
5. Start a PDCA cycle with a baseline and measurable target. Complete Do, Check, Act in order and close it with a result.
6. Record a physical inventory sample to populate the accuracy KPI.

## Screenshots

No screenshot files are checked into this repository. For a report, capture only fictional demo-data views for the Admin dashboard, TQM dashboard, and Member dashboard. Do not capture real member data.
