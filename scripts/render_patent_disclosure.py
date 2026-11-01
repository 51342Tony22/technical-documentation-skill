#!/usr/bin/env python3
"""Render a validated patent disclosure as a long-form reference-style DOCX."""

from __future__ import annotations

import argparse
import json
import math
import re
import tempfile
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor

import validate_draft


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = ROOT / "assets" / "templates" / "patent-technical-disclosure.docx"
BODY_CN_FONT = "Songti SC"
HEADING_CN_FONT = "Heiti SC"
LATIN_FONT = "Times New Roman"
ALLOWED_FIGURE_TYPES = {
    "flowchart",
    "architecture",
    "module",
    "sequence",
    "data-structure",
    "formula",
    "chart",
    "screenshot",
}
CHINESE_ORDINALS = ("第一", "第二", "第三", "第四", "第五", "第六", "第七", "第八", "第九", "第十")


def set_run_font(run, *, size: float = 12, bold: bool = False, heading: bool = False) -> None:
    run.bold = bold
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor(0, 0, 0)
    run.font.name = LATIN_FONT
    east_asia = HEADING_CN_FONT if heading else BODY_CN_FONT
    fonts = run._element.get_or_add_rPr().rFonts
    fonts.set(qn("w:eastAsia"), east_asia)
    fonts.set(qn("w:ascii"), LATIN_FONT)
    fonts.set(qn("w:hAnsi"), LATIN_FONT)
    fonts.set(qn("w:cs"), LATIN_FONT)


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def set_table_borders(table) -> None:
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.find(qn("w:tblBorders"))
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = borders.find(qn(f"w:{edge}"))
        if element is None:
            element = OxmlElement(f"w:{edge}")
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "6")
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), "666666")


def clear_template_body(document: Document) -> None:
    body = document._element.body
    for child in list(body):
        if child.tag != qn("w:sectPr"):
            body.remove(child)


def setup_page(document: Document) -> None:
    section = document.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(3.18)
    section.right_margin = Cm(3.18)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.header_distance = Cm(1.2)
    section.footer_distance = Cm(1.2)

    for header in (section.header,):
        for paragraph in header.paragraphs:
            paragraph.clear()

    footer = section.footer
    for child in list(footer._element):
        footer._element.remove(child)
    paragraph = footer.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = " PAGE "
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instruction, separate, end])
    set_run_font(run, size=10)


def format_body_paragraph(paragraph, *, indent: bool = True) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(6)
    paragraph.paragraph_format.line_spacing = 1.5
    paragraph.paragraph_format.widow_control = True
    if indent:
        paragraph.paragraph_format.first_line_indent = Pt(24)


def add_text(document: Document, text: str, *, indent: bool = True, bold_prefix: str | None = None):
    paragraph = document.add_paragraph()
    format_body_paragraph(paragraph, indent=indent)
    if bold_prefix and text.startswith(bold_prefix):
        set_run_font(paragraph.add_run(bold_prefix), bold=True)
        set_run_font(paragraph.add_run(text[len(bold_prefix):]))
    else:
        set_run_font(paragraph.add_run(text))
    return paragraph


def add_blocks(document: Document, text: str) -> None:
    for block in (part.strip() for part in re.split(r"\n\s*\n", text or "")):
        if not block:
            continue
        if re.match(r"^(S\d+|步骤\s*\d+|第[一二三四五六七八九十]+[阶段步])", block):
            add_text(document, block, indent=False)
        else:
            add_text(document, block)


def add_title(document: Document, text: str, *, size: float, space_after: float = 18) -> None:
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_after = Pt(space_after)
    paragraph.paragraph_format.keep_with_next = True
    set_run_font(paragraph.add_run(text), size=size, bold=True, heading=True)


def add_major_heading(document: Document, text: str) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(12)
    paragraph.paragraph_format.space_after = Pt(8)
    paragraph.paragraph_format.keep_with_next = True
    run = paragraph.add_run(text)
    set_run_font(run, size=14, bold=True, heading=True)
    run.underline = True


