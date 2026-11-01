#!/usr/bin/env python3
"""Render template-aligned application-software copyright materials."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import (
    WD_ALIGN_PARAGRAPH,
    WD_BREAK,
    WD_LINE_SPACING,
    WD_TAB_ALIGNMENT,
    WD_TAB_LEADER,
)
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.shared import Cm, Inches, Pt, RGBColor

import validate_draft


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "assets" / "template-manifest.json"
TEMPLATE_DIR = ROOT / "assets" / "templates"
BODY_FONT = "Songti SC"
HEADING_FONT = "Heiti SC"
CODE_FONT = "Menlo"
ACCENT = RGBColor(0, 0, 0)
MUTED = RGBColor(89, 89, 89)


def set_run_font(run, font: str, size: float, *, bold: bool = False) -> None:
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor(0, 0, 0)
    r_fonts = run._element.get_or_add_rPr().get_or_add_rFonts()
    for key in ("w:ascii", "w:hAnsi", "w:cs"):
        r_fonts.set(qn(key), font)
    r_fonts.set(qn("w:eastAsia"), BODY_FONT if font == CODE_FONT else font)


def configure_styles(document: Document) -> None:
    definitions = {
        "Normal": (BODY_FONT, 10.5, False, RGBColor(0, 0, 0)),
        "Title": (HEADING_FONT, 26, True, RGBColor(0, 0, 0)),
        "Subtitle": (HEADING_FONT, 18, True, RGBColor(0, 0, 0)),
        "Heading 1": (HEADING_FONT, 16, True, ACCENT),
        "Heading 2": (HEADING_FONT, 14, True, RGBColor(0, 0, 0)),
        "Heading 3": (HEADING_FONT, 12, True, RGBColor(0, 0, 0)),
    }
    for style_name, (font, size, bold, color) in definitions.items():
        if style_name not in document.styles:
            document.styles.add_style(style_name, WD_STYLE_TYPE.PARAGRAPH)
        style = document.styles[style_name]
        style.font.name = font
        style.font.size = Pt(size)
        style.font.bold = bold
        style.font.color.rgb = color
        r_fonts = style._element.get_or_add_rPr().get_or_add_rFonts()
        for key in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
            r_fonts.set(qn(key), font)

    normal = document.styles["Normal"].paragraph_format
    normal.space_after = Pt(3)
    normal.line_spacing = 1.25
    for style_name, before, after in (
        ("Heading 1", 12, 6),
        ("Heading 2", 9, 4),
        ("Heading 3", 7, 3),
    ):
        if style_name in document.styles:
            paragraph_format = document.styles[style_name].paragraph_format
            paragraph_format.space_before = Pt(before)
            paragraph_format.space_after = Pt(after)
            paragraph_format.keep_with_next = True

    section = document.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(3.18)
    section.right_margin = Cm(3.18)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.header_distance = Cm(1.2)
    section.footer_distance = Cm(1.2)

    settings = document.settings._element
    update_fields = settings.find(qn("w:updateFields"))
    if update_fields is None:
        update_fields = OxmlElement("w:updateFields")
        settings.append(update_fields)
    update_fields.set(qn("w:val"), "true")


def clear_body(document: Document) -> None:
    body = document._element.body
    for child in list(body):
        if child.tag != qn("w:sectPr"):
            body.remove(child)
    remove_image_relationships(document)


def remove_image_relationships(document: Document) -> None:
    for relationship_id, relationship in list(document.part.rels.items()):
        if relationship.reltype == RT.IMAGE:
            del document.part.rels[relationship_id]


def clear_container(container) -> None:
    element = container._element
    for child in list(element):
        element.remove(child)
    element.append(OxmlElement("w:p"))


def add_page_number(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    set_run_font(run, BODY_FONT, 9)
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


def configure_header_footer(document: Document, identity: str) -> None:
    section = document.sections[0]
    section.different_first_page_header_footer = True
    clear_container(section.header)
    header_paragraph = section.header.paragraphs[0]
    header_paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    header_run = header_paragraph.add_run(identity)
    set_run_font(header_run, BODY_FONT, 9, bold=True)
    header_run.font.color.rgb = MUTED

    clear_container(section.first_page_header)
    clear_container(section.footer)
    add_page_number(section.footer.paragraphs[0])


def add_cover(document: Document, identity: str, document_title: str) -> None:
    for _ in range(7):
        document.add_paragraph()
    title = document.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.add_run(identity)
    subtitle = document.add_paragraph(style="Subtitle")
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.add_run(document_title)
    document.add_page_break()


def add_toc(document: Document, entries: list[tuple[int, str, int]]) -> None:
    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_after = Pt(12)
    set_run_font(title.add_run("目录"), HEADING_FONT, 18, bold=True)

    # Use visible template-style entries instead of an empty TOC field. This keeps
    # the directory complete in PDF/headless previews as well as in Word.
    for level, label, page_number in entries:
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.left_indent = Cm(0.55 * (level - 1))
        paragraph.paragraph_format.right_indent = Cm(0.1)
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(2)
        paragraph.paragraph_format.line_spacing = 1.15
        paragraph.paragraph_format.tab_stops.add_tab_stop(
            Cm(14.3 - 0.55 * (level - 1)),
            WD_TAB_ALIGNMENT.RIGHT,
            WD_TAB_LEADER.DOTS,
        )
        run = paragraph.add_run(f"{label}\t{page_number}")
        set_run_font(run, BODY_FONT, 10.5, bold=level == 1)
    document.add_page_break()


def add_numbered_section(document: Document, number: str, title: str, value: str, *, level: int) -> None:
    document.add_heading(f"{number} {title}", level=level)
    add_body_text(document, value)


def add_body_text(document: Document, value: str) -> None:
    blocks = [item.strip() for item in value.split("\n\n") if item.strip()]
    for block in blocks:
        paragraph = document.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        paragraph.paragraph_format.first_line_indent = Pt(21)
        paragraph.paragraph_format.space_after = Pt(3)
        paragraph.paragraph_format.line_spacing = 1.25
        paragraph.paragraph_format.widow_control = True
        run = paragraph.add_run(block)
        set_run_font(run, BODY_FONT, 10.5)


def add_required_sections(
    document: Document,
    sections: dict[str, str],
    ordered_sections: list[str],
) -> None:
    for name in ordered_sections:
        document.add_heading(name, level=1)
        add_body_text(document, sections[name])


def add_screenshot_section(document: Document, screenshots: list[dict]) -> None:
    document.add_heading("3.4 界面截图及说明", level=2)
    for index, screenshot in enumerate(screenshots, start=1):
        path = Path(screenshot["path"])
        if not path.is_file():
            raise ValueError(f"missing actual screenshot: {path}")
        document.add_heading(f"3.4.{index} {screenshot['title']}", level=3)
        add_body_text(document, screenshot["description"])
        image_paragraph = document.add_paragraph()
        image_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        image_paragraph.paragraph_format.keep_together = True
        image_paragraph.paragraph_format.keep_with_next = True
        image_width = float(screenshot.get("width_inches", 5.5))
        image_paragraph.add_run().add_picture(str(path), width=Inches(image_width))
        caption = document.add_paragraph()
        caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
        caption.paragraph_format.keep_with_next = False
        caption_run = caption.add_run(f"图3-{index}  {screenshot['caption']}")
        set_run_font(caption_run, BODY_FONT, 9)
        caption_run.font.color.rgb = MUTED


def add_design_figures(document: Document, figures: list[dict], *, heading_prefix: str) -> None:
    for index, figure in enumerate(figures, start=1):
        path = Path(figure["path"])
        if not path.is_file():
            raise ValueError(f"missing design figure: {path}")
        add_body_text(document, figure.get("description", ""))
        paragraph = document.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.keep_with_next = True
        paragraph.add_run().add_picture(
            str(path), width=Inches(float(figure.get("width_inches", 5.4)))
        )
        caption = document.add_paragraph()
        caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
        caption.paragraph_format.space_after = Pt(6)
        set_run_font(
            caption.add_run(f"图{heading_prefix}-{index}  {figure['title']}"),
            BODY_FONT,
            9,
        )


def set_cell_value(cell, value: str, *, bold: bool = False, size: float = 9.5) -> None:
    cell.text = ""
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    paragraph = cell.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    paragraph.paragraph_format.space_before = Pt(2)
    paragraph.paragraph_format.space_after = Pt(2)
    paragraph.paragraph_format.line_spacing = 1.2
    run = paragraph.add_run(value)
    set_run_font(run, BODY_FONT, size, bold=bold)


def remove_fixed_row_heights(document: Document) -> None:
    for table in document.tables:
        for row in table.rows:
            properties = row._tr.get_or_add_trPr()
            for height in properties.findall(qn("w:trHeight")):
                properties.remove(height)


def style_table(table) -> None:
    properties = table._tbl.tblPr
    borders = properties.find(qn("w:tblBorders"))
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        properties.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = qn(f"w:{edge}")
        border = borders.find(tag)
        if border is None:
            border = OxmlElement(f"w:{edge}")
            borders.append(border)
        border.set(qn("w:val"), "single")
        border.set(qn("w:sz"), "4")
        border.set(qn("w:color"), "7F8C8D")

    margins = properties.find(qn("w:tblCellMar"))
    if margins is None:
        margins = OxmlElement("w:tblCellMar")
        properties.append(margins)
    for side in ("top", "start", "bottom", "end"):
        tag = qn(f"w:{side}")
        margin = margins.find(tag)
        if margin is None:
            margin = OxmlElement(f"w:{side}")
            margins.append(margin)
        margin.set(qn("w:w"), "120")
        margin.set(qn("w:type"), "dxa")

    header_properties = table.rows[0]._tr.get_or_add_trPr()
    repeat = OxmlElement("w:tblHeader")
    repeat.set(qn("w:val"), "true")
    header_properties.append(repeat)
    for cell in table.rows[0].cells:
        shading = cell._tc.get_or_add_tcPr().find(qn("w:shd"))
        if shading is None:
            shading = OxmlElement("w:shd")
            cell._tc.get_or_add_tcPr().append(shading)
        shading.set(qn("w:fill"), "D9E2F3")
    for row_index, row in enumerate(table.rows[1:], start=1):
        if row_index % 2 == 0:
            for cell in row.cells:
                shading = cell._tc.get_or_add_tcPr().find(qn("w:shd"))
                if shading is None:
                    shading = OxmlElement("w:shd")
                    cell._tc.get_or_add_tcPr().append(shading)
                shading.set(qn("w:fill"), "F7F8FA")


def render_registration(draft: dict, output_path: Path, template_path: Path) -> None:
    sections = draft["documents"]["registration-info"]["sections"]
    document = Document(template_path)
    configure_styles(document)
    if len(document.tables) != 1 or len(document.tables[0].rows) < 27:
        raise ValueError("registration template structure changed unexpectedly")
    table = document.tables[0]

    set_cell_value(table.rows[0].cells[2], sections["软件全称"], bold=True)
    set_cell_value(table.rows[1].cells[2], "")
    set_cell_value(table.rows[1].cells[8], sections["版本号"], bold=True)
    set_cell_value(table.rows[2].cells[2], sections["软件作品说明"])
    set_cell_value(table.rows[3].cells[2], sections["软件分类"])
    set_cell_value(table.rows[4].cells[2], "[待补充]")
    set_cell_value(table.rows[5].cells[2], sections["开发完成日期"])
    set_cell_value(table.rows[6].cells[2], "□ 已发表")
    set_cell_value(table.rows[6].cells[5], "[待补充]")
    set_cell_value(table.rows[7].cells[5], "[待补充]")
    set_cell_value(table.rows[8].cells[2], "☑ 未发表")
    set_cell_value(table.rows[8].cells[3], "合成流程测试")
    set_cell_value(table.rows[9].cells[2], sections["开发方式"])

    for row_index in range(11, 15):
        for cell in {id(cell._tc): cell for cell in table.rows[row_index].cells}.values():
            set_cell_value(cell, "")
    set_cell_value(table.rows[11].cells[1], sections["著作权人"])
    set_cell_value(table.rows[11].cells[2], "[待补充]")
    set_cell_value(table.rows[11].cells[4], "[待补充]")
    set_cell_value(table.rows[11].cells[7], "")

    field_rows = [
        (15, "开发硬件环境"),
        (16, "运行硬件环境"),
        (17, "开发操作系统"),
        (18, "开发环境和工具"),
        (19, "运行平台和操作系统"),
        (20, "运行支撑环境和支持软件"),
        (21, "编程语言"),
        (22, "源程序量"),
        (23, "开发目的"),
        (24, "面向领域和行业"),
        (25, "软件主要功能"),
        (26, "软件技术特点"),
    ]
    for row_index, section_name in field_rows:
        set_cell_value(table.rows[row_index].cells[2], sections[section_name])

    remove_fixed_row_heights(document)
    for paragraph in document.paragraphs:
        for run in paragraph.runs:
            set_run_font(run, BODY_FONT, 10.5, bold=run.bold is True)
    properties = document.core_properties
    properties.title = f"{sections['软件全称']} {sections['版本号']} 登记信息采集表"
    properties.subject = "应用软件著作权登记信息合成测试材料"
    properties.author = ""
    properties.last_modified_by = ""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(output_path)


def render_operation_manual(draft: dict, output_path: Path, template_path: Path) -> None:
    sections = draft["documents"]["operation-manual"]["sections"]
    identity = sections["软件名称与版本"]
    screenshots = draft.get("artifacts", {}).get("screenshots", [])
    if not screenshots:
        raise ValueError("operation manual requires actual screenshots")

    document = Document(template_path)
    clear_body(document)
    configure_styles(document)
    configure_header_footer(document, identity)
    add_cover(document, identity, "用户操作说明书")
    toc_entries = [
        (1, "1 引言", 3),
        (2, "1.1 编写目的", 3),
        (1, "2 软件概述", 3),
        (2, "2.1 软件功能与定位", 3),
        (2, "2.2 运行环境", 3),
        (2, "2.3 系统要求", 3),
        (1, "3 系统使用", 3),
        (2, "3.1 功能结构", 3),
        (2, "3.2 操作流程", 4),
        (2, "3.3 功能模块操作", 4),
        (2, "3.4 界面截图及说明", 4),
    ]
    toc_entries.extend(
        (3, f"3.4.{index} {screenshot['title']}", min(4 + index, 8))
        for index, screenshot in enumerate(screenshots, start=1)
    )
    add_toc(document, toc_entries)
    document.add_heading("1 引言", level=1)
    add_numbered_section(document, "1.1", "编写目的", sections["编写目的"], level=2)
    document.add_heading("2 软件概述", level=1)
    add_numbered_section(document, "2.1", "软件功能与定位", sections["软件概述"], level=2)
    add_numbered_section(document, "2.2", "运行环境", sections["运行环境"], level=2)
    add_numbered_section(document, "2.3", "系统要求", sections["系统要求"], level=2)
    document.add_heading("3 系统使用", level=1)
    add_numbered_section(document, "3.1", "功能结构", sections["功能结构"], level=2)
    add_numbered_section(document, "3.2", "操作流程", sections["操作流程"], level=2)
    add_numbered_section(document, "3.3", "功能模块操作", sections["功能模块操作"], level=2)
    add_screenshot_section(document, screenshots)

    properties = document.core_properties
    properties.title = f"{identity} 用户操作说明书"
    properties.subject = "应用软件著作权操作说明书合成测试材料"
    properties.author = ""
    properties.last_modified_by = ""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(output_path)


def add_architecture_table(document: Document, layers: list[dict]) -> None:
    if not layers:
        return
    document.add_heading("2.1.1 架构分层视图", level=3)
    table = document.add_table(rows=1, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table.columns[0].width = Inches(1.35)
    table.columns[1].width = Inches(4.2)
    headers = table.rows[0].cells
    set_cell_value(headers[0], "层级", bold=True)
    set_cell_value(headers[1], "职责与实现", bold=True)
    for layer in layers:
        cells = table.add_row().cells
        set_cell_value(cells[0], layer["name"], bold=True)
        set_cell_value(cells[1], layer["description"])
    style_table(table)


def add_data_table(document: Document, fields: list[dict]) -> None:
    if not fields:
        return
    document.add_page_break()
    document.add_heading("3.2.1 核心数据结构", level=3)
    table = document.add_table(rows=1, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    widths = (1.4, 1.2, 3.0)
    for cell, text, width in zip(
        table.rows[0].cells,
        ("字段", "类型", "含义"),
        widths,
        strict=True,
    ):
        cell.width = Inches(width)
        set_cell_value(cell, text, bold=True)
    for field in fields:
        cells = table.add_row().cells
        for cell, key in zip(cells, ("name", "type", "description"), strict=True):
            set_cell_value(cell, field[key])
    style_table(table)


def render_detailed_design(draft: dict, output_path: Path, template_path: Path) -> None:
    sections = draft["documents"]["detailed-design"]["sections"]
    identity = sections["软件名称与版本"]
    artifacts = draft.get("artifacts", {})
    document = Document(template_path)
    clear_body(document)
    configure_styles(document)
    configure_header_footer(document, identity)
    add_cover(document, identity, "软件详细设计说明书")
    add_toc(
        document,
        [
            (1, "1 引言", 3),
            (2, "1.1 编写目的", 3),
            (2, "1.2 项目背景", 3),
            (1, "2 总体设计", 3),
            (2, "2.1 总体架构", 3),
            (3, "2.1.1 架构分层视图", 3),
            (2, "2.2 软件模块设计", 4),
            (1, "3 功能与数据设计", 4),
            (2, "3.1 功能设计和描述", 4),
            (2, "3.2 数据设计", 4),
            (3, "3.2.1 核心数据结构", 5),
            (1, "4 接口与处理流程", 5),
            (2, "4.1 接口设计", 5),
            (2, "4.2 运行流程", 5),
            (2, "4.3 算法说明", 7),
            (1, "5 异常与限制", 7),
            (2, "5.1 异常处理", 7),
            (2, "5.2 条件与限制", 8),
        ],
    )
    document.add_heading("1 引言", level=1)
    add_numbered_section(document, "1.1", "编写目的", sections["编写目的"], level=2)
    add_numbered_section(document, "1.2", "项目背景", sections["项目背景"], level=2)
    document.add_heading("2 总体设计", level=1)
    add_numbered_section(document, "2.1", "总体架构", sections["总体架构"], level=2)
    add_architecture_table(document, artifacts.get("architecture_layers", []))
    add_design_figures(document, artifacts.get("design_figures", [])[:1], heading_prefix="2")
    add_numbered_section(document, "2.2", "软件模块设计", sections["软件模块设计"], level=2)
    document.add_heading("3 功能与数据设计", level=1)
    add_numbered_section(document, "3.1", "功能设计和描述", sections["功能设计和描述"], level=2)
    add_numbered_section(document, "3.2", "数据设计", sections["数据设计"], level=2)
    add_data_table(document, artifacts.get("data_fields", []))
    document.add_heading("4 接口与处理流程", level=1)
    add_numbered_section(document, "4.1", "接口设计", sections["接口设计"], level=2)
    add_numbered_section(document, "4.2", "运行流程", sections["运行流程"], level=2)
    add_design_figures(document, artifacts.get("design_figures", [])[1:], heading_prefix="4")
    add_numbered_section(document, "4.3", "算法说明", sections["算法说明"], level=2)
    document.add_heading("5 异常与限制", level=1)
    add_numbered_section(document, "5.1", "异常处理", sections["异常处理"], level=2)
    add_numbered_section(document, "5.2", "条件与限制", sections["条件与限制"], level=2)

    properties = document.core_properties
    properties.title = f"{identity} 软件详细设计说明书"
    properties.subject = "应用软件著作权详细设计说明书合成测试材料"
    properties.author = ""
    properties.last_modified_by = ""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(output_path)


def code_paragraph(document: Document, text: str, *, file_heading: bool = False) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    paragraph.paragraph_format.line_spacing = Pt(9.6)
    paragraph.paragraph_format.keep_together = True
    run = paragraph.add_run(text if text else " ")
    set_run_font(run, CODE_FONT if not file_heading else BODY_FONT, 7.4, bold=file_heading)
    if file_heading:
        run.font.color.rgb = ACCENT


def render_source_code(draft: dict, output_path: Path, template_path: Path) -> None:
    sections = draft["documents"]["source-code"]["sections"]
    identity = sections["软件名称与版本"]
    expected_count = int(sections["源程序总行数"])
    source_lines = sections["源程序正文"].splitlines()
    actual_source_lines = [line for line in source_lines if not line.startswith("===== FILE:")]
    if len(actual_source_lines) != expected_count:
        raise ValueError(
            f"source body line count {len(actual_source_lines)} does not match declared {expected_count}"
        )

    document = Document(template_path)
    clear_body(document)
    configure_styles(document)
    section = document.sections[0]
    section.different_first_page_header_footer = False
    clear_container(section.header)
    header = section.header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.CENTER
    header_run = header.add_run(
        f"{identity}｜{sections['编程语言']}｜源程序共 {expected_count} 行"
    )
    set_run_font(header_run, BODY_FONT, 8.5, bold=True)
    clear_container(section.footer)
    add_page_number(section.footer.paragraphs[0])

    lines_on_page = 0
    for source_line in source_lines:
        file_heading = source_line.startswith("===== FILE:")
        if not file_heading and lines_on_page == 50:
            document.add_page_break()
            lines_on_page = 0
        code_paragraph(document, source_line, file_heading=file_heading)
        if not file_heading:
            lines_on_page += 1

    properties = document.core_properties
    properties.title = f"{identity} 源代码"
    properties.subject = "应用软件著作权源代码合成测试材料"
    properties.author = ""
    properties.last_modified_by = ""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(output_path)


def render_all(draft: dict, output_dir: Path) -> list[Path]:
    validation = validate_draft.validate(draft)
    if not validation["valid"] or not validation["render_ready"]:
        details = "; ".join(validation["errors"]) or "response is not render-ready"
        raise ValueError(details)
    if draft.get("mode") != "software-copyright":
        raise ValueError("render_software_copyright.py accepts software-copyright mode only")

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    configs = {
        item["id"]: item
        for item in manifest["software-copyright"]["output_documents"]
    }
    renderers = {
        "registration-info": render_registration,
        "operation-manual": render_operation_manual,
        "detailed-design": render_detailed_design,
        "source-code": render_source_code,
    }
    output_paths = []
    for document_id, renderer in renderers.items():
        config = configs[document_id]
        output_path = output_dir / config["output_filename"]
        renderer(draft, output_path, ROOT / config["template"])
        output_paths.append(output_path)
    checklist = manifest["software-copyright"].get("supporting_references", [])[0]
    checklist_path = output_dir / checklist["output_filename"]
    shutil.copy2(ROOT / checklist["template"], checklist_path)
    output_paths.append(checklist_path)
    return output_paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft_json", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    draft = json.loads(args.draft_json.read_text(encoding="utf-8"))
    for output_path in render_all(draft, args.output_dir):
        print(f"rendered: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
