# Metric Definitions — phiên bản 0.1

Tài liệu này là nguồn định nghĩa chính thức cho Python, SQL và Power BI. Khi thay đổi một metric, phải cập nhật tài liệu, cấu hình, test và DAX liên quan trong cùng một thay đổi.

## 1. Phạm vi đã khóa

| Hạng mục | Quyết định |
|---|---|
| Kênh | Inbound voice |
| Queue MVP | `INBOUND_SUPPORT` |
| Múi giờ | `Asia/Ho_Chi_Minh` |
| Interval | 30 phút, căn từ phút 00 và 30 |
| Forecast horizon | 7 ngày |
| Service Level | 80% trong 20 giây (80/20) |
| Short abandon | thời gian chờ không quá 5 giây |
| Occupancy target | tối đa 85% |
| Shrinkage kế hoạch | 30% |
| Staffing MVP | capacity-based; Erlang C là stretch goal |
| Dữ liệu mặc định | synthetic, seed 42 |

## 2. Quy tắc thời gian và grain

- Tất cả timestamp nguồn được chuyển sang `Asia/Ho_Chi_Minh` trước khi tạo date/interval key.
- Interval là nửa kín `[start, end)`. Ví dụ `09:00:00` đến trước `09:30:00` thuộc interval 09:00.
- Fact call có grain một cuộc gọi inbound. Transfer bị loại khỏi MVP; nếu xuất hiện phải được gắn cờ và báo cáo riêng.
- Queue mart có grain `date × interval × queue`.
- Agent daily KPI có grain `date × agent × queue`.
- Interval ngoài giờ hoạt động không thuộc mẫu forecast chính. Interval trong giờ hoạt động nhưng không có cuộc gọi phải có `offered_calls = 0`.

## 3. Queue metrics

### Offered Calls

```text
offered_calls = answered_calls + abandoned_calls
```

Một `call_id` chỉ được tính một lần. Record test, outbound, duplicate hoặc timestamp không hợp lệ được loại theo reason code và phải xuất hiện trong DQ report.

### Answer Rate

```text
answer_rate = answered_calls / offered_calls
```

Trả về blank khi `offered_calls = 0`.

### Abandon Rate

```text
abandon_rate = abandoned_calls / offered_calls
```

KPI này bao gồm short abandons. Dashboard phải ghi rõ nếu hiển thị một phiên bản loại short abandons.

### Average Handle Time — AHT

```text
handle_seconds = talk_seconds + hold_seconds + acw_seconds
aht_seconds = sum(handle_seconds) / handled_calls
```

Chỉ tính cuộc gọi answered/handled hợp lệ. Không lấy trung bình của các AHT trung bình con; luôn dùng tỷ lệ giữa tổng thời gian và tổng handled calls.

### Average Speed of Answer — ASA

```text
asa_seconds = sum(answer_wait_seconds for answered calls) / answered_calls
```

Không đưa abandoned calls vào ASA.

### Service Level

```text
eligible_offered = answered_calls + abandons_waiting_more_than_5_seconds
answered_in_20s = answered calls with answer_wait_seconds <= 20
service_level = answered_in_20s / eligible_offered
```

Short abandon là abandoned call có `wait_seconds <= 5`. Quy tắc biên `<=` được dùng nhất quán.

## 4. Forecast metrics

```text
error = actual - forecast
absolute_error = abs(error)
wape = sum(absolute_error) / sum(actual)
bias = sum(forecast - actual) / sum(actual)
mae = mean(absolute_error)
rmse = sqrt(mean(error^2))
```

- Error dương: under-forecast.
- Bias dương: over-forecast; bias âm: under-forecast.
- WAPE là metric chọn model chính. Fold có tổng actual bằng 0 không được tính WAPE và phải được gắn cờ.
- Không dùng random split. Mọi metric báo cáo phải đến từ rolling-origin backtest hoặc holdout tương lai.

## 5. Staffing metrics

Với `interval_hours = 0.5`:

```text
workload_hours = forecast_offered_calls * forecast_aht_seconds / 3600
productive_agents_required = ceil(
    workload_hours / (interval_hours * occupancy_target)
)
scheduled_agents_required = ceil(
    productive_agents_required / (1 - shrinkage_rate)
)
staffing_gap = available_agents - productive_agents_required
schedule_gap = scheduled_headcount - scheduled_agents_required
```

- `productive_agents_required`: agent cần thực sự available để nhận call.
- `scheduled_agents_required`: người cần xếp lịch trước shrinkage.
- `scheduled_headcount`: người có tên trong lịch.
- `available_agents`: agent thực tế login và ở trạng thái có thể nhận call.
- Gap âm là thiếu người; gap dương là dư người.
- Mọi headcount requirement làm tròn lên.
- Planned staffing dùng forecast volume và forecast AHT. Actualized analysis dùng actual volume/AHT và không được trình bày như kế hoạch đã biết trước.

## 6. Attendance và agent metrics

```text
scheduled_paid_minutes = scheduled_end - scheduled_start - unpaid_break_minutes
actual_login_minutes = actual_logout - actual_login
late_minutes = max(0, actual_login - scheduled_start - 5-minute grace)
early_logout_minutes = max(0, scheduled_end - actual_logout - 5-minute grace)
absence_rate = absent_scheduled_minutes / scheduled_paid_minutes
attendance_rate = attended_scheduled_days / scheduled_work_days
occupancy = handling_time / logged_in_available_time
utilization = productive_time / paid_time
```

Schedule adherence chỉ được công bố khi có state-event data:

```text
schedule_adherence = minutes_in_adherent_state / scheduled_production_minutes
```

Nếu chỉ có login/logout, metric phải mang tên `login_coverage_proxy`; không được đổi tên thành adherence.

## 7. FCR và CSAT

```text
fcr = first-contact-resolved eligible calls / eligible resolved calls
csat = responses with score >= 4 / valid survey responses
```

- CSAT dùng thang 1-5; positive là 4 hoặc 5.
- Luôn hiển thị số survey responses cạnh CSAT.
- Agent ranking yêu cầu tối thiểu 30 handled calls và 10 CSAT responses trong kỳ; dưới ngưỡng chỉ hiển thị “insufficient sample”.

## 8. Quy tắc thay đổi

Các giá trị 80/20, 5 giây, 85%, 30% và grace 5 phút là giả định của project, không phải chuẩn áp dụng cho mọi contact center. Thay đổi chúng tại `config/project.yml`, sau đó chạy lại toàn pipeline và test reconciliation.