def add_subheading(document: Document, text: str, *, level: int = 2) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.left_indent = Pt(0 if level == 2 else 24)
    paragraph.paragraph_format.space_before = Pt(8)
    paragraph.paragraph_format.space_after = Pt(4)
    paragraph.paragraph_format.keep_with_next = True
    set_run_font(paragraph.add_run(text), size=12, bold=True, heading=True)


def add_metadata_line(document: Document, label: str, value: str) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(8)
    set_run_font(paragraph.add_run(label), bold=True)
    set_run_font(paragraph.add_run(value or "[待补充]"))


def add_table(document: Document, spec: dict) -> None:
    headers = spec.get("表头", [])
    rows = spec.get("数据行", [])
    if not headers or not rows:
        return
    if spec.get("表前分页") is True:
        document.add_page_break()
    caption = document.add_paragraph()
    caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption.paragraph_format.space_before = Pt(8)
    caption.paragraph_format.space_after = Pt(5)
    set_run_font(
        caption.add_run(f"{spec.get('表号', '表')} {spec.get('标题', '')}".strip()),
        bold=True,
    )
    table = document.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(table)
    set_repeat_table_header(table.rows[0])
    for index, header in enumerate(headers):
        cell = table.rows[0].cells[index]
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        set_cell_shading(cell, "E7E6E6")
        paragraph = cell.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_run_font(paragraph.add_run(str(header)), size=10.5, bold=True)
    for values in rows:
        row = table.add_row()
        for index, value in enumerate(values[: len(headers)]):
            cell = row.cells[index]
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            paragraph = cell.paragraphs[0]
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.space_after = Pt(0)
            set_run_font(paragraph.add_run(str(value)), size=10.5)
    document.add_paragraph().paragraph_format.space_after = Pt(2)


def add_engineering_evidence(document: Document, evidence: dict) -> None:
    if not isinstance(evidence, dict):
        return
    add_major_heading(document, "工程实现与接口证据")
    assets = evidence.get("代码资产", [])
    if assets:
        add_subheading(document, "1. 代码资产清单")
        add_table(document, {
            "表号": "工程表1",
            "标题": "经预检的项目代码资产",
            "表头": ["资产ID", "路径", "用途", "语言/行数", "SHA-256（前12位）"],
            "数据行": [[
                item.get("artifact_id", ""), item.get("路径", ""), item.get("用途", ""),
                f"{item.get('语言', '')}/{item.get('行数', '')}", str(item.get("sha256", ""))[:12],
            ] for item in assets],
        })
    interfaces = evidence.get("接口契约", [])
    if interfaces:
        add_subheading(document, "2. 接口契约")
        add_table(document, {
            "表号": "工程表2",
            "标题": "端到端接口定义",
            "表头": ["接口ID", "方法与路径", "请求", "响应", "异常"],
            "数据行": [[
                item.get("接口ID", ""), f"{item.get('方法', '')} {item.get('路径', '')}",
                item.get("请求", ""), item.get("响应", ""), item.get("异常", ""),
            ] for item in interfaces],
        })
    workflow = evidence.get("端到端工作流", [])
    if workflow:
        add_subheading(document, "3. 接口工作流")
        for item in workflow:
            add_text(document, (
                f"{item.get('步骤', '')}：输入为{item.get('输入', '')}；"
                f"由{item.get('接口或模块', '')}执行{item.get('处理', '')}；"
                f"输出为{item.get('输出', '')}。"
            ), indent=False)
    preflight = evidence.get("资产预检", {})
    if preflight:
        add_subheading(document, "4. 资产预检结论")
        add_text(document, (
            f"预检状态：{preflight.get('状态', 'unknown')}；"
            f"真实运行截图：{'已核验' if preflight.get('截图为真实运行界面') else '未核验'}；"
            f"技术附图：{'确定性生成' if preflight.get('技术附图为确定性生成') else '来源待核验'}；"
            f"密钥扫描：{preflight.get('密钥扫描', 'unknown')}；"
            f"报告：{preflight.get('报告路径', '')}。"
        ), indent=False)


