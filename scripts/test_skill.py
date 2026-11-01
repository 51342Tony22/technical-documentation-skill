#!/usr/bin/env python3
"""Run lightweight tests for the deterministic shell scripts."""

from __future__ import annotations

import base64
import json
import re
import tempfile
import unittest
import zipfile
from pathlib import Path

import analyze_public_records
import check_setup
import package_deliverables
import preflight_software_artifacts
import preflight_patent_artifacts
import prior_art_report
import render_patent_disclosure
import render_software_copyright
import scan_delivery_secrets
import search_public_records
import validate_draft
import validate_prior_art


def complete_documents(mode: str) -> dict:
    manifest = json.loads(
        validate_draft.MANIFEST_PATH.read_text(encoding="utf-8")
    )
    documents = {
        item["id"]: {
            "sections": {section: "content" for section in item["required_sections"]}
        }
        for item in manifest[mode]["output_documents"]
    }
    if mode == "software-copyright":
        documents["registration-info"]["sections"]["源程序量"] = "1"
        documents["source-code"]["sections"].update(
            {
                "源程序总行数": "1",
                "源程序正文": "===== FILE: app/test.js =====\nconst value = 1;",
            }
        )
    return documents


def ready_contract(mode: str, *, project_lines: int = 1, submitted_lines: int = 1) -> dict:
    manifest = json.loads(
        validate_draft.MANIFEST_PATH.read_text(encoding="utf-8")
    )
    evidence_targets = [
        f"{item['id']}.{section}"
        for item in manifest[mode]["output_documents"]
        for section in item["required_sections"]
    ]
    common = {
        "evidence_map": [
            {
                "fact_id": "F-001",
                "statement": "confirmed test fact",
                "basis_type": "user-confirmed",
                "source_refs": ["case_json.known_features[0]"],
                "used_in": evidence_targets,
            }
        ],
        "conflicts": [],
    }
    if mode == "patent":
        common["risk_assessment"] = {
            "closest_single_reference": "DEMO-1",
            "single_reference_risk": "medium",
            "combination_risk": "high",
            "reasoning": "The captured records overlap with part of the solution.",
            "unresolved_questions": [],
        }
    else:
        common["source_selection"] = {
            "project_qualifying_line_count": project_lines,
            "submitted_source_line_count": submitted_lines,
            "selection_strategy": (
                "all-qualifying-source"
                if project_lines == submitted_lines
                else "custom-confirmed"
            ),
            "selected_files": ["app/test.js"],
            "excluded_files": [],
        }
        common["artifact_preflight"] = {
            "screenshots_verified_actual": True,
            "screenshot_framing_verified": True,
            "source_inventory_verified": True,
            "secrets_scan_status": "passed",
            "third_party_exclusions_reviewed": True,
            "notes": [],
        }
    return common


def routed_patent_profile(*, engineering_route: str = "omit") -> dict:
    return {
        "写作路由": {
            "背景组织": "three-part",
            "技术方案组织": "overall-prose",
            "工程实现证据": engineering_route,
        },
        "所属技术领域": "本方案属于测试控制技术领域。",
        "背景技术": {
            "技术背景": "测试设备需要执行稳定的控制。",
            "最接近的现有技术": "现有方案采用单一控制器执行固定控制。",
            "现有技术的缺陷和不足": "固定控制不能适应状态变化。",
        },
        "发明内容": {
            "要解决的技术问题": "解决状态变化下的控制适配问题。",
            "总体技术方案": "系统包括采集模块、判断模块和执行模块，三者依次传递状态数据与控制结果。",
            "关键点及对应技术效果": [
                {"关键点": "采集状态", "技术效果": "获得控制依据", "evidence_refs": ["F-001"]},
                {"关键点": "判断状态", "技术效果": "区分控制条件", "evidence_refs": ["F-001"]},
                {"关键点": "执行控制", "技术效果": "输出对应动作", "evidence_refs": ["F-001"]},
            ],
            "本发明创造的优点": [
                "通过状态采集形成可核对的控制输入。",
                "通过条件判断区分不同运行状态。",
                "通过对应执行避免固定控制造成的失配。",
                "通过模块间的确定关系使控制过程能够复现。",
            ],
        },
        "具体实施方式": [
            {"标题": "总体结构", "正文": "采集模块连接判断模块，判断模块连接执行模块。", "步骤": []},
            {"标题": "采集模块", "正文": "采集模块输出状态数据。", "步骤": []},
            {"标题": "判断模块", "正文": "判断模块依据状态数据形成条件结果。", "步骤": []},
            {"标题": "实施例", "正文": "执行模块依据条件结果输出控制动作。", "步骤": []},
        ],
        "表格": [],
        "附图": [],
        "检索附件": {
            "检索日期": "2026-08-27",
            "检索数据库": [],
            "检索式": [],
            "保留记录": [],
            "最接近记录对比": "未检出可核对记录。",
            "检索局限": "本次仅用于结构回归测试。",
        },
    }


