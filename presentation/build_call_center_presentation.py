from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image
from pptx import Presentation
from pptx.chart.data import ChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_DATA_LABEL_POSITION
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "presentation"
OUT_PATH = OUT_DIR / "CALL_CENTER_WFM_Project_Report.pptx"

IMG_OVERVIEW = ROOT / "reports" / "powerbi_interactions" / "01 Executive Overview recheck.png"
IMG_FORECAST = ROOT / "reports" / "powerbi_interactions" / "02 Forecast & Staffing recheck.png"
IMG_SERVICE = ROOT / "reports" / "powerbi_interactions" / "03 Service Mix & Data Quality.png"

SLIDE_W = 13.333
SLIDE_H = 7.5

NAVY = "1F4E78"
NAVY_DARK = "173A5E"
BLUE = "2F75B5"
ORANGE = "F28E2B"
TEAL = "2A9D8F"
RED = "D9534F"
GREEN = "3A8D5D"
DARK = "1F2937"
MID = "4B5563"
MUTED = "6B7280"
LIGHT = "F4F7FA"
LIGHT_BLUE = "EAF2F8"
LIGHT_ORANGE = "FEF1E5"
LIGHT_TEAL = "E7F4F1"
WHITE = "FFFFFF"
LINE = "D9E2EC"


def rgb(hex_color: str) -> RGBColor:
    return RGBColor.from_string(hex_color.replace("#", ""))


def set_background(slide, color: str = WHITE) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = rgb(color)


def add_rect(
    slide,
    x: float,
    y: float,
    w: float,
    h: float,
    fill: str,
    line: str | None = None,
    radius: bool = False,
    transparency: int = 0,
):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    shape = slide.shapes.add_shape(shape_type, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb(fill)
    shape.fill.transparency = transparency
    shape.line.color.rgb = rgb(line or fill)
    if radius:
        try:
            shape.adjustments[0] = 0.12
        except (IndexError, ValueError):
            pass
    return shape


def add_text(
    slide,
    text: str,
    x: float,
    y: float,
    w: float,
    h: float,
    size: float = 18,
    color: str = DARK,
    bold: bool = False,
    font: str = "Aptos",
    align: PP_ALIGN = PP_ALIGN.LEFT,
    valign: MSO_ANCHOR = MSO_ANCHOR.TOP,
    margin: float = 0.03,
    linespacing: float = 1.0,
):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Inches(margin)
    tf.margin_right = Inches(margin)
    tf.margin_top = Inches(margin)
    tf.margin_bottom = Inches(margin)
    tf.vertical_anchor = valign
    p = tf.paragraphs[0]
    p.alignment = align
    p.line_spacing = linespacing
    run = p.add_run()
    run.text = text
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = rgb(color)
    return box


def add_rich_text(
    slide,
    parts: Sequence[tuple[str, bool, str]],
    x: float,
    y: float,
    w: float,
    h: float,
    size: float = 16,
    align: PP_ALIGN = PP_ALIGN.LEFT,
):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.margin_left = tf.margin_right = Inches(0.03)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    p = tf.paragraphs[0]
    p.alignment = align
    for text, bold, color in parts:
        run = p.add_run()
        run.text = text
        run.font.name = "Aptos"
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = rgb(color)
    return box


def add_bullets(
    slide,
    items: Iterable[str],
    x: float,
    y: float,
    w: float,
    h: float,
    size: float = 16,
    color: str = DARK,
    accent: str = ORANGE,
    spacing: float = 8,
):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Inches(0.02)
    tf.margin_right = Inches(0.02)
    tf.margin_top = Inches(0.02)
    tf.margin_bottom = Inches(0.02)
    for idx, item in enumerate(items):
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.level = 0
        p.space_after = Pt(spacing)
        p.line_spacing = 1.05
        p.text = ""
        marker = p.add_run()
        marker.text = "●  "
        marker.font.name = "Aptos"
        marker.font.size = Pt(max(8, size - 4))
        marker.font.color.rgb = rgb(accent)
        run = p.add_run()
        run.text = item
        run.font.name = "Aptos"
        run.font.size = Pt(size)
        run.font.color.rgb = rgb(color)
    return box


def add_header(slide, title: str, section: str, number: int) -> None:
    add_text(slide, section.upper(), 0.55, 0.22, 2.8, 0.22, 8.5, ORANGE, True)
    add_text(slide, title, 0.55, 0.48, 11.7, 0.48, 25, NAVY_DARK, True)
    add_rect(slide, 0.55, 1.04, 12.23, 0.025, LINE)
    add_text(slide, f"CALL CENTER WFM ANALYTICS  •  {number:02d}", 9.55, 7.19, 3.23, 0.18, 8, MUTED, False, align=PP_ALIGN.RIGHT)


def add_kpi_card(
    slide,
    x: float,
    y: float,
    w: float,
    h: float,
    value: str,
    label: str,
    accent: str = NAVY,
    note: str | None = None,
    value_size: float = 24,
):
    add_rect(slide, x, y, w, h, WHITE, LINE, True)
    add_rect(slide, x, y, 0.08, h, accent, accent, True)
    add_text(slide, value, x + 0.2, y + 0.16, w - 0.35, 0.48, value_size, accent, True)
    add_text(slide, label, x + 0.2, y + 0.68, w - 0.35, 0.30, 10.5, MID, True)
    if note:
        add_text(slide, note, x + 0.2, y + 1.0, w - 0.35, h - 1.05, 8.5, MUTED)


def add_picture_crop(slide, path: Path, x: float, y: float, w: float, h: float):
    if not path.exists():
        raise FileNotFoundError(path)
    with Image.open(path) as im:
        image_ratio = im.width / im.height
    frame_ratio = w / h
    pic = slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w), Inches(h))
    if image_ratio > frame_ratio:
        crop = (1 - frame_ratio / image_ratio) / 2
        pic.crop_left = crop
        pic.crop_right = crop
    elif image_ratio < frame_ratio:
        crop = (1 - image_ratio / frame_ratio) / 2
        pic.crop_top = crop
        pic.crop_bottom = crop
    return pic


