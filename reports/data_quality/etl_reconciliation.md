# ETL Reconciliation Report

Generated at UTC: `2026-11-04T13:28:04.715818+00:00`

## Row reconciliation

- Raw rows: **444,448**
- Clean rows: **440,844**
- Excluded rows: **3,599**
- Quarantine rows: **5**
- Repaired rows: **12**
- 30-minute interval rows: **12,834**
- Offered calls across intervals: **440,844**
- Reconciliation passed: **True**

```text
444,448 = 440,844 + 3,599 + 5
```

## Reasons and quality flags

- Exclusion reasons: `{"phantom_record": 3599}`
- Quarantine reasons: `{"unexpected_service_type": 5}`
- Repair codes: `{"split_merged_priority_service_type": 12}`
- Quality flags: `{"abandoned_with_agent_label": 10, "answered_without_agent_label": 5216, "negative_vru_duration": 332, "queue_exit_midnight_rollover": 396, "queue_start_midnight_rollover": 338, "service_end_invalid_time_sequence": 5, "service_end_midnight_rollover": 2909, "service_start_invalid_time_sequence": 211, "service_start_midnight_rollover": 2622, "service_start_minor_clock_skew": 269428, "vru_exit_implausible_elapsed_time": 3, "vru_exit_invalid_time_sequence": 332, "zero_service_duration": 1250}`
- Source issues observed: `{"abandoned_with_agent_label": 10, "answered_with_zero_service_duration": 1250, "answered_without_agent_label": 5216, "negative_vru_duration": 350, "unexpected_service_type": 5}`

Customer IDs and raw agent labels are not present in any ETL output.