def _font_path() -> str | None:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    return next((item for item in candidates if Path(item).exists()), None)


def create_diagram(spec: dict, output_path: Path) -> bool:
    diagram = spec.get("diagram")
    if not isinstance(diagram, dict) or not diagram.get("nodes"):
        return False
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return False

    nodes = [str(item) for item in diagram["nodes"]]
    direction = diagram.get("direction", "horizontal")
    count = len(nodes)
    if direction == "vertical":
        width, cols = 1100, 1
        box_h, gap_y, bottom_margin = 120, 72, 45
    elif direction == "grid":
        width, cols = 1500, min(3, count)
        box_h, gap_y, bottom_margin = 135, 55, 55
    else:
        width, cols = max(1600, count * 460), count
        box_h, gap_y, bottom_margin = 135, 55, 140
    rows = math.ceil(count / cols)
    margin_y = 85
    # Size the canvas to its actual rows instead of embedding every diagram in a
    # fixed tall bitmap. Word can then place several compact diagrams on one page.
    height = margin_y + rows * box_h + (rows - 1) * gap_y + bottom_margin
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font_file = _font_path()
    font = ImageFont.truetype(font_file, 34) if font_file else ImageFont.load_default()
    small = ImageFont.truetype(font_file, 27) if font_file else ImageFont.load_default()

    gap_x = 70
    margin_x = 75
    box_w = (width - 2 * margin_x - (cols - 1) * gap_x) / cols
    positions = []
    for index, label in enumerate(nodes):
        row, col = divmod(index, cols)
        x1 = margin_x + col * (box_w + gap_x)
        y1 = margin_y + row * (box_h + gap_y)
        x2, y2 = x1 + box_w, y1 + box_h
        positions.append((x1, y1, x2, y2))
        draw.rounded_rectangle((x1, y1, x2, y2), radius=16, fill="#F6F7F8", outline="#273746", width=4)
        wrapped = []
        line = ""
        for char in label:
            if draw.textlength(line + char, font=small) <= box_w - 36:
                line += char
            else:
                wrapped.append(line)
                line = char
        if line:
            wrapped.append(line)
        total_h = len(wrapped) * 38
        for line_index, line_text in enumerate(wrapped[:3]):
            line_w = draw.textlength(line_text, font=small)
            draw.text(
                (x1 + (box_w - line_w) / 2, y1 + (box_h - total_h) / 2 + line_index * 38),
                line_text,
                fill="#111111",
                font=small,
            )

    edges = diagram.get("edges") or [[i, i + 1, ""] for i in range(count - 1)]
    for edge in edges:
        try:
            start, end = int(edge[0]), int(edge[1])
        except (TypeError, ValueError, IndexError):
            continue
        if not (0 <= start < count and 0 <= end < count):
            continue
        sx1, sy1, sx2, sy2 = positions[start]
        ex1, ey1, ex2, ey2 = positions[end]
        if ey1 > sy1 + 10:
            start_point = ((sx1 + sx2) / 2, sy2)
            end_point = ((ex1 + ex2) / 2, ey1)
        else:
            start_point = (sx2, (sy1 + sy2) / 2)
            end_point = (ex1, (ey1 + ey2) / 2)
        draw.line((*start_point, *end_point), fill="#273746", width=5)
        angle = math.atan2(end_point[1] - start_point[1], end_point[0] - start_point[0])
        arrow = 18
        points = [
            end_point,
            (
                end_point[0] - arrow * math.cos(angle - math.pi / 6),
                end_point[1] - arrow * math.sin(angle - math.pi / 6),
            ),
            (
                end_point[0] - arrow * math.cos(angle + math.pi / 6),
                end_point[1] - arrow * math.sin(angle + math.pi / 6),
            ),
        ]
        draw.polygon(points, fill="#273746")
        if len(edge) > 2 and edge[2]:
            if abs(end_point[1] - start_point[1]) < 10:
                midpoint = ((start_point[0] + end_point[0]) / 2, max(sy2, ey2) + 38)
            else:
                midpoint = ((start_point[0] + end_point[0]) / 2, (start_point[1] + end_point[1]) / 2 - 32)
            label = str(edge[2])
            bounds = draw.textbbox(midpoint, label, font=small, anchor="mm")
            draw.rectangle((bounds[0] - 8, bounds[1] - 3, bounds[2] + 8, bounds[3] + 3), fill="white")
            draw.text(midpoint, label, fill="#111111", font=small, anchor="mm")

    title = str(spec.get("标题", "技术示意图"))
    title_w = draw.textlength(title, font=font)
    draw.text(((width - title_w) / 2, 24), title, fill="#111111", font=font)
    image.save(output_path)
    return True


