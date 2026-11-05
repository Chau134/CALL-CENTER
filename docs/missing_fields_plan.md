# Kế hoạch bổ sung trường dữ liệu sau ETL

## 1. Mục đích

Tài liệu này xác định các trường còn thiếu sau khi ETL bộ Technion Anonymous Bank, nguồn của từng trường, quy tắc tạo, mức ưu tiên và kiểm tra chất lượng cần áp dụng.

Hiện trạng đầu vào sau ETL:

- 440.844 call records thuộc luồng clean;
- 3.599 record `PHANTOM` thuộc luồng excluded;
- 5 record service type không hợp lệ thuộc quarantine;
- 12.834 interval 30 phút có ít nhất một cuộc gọi;
- tổng `offered_calls` trên interval bằng 440.844;
- có 52 agent ID đã được giả danh;
- dữ liệu nguồn/call-level ETL không có schedule, attendance, agent state, team, holiday, hold, ACW, CSAT hoặc FCR; holiday sau đó được bổ sung như external calendar reference, không phải source-observed field.

**Trạng thái triển khai ngày 05/11/2026:** P0 foundation marts, rolling-origin forecast, AHT proxy forecast, workload-based staffing requirement và PostgreSQL analytics warehouse đã hoàn thành. Chín marts/9 KPI views đã được load và đối soát. Workforce extension dùng schedule/attendance/state synthetic chưa được thực hiện.

Tài liệu này không cho phép sửa raw data hoặc điền giá trị không có bằng giá trị 0 nếu chưa có quy tắc nghiệp vụ.

## 2. Quy ước chung

### 2.1 Phân loại nguồn dữ liệu

Mỗi bảng hoặc record bổ sung phải có `data_origin` thuộc một trong các giá trị:

| Giá trị | Ý nghĩa |
|---|---|
| `source_observed` | Giá trị có trực tiếp trong dữ liệu nguồn |
| `derived` | Tính xác định từ giá trị nguồn |
| `external_reference` | Lấy từ lịch hoặc danh mục tham chiếu bên ngoài |
| `project_assumption` | Giả định đã được dự án phê duyệt |
| `synthetic` | Dữ liệu mô phỏng, không phải dữ liệu vận hành thật |

Không được gắn nhãn `source_observed` cho trường được suy luận hoặc tự tạo.

### 2.2 Trường audit dùng chung

Các bảng bổ sung nên có các trường sau khi phù hợp:

| Trường | Kiểu đề xuất | Nullable | Quy tắc |
|---|---|---:|---|
| `data_origin` | varchar(32) | Không | Một trong năm giá trị nguồn đã định nghĩa |
| `source_reference` | text | Có | URL, tên file hoặc tài liệu tạo dữ liệu |
| `is_synthetic` | boolean | Không | `true` chỉ khi record được mô phỏng |
| `generation_method` | text | Có | Tên quy tắc/script sinh dữ liệu |
| `generation_version` | varchar(20) | Có | Phiên bản logic sinh dữ liệu |
| `random_seed` | integer | Có | Bắt buộc với dữ liệu synthetic ngẫu nhiên |
| `created_at` | timestamptz | Không | Thời điểm record được tạo |
| `etl_run_id` | varchar(64) | Không | Khóa liên kết với một lần chạy ETL |

### 2.3 Mức ưu tiên

| Mức | Ý nghĩa |
|---|---|
| P0 | Bắt buộc trước EDA và forecast |
| P1 | Bắt buộc trước staffing requirement và Power BI MVP |
| P2 | Bắt buộc trước schedule gap, adherence và occupancy |
| P3 | Phần mở rộng cho customer experience hoặc agent quality |

## 3. Hoàn thiện time spine 30 phút — P0

Dữ liệu hiện có 12.834 interval có call. Năm 1999 có 17.520 vị trí wall-clock 30 phút (`365 × 48`), vì vậy có 4.686 vị trí chưa xuất hiện trong interval mart. Các vị trí này phải được phân loại trước khi điền volume bằng 0.

### 3.1 Các trường cần thêm vào `fact_queue_interval_complete`

Grain mục tiêu:

```text
date_key × interval_key × queue_id
```