def add_tag(slide, text: str, x: float, y: float, w: float, color: str, fill: str):
    add_rect(slide, x, y, w, 0.34, fill, fill, True)
    add_text(slide, text, x + 0.05, y + 0.05, w - 0.1, 0.22, 9, color, True, align=PP_ALIGN.CENTER)


def add_arrow(slide, x1: float, y1: float, x2: float, y2: float, color: str = NAVY):
    connector = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT,
        Inches(x1),
        Inches(y1),
        Inches(x2),
        Inches(y2),
    )
    connector.line.color.rgb = rgb(color)
    connector.line.width = Pt(2)
    connector.line.end_arrowhead = True
    return connector


def add_section_card(slide, x, y, w, h, title, body, accent=NAVY, index=None):
    add_rect(slide, x, y, w, h, WHITE, LINE, True)
    if index is not None:
        add_rect(slide, x + 0.22, y + 0.2, 0.46, 0.46, accent, accent, True)
        add_text(slide, str(index), x + 0.22, y + 0.27, 0.46, 0.22, 11, WHITE, True, align=PP_ALIGN.CENTER)
        title_x = x + 0.82
    else:
        title_x = x + 0.24
    add_text(slide, title, title_x, y + 0.2, w - (title_x - x) - 0.2, 0.34, 15, accent, True)
    add_text(slide, body, x + 0.24, y + 0.78, w - 0.48, h - 0.94, 11.5, MID)


def add_wape_chart(slide, x: float, y: float, w: float, h: float):
    data = ChartData()
    data.categories = [
        "4-week mean",
        "XGBoost",
        "Seasonal naive",
        "Holt–Winters",
    ]
    data.add_series("WAPE", [0.1795, 0.1861, 0.2297, 0.2781])
    chart = slide.shapes.add_chart(
        XL_CHART_TYPE.BAR_CLUSTERED,
        Inches(x),
        Inches(y),
        Inches(w),
        Inches(h),
        data,
    ).chart
    chart.has_legend = False
    chart.has_title = False
    chart.value_axis.minimum_scale = 0
    chart.value_axis.maximum_scale = 0.30
    chart.value_axis.major_unit = 0.05
    chart.value_axis.tick_labels.number_format = "0%"
    chart.value_axis.tick_labels.font.size = Pt(9)
    chart.category_axis.tick_labels.font.size = Pt(10)
    chart.category_axis.reverse_order = True
    chart.plots[0].gap_width = 55
    series = chart.series[0]
    series.format.fill.solid()
    series.format.fill.fore_color.rgb = rgb(NAVY)
    colors = [ORANGE, TEAL, BLUE, MUTED]
    for point, color in zip(series.points, colors):
        point.format.fill.solid()
        point.format.fill.fore_color.rgb = rgb(color)
        point.format.line.color.rgb = rgb(color)
    chart.plots[0].has_data_labels = True
    labels = chart.plots[0].data_labels
    labels.position = XL_DATA_LABEL_POSITION.OUTSIDE_END
    labels.number_format = "0.0%"
    labels.font.size = Pt(9)
    labels.font.bold = True
    labels.font.color.rgb = rgb(DARK)
    return chart