def create_altair_chart(spec: dict, output_path: Path) -> bool:
    if spec.get("类型") != "chart" or spec.get("生成器") != "altair":
        return False
    chart_spec = spec.get("chart_spec")
    if not isinstance(chart_spec, dict):
        return False
    data = chart_spec.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("values"), list) or not data["values"]:
        raise ValueError("Altair chart requires self-contained chart_spec.data.values")
    if "url" in data:
        raise ValueError("Altair chart must not load data from an external URL")
    try:
        import altair as alt
    except ImportError as error:
        raise RuntimeError(
            "Altair chart generation requires the packages listed in scripts/requirements-altair.txt"
        ) from error
    payload = dict(chart_spec)
    payload.setdefault("$schema", "https://vega.github.io/schema/vega-lite/v5.json")
    payload.setdefault("width", 640)
    payload.setdefault("height", 360)
    chart = alt.Chart.from_dict(payload)
    try:
        chart.save(str(output_path), scale_factor=2)
    except Exception as error:
        raise RuntimeError(
            "Altair PNG export failed; install vl-convert-python and verify the chart_spec"
        ) from error
    return True


def add_figure(document: Document, spec: dict, *, base_dir: Path, temp_dir: Path) -> None:
    image_path = spec.get("image_path")
    resolved = None
    if isinstance(image_path, str) and image_path.strip():
        candidate = Path(image_path)
        resolved = candidate if candidate.is_absolute() else (base_dir / candidate).resolve()
        if not resolved.exists():
            resolved = None
    if resolved is None:
        candidate = temp_dir / f"figure-{re.sub(r'[^0-9A-Za-z_-]+', '-', str(spec.get('图号', 'x')))}.png"
        if create_altair_chart(spec, candidate) or create_diagram(spec, candidate):
            resolved = candidate

    layout = spec.get("排版") if isinstance(spec.get("排版"), dict) else {}
    if layout.get("前置分页") is True:
        document.add_page_break()

    if resolved is not None:
        width_by_mode = {"full": 5.75, "medium": 5.1, "compact": 3.6}
        width_inches = width_by_mode.get(layout.get("宽度"), 5.75)
        if "宽度" not in layout:
            if (spec.get("diagram") or {}).get("direction") == "vertical":
                width_inches = 4.7
            try:
                from PIL import Image

                with Image.open(resolved) as source_image:
                    aspect = source_image.height / source_image.width
                if aspect > 1.45:
                    width_inches = 4.4
                elif aspect > 1.0 and (spec.get("diagram") or {}).get("direction") != "vertical":
                    width_inches = 4.8
            except (ImportError, OSError):
                pass
        paragraph = document.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.space_before = Pt(4)
        paragraph.paragraph_format.space_after = Pt(2)
        paragraph.paragraph_format.keep_with_next = True
        run = paragraph.add_run()
        run.add_picture(str(resolved), width=Inches(width_inches))
    else:
        paragraph = document.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.space_before = Pt(12)
        paragraph.paragraph_format.space_after = Pt(4)
        paragraph.paragraph_format.keep_with_next = True
        run = paragraph.add_run(f"[{spec.get('图号', '附图')}待研发人员依据说明绘制] ")
        set_run_font(run, size=11, bold=True)
        set_run_font(paragraph.add_run(str(spec.get("说明", ""))), size=11)

    caption = document.add_paragraph()
    caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption.paragraph_format.space_after = Pt(10)
    caption.paragraph_format.keep_together = True
    evidence_labels = {
        "generated-technical-figure": "代码确定性生成图",
        "actual-runtime-screenshot": "真实运行界面截图",
        "conceptual-non-evidence": "概念示意图（非实现证据）",
    }
    caption_text = f"{spec.get('图号', '图')} {spec.get('标题', '')}".strip()
    if spec.get("evidence_class") in evidence_labels:
        caption_text += f"（{evidence_labels[spec['evidence_class']]}）"
    set_run_font(caption.add_run(caption_text), bold=True)