| Trường | Kiểu đề xuất | Nullable | Nguồn | Quy tắc |
|---|---|---:|---|---|
| `local_interval_start` | timestamp | Không | derived | Wall-clock local time; dùng cho grain và phân tích intraday |
| `local_interval_end` | timestamp | Không | derived | `local_interval_start + 30 phút` theo wall clock |
| `interval_start_utc` | timestamptz | Có | derived | Null khi local time ambiguous/nonexistent và nguồn không đủ thông tin chọn fold |
| `interval_end_utc` | timestamptz | Có | derived | Null khi không xác định an toàn được UTC boundary |
| `interval_minutes` | smallint | Không | project_assumption | Luôn bằng `30` |
| `queue_id` | varchar(50) | Không | project_assumption | MVP dùng `INBOUND_SUPPORT` |
| `channel` | varchar(30) | Không | project_assumption | Luôn bằng `inbound_voice` |
| `direction` | varchar(20) | Không | project_assumption | Luôn bằng `inbound` |
| `has_calls` | boolean | Không | derived | `offered_calls > 0` |
| `agent_demand_calls` | integer | Không | derived | Answered calls + abandoned calls đã vào queue; target cho staffing forecast |
| `queue_abandoned_calls` | integer | Không | derived | Abandoned và `reached_queue = true` |
| `vru_abandoned_calls` | integer | Không | derived | Abandoned trước khi vào queue; không tạo workload cho agent |
| `source_file_available` | boolean | Không | derived | File nguồn tương ứng tồn tại và qua kiểm tra toàn vẹn |
| `source_date_covered` | boolean | Không | derived | Ngày có dữ liệu nguồn được xác nhận đầy đủ |
| `interval_coverage_verified` | boolean | Không | derived | Có bằng chứng interval thuộc phạm vi ghi nhận đầy đủ |
| `source_period_covered` | boolean | Không | derived | Trường tổng hợp tương thích; không chỉ dựa vào việc file tháng tồn tại và qua checksum |
| `is_operating_interval` | boolean | Không | derived | Dựa trên operating hours trong `config/project.yml` |
| `is_closed_interval` | boolean | Không | derived | Phủ định của `is_operating_interval` |
| `coverage_status` | varchar(40) | Không | derived | Theo danh mục coverage bên dưới |
| `zero_fill_reason` | varchar(50) | Có | derived | Lý do volume được điền 0 |
| `timezone_assumption` | varchar(50) | Không | project_assumption | `Asia/Jerusalem` |
| `dst_transition_flag` | boolean | Không | derived | Đánh dấu interval nằm trong ngày chuyển DST |
| `dst_status` | varchar(20) | Có | derived | `normal`, `ambiguous`, `nonexistent` hoặc `unknown` |

Danh mục `coverage_status`:

| Giá trị | Điều kiện |
|---|---|
| `observed_with_calls` | Có ít nhất một clean call |
| `observed_excluded_only` | Có raw record trong interval nhưng tất cả bị excluded/quarantine |
| `zero_filled_operating` | File nguồn bao phủ, trong giờ hoạt động, không có call |
| `zero_filled_closed` | File nguồn bao phủ, ngoài giờ hoạt động, không có call |
| `data_gap` | Không đủ bằng chứng để kết luận volume bằng 0 |

Chỉ hai trạng thái `zero_filled_operating` và `zero_filled_closed` mới được điền `offered_calls = 0`, đồng thời phải có `interval_coverage_verified = true`. Tài liệu nguồn Technion ghi rõ dữ liệu lưu toàn bộ cuộc gọi trong 12 tháng và VRU hoạt động 24/7; kết luận coverage phải dựa đồng thời trên tuyên bố này, đủ 12 file, checksum, phạm vi ngày và row reconciliation. Không được suy ra coverage đầy đủ chỉ vì file tháng tồn tại. `data_gap` phải giữ metric null và được điều tra.

### 3.2 Quy tắc DST

Nguồn chỉ chứa local date/time, không có UTC offset hoặc fold indicator. Vì vậy:

- `dim_time_interval` vẫn có 48 wall-clock slots/ngày để phân tích giờ trong ngày;
- không mặc định mọi ngày đều có đúng 48 timestamp thực tế sau khi chuyển sang UTC; ngày DST có thể có interval local không tồn tại hoặc bị lặp;
- khóa nghiệp vụ dùng `date_key + interval_key + queue_id`, nhưng phải bổ sung cờ/trạng thái DST để nhận diện giờ lặp; không dùng riêng `interval_start` làm bằng chứng tuyệt đối cho giờ lặp khi kết thúc DST;
- giữ `timezone_assumption = Asia/Jerusalem` chỉ sau khi đối chiếu với logic ETL và tài liệu nguồn; Python, SQL và Power BI phải dùng cùng một timezone;
- đánh dấu ngày/interval DST để người dùng biết giới hạn của dữ liệu nguồn.

**Lưu ý về số lượng:** `365 × 48 = 17.520` là số wall-clock slots theo lịch, không nhất thiết là số timestamp thực tế duy nhất trong timezone có DST. Vì vậy, điều kiện kiểm tra 17.520 bên dưới phải được hiểu là số tổ hợp date × wall-clock interval, không phải khẳng định mọi ngày có 48 interval thực tế theo UTC.

## 4. Bảng ngày `dim_date` — P0

Grain: một ngày, từ `1999-01-01` đến `1999-12-31`.

