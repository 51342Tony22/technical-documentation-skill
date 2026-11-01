#!/usr/bin/env python3
"""Validate an intake-question response or a render-ready structured draft."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "assets" / "template-manifest.json"
VALID_STATUSES = {"needs-information", "draft-ready"}
ALLOWED_EVIDENCE_TYPES = {
    "user-confirmed",
    "artifact",
    "public-source",
    "pending-administrative",
}
RISK_LEVELS = {"high", "medium", "low", "unknown"}
PATENT_FIGURE_TYPES = {
    "flowchart",
    "architecture",
    "module",
    "sequence",
    "data-structure",
    "formula",
    "chart",
    "screenshot",
}
PATENT_BACKGROUND_ROUTES = {"three-part", "integrated"}
PATENT_SOLUTION_ROUTES = {"overall-prose", "stepwise-method", "hybrid"}
PATENT_ENGINEERING_ROUTES = {"omit", "include"}


def result(status: str | None, errors: list[str], warnings: list[str]) -> dict:
    return {
        "valid": not errors,
        "status": status,
        "render_ready": not errors and status == "draft-ready",
        "errors": errors,
        "warnings": warnings,
    }


def validate_string_list(value: object, field: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{field} must be a JSON array")
        return []
    if any(not isinstance(item, str) or not item.strip() for item in value):
        errors.append(f"{field} must contain only non-empty strings")
        return []
    return value


def validate_conflicts(value: object, errors: list[str]) -> list[dict]:
    if not isinstance(value, list):
        errors.append("conflicts must be a JSON array")
        return []
    valid = []
    for index, item in enumerate(value):
        field = f"conflicts[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{field} must be a JSON object")
            continue
        if not isinstance(item.get("field"), str) or not item["field"].strip():
            errors.append(f"{field}.field must be a non-empty string")
        validate_string_list(item.get("evidence_values"), f"{field}.evidence_values", errors)
        if not isinstance(item.get("resolution_required"), str) or not item["resolution_required"].strip():
            errors.append(f"{field}.resolution_required must be a non-empty string")
        valid.append(item)
    return valid


def validate_evidence_map(
    value: object,
    errors: list[str],
    required_targets: set[str] | None = None,
) -> list[dict]:
    if not isinstance(value, list):
        errors.append("evidence_map must be a JSON array")
        return []
    if not value:
        errors.append("draft-ready response requires a non-empty evidence_map")
        return []
    seen_ids = set()
    covered_targets = set()
    valid = []
    for index, item in enumerate(value):
        field = f"evidence_map[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{field} must be a JSON object")
            continue
        fact_id = item.get("fact_id")
        if not isinstance(fact_id, str) or not fact_id.strip():
            errors.append(f"{field}.fact_id must be a non-empty string")
        elif fact_id in seen_ids:
            errors.append(f"duplicate evidence fact_id: {fact_id}")
        else:
            seen_ids.add(fact_id)
        if not isinstance(item.get("statement"), str) or not item["statement"].strip():
            errors.append(f"{field}.statement must be a non-empty string")
        basis_type = item.get("basis_type")
        if basis_type not in ALLOWED_EVIDENCE_TYPES:
            errors.append(
                f"{field}.basis_type must be one of: "
                + ", ".join(sorted(ALLOWED_EVIDENCE_TYPES))
            )
        source_refs = validate_string_list(item.get("source_refs"), f"{field}.source_refs", errors)
        used_in = validate_string_list(item.get("used_in"), f"{field}.used_in", errors)
        if not source_refs:
            errors.append(f"{field}.source_refs requires at least one traceable reference")
        if not used_in:
            errors.append(f"{field}.used_in requires at least one target section")
        if required_targets is not None:
            unknown_targets = sorted(set(used_in) - required_targets)
            if unknown_targets:
                errors.append(
                    f"{field}.used_in contains unknown document sections: "
                    + ", ".join(unknown_targets)
                )
            covered_targets.update(set(used_in) & required_targets)
        valid.append(item)
    if required_targets is not None:
        missing_targets = sorted(required_targets - covered_targets)
        if missing_targets:
            errors.append(
                "evidence_map does not cover required document sections: "
                + ", ".join(missing_targets)
            )
    return valid


def positive_integer(value: object, field: str, errors: list[str]) -> int | None:
    if isinstance(value, bool):
        errors.append(f"{field} must be a positive integer")
        return None
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        errors.append(f"{field} must be a positive integer")
        return None
    if str(value).strip() != str(parsed) or parsed <= 0:
        errors.append(f"{field} must be a positive integer")
        return None
    return parsed


def validate_patent_profile(value: object, errors: list[str], warnings: list[str]) -> None:
    if value is None:
        warnings.append(
            "technical-disclosure.disclosure_profile is missing; renderer will use the V1.2 compatibility layout"
        )
        return
    if not isinstance(value, dict):
        errors.append("technical-disclosure.disclosure_profile must be a JSON object")
        return

    field = value.get("所属技术领域")
    if not isinstance(field, str) or not field.strip():
        errors.append("disclosure_profile.所属技术领域 must be a non-empty string")

    writing_route = value.get("写作路由")
    background_route = None
    solution_route = None
    engineering_route = None
    if writing_route is not None:
        if not isinstance(writing_route, dict):
            errors.append("disclosure_profile.写作路由 must be a JSON object")
        else:
            background_route = writing_route.get("背景组织")
            solution_route = writing_route.get("技术方案组织")
            engineering_route = writing_route.get("工程实现证据")
            if background_route not in PATENT_BACKGROUND_ROUTES:
                errors.append("disclosure_profile.写作路由.背景组织 must be three-part or integrated")
            if solution_route not in PATENT_SOLUTION_ROUTES:
                errors.append(
                    "disclosure_profile.写作路由.技术方案组织 must be overall-prose, stepwise-method, or hybrid"
                )
            if engineering_route not in PATENT_ENGINEERING_ROUTES:
                errors.append("disclosure_profile.写作路由.工程实现证据 must be omit or include")

    background = value.get("背景技术")
    if not isinstance(background, dict):
        errors.append("disclosure_profile.背景技术 must be a JSON object")
    else:
        if background_route == "three-part":
            required_background = ("技术背景", "最接近的现有技术", "现有技术的缺陷和不足")
        elif background_route == "integrated":
            required_background = ("现有技术状况描述与评价", "现有技术存在的问题和缺点")
        else:
            required_background = ("现有技术状况描述与评价", "现有技术存在的问题和缺点", "发明形成过程")
        for name in required_background:
            if not isinstance(background.get(name), str) or not background[name].strip():
                errors.append(f"disclosure_profile.背景技术.{name} must be non-empty")
        formation = background.get("发明形成过程")
        if formation is not None and (not isinstance(formation, str) or not formation.strip()):
            errors.append("disclosure_profile.背景技术.发明形成过程 must be omitted or non-empty")

    invention = value.get("发明内容")
    if not isinstance(invention, dict):
        errors.append("disclosure_profile.发明内容 must be a JSON object")
    else:
        required_invention = ["要解决的技术问题"]
        if writing_route is not None:
            required_invention.append("总体技术方案")
        elif "总体技术方案" not in invention:
            required_invention.append("总体技术效果")
        for name in required_invention:
            if not isinstance(invention.get(name), str) or not invention[name].strip():
                errors.append(f"disclosure_profile.发明内容.{name} must be non-empty")
        key_points = invention.get("关键点及对应技术效果")
        if not isinstance(key_points, list) or not key_points:
            errors.append("disclosure_profile.发明内容.关键点及对应技术效果 requires at least one item")
        else:
            if len(key_points) < 3:
                warnings.append("long-form patent profile has fewer than three key technical points")
            for index, item in enumerate(key_points):
                prefix = f"disclosure_profile.发明内容.关键点及对应技术效果[{index}]"
                if not isinstance(item, dict):
                    errors.append(f"{prefix} must be a JSON object")
                    continue
                for name in ("关键点", "技术效果"):
                    if not isinstance(item.get(name), str) or not item[name].strip():
                        errors.append(f"{prefix}.{name} must be non-empty")
                validate_string_list(item.get("evidence_refs"), f"{prefix}.evidence_refs", errors)
        advantages = invention.get("本发明创造的优点")
        if writing_route is not None:
            valid_advantages = validate_string_list(
                advantages, "disclosure_profile.发明内容.本发明创造的优点", errors
            )
            if len(valid_advantages) < 4:
                errors.append("disclosure_profile.发明内容.本发明创造的优点 requires at least four separate items")
            if len(set(item.strip() for item in valid_advantages)) != len(valid_advantages):
                errors.append("disclosure_profile.发明内容.本发明创造的优点 must not contain duplicate items")
        elif advantages is not None:
            validate_string_list(advantages, "disclosure_profile.发明内容.本发明创造的优点", errors)

    implementations = value.get("具体实施方式")
    if not isinstance(implementations, list) or not implementations:
        errors.append("disclosure_profile.具体实施方式 requires at least one subsection")
    else:
        if len(implementations) < 4:
            warnings.append("long-form patent profile has fewer than four implementation subsections")
        for index, item in enumerate(implementations):
            prefix = f"disclosure_profile.具体实施方式[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{prefix} must be a JSON object")
                continue
            for name in ("标题", "正文"):
                if not isinstance(item.get(name), str) or not item[name].strip():
                    errors.append(f"{prefix}.{name} must be non-empty")
            validate_string_list(item.get("步骤", []), f"{prefix}.步骤", errors)
        if solution_route in {"stepwise-method", "hybrid"}:
            all_steps = [
                step
                for item in implementations
                if isinstance(item, dict)
                for step in item.get("步骤", [])
                if isinstance(step, str)
            ]
            if not any(step.strip().startswith("S1") for step in all_steps):
                errors.append(
                    f"disclosure_profile.具体实施方式 requires an S1-Sn sequence for {solution_route}"
                )

    tables = value.get("表格")
    if not isinstance(tables, list):
        errors.append("disclosure_profile.表格 must be a JSON array")
    else:
        for index, item in enumerate(tables):
            prefix = f"disclosure_profile.表格[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{prefix} must be a JSON object")
                continue
            headers = validate_string_list(item.get("表头"), f"{prefix}.表头", errors)
            rows = item.get("数据行")
            if not isinstance(rows, list) or not rows:
                errors.append(f"{prefix}.数据行 requires at least one row")
            elif headers and any(not isinstance(row, list) or len(row) != len(headers) for row in rows):
                errors.append(f"{prefix}.数据行 width must match 表头")
            validate_string_list(item.get("evidence_refs"), f"{prefix}.evidence_refs", errors)
            priority = item.get("优先级")
            if priority is not None and priority not in {"high", "normal", "low"}:
                errors.append(f"{prefix}.优先级 must be high, normal, or low")
            purpose = item.get("用途")
            if purpose == "experimental-result":
                if item.get("优先级") != "high":
                    errors.append(f"{prefix} experimental-result requires 优先级=high")
                if not isinstance(item.get("关联小节"), str) or not item["关联小节"].strip():
                    errors.append(f"{prefix} experimental-result requires 关联小节")

    figures = value.get("附图")
    if not isinstance(figures, list):
        errors.append("disclosure_profile.附图 must be a JSON array")
    else:
        if len(figures) < 4:
            warnings.append("long-form patent profile has fewer than four proposed figures")
        for index, item in enumerate(figures):
            prefix = f"disclosure_profile.附图[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{prefix} must be a JSON object")
                continue
            for name in ("图号", "标题", "说明", "关联小节"):
                if not isinstance(item.get(name), str) or not item[name].strip():
                    errors.append(f"{prefix}.{name} must be non-empty")
            if item.get("类型") not in PATENT_FIGURE_TYPES:
                errors.append(
                    f"{prefix}.类型 must be one of: " + ", ".join(sorted(PATENT_FIGURE_TYPES))
                )
            evidence_class = item.get("evidence_class")
            if evidence_class is not None and evidence_class not in {
                "generated-technical-figure",
                "actual-runtime-screenshot",
                "conceptual-non-evidence",
            }:
                errors.append(f"{prefix}.evidence_class is unsupported")
            if item.get("类型") == "screenshot" and evidence_class != "actual-runtime-screenshot":
                errors.append(f"{prefix} screenshot requires evidence_class=actual-runtime-screenshot")
            if item.get("类型") == "chart":
                if item.get("生成器") != "altair":
                    errors.append(f"{prefix} chart requires 生成器=altair")
                chart_spec = item.get("chart_spec")
                if not isinstance(chart_spec, dict):
                    errors.append(f"{prefix}.chart_spec must be a JSON object")
                else:
                    data = chart_spec.get("data")
                    if not isinstance(data, dict) or not isinstance(data.get("values"), list) or not data["values"]:
                        errors.append(f"{prefix}.chart_spec.data.values requires a non-empty array")
                    if isinstance(data, dict) and "url" in data:
                        errors.append(f"{prefix}.chart_spec.data must not use an external URL")
                    if not chart_spec.get("mark"):
                        errors.append(f"{prefix}.chart_spec.mark is required")
                    if not isinstance(chart_spec.get("encoding"), dict) or not chart_spec["encoding"]:
                        errors.append(f"{prefix}.chart_spec.encoding requires a non-empty object")
                refs = validate_string_list(item.get("evidence_refs"), f"{prefix}.evidence_refs", errors)
                if not refs:
                    errors.append(f"{prefix} chart requires evidence_refs")
                if item.get("用途") == "experimental-result" and item.get("优先级") != "high":
                    errors.append(f"{prefix} experimental-result chart requires 优先级=high")
            if evidence_class and not isinstance(item.get("artifact_id"), str):
                errors.append(f"{prefix}.artifact_id is required when evidence_class is set")
            layout = item.get("排版")
            if layout is not None:
                if not isinstance(layout, dict):
                    errors.append(f"{prefix}.排版 must be a JSON object")
                else:
                    if layout.get("宽度", "full") not in {"full", "medium", "compact"}:
                        errors.append(f"{prefix}.排版.宽度 must be full, medium, or compact")
                    if not isinstance(layout.get("前置分页", False), bool):
                        errors.append(f"{prefix}.排版.前置分页 must be a Boolean")
            diagram = item.get("diagram")
            if diagram is not None:
                if not isinstance(diagram, dict):
                    errors.append(f"{prefix}.diagram must be a JSON object")
                else:
                    if diagram.get("direction") not in {"horizontal", "vertical", "grid"}:
                        errors.append(f"{prefix}.diagram.direction must be horizontal, vertical, or grid")
                    nodes = validate_string_list(diagram.get("nodes"), f"{prefix}.diagram.nodes", errors)
                    if len(nodes) < 2:
                        errors.append(f"{prefix}.diagram.nodes requires at least two nodes")
                    edges = diagram.get("edges", [])
                    if not isinstance(edges, list):
                        errors.append(f"{prefix}.diagram.edges must be a JSON array")
                    else:
                        for edge_index, edge in enumerate(edges):
                            if not isinstance(edge, list) or len(edge) != 3:
                                errors.append(
                                    f"{prefix}.diagram.edges[{edge_index}] must be [from, to, label]"
                                )

    engineering = value.get("工程实现证据")
    if engineering_route == "include" and engineering is None:
        errors.append("disclosure_profile.工程实现证据 is required by the include route")
    if engineering_route == "omit" and engineering is not None:
        errors.append("disclosure_profile.工程实现证据 must be omitted by the omit route")
    if engineering is not None:
        if not isinstance(engineering, dict):
            errors.append("disclosure_profile.工程实现证据 must be a JSON object")
        else:
            for name in ("代码资产", "接口契约", "端到端工作流"):
                entries = engineering.get(name)
                if not isinstance(entries, list) or not entries:
                    errors.append(f"disclosure_profile.工程实现证据.{name} requires a non-empty array")
            preflight = engineering.get("资产预检")
            if not isinstance(preflight, dict) or preflight.get("状态") != "passed":
                errors.append("disclosure_profile.工程实现证据.资产预检.状态 must be passed")
            elif preflight.get("密钥扫描") != "passed":
                errors.append("disclosure_profile.工程实现证据.资产预检.密钥扫描 must be passed")

    appendix = value.get("检索附件")
    if not isinstance(appendix, dict):
        errors.append("disclosure_profile.检索附件 must be a JSON object")
    else:
        for name in ("检索日期", "最接近记录对比", "检索局限"):
            if not isinstance(appendix.get(name), str) or not appendix[name].strip():
                errors.append(f"disclosure_profile.检索附件.{name} must be non-empty")
        for name in ("检索数据库", "检索式", "保留记录"):
            validate_string_list(appendix.get(name), f"disclosure_profile.检索附件.{name}", errors)


def validate(draft: dict) -> dict:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    errors = []
    warnings = []
    mode = draft.get("mode")
    status = draft.get("status")

    if mode not in manifest:
        errors.append("mode must be 'patent' or 'software-copyright'")
        return result(status, errors, warnings)

    if status is None:
        status = "draft-ready"
        warnings.append("status is missing; interpreted as 'draft-ready' for compatibility")
    elif status not in VALID_STATUSES:
        errors.append("status must be 'needs-information' or 'draft-ready'")
        return result(status, errors, warnings)

    if status == "needs-information":
        if "documents" in draft:
            errors.append("needs-information response must not include documents")
        missing_facts = validate_string_list(
            draft.get("missing_facts"), "missing_facts", errors
        )
        validate_string_list(draft.get("known_facts", []), "known_facts", errors)
        questions = validate_string_list(draft.get("questions"), "questions", errors)
        conflicts = validate_conflicts(draft.get("conflicts"), errors)
        if not missing_facts:
            if not conflicts:
                errors.append(
                    "needs-information response requires at least one missing fact or conflict"
                )
        if not questions:
            errors.append("needs-information response requires at least one question")
        question_limit = 5 if mode == "patent" else 6
        if len(questions) > question_limit:
            errors.append(
                f"{mode} needs-information response allows at most {question_limit} questions"
            )
        if mode == "software-copyright" and draft.get("software_type") != "application":
            errors.append("software-copyright mode requires software_type 'application'")
        return result(status, errors, warnings)

    documents = draft.get("documents")
    if not isinstance(documents, dict):
        errors.append("documents must be a JSON object")
        documents = {}

    expected_ids = {item["id"] for item in manifest[mode]["output_documents"]}
    other_mode = "software-copyright" if mode == "patent" else "patent"
    foreign_ids = {item["id"] for item in manifest[other_mode]["output_documents"]}

    for document_config in manifest[mode]["output_documents"]:
        document_id = document_config["id"]
        document = documents.get(document_id)
        if not isinstance(document, dict):
            errors.append(f"missing required document: {document_id}")
            continue

        sections = document.get("sections")
        if not isinstance(sections, dict):
            errors.append(f"{document_id}.sections must be a JSON object")
            continue

        for name in document_config["required_sections"]:
            value = sections.get(name)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{document_id}: missing or empty required section: {name}")

    unexpected = sorted(set(documents) - expected_ids)
    if unexpected:
        warnings.append("unexpected document IDs: " + ", ".join(unexpected))

    mixed = sorted(set(documents) & foreign_ids)
    if mixed:
        warnings.append("possible cross-mode documents: " + ", ".join(mixed))

    conflicts = validate_conflicts(draft.get("conflicts"), errors)
    if conflicts:
        errors.append("draft-ready response must resolve all conflicts before rendering")
    required_targets = {
        f"{item['id']}.{section}"
        for item in manifest[mode]["output_documents"]
        for section in item["required_sections"]
    }
    validate_evidence_map(draft.get("evidence_map"), errors, required_targets)

    if mode == "software-copyright":
        if draft.get("software_type") != "application":
            warnings.append("software_type is not 'application'; confirm the four-document policy")
        registration = documents.get("registration-info", {})
        registration_sections = registration.get("sections", {}) if isinstance(registration, dict) else {}
        source_document = documents.get("source-code", {})
        source_sections = source_document.get("sections", {}) if isinstance(source_document, dict) else {}
        registration_count = positive_integer(
            registration_sections.get("源程序量") if isinstance(registration_sections, dict) else None,
            "registration-info.源程序量",
            errors,
        )
        submitted_section_count = positive_integer(
            source_sections.get("源程序总行数") if isinstance(source_sections, dict) else None,
            "source-code.源程序总行数",
            errors,
        )

        selection = draft.get("source_selection")
        if not isinstance(selection, dict):
            errors.append("software draft-ready response requires source_selection")
            selection = {}
        project_count = positive_integer(
            selection.get("project_qualifying_line_count"),
            "source_selection.project_qualifying_line_count",
            errors,
        )
        submitted_count = positive_integer(
            selection.get("submitted_source_line_count"),
            "source_selection.submitted_source_line_count",
            errors,
        )
        strategy = selection.get("selection_strategy")
        if strategy not in {"all-qualifying-source", "first-last-continuous", "custom-confirmed"}:
            errors.append(
                "source_selection.selection_strategy must be all-qualifying-source, "
                "first-last-continuous, or custom-confirmed"
            )
        selected_files = validate_string_list(
            selection.get("selected_files"), "source_selection.selected_files", errors
        )
        if not selected_files:
            errors.append("source_selection.selected_files requires at least one file")
        excluded_files = selection.get("excluded_files")
        if not isinstance(excluded_files, list):
            errors.append("source_selection.excluded_files must be a JSON array")
        else:
            for index, item in enumerate(excluded_files):
                if not isinstance(item, dict):
                    errors.append(f"source_selection.excluded_files[{index}] must be an object")
                    continue
                for key in ("path", "reason"):
                    if not isinstance(item.get(key), str) or not item[key].strip():
                        errors.append(
                            f"source_selection.excluded_files[{index}].{key} must be non-empty"
                        )

        if project_count is not None and registration_count is not None and project_count != registration_count:
            errors.append("registration-info.源程序量 must equal project_qualifying_line_count")
        if submitted_count is not None and submitted_section_count is not None and submitted_count != submitted_section_count:
            errors.append("source-code.源程序总行数 must equal submitted_source_line_count")
        if project_count is not None and submitted_count is not None:
            if submitted_count > project_count:
                errors.append("submitted source line count cannot exceed project qualifying line count")
            target = min(3000, project_count)
            if submitted_count < target:
                warnings.append(
                    f"submitted source contains {submitted_count} lines; supplied package target is {target}"
                )
            if project_count < 3000:
                warnings.append(
                    "project qualifying source line count is below the supplied package's 3000-line target"
                )

        source_body = source_sections.get("源程序正文") if isinstance(source_sections, dict) else None
        if isinstance(source_body, str):
            body_lines = [
                line for line in source_body.splitlines()
                if not line.startswith("===== FILE:")
            ]
            if submitted_count is not None and len(body_lines) != submitted_count:
                errors.append(
                    f"source-code.源程序正文 contains {len(body_lines)} source lines; "
                    f"expected {submitted_count}"
                )
            heading_paths = []
            for line in source_body.splitlines():
                if line.startswith("===== FILE:") and line.endswith("====="):
                    heading_paths.append(line[len("===== FILE:"): -len("=====")].strip())
            if not heading_paths:
                errors.append("source-code.源程序正文 requires traceable FILE headings")
            elif selected_files and heading_paths != selected_files:
                errors.append("source-code FILE headings must match source_selection.selected_files order")

        preflight = draft.get("artifact_preflight")
        if not isinstance(preflight, dict):
            errors.append("software draft-ready response requires artifact_preflight")
        else:
            for field in (
                "screenshots_verified_actual",
                "screenshot_framing_verified",
                "source_inventory_verified",
                "third_party_exclusions_reviewed",
            ):
                if preflight.get(field) is not True:
                    errors.append(f"artifact_preflight.{field} must be true")
            if preflight.get("secrets_scan_status") not in {"passed", "redacted"}:
                errors.append(
                    "artifact_preflight.secrets_scan_status must be passed or redacted"
                )
            validate_string_list(preflight.get("notes", []), "artifact_preflight.notes", errors)
    else:
        disclosure = documents.get("technical-disclosure", {})
        disclosure_sections = disclosure.get("sections", {}) if isinstance(disclosure, dict) else {}
        validate_patent_profile(
            disclosure.get("disclosure_profile") if isinstance(disclosure, dict) else None,
            errors,
            warnings,
        )
        prohibited = {"权利要求书", "说明书摘要", "专利摘要", "独立权利要求", "从属权利要求"}
        present = sorted(prohibited & set(disclosure_sections)) if isinstance(disclosure_sections, dict) else []
        if present:
            errors.append(
                "patent mode is limited to the technical disclosure; remove final-application sections: "
                + ", ".join(present)
            )

        assessment = draft.get("risk_assessment")
        if not isinstance(assessment, dict):
            errors.append("patent draft-ready response requires risk_assessment")
        else:
            closest = assessment.get("closest_single_reference")
            if not isinstance(closest, str) or not closest.strip():
                errors.append("risk_assessment.closest_single_reference must be non-empty")
            for field in ("single_reference_risk", "combination_risk"):
                if assessment.get(field) not in RISK_LEVELS:
                    errors.append(
                        f"risk_assessment.{field} must be one of: "
                        + ", ".join(sorted(RISK_LEVELS))
                    )
            if not isinstance(assessment.get("reasoning"), str) or not assessment["reasoning"].strip():
                errors.append("risk_assessment.reasoning must be non-empty")
            validate_string_list(
                assessment.get("unresolved_questions", []),
                "risk_assessment.unresolved_questions",
                errors,
            )

    sources = draft.get("sources", [])
    if not isinstance(sources, list):
        errors.append("sources must be a JSON array")
    elif not sources:
        warnings.append("no traceable source identifiers were recorded")
    elif mode == "patent" and isinstance(draft.get("risk_assessment"), dict):
        closest = draft["risk_assessment"].get("closest_single_reference")
        if closest != "none-captured" and closest not in sources:
            errors.append("risk_assessment.closest_single_reference must appear in sources")

    limitations = draft.get("limitations", [])
    if not isinstance(limitations, list) or not limitations:
        warnings.append("add a preliminary-search and professional-review limitation")

    return result(status, errors, warnings)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft_json", type=Path)
    parser.add_argument("--json", action="store_true", help="Print JSON result")
    args = parser.parse_args()

    draft = json.loads(args.draft_json.read_text(encoding="utf-8"))
    result = validate(draft)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if result["valid"] and result["render_ready"]:
            print("draft: valid and ready to render")
        elif result["valid"]:
            print("intake response: valid; more information required")
        else:
            print("drafting response: invalid")
        for error in result["errors"]:
            print(f"ERROR: {error}")
        for warning in result["warnings"]:
            print(f"WARNING: {warning}")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