def fallback_profile(sections: dict, draft: dict) -> dict:
    figures = []
    figure_text = sections.get("具体实施方式及附图", "")
    for match in re.finditer(r"图(\d+)[，,、\s]+([^；;。\n]+)", figure_text):
        figures.append(
            {
                "图号": f"图{match.group(1)}",
                "标题": match.group(2).strip(),
                "类型": "flowchart",
                "说明": "根据正文描述绘制的建议附图，正式交底前需由研发人员核对。",
                "关联小节": "具体实施方式",
            }
        )
    return {
        "所属技术领域": "本发明属于计算机技术领域，具体技术对象和应用场景见下述技术方案。",
        "背景技术": {
            "现有技术状况描述与评价": sections.get("背景技术及现有技术的缺陷和不足", ""),
            "现有技术存在的问题和缺点": sections.get("背景技术及现有技术的缺陷和不足", ""),
            "发明形成过程": "现有结构化草稿未单独提供发明形成过程，正式交底前需由研发人员补充并确认。",
        },
        "发明内容": {
            "要解决的技术问题": sections.get("具体的技术方案描述", ""),
            "总体技术方案": sections.get("具体的技术方案描述", ""),
            "关键点及对应技术效果": [],
            "本发明创造的优点": [sections.get("本发明创造的优点", "")],
        },
        "具体实施方式": [
            {
                "标题": "技术方案与实施流程",
                "正文": sections.get("具体的技术方案描述", ""),
                "步骤": [],
            },
            {
                "标题": "实施例",
                "正文": sections.get("具体实施方式及附图", ""),
                "步骤": [],
            },
        ],
        "表格": [],
        "附图": figures,
        "检索附件": {
            "检索日期": "[待补充]",
            "检索数据库": [],
            "检索式": [],
            "保留记录": draft.get("sources", []),
            "最接近记录对比": draft.get("risk_assessment", {}).get("reasoning", ""),
            "检索局限": "本附件基于有限公开信息，不构成法律意见。",
        },
    }