| Trường | Kiểu đề xuất | Nullable | Nguồn/Quy tắc |
|---|---|---:|---|
| `date_key` | integer | Không | Dạng `YYYYMMDD`, primary key |
| `calendar_date` | date | Không | Ngày đầy đủ |
| `day_of_week_iso` | smallint | Không | Thứ Hai = 1, Chủ Nhật = 7 |
| `day_name` | varchar(12) | Không | Tên ngày chuẩn tiếng Anh hoặc tiếng Việt thống nhất |
| `day_of_month` | smallint | Không | 1–31 |
| `day_of_year` | smallint | Không | 1–365 |
| `week_of_year` | smallint | Không | ISO week |
| `week_start_date` | date | Không | Ngày đầu tuần theo ISO |
| `month_number` | smallint | Không | 1–12 |
| `month_name` | varchar(12) | Không | Tên tháng |
| `quarter_number` | smallint | Không | 1–4 |
| `year_number` | smallint | Không | 1999 |
| `is_weekend` | boolean | Không | Thứ Sáu hoặc Thứ Bảy theo tuần làm việc tại Israel; không đồng nghĩa đóng cửa cả ngày |
| `is_operating_day` | boolean | Không | Có ít nhất một interval hoạt động |
| `is_holiday` | boolean | Không | Từ lịch Israel năm 1999 |
| `holiday_name` | varchar(150) | Có | Tên ngày lễ |
| `holiday_type` | varchar(50) | Có | `national`, `religious`, `bank` hoặc loại phù hợp |
| `is_calendar_day_before_holiday` | boolean | Không | Một ngày lịch trước holiday; không khẳng định có ảnh hưởng vận hành |
| `is_calendar_day_after_holiday` | boolean | Không | Một ngày lịch sau holiday; không khẳng định có ảnh hưởng vận hành |
| `is_dst_transition_day` | boolean | Không | Ngày đổi DST tại Israel |

Các trường holiday phải dùng lịch Israel năm 1999 và có `data_origin = external_reference`. Không dùng lịch Việt Nam hoặc lịch năm hiện tại. `is_holiday` ở đây chỉ có nghĩa là ngày có observance trong calendar reference, không đồng nghĩa ngày nghỉ ngân hàng hoặc call center đóng cửa. Cần lưu nguồn tham chiếu và không mặc định mọi ngày lễ tôn giáo đều làm call center đóng cửa.

## 5. Bảng interval trong ngày `dim_time_interval` — P0

Grain: 48 interval wall-clock trong một ngày.

| Trường | Kiểu đề xuất | Nullable | Quy tắc |
|---|---|---:|---|
| `interval_key` | char(4) | Không | `HHMM`, ví dụ `0730` |
| `interval_number` | smallint | Không | 0–47 |
| `start_time` | time | Không | Giờ bắt đầu |
| `end_time` | time | Không | Giờ kết thúc |
| `interval_minutes` | smallint | Không | 30 |
| `hour_number` | smallint | Không | 0–23 |
| `minute_number` | smallint | Không | 0 hoặc 30 |
| `daypart` | varchar(20) | Không | `overnight`, `morning`, `afternoon`, `evening` |

Ranh giới `daypart` phải được định nghĩa một lần trong tài liệu metric, không hard-code khác nhau giữa Python, SQL và Power BI.

## 6. Queue và service mapping — P0

### 6.1 `dim_queue`

MVP tiếp tục dùng một queue tổng hợp. `service_type_code` vẫn là chiều phân tích riêng, không tự tuyên bố sáu service type là sáu queue thật. Do bảng queue interval có grain tổng hợp theo queue, cần thêm `fact_service_type_interval` để phân tích volume theo service type mà không làm thay đổi grain của bảng queue.

| Trường | Kiểu đề xuất | Nullable | Nguồn/Quy tắc |
|---|---|---:|---|
| `queue_id` | varchar(50) | Không | `INBOUND_SUPPORT` |
| `queue_name` | varchar(100) | Không | Tên hiển thị của queue MVP |
| `channel` | varchar(30) | Không | `inbound_voice` |
| `direction` | varchar(20) | Không | `inbound` |
| `timezone` | varchar(50) | Không | `Asia/Jerusalem` |
| `is_active` | boolean | Không | `true` cho giai đoạn nguồn |
| `valid_from` | date | Không | `1999-01-01` |
| `valid_to` | date | Không | `1999-12-31` |

### 6.2 `dim_service_type`

| Trường | Kiểu đề xuất | Nullable | Nguồn/Quy tắc |
|---|---|---:|---|
| `service_type_code` | varchar(5) | Không | `PS`, `PE`, `IN`, `NE`, `NW`, `TT` |
| `service_type_name` | varchar(150) | Không | Theo documentation nguồn |
| `queue_id` | varchar(50) | Không | MVP map về `INBOUND_SUPPORT` |
| `is_valid` | boolean | Không | `true` cho sáu mã hợp lệ |
| `valid_from` | date | Không | Bắt đầu coverage |
| `valid_to` | date | Có | Kết thúc coverage nếu có |

### 6.3 `fact_service_type_interval` — P0 (bổ sung)

Grain:

```text
date_key × interval_key × service_type_code
```

Các measure tối thiểu: `offered_calls`, `answered_calls`, `abandoned_calls`, `valid_for_aht_calls`, `service_seconds_sum`. Bảng được aggregate từ `fact_call`; không tạo queue/service mapping giả định mới. Tổng volume của tất cả service type hợp lệ phải reconcile với tổng volume call hợp lệ theo cùng quy tắc loại trừ/quarantine.

