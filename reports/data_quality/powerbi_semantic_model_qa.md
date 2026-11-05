# Power BI semantic model QA

Kiểm tra ngày: 2026-11-05

Power BI Project: `powerbi/call_center_wfm.pbip`

## Kết quả

| Hạng mục | Kết quả |
|---|---:|
| Warehouse tables/views đã import | 10/10 |
| DAX measures trong `_Measures` | 40 |
| Measures thực thi bằng DAX query | 40/40 |
| Measures trả BLANK ở total context | 0 |
| Business relationships | 13 |
| Technical columns đã ẩn | 33 |
| Discourage implicit measures | Bật |
| Report pages | 3 |
| PBIR visuals | 29 |
| PBIR query references hợp lệ | 37/37 |
| PBIR JSON parse errors | 0 |

Relationships đã khớp star schema trong `docs/power_bi_dashboard_plan.md`: bốn quan hệ Date, bốn quan hệ Time Interval, bốn quan hệ Queue và một quan hệ Service Type. `fact_model_evaluation` và `vw_powerbi_refresh_status` vẫn disconnected theo thiết kế MVP.

## KPI smoke test

| Measure | Giá trị |
|---|---:|
| Offered Calls | 440,844 |
| Answered Calls | 353,143 |
| Answer Rate | 80.1061% |
| Service Level | 46.4631% |
| Selected Model Name | `same_weekday_interval_mean_4w` |
| Selected Forecast WAPE | 17.9539% |
| Peak Scheduled Agents | 22 |
| Service Offered Calls | 440,844 |
| Last Warehouse Load | 2026-11-05 16:01:47 |

## Report render QA

| Trang | Visuals | Trạng thái |
|---|---:|---|
| 01 Executive Overview | 9 | Render thành công |
| 02 Forecast & Staffing | 10 | Render thành công |
| 03 Service Mix & Data Quality | 10 | Render thành công |

Power BI Desktop đã áp dụng external PBIR changes và lưu project lúc 2026-11-05 19:27. Không phát hiện visual lỗi hoặc field reference thiếu khi render.

## Việc còn lại trước khi publish

1. Áp dụng background-color conditional formatting cho ba matrix heatmaps.
2. Chuyển các categorical slicers sang dropdown để tiết kiệm diện tích.
3. Bổ sung page navigation, Reset Filters và tooltip giải thích AHT proxy.
4. Kiểm tra cross-filter interactions, accessibility và publish readiness.
