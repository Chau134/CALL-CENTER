# Source Data Dictionary — Technion Anonymous Bank

Các file nguồn là text phân tách bằng tab, mỗi file tương ứng một tháng năm 1999. Grain là một record cuộc gọi. Raw data không được chỉnh sửa trực tiếp.

## Xem cấu trúc dữ liệu an toàn

Chạy profile không hiển thị customer ID hoặc tên agent:

```powershell
.\.venv\Scripts\Activate.ps1
python src/inspect_raw_data.py
```

Chụp baseline trước ETL để dùng cho reconciliation:

```powershell
python src/capture_raw_baseline.py
```

Kết quả nằm tại `reports/data_quality/raw_baseline.json` và `raw_baseline.md`.

Xem riêng header của một file:

```powershell
Get-Content data\raw\technion\AnonymousBank\January1999.txt -TotalCount 1
```

Xem năm dòng nhưng loại hai trường cần bảo vệ:

```python
import pandas as pd

path = "data/raw/technion/AnonymousBank/January1999.txt"
df = pd.read_csv(path, sep="\t", dtype="string", nrows=5)
print(df.drop(columns=["customer_id", "server"]))
```

## Giải thích 17 trường nguồn

| Trường nguồn | Ý nghĩa | Kiểu staging | Xử lý ETL |
|---|---|---|---|
| `vru+line` | mã VRU ghép với line nhận cuộc gọi | text | đổi tên `vru_line`; giữ để trace nguồn |
| `call_id` | ID do VRU cấp, không bảo đảm tuần tự/toàn cục | text | không dùng một mình làm primary key |
| `customer_id` | định danh khách hàng; `0` khi không xác định | text | raw-only; băm có salt hoặc loại khỏi analytics |
| `priority` | `0/1` thường hoặc không xác định, `2` ưu tiên | smallint | validate danh mục; giữ làm segmentation |
| `type` | mã loại dịch vụ | text | map sang `service_type`; không tự gọi là queue nếu chưa xác nhận |
| `date` | ngày dạng `YYMMDD` | date | parse rõ century `19` để tránh thành năm 2099 |
| `vru_entry` | thời điểm vào VRU/call center | time | ghép với date thành `offered_at` |
| `vru_exit` | thời điểm rời VRU | time | ghép date; dùng kiểm tra `vru_time` |
| `vru_time` | số giây ở VRU | integer | giữ source value và tính lại để reconciliation |
| `q_start` | thời điểm vào queue; `00:00:00` nếu không vào queue | time/nullable | đổi sentinel thành null có kiểm soát |
| `q_exit` | thời điểm rời queue để được phục vụ hoặc abandon | time/nullable | ghép date; diễn giải theo outcome |
| `q_time` | số giây chờ trong queue | integer | giữ nguồn và tính lại để đối chiếu |
| `outcome` | `AGENT`, `HANG`, `PHANTOM` | text | map status; PHANTOM vào excluded/quarantine |
| `ser_start` | thời điểm agent bắt đầu phục vụ | time/nullable | tạo `service_started_at`/`answered_at` |
| `ser_exit` | thời điểm agent kết thúc phục vụ | time/nullable | tạo `service_ended_at` |
| `ser_time` | thời lượng phục vụ bằng giây | integer | dùng làm service-time/AHT proxy, không gọi là full AHT nếu thiếu ACW/hold |
| `server` | tên/nhãn agent; `NO_SERVER` khi không có agent | text | pseudonymize thành `agent_id`; không đưa tên thô vào BI |

## Mã loại dịch vụ

| Mã | Diễn giải từ tài liệu nguồn |
|---|---|
| `PS` | regular activity |
| `PE` | regular activity in English |
| `IN` | internet consulting |
| `NE` | stock exchange activity |
| `NW` | prospective customer information |
| `TT` | callback-related call được đưa vào queue |

## Trường dẫn xuất chính

```text
source_call_key
offered_at
queue_started_at
queue_exited_at
answered_at
abandoned_at
service_ended_at
call_status
wait_seconds
service_seconds
interval_start
answered_in_threshold
is_short_abandon
agent_id
data_origin
exclusion_reason
```

`source_call_key` nên chứa ít nhất source month, `vru_line` và `call_id`. Chỉ chốt primary key sau khi profiling duplicate hoàn tất.

## Quy tắc bảo vệ và lineage

- Không in `customer_id` hoặc `server` trong notebook/report công khai.
- Không commit dữ liệu raw.
- Giữ riêng source duration và recomputed duration.
- Không thay giá trị lỗi âm bằng 0. Giữ source value để audit; canonical value chỉ dùng timestamp tính lại khi an toàn, nếu không thì để null và gắn quality flag. Record vẫn có thể dùng cho volume nếu các trường lõi khác hợp lệ.
- Các trường schedule, attendance, states, ACW, hold, FCR và CSAT bổ sung sau này phải mang `data_origin = synthetic`.
- Timestamp nguồn là local time của call center tại Israel; timezone `Asia/Jerusalem` là giả định cần ghi rõ khi ETL.