## 7. Sự kiện vận hành `fact_event_calendar` — P1

Không trộn event với holiday nếu event chỉ là giả định cho portfolio.

| Trường | Kiểu đề xuất | Nullable | Quy tắc |
|---|---|---:|---|
| `event_id` | varchar(50) | Không | Primary key |
| `event_name` | varchar(150) | Không | Tên sự kiện |
| `event_type` | varchar(50) | Không | `holiday`, `campaign`, `outage`, `policy_change`, `other` |
| `event_start` | timestamptz | Không | Thời điểm bắt đầu |
| `event_end` | timestamptz | Không | Thời điểm kết thúc |
| `impact_level` | varchar(10) | Có | `low`, `medium`, `high` |
| `expected_volume_uplift_pct` | numeric(8,4) | Có | Chỉ dùng khi có giả định/tài liệu rõ ràng |
| `notes` | text | Có | Giải thích |

Nếu event được tự tạo, bắt buộc `data_origin = synthetic`; không trình bày như sự kiện lịch sử thật.

## 8. Agent master `dim_agent` — P1

52 `agent_id` hiện có được lấy từ nhãn agent nguồn đã giả danh. Không khôi phục hoặc xuất raw agent label. Chỉ `agent_id` và các thuộc tính quan sát được như `first_seen_date`/`last_seen_date` (nếu bổ sung) là nền tảng từ dữ liệu nguồn. `team_id`, `site_id`, `employment_type`, `fte_ratio`, `hire_date`, `termination_date`, `employment_status` và `primary_skill` không được suy luận từ call log; để null nếu chưa mô phỏng. Mọi thuộc tính mô phỏng phải có `data_origin = synthetic`.

| Trường | Kiểu đề xuất | Nullable | Nguồn/Quy tắc |
|---|---|---:|---|
| `agent_id` | varchar(20) | Không | ID giả danh hiện có |
| `team_id` | varchar(20) | Có | Null nếu chưa tạo mapping; synthetic nếu mô phỏng team |
| `site_id` | varchar(20) | Có | Synthetic hoặc project assumption |
| `employment_type` | varchar(20) | Có | Chỉ có giá trị khi có nguồn hoặc synthetic được gắn nhãn rõ ràng |
| `fte_ratio` | numeric(4,2) | Có | Trong khoảng `(0, 1]`; chỉ điền khi có nguồn hoặc synthetic được gắn nhãn |
| `hire_date` | date | Có | Nếu synthetic, không sau ngày agent xuất hiện đầu tiên; không suy ra từ lần xuất hiện đầu tiên |
| `termination_date` | date | Có | Phải không trước lần xuất hiện cuối |
| `employment_status` | varchar(20) | Có | `active`, `inactive`, `terminated`; chỉ điền khi có nguồn hoặc synthetic |
| `primary_skill` | varchar(20) | Có | Chỉ synthetic nếu không có skill source |
| `valid_from` | date | Không | Hiệu lực phiên bản dimension |
| `valid_to` | date | Có | Null cho phiên bản hiện hành |
| `is_current` | boolean | Không | Cờ Slowly Changing Dimension |

Không được gán agent giả cho 5.216 answered calls thiếu agent label. Các call đó giữ `agent_id = null`, vẫn tính queue volume nhưng không tính agent KPI. Không được lấy phân bổ team/skill synthetic để gán ngược agent cho những call thiếu agent label.

## 9. Team master `dim_team` — P1

| Trường | Kiểu đề xuất | Nullable | Nguồn/Quy tắc |
|---|---|---:|---|
| `team_id` | varchar(20) | Không | Primary key |
| `team_name` | varchar(100) | Không | Tên trung tính, không dùng tên người thật |
| `supervisor_id` | varchar(20) | Có | Synthetic nếu cần mô phỏng hierarchy |
| `site_id` | varchar(20) | Có | Liên kết site |
| `valid_from` | date | Không | Ngày bắt đầu hiệu lực |
| `valid_to` | date | Có | Ngày kết thúc hiệu lực |
| `is_current` | boolean | Không | Phiên bản hiện hành |

## 10. Schedule `fact_schedule_segment` — P2

Chỉ tạo sau khi có forecast và required staffing để tránh dùng trực tiếp actual volume của cùng interval làm schedule.

Grain:

```text
agent_id × activity segment
```

| Trường | Kiểu đề xuất | Nullable | Quy tắc |
|---|---|---:|---|
| `schedule_segment_id` | varchar(64) | Không | Primary key xác định |
| `schedule_version` | varchar(30) | Không | Phiên bản kế hoạch |
| `agent_id` | varchar(20) | Không | Foreign key `dim_agent` |
| `schedule_date` | date | Không | Ngày ca |
| `scheduled_start` | timestamptz | Không | Bắt đầu segment |
| `scheduled_end` | timestamptz | Không | Lớn hơn start |
| `activity_code` | varchar(30) | Không | Theo danh mục activity |
| `queue_id` | varchar(50) | Có | Bắt buộc với `PRODUCTION` |
| `scheduled_seconds` | integer | Không | `end - start` |
| `productive_seconds` | integer | Không | Chỉ phần được tính productive |
| `paid_seconds` | integer | Không | Phần được trả lương |
| `is_overtime` | boolean | Không | Cờ làm thêm |