def add_search_appendix(document: Document, appendix: dict, draft: dict) -> None:
    add_major_heading(document, "附件（参考文件、检索内容）")
    add_subheading(document, "1. 检索范围与检索式")
    add_text(document, f"检索日期：{appendix.get('检索日期', '[待补充]')}。", indent=False)
    databases = appendix.get("检索数据库", [])
    add_text(document, "检索数据库：" + ("、".join(databases) if databases else "[待补充]"), indent=False)
    queries = appendix.get("检索式", [])
    if queries:
        for index, query in enumerate(queries, start=1):
            add_text(document, f"检索式{index}：{query}", indent=False)
    else:
        add_text(document, "检索式：[待补充]", indent=False)

    add_subheading(document, "2. 最接近记录与差异核对")
    records = appendix.get("保留记录", []) or draft.get("sources", [])
    comparison_by_id = {item.get("source_id"): item for item in draft.get("differentiation", [])}
    rows = []
    for record_id in records:
        item = comparison_by_id.get(record_id, {})
        rows.append(
            [
                record_id,
                "；".join(item.get("overlap", [])) or "见检索记录",
                "；".join(item.get("confirmed_difference", [])) or "待研发人员核对",
                item.get("evidence_status", "待核对"),
            ]
        )
    if rows:
        add_table(
            document,
            {
                "表号": "检索表1",
                "标题": "最接近公开记录与本方案初步对比",
                "表头": ["公开编号", "重合特征", "当前确认差异", "证据状态"],
                "数据行": rows,
            },
        )
    add_blocks(document, appendix.get("最接近记录对比", ""))
    add_subheading(document, "3. 检索局限与复核要求")
    limitation = appendix.get("检索局限") or "本材料为初步机器辅助检索，不构成法律意见。"
    add_blocks(document, limitation)
    for item in draft.get("limitations", []):
        add_text(document, item, indent=False)