def build_deck() -> Presentation:
    prs = Presentation()
    prs.slide_width = Inches(SLIDE_W)
    prs.slide_height = Inches(SLIDE_H)
    blank = prs.slide_layouts[6]

    # 1 — Cover
    slide = prs.slides.add_slide(blank)
    set_background(slide, NAVY_DARK)
    add_rect(slide, 0, 0, 0.16, 7.5, ORANGE)
    add_text(slide, "DATA ANALYTICS PORTFOLIO PROJECT", 0.72, 0.58, 5.6, 0.32, 10, ORANGE, True)
    add_text(slide, "CALL CENTER\nWFM ANALYTICS", 0.72, 1.02, 5.75, 1.55, 34, WHITE, True)
    add_text(
        slide,
        "Từ dữ liệu cuộc gọi công khai đến ETL,\ndự báo nhu cầu, staffing và Power BI",
        0.75,
        2.73,
        5.0,
        1.05,
        15.5,
        "DCE6EF",
    )
    add_tag(slide, "POSTGRESQL", 0.75, 4.18, 1.35, NAVY_DARK, "DCE6EF")
    add_tag(slide, "PYTHON ETL", 2.22, 4.18, 1.45, NAVY_DARK, "DCE6EF")
    add_tag(slide, "XGBOOST", 3.79, 4.18, 1.18, NAVY_DARK, "DCE6EF")
    add_tag(slide, "POWER BI", 5.09, 4.18, 1.13, NAVY_DARK, "DCE6EF")
    add_text(slide, "Dữ liệu: Technion Anonymous Bank • 01/1999–12/1999", 0.75, 6.62, 5.6, 0.30, 10, "C4D3E1")
    add_rect(slide, 6.62, 0.55, 6.17, 6.38, WHITE, WHITE, True)
    add_picture_crop(slide, IMG_OVERVIEW, 6.79, 0.72, 5.83, 6.04)

    # 2 — Executive summary
    slide = prs.slides.add_slide(blank)
    set_background(slide, LIGHT)
    add_header(slide, "Tóm tắt điều hành", "Kết quả chính", 2)
    cards = [
        ("440.844", "Offered calls", NAVY),
        ("80,11%", "Answer rate", TEAL),
        ("46,46%", "Service level", ORANGE),
        ("17,95%", "Forecast WAPE", BLUE),
        ("22", "Peak scheduled agents", RED),
    ]
    for i, (value, label, accent) in enumerate(cards):
        add_kpi_card(slide, 0.55 + i * 2.48, 1.35, 2.28, 1.33, value, label, accent)
    add_section_card(
        slide,
        0.55,
        3.0,
        3.9,
        2.9,
        "Một pipeline end-to-end",
        "Audit dữ liệu thô → ETL theo interval 30 phút → star schema PostgreSQL → forecast rolling-origin → staffing requirement → Power BI.",
        NAVY,
        1,
    )
    add_section_card(
        slide,
        4.72,
        3.0,
        3.9,
        2.9,
        "Model đơn giản thắng",
        "Trung bình cùng weekday/interval 4 tuần đạt WAPE thấp nhất. XGBoost đứng thứ hai; không chọn mô hình chỉ vì phức tạp hơn.",
        ORANGE,
        2,
    )
    add_section_card(
        slide,
        8.89,
        3.0,
        3.89,
        2.9,
        "Diễn giải có kiểm soát",
        "AHT là proxy; staffing là workload-based approximation. Chưa có schedule/attendance nên không tuyên bố understaffing, adherence hay occupancy thực tế.",
        TEAL,
        3,
    )
    add_text(slide, "Đầu ra bàn giao: 9 marts • 9 KPI views • 40 DAX measures • 3 dashboard pages • 41 visuals", 0.58, 6.31, 12.1, 0.40, 13, NAVY_DARK, True, align=PP_ALIGN.CENTER)

    # 3 — Business problem
    slide = prs.slides.add_slide(blank)
    set_background(slide, WHITE)
    add_header(slide, "Bài toán nghiệp vụ và người dùng", "Business framing", 3)
    add_text(slide, "Câu hỏi trung tâm", 0.7, 1.34, 2.8, 0.35, 12, ORANGE, True)
    add_text(slide, "Làm thế nào biến call-level logs thành quyết định vận hành theo từng interval 30 phút?", 0.7, 1.72, 5.5, 1.42, 22, NAVY_DARK, True)
    roles = [
        ("Operations Manager", "Theo dõi volume, answer/abandon rate, service level và peak demand.", NAVY),
        ("WFM Analyst", "So sánh forecast models, lập planned workload và staffing requirement.", ORANGE),
        ("Data/BI Team", "Bảo đảm provenance, data quality, grain, metric definitions và refresh.", TEAL),
    ]
    for i, (role, body, accent) in enumerate(roles):
        add_section_card(slide, 6.55, 1.3 + i * 1.68, 5.72, 1.40, role, body, accent, i + 1)
    add_rect(slide, 0.7, 3.25, 5.35, 2.6, LIGHT_BLUE, LIGHT_BLUE, True)
    add_text(slide, "Quyết định cần hỗ trợ", 1.0, 3.55, 4.75, 0.40, 17, NAVY, True)
    add_bullets(
        slide,
        [
            "Khi nào demand đạt đỉnh theo ngày/interval?",
            "Model nào dự báo ổn định nhất qua nhiều rolling folds?",
            "Planned workload cần bao nhiêu productive/scheduled agents?",
            "Service type nào có volume hoặc AHT proxy nổi bật?",
        ],
        1.0,
        4.08,
        4.78,
        1.48,
        12.5,
        MID,
        ORANGE,
        4,
    )

    # 4 — Data source and scope
    slide = prs.slides.add_slide(blank)
    set_background(slide, LIGHT)
    add_header(slide, "Nguồn dữ liệu, phạm vi và provenance", "Data foundation", 4)
    add_rect(slide, 0.55, 1.3, 4.2, 5.45, NAVY_DARK, NAVY_DARK, True)
    add_text(slide, "TECHNION\nANONYMOUS BANK", 0.95, 1.72, 3.35, 0.95, 25, WHITE, True)
    add_text(slide, "Call-level logs của call center ngân hàng", 0.95, 2.83, 3.3, 0.52, 14, "DCE6EF")
    add_kpi_card(slide, 0.95, 3.58, 1.5, 1.23, "12", "monthly files", ORANGE)
    add_kpi_card(slide, 2.52, 3.58, 1.68, 1.23, "444.448", "raw rows", TEAL, value_size=20)
    add_text(slide, "Coverage: 01/01/1999–31/12/1999\n52 agent labels (tên đã ẩn)\nSHA-256 và raw baseline được lưu làm bằng chứng", 0.95, 5.15, 3.25, 1.05, 11.5, "DCE6EF")
    add_text(slide, "Những trường nguồn đáp ứng", 5.15, 1.37, 3.35, 0.36, 16, NAVY, True)
    add_bullets(
        slide,
        [
            "Thời điểm vào hệ thống và queue duration",
            "Outcome: answered, hang-up, phantom",
            "Service duration, service type, priority và agent label",
            "Đủ để xây volume, answer/abandon và AHT proxy",
        ],
        5.15,
        1.86,
        3.45,
        2.05,
        12,
        MID,
        TEAL,
        4,
    )
    add_text(slide, "Giới hạn cần công bố", 8.9, 1.37, 3.35, 0.36, 16, RED, True)
    add_bullets(
        slide,
        [
            "Dữ liệu lịch sử năm 1999, không đại diện thị trường hiện tại",
            "Không có hold time và after-call work (ACW)",
            "Không có schedule, attendance hoặc agent state thực tế",
            "Không phân phối lại raw archive nếu chưa xác nhận quyền",
        ],
        8.9,
        1.86,
        3.55,
        2.25,
        12,
        MID,
        RED,
        4,
    )
    add_rect(slide, 5.15, 4.55, 7.25, 1.55, LIGHT_ORANGE, LIGHT_ORANGE, True)
    add_text(slide, "Nguyên tắc sử dụng", 5.48, 4.82, 2.1, 0.32, 13, ORANGE, True)
    add_text(slide, "Dùng cho portfolio/learning; ghi nguồn Technion; phân biệt observed, derived và synthetic; không suy diễn KPI ngoài dữ liệu.", 5.48, 5.20, 6.55, 0.55, 12.5, DARK)

    # 5 — Architecture
    slide = prs.slides.add_slide(blank)
    set_background(slide, WHITE)
    add_header(slide, "Kiến trúc giải pháp end-to-end", "Solution architecture", 5)
    stages = [
        ("RAW", "12 monthly TXT\n+ documentation\n+ checksums", NAVY, LIGHT_BLUE),
        ("ETL", "Clean & classify\n30-min intervals\ncalendar enrichment", TEAL, LIGHT_TEAL),
        ("ANALYTICS", "Foundation marts\nforecast facts\nstaffing facts", ORANGE, LIGHT_ORANGE),
        ("POSTGRESQL", "analytics schema\nstar model\nKPI serving views", BLUE, LIGHT_BLUE),
        ("POWER BI", "40 measures\n3 pages\n41 visuals", NAVY_DARK, "E8EDF3"),
    ]
    start_x = 0.48
    for i, (title, body, accent, fill) in enumerate(stages):
        x = start_x + i * 2.55
        add_rect(slide, x, 2.05, 2.06, 2.72, fill, accent, True)
        add_rect(slide, x, 2.05, 2.06, 0.50, accent, accent, True)
        add_text(slide, title, x + 0.08, 2.18, 1.9, 0.20, 10, WHITE, True, align=PP_ALIGN.CENTER)
        add_text(slide, body, x + 0.18, 2.83, 1.70, 1.34, 12.5, DARK, False, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
        if i < len(stages) - 1:
            add_arrow(slide, x + 2.09, 3.40, x + 2.46, 3.40, MUTED)
    add_rect(slide, 0.72, 5.35, 11.9, 0.88, LIGHT, LINE, True)
    add_text(slide, "Control gates", 0.98, 5.62, 1.25, 0.22, 10, NAVY, True)
    gates = ["Raw baseline", "Reconciliation", "Leakage checks", "PK/FK checks", "PBIR validation"]
    for i, gate in enumerate(gates):
        add_tag(slide, gate, 2.25 + i * 1.95, 5.55, 1.68, NAVY, WHITE)

    # 6 — ETL and data quality
    slide = prs.slides.add_slide(blank)
    set_background(slide, LIGHT)
    add_header(slide, "ETL và bằng chứng chất lượng dữ liệu", "Data engineering", 6)
    add_text(slide, "Reconciliation identity", 0.65, 1.35, 3.4, 0.35, 15, NAVY, True)
    flow = [
        ("444.448", "Raw records", NAVY),
        ("440.844", "Offered calls", TEAL),
        ("3.599", "Excluded phantom", ORANGE),
        ("5", "Quarantine", RED),
    ]
    for i, (value, label, color) in enumerate(flow):
        y = 1.88 + i * 1.02
        add_kpi_card(slide, 0.65, y, 3.55, 0.84, value, label, color)
    add_rect(slide, 4.68, 1.32, 3.67, 4.75, WHITE, LINE, True)
    add_text(slide, "Foundation marts", 4.98, 1.62, 3.05, 0.35, 16, TEAL, True)
    add_kpi_card(slide, 4.98, 2.16, 3.05, 1.12, "17.520", "queue × 30-min intervals", NAVY)
    add_kpi_card(slide, 4.98, 3.48, 3.05, 1.12, "105.120", "service-type interval rows", TEAL)
    add_kpi_card(slide, 4.98, 4.80, 3.05, 1.12, "417.149", "agent-demand calls", ORANGE)
    add_rect(slide, 8.75, 1.32, 3.92, 4.75, NAVY_DARK, NAVY_DARK, True)
    add_text(slide, "Quy tắc ETL nổi bật", 9.05, 1.65, 3.30, 0.35, 16, WHITE, True)
    add_bullets(
        slide,
        [
            "Chuẩn hóa malformed delimiter và kiểu thời lượng",
            "Âm duration được xử lý theo rule, không xóa im lặng",
            "Zero-fill chỉ khi coverage đã được xác nhận",
            "DST ambiguous/nonexistent giữ UTC null",
            "Mọi row phải clean, excluded hoặc quarantine",
        ],
        9.05,
        2.18,
        3.10,
        2.92,
        12,
        "EAF0F5",
        ORANGE,
        6,
    )
    add_text(slide, "Không có record biến mất ngoài reconciliation.", 9.05, 5.42, 3.05, 0.32, 11, ORANGE, True)

    # 7 — Semantic model
    slide = prs.slides.add_slide(blank)
    set_background(slide, WHITE)
    add_header(slide, "Dimensional model và lớp KPI", "Analytics warehouse", 7)
    add_rect(slide, 4.62, 2.40, 4.08, 2.20, NAVY_DARK, NAVY_DARK, True)
    add_text(slide, "FACTS", 4.92, 2.68, 3.48, 0.30, 14, ORANGE, True, align=PP_ALIGN.CENTER)
    add_text(slide, "Queue interval\nService type interval\nForecast interval\nModel evaluation\nStaffing requirement", 4.92, 3.10, 3.48, 1.18, 13, WHITE, False, align=PP_ALIGN.CENTER)
    dims = [
        ("DIM DATE", "calendar • weekday • holiday", 0.65, 1.55, NAVY),
        ("DIM TIME", "30-minute interval • daypart", 0.65, 4.55, TEAL),
        ("DIM QUEUE", "queue label • source mapping", 9.05, 1.55, ORANGE),
        ("DIM SERVICE", "6 normalized service types", 9.05, 4.55, BLUE),
    ]
    for title, body, x, y, accent in dims:
        add_rect(slide, x, y, 3.25, 1.26, LIGHT, accent, True)
        add_text(slide, title, x + 0.22, y + 0.20, 2.8, 0.28, 13, accent, True)
        add_text(slide, body, x + 0.22, y + 0.62, 2.8, 0.30, 10.5, MID)
        if x < 4:
            add_arrow(slide, x + 3.25, y + 0.63, 4.55, 3.50, accent)
        else:
            add_arrow(slide, x, y + 0.63, 8.76, 3.50, accent)
    add_text(slide, "13 relationships", 4.92, 5.12, 1.42, 0.26, 10, NAVY, True, align=PP_ALIGN.CENTER)
    add_text(slide, "1:* • single direction", 6.34, 5.12, 2.1, 0.26, 10, MID, True, align=PP_ALIGN.CENTER)
    add_rect(slide, 3.45, 5.65, 6.42, 0.74, LIGHT_BLUE, LIGHT_BLUE, True)
    add_text(slide, "40 DAX measures • additive numerator/denominator • không tạo fact-to-fact relationship", 3.62, 5.88, 6.05, 0.22, 11, NAVY_DARK, True, align=PP_ALIGN.CENTER)

    # 8 — Executive dashboard
    slide = prs.slides.add_slide(blank)
    set_background(slide, LIGHT)
    add_header(slide, "Dashboard 01 — Executive Overview", "Power BI", 8)
    add_rect(slide, 0.5, 1.28, 9.55, 5.55, WHITE, LINE, True)
    add_picture_crop(slide, IMG_OVERVIEW, 0.63, 1.41, 9.29, 5.29)
    add_text(slide, "Điểm đọc chính", 10.35, 1.42, 2.32, 0.35, 15, NAVY, True)
    add_bullets(
        slide,
        [
            "Volume có seasonality intraday và weekday rõ",
            "Answer Rate đạt 80,11% nhưng Service Level chỉ 46,46%",
            "Heatmap giúp xác định peak demand theo ngày × interval",
            "Slicer hỗ trợ date, queue, day, daypart và holiday",
        ],
        10.35,
        1.94,
        2.38,
        2.68,
        11.5,
        MID,
        ORANGE,
        6,
    )
    add_rect(slide, 10.32, 5.00, 2.42, 1.20, LIGHT_ORANGE, LIGHT_ORANGE, True)
    add_text(slide, "AHT Proxy", 10.55, 5.21, 1.96, 0.25, 12, ORANGE, True, align=PP_ALIGN.CENTER)
    add_text(slide, "194,25 giây\nkhông gồm hold + ACW", 10.48, 5.55, 2.10, 0.44, 11, DARK, True, align=PP_ALIGN.CENTER)

    # 9 — Forecast model selection
    slide = prs.slides.add_slide(blank)
    set_background(slide, WHITE)
    add_header(slide, "So sánh mô hình dự báo", "Forecasting", 9)
    add_text(slide, "Rolling-origin backtest", 0.65, 1.32, 3.5, 0.35, 15, NAVY, True)
    add_wape_chart(slide, 0.50, 1.82, 6.25, 4.35)
    add_rect(slide, 7.12, 1.30, 5.55, 2.12, LIGHT_ORANGE, LIGHT_ORANGE, True)
    add_text(slide, "MODEL ĐƯỢC CHỌN", 7.45, 1.62, 2.18, 0.25, 10, ORANGE, True)
    add_text(slide, "same_weekday_interval_mean_4w", 7.45, 2.00, 4.77, 0.42, 18, NAVY_DARK, True)
    add_text(slide, "WAPE 17,95%  •  Bias -1,21%  •  MAE 4,78  •  RMSE 8,02", 7.45, 2.55, 4.75, 0.35, 11, MID, True)
    add_rect(slide, 7.12, 3.66, 5.55, 2.72, LIGHT_TEAL, LIGHT_TEAL, True)
    add_text(slide, "Vì sao không chọn XGBoost?", 7.45, 3.96, 4.73, 0.32, 15, TEAL, True)
    add_bullets(
        slide,
        [
            "XGBoost WAPE 18,61% — cao hơn baseline khoảng 0,65 điểm %",
            "Cùng 6 folds, cùng 7-day horizon và cùng scope overall",
            "Weekly lags 1–4 tuần ngăn leakage vào test horizon",
            "Ưu tiên độ chính xác và tính giải thích thay vì độ phức tạp",
        ],
        7.45,
        4.42,
        4.72,
        1.48,
        11,
        MID,
        TEAL,
        4,
    )
    add_text(slide, "6 folds  •  336 intervals/fold  •  4 models  •  WAPE là metric chọn model", 0.68, 6.40, 6.0, 0.28, 10.5, MUTED, True, align=PP_ALIGN.CENTER)

    # 10 — Forecast & staffing dashboard and methodology
    slide = prs.slides.add_slide(blank)
    set_background(slide, LIGHT)
    add_header(slide, "Dashboard 02 — Forecast & Staffing", "WFM planning", 10)
    add_rect(slide, 0.5, 1.30, 8.52, 5.46, WHITE, LINE, True)
    add_picture_crop(slide, IMG_FORECAST, 0.63, 1.43, 8.26, 5.20)
    add_text(slide, "Staffing logic", 9.35, 1.46, 3.15, 0.32, 15, NAVY, True)
    formula = [
        ("1", "Forecast agent-demand calls", NAVY),
        ("2", "Forecast AHT proxy", TEAL),
        ("3", "Workload hours", ORANGE),
        ("4", "Productive agents", BLUE),
        ("5", "Gross-up shrinkage → scheduled", RED),
    ]
    for i, (idx, label, color) in enumerate(formula):
        y = 1.92 + i * 0.68
        add_rect(slide, 9.35, y, 0.42, 0.42, color, color, True)
        add_text(slide, idx, 9.35, y + 0.09, 0.42, 0.18, 10, WHITE, True, align=PP_ALIGN.CENTER)
        add_text(slide, label, 9.94, y + 0.05, 2.62, 0.30, 11.5, DARK, i in (2, 4))
    add_rect(slide, 9.35, 5.56, 3.22, 0.82, LIGHT_ORANGE, LIGHT_ORANGE, True)
    add_text(slide, "Peak scheduled agents: 22", 9.55, 5.78, 2.82, 0.26, 13, ORANGE, True, align=PP_ALIGN.CENTER)
    add_text(slide, "Workload-based approximation — chưa phải Erlang C", 9.38, 6.47, 3.14, 0.24, 9.5, RED, True, align=PP_ALIGN.CENTER)

    # 11 — Service mix dashboard
    slide = prs.slides.add_slide(blank)
    set_background(slide, WHITE)
    add_header(slide, "Dashboard 03 — Service Mix & Data Quality", "Operational segmentation", 11)
    add_rect(slide, 0.5, 1.30, 9.55, 5.47, LIGHT, LINE, True)
    add_picture_crop(slide, IMG_SERVICE, 0.63, 1.43, 9.29, 5.21)
    add_text(slide, "Giá trị phân tích", 10.33, 1.47, 2.40, 0.34, 15, TEAL, True)
    add_bullets(
        slide,
        [
            "So sánh volume theo 6 service types đã chuẩn hóa",
            "Đặt Answer Rate và Abandon Rate trong cùng ngữ cảnh",
            "Nhận diện service có AHT proxy cao",
            "Theo dõi coverage status: observed và zero-filled",
            "Heatmap service demand theo interval",
        ],
        10.33,
        1.97,
        2.40,
        3.32,
        11.2,
        MID,
        TEAL,
        6,
    )
    add_rect(slide, 10.33, 5.55, 2.38, 0.82, LIGHT_TEAL, LIGHT_TEAL, True)
    add_text(slide, "Service slicer chỉ lọc các fact có quan hệ hợp lệ", 10.52, 5.70, 2.02, 0.55, 9.0, TEAL, True, align=PP_ALIGN.CENTER)

    # 12 — Engineering quality and delivery
    slide = prs.slides.add_slide(blank)
    set_background(slide, LIGHT)
    add_header(slide, "Chất lượng kỹ thuật và khả năng tái lập", "Delivery", 12)
    stats = [
        ("10/10", "warehouse objects imported", NAVY),
        ("13", "business relationships", TEAL),
        ("40/40", "DAX measures executed", ORANGE),
        ("0", "blank measures at total", GREEN),
        ("41", "PBIR visuals", BLUE),
        ("0 / 0", "PBIR errors / warnings", RED),
    ]
    for i, (value, label, color) in enumerate(stats):
        row, col = divmod(i, 3)
        add_kpi_card(slide, 0.63 + col * 4.18, 1.35 + row * 1.57, 3.86, 1.30, value, label, color)
    add_rect(slide, 0.63, 4.78, 12.05, 1.35, NAVY_DARK, NAVY_DARK, True)
    add_text(slide, "Bằng chứng trong repository", 0.95, 5.05, 2.85, 0.30, 15, WHITE, True)
    add_text(slide, "Raw baseline + SHA-256", 4.05, 5.04, 2.00, 0.30, 11, "DCE6EF", True, align=PP_ALIGN.CENTER)
    add_text(slide, "ETL reconciliation", 6.18, 5.04, 1.70, 0.30, 11, "DCE6EF", True, align=PP_ALIGN.CENTER)
    add_text(slide, "Warehouse QA", 8.03, 5.04, 1.52, 0.30, 11, "DCE6EF", True, align=PP_ALIGN.CENTER)
    add_text(slide, "PBIR validation + screenshots", 9.70, 5.04, 2.42, 0.30, 11, ORANGE, True, align=PP_ALIGN.CENTER)
    add_text(slide, "Scripts có backup, chạy lại được và giữ UTF-8; mô hình/measure definitions được version bằng source files.", 1.0, 5.56, 11.0, 0.35, 11.5, WHITE, False, align=PP_ALIGN.CENTER)

    # 13 — Limitations
    slide = prs.slides.add_slide(blank)
    set_background(slide, WHITE)
    add_header(slide, "Giới hạn và cách diễn giải có trách nhiệm", "Risk & governance", 13)
    items = [
        ("AHT Proxy", "Không có hold time và ACW; chỉ dùng service_seconds / eligible answered calls.", ORANGE),
        ("Staffing", "Workload/capacity baseline, chưa tối ưu service-level bằng Erlang C.", NAVY),
        ("No staffing gap", "Thiếu scheduled/available headcount thật; không gọi planned-vs-actualized là understaffing.", RED),
        ("Historical scope", "Dữ liệu 1999 phù hợp portfolio, không đại diện volume/channel mix hiện tại.", TEAL),
        ("Privacy", "Agent labels được ẩn; không có customer IDs/names trong baseline báo cáo.", BLUE),
        ("Model transfer", "Model selection đúng trên bộ dữ liệu này; cần backtest lại khi đổi center hoặc thời kỳ.", GREEN),
    ]
    for i, (title, body, accent) in enumerate(items):
        row, col = divmod(i, 2)
        x = 0.65 + col * 6.18
        y = 1.32 + row * 1.70
        add_rect(slide, x, y, 5.83, 1.42, LIGHT, accent, True)
        add_rect(slide, x, y, 0.09, 1.42, accent, accent, True)
        add_text(slide, title, x + 0.28, y + 0.20, 1.63, 0.30, 14, accent, True)
        add_text(slide, body, x + 1.93, y + 0.18, 3.62, 0.84, 11.5, MID)
    add_rect(slide, 0.65, 6.45, 12.0, 0.42, LIGHT_ORANGE, LIGHT_ORANGE, True)
    add_text(slide, "Nguyên tắc: chỉ báo cáo KPI khi grain, denominator và ý nghĩa nghiệp vụ đều hợp lệ.", 0.85, 6.55, 11.6, 0.20, 11, ORANGE, True, align=PP_ALIGN.CENTER)

    # 14 — Next steps
    slide = prs.slides.add_slide(blank)
    set_background(slide, NAVY_DARK)
    add_text(slide, "NEXT STEPS", 0.70, 0.55, 2.0, 0.30, 10, ORANGE, True)
    add_text(slide, "Từ portfolio MVP đến WFM decision system", 0.70, 1.0, 10.5, 0.58, 28, WHITE, True)
    roadmap = [
        ("01", "Workforce marts", "Bổ sung schedule, attendance và agent state; tính staffing gap/adherence thật.", TEAL),
        ("02", "Queueing model", "So sánh workload baseline với Erlang C theo service-level target.", ORANGE),
        ("03", "Forecast monitoring", "Theo dõi drift, WAPE theo horizon/segment và trigger retraining.", BLUE),
        ("04", "Production BI", "Publish, refresh gateway, RLS, accessibility và alerting.", RED),
    ]
    for i, (idx, title, body, accent) in enumerate(roadmap):
        x = 0.72 + i * 3.12
        add_rect(slide, x, 2.04, 2.78, 3.62, WHITE, WHITE, True)
        add_rect(slide, x + 0.22, 2.27, 0.56, 0.56, accent, accent, True)
        add_text(slide, idx, x + 0.22, 2.42, 0.56, 0.22, 11, WHITE, True, align=PP_ALIGN.CENTER)
        add_text(slide, title, x + 0.22, 3.05, 2.34, 0.55, 16, accent, True)
        add_text(slide, body, x + 0.22, 3.77, 2.30, 1.18, 12, DARK)
    add_text(slide, "Kết luận", 0.72, 6.20, 1.25, 0.28, 12, ORANGE, True)
    add_text(slide, "Dự án kết nối data engineering, forecasting, WFM logic và BI storytelling — đồng thời kiểm soát chặt giới hạn dữ liệu.", 2.02, 6.08, 10.25, 0.72, 12.5, WHITE, True)
    add_text(slide, "Nguồn chính: Technion Anonymous Bank • Tài liệu, ETL rules, metric definitions và QA artifacts trong repository", 0.72, 7.06, 11.9, 0.20, 8.5, "B8C8D8", False, align=PP_ALIGN.CENTER)

    return prs


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    missing = [p for p in (IMG_OVERVIEW, IMG_FORECAST, IMG_SERVICE) if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing dashboard screenshots: {missing}")
    prs = build_deck()
    prs.save(OUT_PATH)
    print(f"output={OUT_PATH}")
    print(f"slides={len(prs.slides)}")
    print(f"bytes={OUT_PATH.stat().st_size}")


if __name__ == "__main__":
    main()