Danh mục `activity_code` tối thiểu:

```text
PRODUCTION
BREAK
MEAL
TRAINING
MEETING
COACHING
OFF
LEAVE
```

Các segment của cùng một agent không được overlap, trừ khi tài liệu nghiệp vụ cho phép.

## 11. Attendance `fact_attendance` — P2

Grain: một phiên attendance của agent.

| Trường | Kiểu đề xuất | Nullable | Quy tắc |
|---|---|---:|---|
| `attendance_id` | varchar(64) | Không | Primary key |
| `agent_id` | varchar(20) | Không | Foreign key `dim_agent` |
| `attendance_date` | date | Không | Ngày attendance |
| `actual_login` | timestamptz | Có | Null nếu vắng cả ngày |
| `actual_logout` | timestamptz | Có | Phải sau login |
| `attendance_status` | varchar(30) | Không | Danh mục trạng thái |
| `absence_code` | varchar(30) | Có | Bắt buộc khi absent |
| `late_minutes` | integer | Không | Không âm |
| `early_leave_minutes` | integer | Không | Không âm |
| `actual_paid_seconds` | integer | Không | Không âm |
| `actual_productive_seconds` | integer | Không | Không vượt actual logged seconds |

Danh mục tối thiểu:

```text
PRESENT
SICK
ANNUAL_LEAVE
UNPLANNED_ABSENCE
LATE
EARLY_LEAVE
```

Attendance synthetic phải được sinh độc lập với actual call outcome; dùng seed cố định và ghi rõ phân phối giả định.

## 12. Agent state theo interval `fact_agent_state_interval` — P2

Grain:

```text
agent_id × interval_start
```

| Trường | Kiểu đề xuất | Nullable | Quy tắc |
|---|---|---:|---|
| `agent_id` | varchar(20) | Không | Foreign key `dim_agent` |
| `interval_start` | timestamptz | Không | Cùng time spine 30 phút |
| `queue_id` | varchar(50) | Có | Queue được phục vụ |
| `ready_seconds` | integer | Không | Không âm |
| `talk_seconds` | integer | Không | Không âm |
| `hold_seconds` | integer | Không | Không âm |
| `acw_seconds` | integer | Không | Không âm |
| `not_ready_seconds` | integer | Không | Không âm |
| `break_seconds` | integer | Không | Không âm |
| `meeting_seconds` | integer | Không | Không âm |
| `training_seconds` | integer | Không | Không âm |
| `contacts_handled` | integer | Không | Không âm |
| `logged_in_seconds` | integer | Không | Tối đa 1.800 trong một interval thông thường |

Kiểm tra bắt buộc:

```text
ready_seconds
+ talk_seconds
+ hold_seconds
+ acw_seconds
+ not_ready_seconds
<= logged_in_seconds
<= 1800
```

Chưa có bảng này thì `occupancy`, `utilization` và `adherence` chỉ là ước tính, không được trình bày như KPI quan sát thật. Cần định nghĩa state có loại trừ lẫn nhau hay không; tránh cộng trùng `talk_seconds`, `hold_seconds`, `acw_seconds` với các nhóm thời gian khác. Ràng buộc `logged_in_seconds <= 1800` chỉ áp dụng cho interval wall-clock 30 phút thông thường; với interval DST hoặc interval có độ dài thực tế khác 30 phút, phải dùng độ dài interval đã xác định.

Không được gọi `logged_in_seconds / scheduled_seconds` là schedule adherence. Đây chỉ là tỷ lệ thời gian login so với thời gian được lên lịch, không cho biết agent có ở đúng activity đã schedule hay không.

## 13. Trường call-level còn thiếu

### 13.1 Có thể thêm ngay vào `fact_call`

| Trường | Kiểu đề xuất | Nguồn | Quy tắc |
|---|---|---|---|
| `queue_id` | varchar(50) | project_assumption | `INBOUND_SUPPORT` |
| `channel` | varchar(30) | project_assumption | `inbound_voice` |
| `direction` | varchar(20) | project_assumption | `inbound` |
| `is_answered` | boolean | derived | `call_status = answered` |
| `is_abandoned` | boolean | derived | `call_status = abandoned` |
| `is_sla_answered` | boolean | derived | Answered và wait trong ngưỡng SLA |
| `is_aht_eligible` | boolean | derived | Theo `valid_for_aht` hiện có |
| `handle_time_definition` | varchar(40) | project_assumption | `service_time_proxy` |

### 13.2 Không thể suy ra an toàn từ nguồn hiện tại