def render(
    draft: dict,
    output_path: Path,
    template_path: Path = DEFAULT_TEMPLATE,
    *,
    source_dir: Path | None = None,
) -> None:
    validation = validate_draft.validate(draft)
    if not validation["valid"] or not validation["render_ready"]:
        details = "; ".join(validation["errors"]) or "response is not render-ready"
        raise ValueError(details)
    if draft.get("mode") != "patent":
        raise ValueError("render_patent_disclosure.py accepts patent mode only")

    sections = draft["documents"]["technical-disclosure"]["sections"]
    profile = draft["documents"]["technical-disclosure"].get("disclosure_profile")
    if not isinstance(profile, dict):
        profile = fallback_profile(sections, draft)

    document = Document(template_path)
    clear_template_body(document)
    setup_page(document)
    document.styles["Normal"].font.name = LATIN_FONT
    document.styles["Normal"]._element.rPr.rFonts.set(qn("w:eastAsia"), BODY_CN_FONT)

    add_title(document, "专利申请技术交底书", size=22, space_after=30)
    add_metadata_line(document, "发明名称：", sections["发明创造名称"])
    add_metadata_line(document, "发明类型：", sections["申请类别"])
    add_metadata_line(document, "申请人：", sections["申请人"])
    add_metadata_line(document, "发明人或设计人：", sections["发明人或设计人"])
    add_metadata_line(document, "技术问题联系人（姓名、电话、邮箱）：", sections["联系人及联系方式"])

    add_major_heading(document, "所属技术领域")
    add_blocks(document, profile.get("所属技术领域", ""))

    background = profile.get("背景技术", {})
    writing_route = profile.get("写作路由", {})
    background_route = writing_route.get("背景组织") if isinstance(writing_route, dict) else None
    add_major_heading(document, "背景技术")
    if background_route == "three-part":
        add_subheading(document, "1. 技术背景")
        add_blocks(document, background.get("技术背景", ""))
        add_subheading(document, "2. 最接近的现有技术")
        add_blocks(document, background.get("最接近的现有技术", ""))
        add_subheading(document, "3. 现有技术的缺陷和不足")
        add_blocks(document, background.get("现有技术的缺陷和不足", ""))
    else:
        add_subheading(document, "1. 对现有技术状况进行描述和评价")
        add_blocks(document, background.get("现有技术状况描述与评价", ""))
        add_subheading(document, "2. 客观指出现有技术存在的问题和缺点")
        add_blocks(document, background.get("现有技术存在的问题和缺点", ""))
        formation = background.get("发明形成过程")
        if isinstance(formation, str) and formation.strip():
            add_subheading(document, "3. 该发明的形成过程（体现技术难点）")
            add_blocks(document, formation)

    invention = profile.get("发明内容", {})
    add_major_heading(document, "发明内容")
    add_subheading(document, "（一）本申请提案要解决的技术问题")
    add_blocks(document, invention.get("要解决的技术问题", ""))
    add_subheading(document, "（二）总体技术方案")
    add_blocks(document, invention.get("总体技术方案", sections.get("具体的技术方案描述", "")))
    add_subheading(document, "（三）简要说明欲保护的关键点及对应的技术效果")
    key_points = invention.get("关键点及对应技术效果", [])
    for index, item in enumerate(key_points, start=1):
        add_text(
            document,
            f"关键点{index}，{item.get('关键点', '')}：{item.get('技术效果', '')}",
            indent=False,
        )
    if not key_points:
        add_blocks(document, sections.get("具体的技术方案描述", ""))

    add_major_heading(document, "本发明创造的优点")
    advantages = invention.get("本发明创造的优点")
    if not isinstance(advantages, list) or not advantages:
        fallback_advantage = invention.get("总体技术效果", sections.get("本发明创造的优点", ""))
        advantages = [fallback_advantage] if fallback_advantage else []
    for index, advantage in enumerate(advantages):
        ordinal = CHINESE_ORDINALS[index] if index < len(CHINESE_ORDINALS) else f"第{index + 1}"
        add_text(document, f"{ordinal}，{advantage}", indent=False)

    add_major_heading(document, "具体实施方式")
    table_specs = profile.get("表格", [])
    rendered_tables = set()
    for index, subsection in enumerate(profile.get("具体实施方式", []), start=1):
        subsection_title = subsection.get("标题", "实施小节")
        add_subheading(document, f"{index}. {subsection_title}")
        add_blocks(document, subsection.get("正文", ""))
        for step in subsection.get("步骤", []):
            add_text(document, str(step), indent=False)
        for table_index, table_spec in enumerate(table_specs):
            relation = str(table_spec.get("关联小节", ""))
            if table_spec.get("优先级") == "high" and relation.endswith(subsection_title):
                add_table(document, table_spec)
                rendered_tables.add(table_index)

    for table_index, table_spec in enumerate(table_specs):
        if table_index not in rendered_tables:
            add_table(document, table_spec)

    evidence_route = writing_route.get("工程实现证据") if isinstance(writing_route, dict) else None
    if evidence_route == "include" or (evidence_route is None and profile.get("工程实现证据")):
        add_engineering_evidence(document, profile.get("工程实现证据"))

    figures = profile.get("附图", [])
    add_major_heading(document, "附图说明")
    if figures:
        for item in figures:
            add_text(
                document,
                f"{item.get('图号', '图')}为{item.get('标题', '')}。{item.get('说明', '')}",
                indent=False,
            )
    else:
        add_text(document, "附图需由研发人员根据具体实施方式补充。", indent=False)

    base_dir = source_dir or Path.cwd()
    with tempfile.TemporaryDirectory(prefix="patent-figures-") as temp_name:
        temp_dir = Path(temp_name)
        if figures:
            add_major_heading(document, "附图")
            for figure in figures:
                add_figure(document, figure, base_dir=base_dir, temp_dir=temp_dir)

        document.add_page_break()
        add_search_appendix(document, profile.get("检索附件", {}), draft)

        properties = document.core_properties
        properties.title = sections["发明创造名称"]
        properties.subject = "专利申请技术交底书"
        properties.author = ""
        properties.last_modified_by = ""
        properties.comments = "Generated from validated structured input; professional review required."

        output_path.parent.mkdir(parents=True, exist_ok=True)
        document.save(output_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft_json", type=Path)
    parser.add_argument("output_docx", type=Path)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    args = parser.parse_args()

    draft = json.loads(args.draft_json.read_text(encoding="utf-8"))
    render(draft, args.output_docx, args.template, source_dir=args.draft_json.parent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
