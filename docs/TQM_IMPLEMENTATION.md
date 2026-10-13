# TQM techniques in the application

TQM is expressed as working records and measures in the application, rather than as an informational-only page.

| Technique / measure | How it works | Where it appears |
|---|---|---|
| Voice of the member | Members submit a 1–5 service rating and categorized comment: availability, staff service, waiting time, cleanliness, digital access, or other. | **Share feedback** and the staff **Feedback register** |
| Customer satisfaction | Arithmetic mean of ratings submitted in the trailing 90 days; no ratings produces “Insufficient data.” The chart shows monthly means. | Staff dashboard and TQM dashboard |
| Complaint/service recovery | Members submit categorized complaints and can track state. Staff move them through open, in progress, resolved, or closed; changes create personal notifications. | **Report a concern**, **Complaint register**, **Notifications** |
| Pareto analysis | Complaint and feedback counts are grouped by category over 90 days, sorted high to low, and plotted with cumulative percentage. The leading category is highlighted. | TQM dashboard |
| Ishikawa / fishbone | A structured form captures contributing factors under People, Processes, Technology, Materials/resources, Environment, and Policies/procedures. | **Root-cause analysis** |
| 5 Whys | Up to five linked “why” statements are stored with the identified root cause. The form encourages evidence-based stopping at an actionable cause. | **Root-cause analysis** |
| Corrective-action register | Every action records a problem, root cause, corrective action, staff owner, deadline, and status; completion time supports on-time measurement. | **Improvement actions** |
| PDCA | Cycles are created with a baseline, measurable target, and plan, then advance in order through Do, Check, Act, and completion. Each phase's notes and final outcome remain in the cycle history. | **PDCA cycles** and the TQM dashboard |
| Inventory accuracy | Staff record physical count samples: checked copies and copies matching system state. | **Inventory audits** and KPI dashboard |
| Standard work / defect prevention | Server validation checks IDs, roles, ISBN, due dates, active loans, inventory state, ratings, statuses, and required fields. Issue and return procedures are transactional and audited. | Book forms, loan screen, service layer and audit register |
| Continuous measurement | Actual service records feed dashboards, monthly charts, and CSV reports. No synthetic values are substituted when the sample is empty. | Staff dashboard, TQM dashboard and **Reports & exports** |

## KPI definitions

The staff TQM dashboard uses a trailing 90-day cohort unless noted. The exact source is also exposed beside each metric in the interface.

| KPI | Formula | Reporting period and data source |
|---|---|---|
| Average customer satisfaction | Sum of rating values ÷ number of ratings | Feedback submitted in the trailing 90 days; scale 1–5 |
| Available when requested | Reservation requests with at least one available copy at submission ÷ all reservation requests × 100 | Reservation records created in the trailing 90 days; placing a reservation also records whether at least one copy was available at that moment |
| Average issue processing time | Mean recorded server-side issue workflow duration | Loans issued in the trailing 90 days; milliseconds for the database-backed issue operation, not a stopwatch of in-person queue time |
| Average complaint resolution time | Mean (`resolved_at` − `created_at`) | Resolved/closed complaints submitted in the trailing 90 days; days |
| Complaint resolution rate | Resolved/closed complaints in the cohort ÷ all complaints submitted in the cohort × 100 | Complaint submission cohort, trailing 90 days |
| Overdue-loan rate | Active loans with `due_date` before today ÷ all active loans × 100 | Current point-in-time snapshot; this is not a 90-day issue cohort |
| Inventory accuracy | Matching copies ÷ copies checked × 100 | Inventory audit samples created in the trailing 90 days; weighted by copies checked |
| Improvements completed on time | Actions completed by deadline ÷ all actions completed in period × 100 | Actions completed in the trailing 90 days |
| Borrowing trend / utilization | Count of issued loans by calendar month; total borrowing KPI is count of loans issued | Loan records in the trailing 90 days |

An unavailable denominator or missing sample is shown as **Insufficient data**. The issue-time value is specifically the application operation duration and should not be interpreted as the full service-desk waiting time. Control limits are not shown: this implementation has no consistent, rational subgroup dataset suitable for a statistically valid control chart. KPI values are descriptive; the application does not claim that a process is statistically in control. Management targets are recorded in individual PDCA cycles.