| Trường | Trạng thái | Cách xử lý MVP |
|---|---|---|
| `talk_seconds` | Không có | Dùng `service_seconds` làm proxy, không đổi tên thành talk time |
| `hold_seconds` | Không có | Để null; chỉ tạo synthetic ở phần mở rộng |
| `acw_seconds` | Không có | Để null; chỉ tạo synthetic ở phần mở rộng |
| `transfer_flag` | Không có | Không suy đoán |
| `disposition_code` | Không có | Optional synthetic |
| `case_id` | Không có | Không tạo nếu chưa làm FCR synthetic |
| `repeat_contact_flag` | Không xác định | Không suy từ customer ID đã loại bỏ |
| `csat_score` | Không có | P3 synthetic hoặc nguồn khảo sát khác |
| `quality_score` | Không có | P3 synthetic hoặc nguồn QA khác |

Trong MVP phải dùng tên `aht_proxy_seconds`, vì `service_seconds` chưa chứng minh gồm talk + hold + ACW.

## 14. Forecast và staffing fact — tạo ở bước mô hình

### 14.1 `fact_forecast_interval` — P1

| Trường | Kiểu đề xuất | Nullable |
|---|---|---:|
| `forecast_run_id` | varchar(64) | Không |
| `forecast_generated_at` | timestamptz | Không |
| `target_interval_start` | timestamptz | Không |
| `queue_id` | varchar(50) | Không |
| `model_name` | varchar(100) | Không |
| `model_version` | varchar(30) | Không |
| `training_end_date` | date | Không |
| `target_metric` | varchar(50) | Không |
| `forecast_agent_demand_calls` | numeric(12,4) | Không |
| `actual_agent_demand_calls` | integer | Có |
| `absolute_error` | numeric(12,4) | Có |
| `percentage_error` | numeric(12,6) | Có |
| `backtest_fold` | smallint | Có |
| `forecast_horizon_intervals` | integer | Không | Số interval dự báo trước thời điểm mục tiêu |
| `forecast_type` | varchar(20) | Không | `baseline`, `candidate`, `production` |
| `evaluation_scope` | varchar(20) | Không | `overall`, `operating`, `closed` trong model evaluation |
| `forecast_quantile` | numeric(5,4) | Có | Null với point forecast; ví dụ 0.9000 cho quantile 90% |
| `evaluation_status` | varchar(20) | Không | `pending`, `evaluated`, `excluded` |
| `is_selected_model` | boolean | Không |

### 14.2 `fact_staffing_requirement` — P1

| Trường | Kiểu đề xuất | Nullable |
|---|---|---:|
| `target_interval_start` | timestamptz | Không |
| `queue_id` | varchar(50) | Không |
| `forecast_run_id` | varchar(64) | Không |
| `forecast_agent_demand_calls` | numeric(12,4) | Không |
| `forecast_aht_seconds` | numeric(12,4) | Không |
| `workload_hours` | numeric(12,4) | Không |
| `occupancy_target` | numeric(6,4) | Không |
| `shrinkage_rate` | numeric(6,4) | Không |
| `required_productive_agents` | integer | Không |
| `required_scheduled_agents` | integer | Không |
| `staffing_method` | varchar(30) | Không |
| `assumption_version` | varchar(30) | Không |

**Công thức workload-based baseline:**

```text
workload_hours = forecast_volume × forecast_aht_seconds / 3600
required_productive_agents = CEILING(
    workload_hours / (interval_hours × occupancy_target)
)
required_scheduled_agents = CEILING(
    required_productive_agents / (1 - shrinkage_rate)
)
```

Đây là phép tính workload đơn giản để làm baseline, không phải Erlang C. `forecast_aht_seconds` trong dự án hiện tại là AHT proxy, không phải full AHT. Nếu muốn đánh giá Service Level và waiting probability có tính đến hàng đợi, có thể bổ sung Erlang C ở phiên bản nâng cao.

Ở cấp `forecast_run_id`, nên lưu thêm metric đánh giá như `MAE` và `WAPE` trong bảng/model evaluation riêng hoặc bảng tổng hợp; không cần lặp lại các metric này trên từng interval record.

## 15. Thứ tự triển khai

### Giai đoạn A — P0: nền thời gian và forecast-ready mart

1. Chốt timezone, cách xử lý DST và đối chiếu `Asia/Jerusalem` giữa ETL, SQL và Power BI.
2. Tạo `dim_date` cho toàn bộ năm 1999.
3. Tạo `dim_time_interval` gồm 48 wall-clock slots/ngày; xử lý riêng interval DST.
4. Tạo `dim_queue` và `dim_service_type`.
5. Kiểm tra coverage của 4.686 interval chưa có call, ở cấp ngày/interval khi có thể.
6. Tạo `fact_queue_interval_complete` và chỉ zero-fill khi `interval_coverage_verified = true`.
7. Tạo `fact_service_type_interval` để phân tích volume theo service type.
8. Thêm calendar/holiday Israel 1999 và cờ DST, có nguồn tham chiếu rõ ràng.

Điều kiện hoàn thành:

```text
17.520 wall-clock date × interval combinations trước khi xét quy tắc DST
không duplicate date_key + interval_key + queue_id theo grain đã chọn
sum(offered_calls) = 440.844
sum(answered_calls + abandoned_calls) = 440.844
zero-fill không làm thay đổi tổng call
mọi interval có coverage_status
```

### Giai đoạn B — P1: forecast và staffing requirement

1. Chạy EDA trên mart đã hoàn chỉnh.
2. Tạo baseline seasonal-naive và rolling-origin backtest/time-based split; không random split call records.
3. So sánh baseline với Holt–Winters và XGBoost bằng MAE/WAPE và kiểm tra leakage. Đã hoàn thành với 6 rolling folds; XGBoost dùng weekly lags không đọc actual trong test horizon.
4. Tạo `fact_forecast_interval`.
5. Forecast volume và AHT proxy.
6. Tạo `fact_staffing_requirement` bằng workload-based baseline; ghi rõ chưa phải Erlang C.

Target staffing forecast là `agent_demand_calls`, không phải toàn bộ `offered_calls` tại VRU. `offered_calls` vẫn được giữ làm KPI lưu lượng đầu vào; các cuộc gọi abandon trước queue không được biến thành workload của agent.

### Giai đoạn C — P1/P2: workforce foundation

1. Tạo `dim_agent` cho 52 agent ID đã quan sát.
2. Tạo `dim_team` và mapping synthetic có nhãn.
3. Chỉ sau forecast mới tạo schedule.
4. Tạo attendance độc lập với actual call outcome.
5. Tạo agent state nếu cần occupancy/adherence.

### Giai đoạn D — P3: phần mở rộng

1. Disposition và transfer synthetic.
2. CSAT và quality score synthetic.
3. Case/repeat-contact model cho FCR synthetic.
4. Luôn tách riêng KPI observed và KPI synthetic.

## 16. Những điều không được làm

- Không khôi phục hoặc xuất `customer_id` và raw agent label.
- Không tự gán agent cho 5.216 answered calls thiếu agent.
- Không thay duration âm bằng 0.
- Không gọi `service_seconds` là full AHT nếu chưa có hold và ACW.
- Không tuyên bố service type là queue thật nếu chưa có tài liệu xác nhận.
- Không sinh schedule trực tiếp từ actual volume của cùng interval.
- Không trộn synthetic values với observed values mà thiếu `data_origin`.
- Không zero-fill `data_gap` khi chưa xác nhận coverage.

## 17. Deliverable của bước bổ sung trường

Sau khi triển khai đầy đủ, tối thiểu phải có:

```text
dim_date
dim_time_interval
dim_queue
dim_service_type
fact_queue_interval_complete
fact_service_type_interval
fact_event_calendar
dim_agent
dim_team
fact_forecast_interval
fact_staffing_requirement
fact_schedule_segment
fact_attendance
fact_agent_state_interval
```

MVP có thể dừng sau `fact_staffing_requirement`. Schedule, attendance và agent state chỉ cần thiết khi dự án bắt đầu phân tích staffing gap, adherence và occupancy. `fact_service_type_interval` là bảng bổ sung cho phân tích theo service type trong MVP.


## 18. Bổ sung định nghĩa KPI workforce — P2

Các KPI phải có định nghĩa thống nhất trong `docs/metric_definitions.md`, SQL và Power BI trước khi tạo dashboard.

| KPI | Dữ liệu cần có | Định nghĩa/ghi chú |
|---|---|---|
| `attendance_rate` | Schedule + attendance | Tỷ lệ ca/giờ được yêu cầu mà agent có mặt, theo quy tắc attendance đã chốt |
| `punctuality` | Scheduled start + actual login | Đo mức đúng giờ; `late_minutes` phải được tính từ hai mốc này |
| `schedule_adherence` | Schedule + actual activity/state | Tỷ lệ thời gian agent thực hiện đúng activity đã được schedule; không đồng nhất với login time |
| `occupancy` | Talk + hold + ACW và thời gian ready/available theo định nghĩa đã chốt | Tỷ lệ thời gian xử lý tương tác trên thời gian agent sẵn sàng/được tính vào mẫu số; phải chốt chính xác mẫu số |
| `utilization` | Productive time + logged-in time | Tỷ lệ thời gian productive trên logged-in time theo định nghĩa dự án |
| `staffing_gap` | Required agents + scheduled hoặc actual available agents | Phải ghi rõ đang so sánh requirement với scheduled staffing hay actual staffing |

Không dùng `logged_in_seconds / scheduled_seconds` làm `schedule_adherence`. Có thể đặt tên riêng là `login_coverage_rate` nếu cần theo dõi tỷ lệ login so với thời gian được lên lịch.

## 19. Quy tắc agent attributes — P1

Để tránh tạo ra lịch sử nhân sự giả, chia thuộc tính agent thành hai nhóm:

