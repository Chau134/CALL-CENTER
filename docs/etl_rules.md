# ETL Rules — Technion Calls

## Output streams

Mỗi raw record phải vào đúng một luồng:

```text
raw = clean + excluded + quarantine
```

- `clean`: record usable cho volume/queue; các vấn đề không critical nằm trong `quality_flags`.
- `excluded`: `PHANTOM`, được giữ bằng chứng nhưng không tham gia KPI.
- `quarantine`: lỗi cấu trúc hoặc categorical/core timestamp không thể diễn giải an toàn.

## Repair và xử lý chất lượng

- Dòng 16 fields có `priority` và `service_type` bị dính được tách bằng pattern xác định; gắn `split_merged_priority_service_type`.
- `PHANTOM` được loại với `exclusion_reason = phantom_record`.
- Service type ngoài `PS, PE, IN, NE, NW, TT` đi quarantine.
- `vru_time < 0`: giữ source value, `vru_seconds` chỉ dùng giá trị recomputed nếu timestamp hợp lệ; nếu không thì null và gắn flag.
- `00:00:00` chỉ là sentinel khi duration tương ứng bằng 0.
- `AGENT` không có agent label vẫn được giữ cho volume nhưng không dùng cho agent KPI/AHT.
- `HANG` có agent label vẫn là abandoned; agent label không được gán vào output.
- `ser_time = 0` không hợp lệ cho AHT denominator.

## Derived fields

- `source_call_key = source_file + vru_line + call_id`.
- Timestamp ghép từ source date/time với giả định `Asia/Jerusalem`.
- `call_status`: `AGENT → answered`, `HANG → abandoned`.
- `interval_start`: floor `offered_at` xuống interval 30 phút.
- `answered_in_threshold`: answered và `wait_seconds <= 20`.
- `is_short_abandon`: abandoned và `wait_seconds <= 5`.
- `agent_id`: ID giả danh; raw agent label không được ghi ra.
- `valid_for_aht`: answered, có agent ID, service duration > 0 và timestamp service hợp lệ.

## Interval mart 30 phút

`calls_interval_30m.csv.gz` có grain là một interval 30 phút trên toàn bộ dịch vụ. Chỉ các record thuộc luồng `clean` được tổng hợp:

- `offered_calls = answered_calls + abandoned_calls`;
- `service_level_denominator = offered_calls - short_abandon_calls`;
- `service_level_rate = answered_within_20s / service_level_denominator`;
- `aht_proxy_seconds` chỉ dùng các record có `valid_for_aht = true`;
- tổng `offered_calls` của tất cả interval phải bằng tổng số record clean.

File hiện chỉ chứa interval có ít nhất một cuộc gọi quan sát được. Việc tạo lưới interval đầy đủ và điền volume 0 được để sang bước kế tiếp; ETL này không tự tạo thêm dữ liệu quan sát.

## Foundation marts sau call-level ETL

`build_foundation_marts.py` tạo lưới đầy đủ 17.520 wall-clock interval và sáu service types. Zero-fill được phép vì tài liệu Technion ghi archive chứa toàn bộ calls trong 12 tháng và VRU hoạt động 24/7; pipeline đồng thời kiểm tra đủ 12 file, checksum, phạm vi năm và reconciliation.

```text
data/processed/technion/dim_date.csv.gz
data/processed/technion/dim_time_interval.csv.gz
data/processed/technion/dim_queue.csv.gz
data/processed/technion/dim_service_type.csv.gz
data/processed/technion/fact_queue_interval_complete.csv.gz
data/processed/technion/fact_service_type_interval.csv.gz
```

Các trạng thái coverage gồm `observed_with_calls`, `observed_excluded_only`, `zero_filled_operating`, `zero_filled_closed` và `data_gap`. Chỉ interval có coverage được xác minh mới được zero-fill.

Để tách inbound traffic khỏi workload nhân sự:

```text
agent_demand_calls = answered_calls + queue_abandoned_calls
vru_abandoned_calls = abandoned_calls - queue_abandoned_calls
```

Forecast/staffing dùng `agent_demand_calls`; dashboard inbound traffic vẫn có thể dùng `offered_calls`.

## Kết quả xử lý hiện tại

- 12 dòng 16 cột đã được sửa bằng quy tắc tách `priority + service_type` xác định.
- 3.599 record `PHANTOM` đã chuyển sang luồng excluded.
- 5 record có service type `AA` đã chuyển sang quarantine.
- 350 source record có VRU duration âm được ghi nhận; 332 record thuộc clean giữ source value để audit và để canonical value null khi không tính lại an toàn được, 18 record còn lại thuộc PHANTOM.
- Các bất nhất agent label và service duration 0 được giữ cho volume nhưng đánh dấu để không làm sai agent KPI/AHT.

## Privacy

- Không output `customer_id`.
- Không output raw `server` label.
- Clean/excluded/quarantine chỉ chứa technical source identifiers và dữ liệu vận hành.

## Chạy ETL

```powershell
.\.venv\Scripts\Activate.ps1
python src/transform_calls.py
```

Kết quả:

```text
data/interim/technion/calls_clean.csv.gz
data/interim/technion/calls_excluded.csv.gz
data/interim/technion/calls_quarantine.csv.gz
data/interim/technion/calls_interval_30m.csv.gz
reports/data_quality/etl_reconciliation.json
reports/data_quality/etl_reconciliation.md
```

Kiểm tra lại toàn bộ đầu ra:

```powershell
python src/validate_transformed_data.py
python src/build_foundation_marts.py
python src/validate_foundation_marts.py
```
