# HW8 Metrics

## Part 1 - CREATE_LISTING and GET_LISTING

| Check | Result |
| --- | --- |
| create_success | PASS |
| create_correlation_id_preserved | PASS |
| get_success | PASS |
| get_correlation_id_preserved | PASS |
| round_trip_matches | PASS |

| Error case | Error returned | correlation_id preserved |
| --- | --- | --- |
| GET_LISTING | Listing not found | True |
| CREATE_LISTING | monthly_rent must be a number greater than 0 | True |
| DELETE_LISTING | Unknown operation | True |

## Part 2 - Message journey

correlation_id: `15082799-765b-49e4-8833-e8231f4eaad2`

| Stage | Time (UTC) |
| --- | --- |
| SENDER | 2026-11-01T17:14:55.333Z |
| PLANNER | 2026-11-01T17:15:29.088Z |
| WRITER | 2026-11-01T17:16:05.514Z |
| REVIEWER | 2026-11-01T17:16:27.824Z |

Final status: **approved**

## Part 3 - Failure table

| Failure scenario | Before fix | After fix |
| --- | --- | --- |
| Duplicate delivery | Replay ran every agent again: 2 Reviewer runs, 2 messages in s6758_final | Replay skipped by the Planner: 1 duplicate skipped, 1 message in s6758_final |
| Consumer killed mid-work | Offset already committed at the kill (1); message not redelivered, 0 drafts, so the work was lost | No offset committed at the kill; message redelivered after restart, 1 draft, offset then committed (1) |
| Poison message | Writer crashed 2 times on the same message; later message processed: False | 3 attempts, 1 message in s6758_dead_letter, 0 crashes; later message processed: True |
| Two partitions/two consumers | 20 processed, 2 of 3 listings split across partitions, 2 of 3 out of order (L-6758-002, L-6758-003) | 20 processed, 0 of 3 listings split across partitions, 0 of 3 out of order |

## Part 3 - Ordering runs (VERIFY_SEED 266758, 20 messages)

| Run | Listing | Partitions | Processed seq | In order |
| --- | --- | --- | --- | --- |
| before | L-6758-001 | [1] | [1, 2, 3, 4] | True |
| before | L-6758-002 | [0, 1] | [1, 2, 3, 4, 6, 7, 5, 9, 8] | False |
| before | L-6758-003 | [0, 1] | [1, 2, 3, 4, 5, 7, 6] | False |
| after | L-6758-001 | [1] | [1, 2, 3, 4] | True |
| after | L-6758-002 | [1] | [1, 2, 3, 4, 5, 6, 7, 8, 9] | True |
| after | L-6758-003 | [0] | [1, 2, 3, 4, 5, 6, 7] | True |
