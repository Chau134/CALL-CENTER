# Data Provenance — Technion Anonymous Bank

## Nguồn

- Chủ sở hữu/xuất bản: Service Enterprise Engineering Lab, Technion — Israel Institute of Technology.
- Dataset: “Anonymous Bank” Call-Center Data.
- Thời kỳ dữ liệu: January–December 1999.
- Ngày tải: 2026-11-04.
- Mirror chính thức: <https://see-center.iem.technion.ac.il/databases/AnonymousBank/Data/>
- Archive URL: <https://see-center.iem.technion.ac.il/databases/AnonymousBank/Data/AnonymousBank.rar>
- Documentation URL: <https://see-center.iem.technion.ac.il/databases/AnonymousBank/Data/AnonymousBank.pdf>

Trang tải cũ theo từng tháng tại `serveng.technion.ac.il` bị timeout trong lần thu thập. Dataset được tải từ mirror Technion chính thức nêu trên, không dùng mirror cộng đồng.

## File đã tải

| File | Bytes | SHA-256 |
|---|---:|---|
| `AnonymousBank.rar` | 10,625,021 | `110527823a296e3163566f5d10d687e13859c60d963fd403d4623d89c7cadc4b` |
| `documentation.pdf` | 35,223 | `77816db694fdee313a7d612e22199d87632ddca5a82f17c3258bd6799ff6e045` |

## Nội dung archive đã xác nhận

```text
January1999.txt
February1999.txt
March1999.txt
April1999.txt
May1999.txt
June1999.txt
July1999.txt
August1999.txt
September1999.txt
October1999.txt
November1999.txt
December1999.txt
```

Archive listing hoàn tất với exit code 0. Sau bước thu thập, 12 file đã được giải nén, chụp raw baseline, ETL và kiểm tra lại bằng SHA-256; raw source không bị thay đổi.

## Điều kiện sử dụng

Tài liệu nguồn ghi dữ liệu được dùng miễn phí, yêu cầu acknowledge nguồn và đề nghị thông báo cho Avi Mandelbaum khi sử dụng. Trước khi công bố portfolio, README phải trích dẫn Technion và không phân phối lại raw archive nếu chưa xác nhận việc tái phân phối; repository chỉ nên cung cấp downloader/provenance.

## Quy tắc bảo quản

- `data/raw/technion` được `.gitignore` loại khỏi Git.
- Raw archive không được sửa hoặc overwrite trong ETL.
- Mỗi lần tải lại phải đối chiếu SHA-256.
- Dữ liệu dẫn xuất phải lưu ở `data/interim` hoặc `data/processed`.

## Nguồn tham chiếu bổ sung

| Dữ liệu | Nguồn | Cách diễn giải |
|---|---|---|
| Mô tả coverage và operating hours | Technion `AnonymousBank.pdf` | Tài liệu ghi archive chứa toàn bộ calls trong năm 1999 và VRU hoạt động 24/7 |
| Israel calendar observances 1999 | <https://www.hebcal.com/holidays/1999?i=on> | `external_reference`; chỉ là calendar observance, không chứng minh call center đóng cửa |
| Timezone | IANA `Asia/Jerusalem` | `project_assumption` dựa trên địa điểm Israel; giờ DST ambiguous/nonexistent được gắn cờ |

Holiday reference được lưu tại `data/reference/israel_holidays_1999.csv`. Không có record holiday nào được gắn `source_observed`.

## Các tầng dữ liệu dẫn xuất

```text
data/raw/technion/AnonymousBank
  -> data/interim/technion/calls_*.csv.gz
  -> data/processed/technion/dim_*.csv.gz
  -> data/processed/technion/fact_queue_interval_complete.csv.gz
  -> forecast, model evaluation và staffing requirement facts
```

- `offered_calls` là toàn bộ clean calls đi vào VRU.
- `agent_demand_calls` là answered calls cộng queue abandons và là target cho staffing forecast.
- Không có schedule, attendance hoặc agent state synthetic trong các marts hiện tại.
