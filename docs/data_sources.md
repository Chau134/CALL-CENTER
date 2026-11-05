# Bước 2 — Nguồn dữ liệu đã chọn

Ngày đánh giá và tải: 2026-11-04.

## Quyết định

Dùng **“Anonymous Bank” Call-Center Data** của Technion làm dữ liệu công khai cốt lõi. Đây là dữ liệu call-level của một call center ngân hàng trong 12 tháng năm 1999, có thời điểm vào hệ thống, thời gian queue, outcome, thời gian phục vụ, loại dịch vụ và agent.

- Trang nguồn: <https://serveng.technion.ac.il/homeworks/call-center-data/>
- Mirror chính thức đã dùng để tải: <https://see-center.iem.technion.ac.il/databases/AnonymousBank/Data/>
- Tài liệu: <https://see-center.iem.technion.ac.il/databases/AnonymousBank/Data/AnonymousBank.pdf>
- Archive: <https://see-center.iem.technion.ac.il/databases/AnonymousBank/Data/AnonymousBank.rar>
- Điều kiện sử dụng ghi trong tài liệu: free for use; cần acknowledge nguồn và thông báo cho Avi Mandelbaum khi sử dụng.

Không ghép record từ IBM, NYC 311, UCSD/Intuit hoặc các dataset khác vào cùng contact center này. Các nguồn đó chỉ có thể dùng làm benchmark độc lập.

## Trạng thái thu thập

| Hạng mục | Trạng thái |
|---|---|
| Archive gốc | Đã tải, giữ nguyên, chưa giải nén |
| Tài liệu nguồn | Đã tải |
| Số file tháng trong archive | 12/12, January–December 1999 |
| Archive listing | Đọc thành công bằng `tar -tf` |
| Chữ ký file | PDF và RAR hợp lệ |
| SHA-256 | Đã tạo và lưu |
| ETL/đọc record | Chưa thực hiện |

Chi tiết provenance và checksum nằm tại `docs/data_provenance.md` và `data/raw/technion/SHA256SUMS.txt`.

## Dữ liệu quan sát được từ nguồn

Archive có một file text cho mỗi tháng. Data dictionary nguồn mô tả 17 trường:

```text
vru_line, call_id, customer_id, priority, type, date,
vru_entry, vru_exit, vru_time,
q_start, q_exit, q_time,
outcome,
ser_start, ser_exit, ser_time,
server
```

Các outcome chính là `AGENT`, `HANG` và `PHANTOM`.

## Trường dự kiến tạo trong ETL

Các trường sau phải được tạo từ dữ liệu nguồn và gắn `data_origin = source_derived`:

- `offered_at`, `queue_started_at`, `queue_exited_at`;
- `service_started_at`, `service_ended_at`;
- `call_status`, `wait_seconds`, `service_seconds`;
- `date_key`, `interval_start`, `service_type`;
- `answered_in_threshold`, `is_short_abandon`;
- agent ID giả danh thay cho tên nguồn.

## Trường còn thiếu cần bổ sung synthetic

- team và team leader;
- schedule, break và planned activity;
- login/logout, absence và agent states;
- hold time và ACW nếu dashboard cần AHT enriched;
- FCR và CSAT nếu giữ các module này.

Mọi trường bổ sung phải có lineage rõ ràng như `data_origin`, `generation_rule` và `generation_version`. Không điền dữ liệu synthetic vào cột quan sát mà không gắn nhãn.

## Quy tắc ETL dự kiến

- Tầng `raw` giữ archive bất biến.
- `customer_id` phải bị loại hoặc băm có salt trước tầng analytics.
- `server` được thay bằng agent ID giả danh.
- `PHANTOM` không tham gia KPI và phải có exclusion reason.
- Duration nguồn được giữ để đối chiếu với duration tính lại từ timestamp.
- Record âm, sai thứ tự timestamp hoặc trùng composite key được đưa vào quarantine.
- Không đổi ngày năm 1999 thành năm hiện đại.
- Khi bắt đầu ETL, timezone dự án phải đổi từ `Asia/Ho_Chi_Minh` sang timezone nguồn phù hợp (`Asia/Jerusalem`) và ghi migration decision.

## Các nguồn đã xem xét nhưng không chọn làm lõi

| Nguồn | Lý do không chọn làm lõi |
|---|---|
| [NYC 311](https://data.cityofnewyork.us/d/erm2-nwe9) | phone service request chỉ là demand proxy; thiếu queue/AHT/agent |
| [IBM Call Center Dataset](https://dataplatform.cloud.ibm.com/exchange/public/entry/view/013c690997e27f3a8d91332653378c93?context=cpdaas) | fictitious; khoảng thời gian và quyền tái phân phối chưa rõ |
| [UCSD/Intuit](https://github.com/UCSD-Intuit-Data-Science-Initiative/Fall-2025-Spring-2026-Data-and-Resources/blob/main/data/demand-forecasting/call-center-data-v2-daily.md) | chỉ có grain ngày, không hỗ trợ staffing interval/agent |
| [Kalyvox](https://huggingface.co/datasets/Kalyvoxai/inbound-call-statistics-2026) | calibrated/reconstructed, thiếu queue và agent |
| [DatabaseSample](https://databasesample.com/datasets/call-centre-dataset-calls-agents-queues-and-abandonment) | synthetic và chỉ có 800 calls trong bốn tuần |