class SkillShellTests(unittest.TestCase):
    def test_prompts_and_templates_are_ready(self) -> None:
        result = check_setup.inspect_setup()
        self.assertTrue(result["ready"])
        for details in result["modes"].values():
            self.assertTrue(details["prompt_ready"])
            self.assertEqual(details["prompt_contract_errors"], [])
            self.assertTrue(details["templates_ready"])

    def test_prompt_contract_covers_every_document_and_section(self) -> None:
        manifest = json.loads(check_setup.MANIFEST_PATH.read_text(encoding="utf-8"))
        benchmark = (check_setup.ROOT / "references" / "reference-style-benchmark.md").read_text(encoding="utf-8")
        self.assertIn("专利内容骨架", benchmark)
        self.assertIn("软著内容骨架", benchmark)
        self.assertIn("截图主体必须完整、居中、可读", benchmark)
        for mode, config in manifest.items():
            with self.subTest(mode=mode):
                prompt = (check_setup.ROOT / config["prompt"]).read_text(encoding="utf-8")
                self.assertIn("PROMPT_STATUS: READY_FOR_TESTING", prompt)
                expected_version = (
                    "PROMPT_VERSION: 1.8.2"
                    if mode == "patent"
                    else "PROMPT_VERSION: 1.5.0"
                )
                self.assertIn(expected_version, prompt)
                self.assertNotIn("PROMPT_STATUS: PLACEHOLDER", prompt)
                self.assertIn("evidence_map", prompt)
                self.assertIn("conflicts", prompt)
                self.assertIn("reference-style-benchmark.md", prompt)
                for document in config["output_documents"]:
                    self.assertIn(document["id"], prompt)
                    for section in document["required_sections"]:
                        self.assertIn(section, prompt)

    def test_patent_prompt_declares_form_routes_and_optional_engineering_evidence(self) -> None:
        prompt = (check_setup.ROOT / "references" / "patent-prompt.md").read_text(encoding="utf-8")
        for marker in (
            "背景组织=three-part",
            "技术方案组织=overall-prose",
            "技术方案组织=stepwise-method",
            "技术方案组织=hybrid",
            "工程实现证据=omit",
            "工程实现证据=include",
            "第一，...",
            "Use Altair as the default generator",
            "experimental figures and result tables high inclusion priority",
        ):
            self.assertIn(marker, prompt)

    def test_patent_prompt_keeps_json_internal_and_user_output_natural_language(self) -> None:
        prompt = (check_setup.ROOT / "references" / "patent-prompt.md").read_text(encoding="utf-8")
        for marker in (
            "The JSON contracts in this prompt are internal exchange formats",
            "respond to the user in natural Chinese",
            "do not display the raw object",
            "provide a concise natural-language progress update",
        ):
            self.assertIn(marker, prompt)

    def test_patent_artifact_preflight_rejects_untraceable_screenshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            image_path = root / "screen.png"
            image_path.write_bytes(base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAMAAAADCAIAAADZSiLoAAAAD0lEQVR4nGP4z8DAwMAAAAYAAWgmWQ0AAAAASUVORK5CYII="
            ))
            inventory = root / "inventory.json"
            inventory.write_text(json.dumps({"artifacts": [{
                "id": "SHOT-001", "kind": "actual-runtime-screenshot", "path": "screen.png",
                "sha256": preflight_patent_artifacts.sha256(image_path)
            }]}), encoding="utf-8")
            result = preflight_patent_artifacts.inspect(inventory, root)
            self.assertFalse(result["valid"])
            self.assertTrue(any("capture requires" in error for error in result["errors"]))

    def test_patent_artifact_preflight_rejects_incomplete_screenshot_framing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            image_path = root / "screen.png"
            image_path.write_bytes(base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAMAAAADCAIAAADZSiLoAAAAD0lEQVR4nGP4z8DAwMAAAAYAAWgmWQ0AAAAASUVORK5CYII="
            ))
            inventory = root / "inventory.json"
            inventory.write_text(json.dumps({"artifacts": [{
                "id": "SHOT-001",
                "kind": "actual-runtime-screenshot",
                "path": "screen.png",
                "sha256": preflight_patent_artifacts.sha256(image_path),
                "capture": {
                    "route": "http://127.0.0.1:8000/",
                    "viewport": "1280x720",
                    "captured_at": "2026-08-27T00:00:00Z",
                    "state": "prediction",
                    "framing_review": {
                        "subject": "topology and prediction state",
                        "full_subject_visible": False,
                        "centered": True,
                        "text_readable": True,
                        "no_occlusion": True,
                        "no_scroll_cutoff": False,
                    },
                },
            }]}), encoding="utf-8")
            result = preflight_patent_artifacts.inspect(inventory, root)
            self.assertFalse(result["valid"])
            self.assertTrue(any("all visual checks" in error for error in result["errors"]))

    def test_prompt_json_examples_parse(self) -> None:
        manifest = json.loads(check_setup.MANIFEST_PATH.read_text(encoding="utf-8"))
        for mode, config in manifest.items():
            with self.subTest(mode=mode):
                prompt = (check_setup.ROOT / config["prompt"]).read_text(encoding="utf-8")
                examples = re.findall(r"```json\n(.*?)\n```", prompt, flags=re.DOTALL)
                self.assertEqual(len(examples), 2)
                for example in examples:
                    self.assertIsInstance(json.loads(example), dict)

    def test_related_record_receives_overlap_score(self) -> None:
        case = {
            "case_id": "demo",
            "mode": "patent",
            "known_features": ["传感器采集温度并动态控制风机转速"],
        }
        search = {
            "case_id": "demo",
            "searched_at": "2026-08-20",
            "records": [
                {
                    "record_id": "DEMO-1",
                    "title": "温度传感器控制风机的方法",
                    "abstract": "采集温度数据并调节风机转速",
                    "matching_features": ["温度采集", "风机转速控制"],
                }
            ],
        }
        report = prior_art_report.build_report(case, search)
        self.assertIn("DEMO-1", report)
        self.assertNotIn("| 0.00 | DEMO-1 |", report)

    def test_concise_chinese_evidence_matches_long_case_feature(self) -> None:
        score, matched = prior_art_report.score_record(
            ["控制器根据融合温度和相对湿度计算机房露点温度"],
            {
                "title": "机房冷却控制方法",
                "abstract": "采集机房环境参数并控制风机",
                "matching_features": ["机房露点计算", "变频风机调速"],
            },
        )
        self.assertGreaterEqual(score, 0.45)
        self.assertEqual(matched, ["机房露点计算", "变频风机调速"])

    def test_search_api_payload_uses_web_search_without_credentials(self) -> None:
        case = {
            "mode": "patent",
            "technical_direction": "机房防凝露风机控制",
            "technical_problem": "单一传感器漂移导致误控制",
            "known_features": ["根据温湿度计算露点并调节风机"],
            "constraints": ["不依赖云端控制"],
        }
        groups = search_public_records.build_query_groups(case)
        payload = search_public_records.build_payload(case, "gpt-5.6", groups)
        self.assertEqual(payload["model"], "gpt-5.6")
        self.assertFalse(payload["store"])
        self.assertTrue(payload["stream"])
        self.assertEqual(payload["tools"][0]["type"], "web_search")
        self.assertNotIn("api_key", json.dumps(payload).lower())
        self.assertNotIn("authorization", json.dumps(payload).lower())

    def test_search_api_reads_completed_stream_response(self) -> None:
        expected = {"id": "resp_stream", "output": [], "usage": {}}
        event = json.dumps({"type": "response.completed", "response": expected})
        response = [
            b"event: response.created\n",
            b'data: {"type":"response.created"}\n',
            b"\n",
            b"event: response.completed\n",
            f"data: {event}\n".encode(),
            b"\n",
            b"data: [DONE]\n",
        ]
        self.assertEqual(
            search_public_records.read_streamed_response(response), expected
        )

    def test_search_api_normalizes_only_source_verified_records(self) -> None:
        url = "https://patents.google.com/patent/US20210254843A1/en"
        generated = {
            "sources_attempted": ["Google Patents"],
            "records": [
                {
                    "record_id": "US20210254843A1",
                    "title": "Condensation control system and related method",
                    "source": "Google Patents",
                    "url": url,
                    "publication_date": "2021-08-19",
                    "jurisdiction": "US",
                    "abstract": "Sensors and a controller operate a fan to reduce condensation.",
                    "matching_features": ["dew-point based fan control"],
                    "notes": "Preliminary overlap record.",
                }
            ],
            "search_limitations": ["Professional review required."],
        }
        response = {
            "id": "resp_test",
            "output": [
                {
                    "type": "web_search_call",
                    "action": {"sources": [{"type": "url", "url": url}]},
                },
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": json.dumps(generated)}
                    ],
                },
            ],
            "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
        }
        case = {
            "case_id": "benchmark-1",
            "mode": "patent",
            "technical_direction": "机房防凝露风机控制",
            "technical_problem": "凝露风险",
            "known_features": ["露点控制风机"],
        }
        groups = search_public_records.build_query_groups(case)
        result = search_public_records.build_result(case, response, "gpt-5.6", groups)
        self.assertEqual(result["records"][0]["record_id"], "US20210254843A1")
        self.assertEqual(result["search_run"]["api_response_id"], "resp_test")
        self.assertFalse(result["search_run"]["store"])

    def test_search_api_rejects_unverified_record_url(self) -> None:
        record = {
            "record_id": "FAKE-1",
            "title": "Unverified",
            "source": "unknown",
            "url": "https://unverified.invalid/patent/FAKE-1",
            "publication_date": "unknown",
            "jurisdiction": "unknown",
            "abstract": "unverified",
            "matching_features": ["feature"],
            "notes": "unverified",
        }
        with self.assertRaises(ValueError):
            search_public_records.validate_search_output(
                {"records": [record]},
                {"https://verified.example/patent/REAL-1"},
            )

    def test_analysis_payload_contains_no_credentials(self) -> None:
        case = {
            "case_id": "benchmark-1",
            "technical_direction": "防凝露控制",
            "technical_problem": "凝露风险",
            "known_features": ["根据露点控制风机"],
            "constraints": [],
        }
        prior_art = {
            "records": [
                {
                    "record_id": "KNOWN-1",
                    "title": "Known record",
                    "abstract": "露点控制风机",
                    "matching_features": ["露点控制"],
                    "url": "https://example.com/KNOWN-1",
                }
            ]
        }
        payload = analyze_public_records.build_payload(
            case, prior_art, "deepseek-ai/DeepSeek-V4-Pro"
        )
        serialized = json.dumps(payload).lower()
        self.assertEqual(payload["model"], "deepseek-ai/DeepSeek-V4-Pro")
        self.assertNotIn("api_key", serialized)
        self.assertNotIn("authorization", serialized)

    def test_analysis_rejects_unverified_model_record(self) -> None:
        generated = {
            "overall_assessment": "初步比对",
            "ranked_records": [
                {
                    "record_id": "INVENTED-1",
                    "overlap_level": "high",
                    "overlapping_features": ["特征"],
                    "differentiating_features": ["未确认"],
                    "drafting_implication": "需要复核",
                    "confidence": "low",
                }
            ],
            "caveats": ["不构成法律意见"],
        }
        with self.assertRaises(ValueError):
            analyze_public_records.validate_generated(generated, ["KNOWN-1"])

    def test_prior_art_validator_checks_public_benchmark_recall(self) -> None:
        record = {
            "record_id": "TARGET-1",
            "title": "Target patent",
            "source": "official source",
            "url": "https://patents.example/TARGET-1",
            "publication_date": "2020-01-01",
            "jurisdiction": "US",
            "abstract": "A verified record.",
            "matching_features": ["feature"],
            "notes": "benchmark",
        }
        result = validate_prior_art.validate(
            {
                "case_id": "benchmark",
                "searched_at": "2026-08-20",
                "sources_attempted": ["official source"],
                "search_run": {
                    "provider": "openai-responses-web-search",
                    "model": "gpt-5.6",
                    "api_response_id": "resp_test",
                    "store": False,
                    "source_verification": "cross-checked",
                },
                "benchmark_result": {
                    "expected_record_id": "TARGET-1",
                    "expected_record_recalled": True,
                    "filing_material_generated": False,
                },
                "records": [record],
            }
        )
        self.assertTrue(result["valid"])

    def test_prior_art_validator_rejects_secret_fields(self) -> None:
        result = validate_prior_art.validate(
            {
                "case_id": "demo",
                "searched_at": "2026-08-20",
                "sources_attempted": [],
                "search_run": {
                    "provider": "openai-responses-web-search",
                    "model": "gpt-5.6",
                    "api_response_id": "resp_test",
                    "store": False,
                    "source_verification": "cross-checked",
                    "api_key": "not-allowed",
                },
                "records": [],
            }
        )
        self.assertFalse(result["valid"])

    def test_patent_needs_information_response_is_valid_but_not_renderable(self) -> None:
        result = validate_draft.validate(
            {
                "case_id": "demo",
                "mode": "patent",
                "status": "needs-information",
                "known_facts": ["需要采集温度数据"],
                "missing_facts": ["控制流程未说明"],
                "conflicts": [],
                "questions": ["温度数据如何触发具体控制动作？"],
            }
        )
        self.assertTrue(result["valid"])
        self.assertFalse(result["render_ready"])

    def test_needs_information_response_rejects_documents(self) -> None:
        result = validate_draft.validate(
            {
                "mode": "patent",
                "status": "needs-information",
                "known_facts": [],
                "missing_facts": ["核心流程"],
                "conflicts": [],
                "questions": ["请说明核心流程。"],
                "documents": complete_documents("patent"),
            }
        )
        self.assertFalse(result["valid"])
        self.assertFalse(result["render_ready"])

    def test_software_needs_information_enforces_question_limit(self) -> None:
        result = validate_draft.validate(
            {
                "mode": "software-copyright",
                "software_type": "application",
                "status": "needs-information",
                "known_facts": [],
                "missing_facts": ["缺少实际截图"],
                "conflicts": [],
                "questions": [f"问题 {index}" for index in range(7)],
            }
        )
        self.assertFalse(result["valid"])
        self.assertTrue(any("at most 6" in error for error in result["errors"]))

    def test_complete_patent_disclosure_is_valid(self) -> None:
        result = validate_draft.validate(
            {
                "mode": "patent",
                "documents": complete_documents("patent"),
                **ready_contract("patent"),
                "sources": ["DEMO-1"],
                "limitations": ["professional review required"],
            }
        )
        self.assertTrue(result["valid"])
        self.assertTrue(result["render_ready"])

    def test_patent_renderer_replaces_template_example(self) -> None:
        draft = {
            "mode": "patent",
            "status": "draft-ready",
            "documents": complete_documents("patent"),
            **ready_contract("patent"),
            "sources": ["DEMO-1"],
            "limitations": ["professional review required"],
        }
        draft["documents"]["technical-disclosure"]["sections"]["发明创造名称"] = (
            "一种测试控制方法"
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "disclosure.docx"
            render_patent_disclosure.render(draft, output)
            with zipfile.ZipFile(output) as archive:
                document_xml = archive.read("word/document.xml").decode("utf-8")
            self.assertIn("一种测试控制方法", document_xml)
            self.assertNotIn("X 光机", document_xml)
            self.assertNotIn("MOKA-VGA", document_xml)

    def test_generated_horizontal_diagram_uses_compact_canvas(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "diagram.png"
            created = render_patent_disclosure.create_diagram(
                {
                    "标题": "测试流程",
                    "diagram": {
                        "direction": "horizontal",
                        "nodes": ["采集", "处理", "校验", "发布"],
                        "edges": [[0, 1, ""], [1, 2, ""], [2, 3, ""]],
                    },
                },
                output,
            )
            self.assertTrue(created)
            with preflight_software_artifacts.Image.open(output) as image:
                self.assertLess(image.height / image.width, 0.35)

    def test_patent_profile_rejects_invalid_figure_layout(self) -> None:
        documents = complete_documents("patent")
        documents["technical-disclosure"]["disclosure_profile"] = {
            "所属技术领域": "测试领域",
            "背景技术": {
                "现有技术状况描述与评价": "现有技术",
                "现有技术存在的问题和缺点": "现有问题",
                "发明形成过程": "形成过程",
            },
            "发明内容": {
                "要解决的技术问题": "技术问题",
                "关键点及对应技术效果": [
                    {"关键点": "特征", "技术效果": "效果", "evidence_refs": ["F-001"]}
                ],
                "总体技术效果": "总体效果",
            },
            "具体实施方式": [{"标题": "实施例", "正文": "正文", "步骤": []}],
            "表格": [],
            "附图": [
                {
                    "图号": "图1",
                    "标题": "测试图",
                    "类型": "flowchart",
                    "说明": "测试说明",
                    "关联小节": "具体实施方式.实施例",
                    "排版": {"宽度": "oversized", "前置分页": "false"},
                }
            ],
            "检索附件": {
                "检索日期": "2026-08-27",
                "检索数据库": [],
                "检索式": [],
                "保留记录": [],
                "最接近记录对比": "未检出",
                "检索局限": "初步检索",
            },
        }
        result = validate_draft.validate(
            {
                "mode": "patent",
                "documents": documents,
                **ready_contract("patent"),
                "sources": ["DEMO-1"],
                "limitations": ["professional review required"],
            }
        )
        self.assertFalse(result["valid"])
        self.assertTrue(any("排版.宽度" in error for error in result["errors"]))

    def test_three_part_prose_route_is_valid_without_engineering_evidence(self) -> None:
        documents = complete_documents("patent")
        documents["technical-disclosure"]["disclosure_profile"] = routed_patent_profile()
        result = validate_draft.validate(
            {
                "mode": "patent",
                "documents": documents,
                **ready_contract("patent"),
                "sources": ["DEMO-1"],
                "limitations": ["professional review required"],
            }
        )
        self.assertTrue(result["valid"])
        self.assertTrue(result["render_ready"])

    def test_engineering_include_route_requires_verified_evidence(self) -> None:
        documents = complete_documents("patent")
        documents["technical-disclosure"]["disclosure_profile"] = routed_patent_profile(
            engineering_route="include"
        )
        result = validate_draft.validate(
            {
                "mode": "patent",
                "documents": documents,
                **ready_contract("patent"),
                "sources": ["DEMO-1"],
                "limitations": ["professional review required"],
            }
        )
        self.assertFalse(result["valid"])
        self.assertTrue(any("required by the include route" in error for error in result["errors"]))

    def test_experimental_altair_chart_and_high_priority_table_are_valid(self) -> None:
        documents = complete_documents("patent")
        profile = routed_patent_profile()
        profile["表格"] = [
            {
                "表号": "表1",
                "标题": "实验组结果",
                "表头": ["实验组", "测量值"],
                "数据行": [["A", 1.0], ["B", 1.4]],
                "关联小节": "具体实施方式.实施例",
                "用途": "experimental-result",
                "优先级": "high",
                "evidence_refs": ["experiment.json.results"],
            }
        ]
        profile["附图"] = [
            {
                "图号": "图1",
                "标题": "实验组测量值对比",
                "类型": "chart",
                "说明": "比较已确认实验组A与B的测量值。",
                "关联小节": "具体实施方式.实施例",
                "用途": "experimental-result",
                "优先级": "high",
                "生成器": "altair",
                "chart_spec": {
                    "data": {"values": [{"group": "A", "value": 1.0}, {"group": "B", "value": 1.4}]},
                    "mark": "bar",
                    "encoding": {
                        "x": {"field": "group", "type": "nominal"},
                        "y": {"field": "value", "type": "quantitative"},
                    },
                },
                "evidence_refs": ["experiment.json.results"],
            }
        ]
        documents["technical-disclosure"]["disclosure_profile"] = profile
        result = validate_draft.validate(
            {
                "mode": "patent",
                "documents": documents,
                **ready_contract("patent"),
                "sources": ["DEMO-1"],
                "limitations": ["professional review required"],
            }
        )
        self.assertTrue(result["valid"])

    def test_routed_renderer_uses_three_part_background_and_numbered_advantages(self) -> None:
        documents = complete_documents("patent")
        documents["technical-disclosure"]["disclosure_profile"] = routed_patent_profile()
        draft = {
            "mode": "patent",
            "status": "draft-ready",
            "documents": documents,
            **ready_contract("patent"),
            "sources": ["DEMO-1"],
            "limitations": ["professional review required"],
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "routed.docx"
            render_patent_disclosure.render(draft, output)
            with zipfile.ZipFile(output) as archive:
                document_xml = archive.read("word/document.xml").decode("utf-8")
        for expected in ("1. 技术背景", "2. 最接近的现有技术", "3. 现有技术的缺陷和不足", "第一，", "第四，"):
            self.assertIn(expected, document_xml)
        self.assertNotIn("工程实现与接口证据", document_xml)

    def test_patent_final_application_sections_are_rejected(self) -> None:
        documents = complete_documents("patent")
        documents["technical-disclosure"]["sections"]["权利要求书"] = "not in scope"
        result = validate_draft.validate(
            {
                "mode": "patent",
                "documents": documents,
                **ready_contract("patent"),
                "sources": ["DEMO-1"],
                "limitations": ["professional review required"],
            }
        )
        self.assertFalse(result["valid"])

    def test_application_software_requires_both_manuals(self) -> None:
        for missing_id in ("operation-manual", "detailed-design"):
            with self.subTest(missing_id=missing_id):
                documents = complete_documents("software-copyright")
                del documents[missing_id]
                result = validate_draft.validate(
                    {
                        "mode": "software-copyright",
                        "software_type": "application",
                        "documents": documents,
                        **ready_contract("software-copyright"),
                        "sources": [],
                    }
                )
                self.assertFalse(result["valid"])
                self.assertTrue(any(missing_id in error for error in result["errors"]))

    def test_complete_application_software_package_is_valid(self) -> None:
        documents = complete_documents("software-copyright")
        result = validate_draft.validate(
            {
                "mode": "software-copyright",
                "software_type": "application",
                "documents": documents,
                **ready_contract("software-copyright"),
                "sources": ["DEMO-1"],
                "limitations": ["professional review required"],
            }
        )
        self.assertTrue(result["valid"])
        self.assertTrue(result["render_ready"])

    def test_software_renderer_replaces_all_template_examples(self) -> None:
        documents = complete_documents("software-copyright")
        documents["registration-info"]["sections"]["软件全称"] = "测试巡检软件"
        documents["registration-info"]["sections"]["版本号"] = "V1.0"
        documents["registration-info"]["sections"]["源程序量"] = "2"
        documents["operation-manual"]["sections"]["软件名称与版本"] = (
            "测试巡检软件 V1.0"
        )
        documents["detailed-design"]["sections"]["软件名称与版本"] = (
            "测试巡检软件 V1.0"
        )
        documents["source-code"]["sections"].update(
            {
                "软件名称与版本": "测试巡检软件 V1.0",
                "编程语言": "JavaScript",
                "源程序总行数": "2",
                "源程序正文": (
                    "===== FILE: app/test.js =====\n"
                    "const value = 1;\n"
                    "console.log(value);"
                ),
            }
        )
        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
            "/x8AAusB9Y9Z4x8AAAAASUVORK5CYII="
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            screenshot = root / "actual.png"
            screenshot.write_bytes(png)
            draft = {
                "mode": "software-copyright",
                "software_type": "application",
                "status": "draft-ready",
                "documents": documents,
                **ready_contract(
                    "software-copyright", project_lines=2, submitted_lines=2
                ),
                "artifacts": {
                    "screenshots": [
                        {
                            "path": str(screenshot),
                            "title": "实际界面",
                            "description": "实际测试截图。",
                            "caption": "实际界面",
                        }
                    ]
                },
                "sources": ["DEMO-1"],
                "limitations": ["professional review required"],
            }
            outputs = render_software_copyright.render_all(draft, root / "output")
            self.assertEqual(len(outputs), 5)
            for output in outputs:
                self.assertTrue(output.is_file())
            for output in outputs:
                with zipfile.ZipFile(output) as archive:
                    document_xml = archive.read("word/document.xml").decode("utf-8")
                self.assertNotIn("韦氏盈创", document_xml)
                self.assertNotIn("X-Planner", document_xml)
                self.assertNotIn("JUnit4Test", document_xml)

    def test_draft_ready_rejects_unresolved_conflicts(self) -> None:
        contract = ready_contract("patent")
        contract["conflicts"] = [
            {
                "field": "控制周期",
                "evidence_values": ["10秒：需求记录", "30秒：附图"],
                "resolution_required": "确认实际控制周期",
            }
        ]
        result = validate_draft.validate(
            {
                "mode": "patent",
                "status": "draft-ready",
                "documents": complete_documents("patent"),
                **contract,
                "sources": ["DEMO-1"],
                "limitations": ["professional review required"],
            }
        )
        self.assertFalse(result["valid"])
        self.assertTrue(any("resolve all conflicts" in error for error in result["errors"]))

    def test_draft_ready_requires_field_evidence(self) -> None:
        contract = ready_contract("patent")
        contract["evidence_map"] = []
        result = validate_draft.validate(
            {
                "mode": "patent",
                "documents": complete_documents("patent"),
                **contract,
                "sources": ["DEMO-1"],
                "limitations": ["professional review required"],
            }
        )
        self.assertFalse(result["valid"])
        self.assertTrue(any("non-empty evidence_map" in error for error in result["errors"]))

    def test_patent_requires_combination_risk_assessment(self) -> None:
        contract = ready_contract("patent")
        del contract["risk_assessment"]
        result = validate_draft.validate(
            {
                "mode": "patent",
                "documents": complete_documents("patent"),
                **contract,
                "sources": ["DEMO-1"],
                "limitations": ["professional review required"],
            }
        )
        self.assertFalse(result["valid"])
        self.assertTrue(any("risk_assessment" in error for error in result["errors"]))

    def test_software_separates_project_and_submitted_source_counts(self) -> None:
        documents = complete_documents("software-copyright")
        documents["registration-info"]["sections"]["源程序量"] = "4"
        documents["source-code"]["sections"].update(
            {
                "源程序总行数": "2",
                "源程序正文": (
                    "===== FILE: app/test.js =====\n"
                    "const first = 1;\n"
                    "const second = 2;"
                ),
            }
        )
        result = validate_draft.validate(
            {
                "mode": "software-copyright",
                "software_type": "application",
                "documents": documents,
                **ready_contract(
                    "software-copyright", project_lines=4, submitted_lines=2
                ),
                "sources": [],
                "limitations": ["professional review required"],
            }
        )
        self.assertTrue(result["valid"])
        self.assertTrue(result["render_ready"])

    def test_software_rejects_source_body_count_mismatch(self) -> None:
        documents = complete_documents("software-copyright")
        documents["source-code"]["sections"]["源程序总行数"] = "2"
        result = validate_draft.validate(
            {
                "mode": "software-copyright",
                "software_type": "application",
                "documents": documents,
                **ready_contract(
                    "software-copyright", project_lines=2, submitted_lines=2
                ),
                "sources": [],
                "limitations": ["professional review required"],
            }
        )
        self.assertFalse(result["valid"])
        self.assertTrue(any("contains 1 source lines" in error for error in result["errors"]))

    def test_software_requires_passed_artifact_preflight(self) -> None:
        contract = ready_contract("software-copyright")
        contract["artifact_preflight"]["secrets_scan_status"] = "not-run"
        result = validate_draft.validate(
            {
                "mode": "software-copyright",
                "software_type": "application",
                "documents": complete_documents("software-copyright"),
                **contract,
                "sources": [],
                "limitations": ["professional review required"],
            }
        )
        self.assertFalse(result["valid"])
        self.assertTrue(any("secrets_scan_status" in error for error in result["errors"]))

    def test_packager_contains_required_case_files_and_checklist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for filename in package_deliverables.required_filenames():
                (root / filename).write_bytes(b"test")
            output = root / "materials.zip"
            package_deliverables.package(root, output)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(archive.namelist(), package_deliverables.required_filenames())

    def test_software_artifact_preflight_verifies_source_and_screenshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_dir = root / "app"
            source_dir.mkdir()
            source = source_dir / "test.js"
            source.write_text("const value = 1;\n", encoding="utf-8")
            screenshot = root / "actual.png"
            preflight_software_artifacts.Image.new("RGB", (4, 4), "white").save(screenshot)
            inventory = root / "source_inventory.json"
            inventory.write_text(
                json.dumps(
                    {
                        "files": [
                            {
                                "path": "app/test.js",
                                "line_count": 1,
                                "sha256": preflight_software_artifacts.sha256(source),
                                "included": True,
                            }
                        ],
                        "project_owned_source_line_count": 1,
                        "submitted_source_line_count": 1,
                    }
                ),
                encoding="utf-8",
            )
            result = preflight_software_artifacts.inspect(
                inventory,
                root,
                [screenshot],
                confirm_actual_screenshots=True,
                confirm_complete_framing=True,
            )
            self.assertTrue(result["valid"])
            self.assertEqual(result["source_counts"]["submitted_source_line_count"], 1)
            self.assertEqual(result["artifact_preflight"]["secrets_scan_status"], "passed")

    def test_software_artifact_preflight_rejects_secret(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_dir = root / "app"
            source_dir.mkdir()
            source = source_dir / "test.js"
            source.write_text('const apiKey = "abcdefghijk";\n', encoding="utf-8")
            screenshot = root / "actual.png"
            preflight_software_artifacts.Image.new("RGB", (4, 4), "white").save(screenshot)
            inventory = root / "source_inventory.json"
            inventory.write_text(
                json.dumps(
                    {
                        "files": [
                            {
                                "path": "app/test.js",
                                "line_count": 1,
                                "sha256": preflight_software_artifacts.sha256(source),
                                "included": True,
                            }
                        ],
                        "project_owned_source_line_count": 1,
                        "submitted_source_line_count": 1,
                    }
                ),
                encoding="utf-8",
            )
            result = preflight_software_artifacts.inspect(
                inventory,
                root,
                [screenshot],
                confirm_actual_screenshots=True,
                confirm_complete_framing=True,
            )
            self.assertFalse(result["valid"])
            self.assertEqual(result["artifact_preflight"]["secrets_scan_status"], "failed")

    def test_delivery_secret_scan_detects_api_key_in_nested_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive_path = root / "delivery.zip"
            fake_secret = b"s" + b"k-" + b"A" * 32
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("config.txt", fake_secret)
            findings = scan_delivery_secrets.scan_path(root)
            self.assertTrue(any(item["type"] == "api-key" for item in findings))

    def test_delivery_secret_scan_accepts_clean_skill_source(self) -> None:
        findings = scan_delivery_secrets.scan_path(check_setup.ROOT)
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