- **Có thể quan sát từ call log:** `agent_id`, `first_seen_date`, `last_seen_date` (nếu tính từ các call có agent label).
- **Không có trong nguồn, chỉ được mô phỏng khi cần:** `team_id`, `site_id`, `employment_type`, `fte_ratio`, `hire_date`, `termination_date`, `employment_status`, `primary_skill`, `supervisor_id`.

Các thuộc tính thuộc nhóm thứ hai phải để null nếu chưa mô phỏng. Khi mô phỏng, gắn `data_origin = synthetic`, ghi `generation_method`, `generation_version`, `random_seed` (nếu có ngẫu nhiên). Không suy ra ngày tuyển dụng từ ngày xuất hiện đầu tiên trong call log.

## 20. Quy tắc forecast và staffing — P1

- Dùng time-based split hoặc rolling-origin backtesting; không random split call records vì có nguy cơ rò rỉ thông tin thời gian.
- Luôn có ít nhất một baseline, ví dụ seasonal-naive, trước khi đánh giá candidate model.
- Đánh giá forecast ở cấp interval và tổng hợp theo `forecast_run_id`; ưu tiên MAE và WAPE. Cẩn trọng với MAPE khi actual volume bằng 0.
- `forecast_horizon_intervals` phải xác định rõ khoảng cách dự báo.
- Staffing formula ở mục 14.2 là workload-based approximation. Nếu cần mô hình hóa xác suất chờ và Service Level theo queueing theory, triển khai Erlang C như phần mở rộng riêng.
- Không dùng actual volume của chính interval mục tiêu để tạo schedule hoặc staffing plan được trình bày là forecast-driven.

## 21. Quy tắc time coverage và DST — P0

- `source_file_available` chỉ chứng minh file tồn tại/qua kiểm tra toàn vẹn, không tự chứng minh mọi ngày hoặc interval trong file đều đầy đủ.
- `source_date_covered` và `interval_coverage_verified` cần được xây từ manifest, kiểm tra ngày, thời gian đầu/cuối, số record và các kiểm tra chất lượng nguồn có thể thực hiện.
- Nếu không đủ bằng chứng, giữ `coverage_status = data_gap`, metric volume để null và không zero-fill.
- 17.520 là số wall-clock slots của năm thường 365 ngày × 48. Khi xử lý timezone có DST, phân biệt wall-clock slot với timestamp thực tế; không ép dữ liệu DST vào giả định 48 timestamp UTC mỗi ngày.
- Chốt một timezone duy nhất giữa Python ETL, SQL warehouse và Power BI. `Asia/Jerusalem` hiện là giả định của dự án, cần xác minh với logic ETL và mô tả nguồn trước khi coi là quy ước cuối cùng.

## 22. Phạm vi triển khai khuyến nghị

Để tránh dành quá nhiều thời gian tạo dữ liệu mô phỏng trước khi chứng minh năng lực phân tích, chia deliverable thành ba phạm vi:

### 22.1 MVP — hoàn thành trước

- `dim_date`
- `dim_time_interval`
- `dim_queue`
- `dim_service_type`
- `fact_queue_interval_complete`
- `fact_service_type_interval`
- `fact_forecast_interval`
- `fact_staffing_requirement`

Trạng thái: các bảng trong danh sách này đã được tạo dưới `data/processed/technion/`, load vào PostgreSQL schema `analytics`; model evaluation, staffing và warehouse validators đã pass. EDA trực quan và Power BI là các bước tiếp theo.

Mục tiêu: chứng minh ETL, data quality, SQL, EDA, time-series forecasting, workload/staffing calculation và Power BI dashboard.

### 22.2 WFM extension — sau MVP

- `dim_agent`
- `dim_team`
- `fact_schedule_segment`
- `fact_attendance`
- `fact_agent_state_interval`

Mục tiêu: mô phỏng staffing gap, attendance, schedule adherence, occupancy và utilization. Tất cả dữ liệu mô phỏng phải được nhận diện rõ.

### 22.3 Advanced extension — tùy chọn

- `fact_event_calendar` với event synthetic được gắn nhãn
- Transfer/disposition
- CSAT/quality score
- Case/repeat-contact/FCR

Chỉ triển khai nếu phần MVP đã hoàn thiện và có thời gian mở rộng portfolio.

## 23. Checklist trước khi code

- [ ] Chốt timezone và quy tắc DST giữa Python, SQL và Power BI.
- [ ] Xác định coverage ở cấp ngày/interval; không dựa riêng vào việc file tháng tồn tại.
- [ ] Chốt grain của queue interval và service type interval.
- [ ] Bổ sung `fact_service_type_interval`.
- [ ] Chốt định nghĩa offered, answered, abandoned, SLA, AHT proxy và các quy tắc loại trừ.
- [x] Chốt baseline forecast, rolling-origin backtest và metric MAE/WAPE; đã so sánh bốn models gồm XGBoost.
- [ ] Ghi rõ staffing calculation là workload-based approximation hay Erlang C.
- [ ] Giữ agent attributes không có nguồn ở trạng thái null cho đến khi có mô phỏng được phê duyệt.
- [ ] Tách KPI observed khỏi KPI synthetic trên data model và dashboard.
