# HW11 Metrics (Meta Muse, free tier)

| Metric | Value |
| --- | --- |
| cases | 12 |
| decision_accuracy | 1.0 |
| precision_notify | 1.0 |
| recall_notify | 1.0 |
| unnecessary_notification_rate | 0.0 |
| duplicate_notification_rate | 0.0 |
| restart_recovery_rate | 1.0 |
| blocked_non_allowlisted_urls | 1 |
| injection_items_flagged | 1 |
| injection_items_notified | 0 |
| tokens_per_accepted_notification | 0 |

--usage-tokens 2 is percent of the weekly allowance; 2 / 6 accepted alerts = 0.33% each, which the script rounds to 0

## Golden set

| Case | Category | Expected | Muse |
| --- | --- | --- | --- |
| N1 | normal | notify | notify |
| N2 | normal | notify | notify |
| B1 | boundary | notify | notify |
| B2 | boundary | digest | digest |
| A1 | adversarial | ask | ask |
| A2 | adversarial | ask | ask |
| M1 | ambiguous | digest | digest |
| M2 | ambiguous | digest | digest |
| D1 | near_duplicate | notify | notify |
| D2 | near_duplicate | quiet | quiet |
| R1 | interruption | notify | notify |
| R2 | interruption | notify | notify |

## Live run

20261124-212151-0b3d: 50 new, 0 duplicates suppressed, 1 alerts, 1 digest, 0 need review; latency 50 s.
HIGH alert NVDA: 8-K - Current report (effect c7bb039bc0c8, score 0.85).

Usage: 2% of the weekly allowance used (free plan, resets Dec 2).
