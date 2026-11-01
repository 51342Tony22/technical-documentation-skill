# Data Contracts

Use UTF-8 JSON for all intermediate records.

CONTRACT_VERSION: 1.8.1

## `case.json`

```json
{
  "case_id": "case-001",
  "mode": "software-copyright",
  "case_nature": "owned-confidential",
  "rights_scope": {
    "ownership_confirmed": true,
    "artifact_use_authorized": true
  },
  "software_type": "application",
  "idea": "The user's original idea",
  "technical_direction": "Field and intended implementation",
  "technical_problem": "Problem addressed",
  "known_features": ["feature A", "feature B"],
  "constraints": ["constraint A"],
  "confirmed_new_features": []
}
```

`mode` must be `patent` or `software-copyright`. For application software, set `software_type` to `application` and require both manuals. Do not place unconfirmed model-generated features in `confirmed_new_features`.

`case_nature` must be one of `owned-confidential`, `owned-internal-test`, `public-benchmark`, or `synthetic-evaluation`. Public benchmarks are retrieval/comparison tests only and must not be represented as the user's invention or software. Filing-oriented rendering requires confirmed ownership and artifact-use authorization.

## `prior_art.json`

```json
{
  "case_id": "case-001",
  "searched_at": "2026-08-20",
  "sources_attempted": ["source name"],
  "search_run": {
    "provider": "openai-responses-web-search",
    "model": "gpt-5.6",
    "api_response_id": "resp_...",
    "store": false,
    "query_groups": [
      {"type": "problem", "query": "..."}
    ],
    "source_verification": "cross-checked-against-api-web-search-sources",
    "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
  },
  "records": [
    {
      "record_id": "stable identifier",
      "title": "record title",
      "source": "database or publisher",
      "url": "https://example.com/record",
      "publication_date": "YYYY-MM-DD or unknown",
      "jurisdiction": "CN, WO, EP, US, or N/A",
      "abstract": "faithful short summary",
      "matching_features": ["feature A"],
      "notes": "limitations or uncertainty"
    }
  ]
}
```

An empty `records` list means no verifiable result was captured. It does not mean that no relevant public material exists. Never store an API key, authorization header, cookie, complete raw API request, or secret-bearing environment snapshot in `prior_art.json`.

## Drafting Response States

The selected fixed prompt returns exactly one of two states:

- `needs-information`: core facts or artifacts are missing. Ask the listed questions and do not render documents.
- `draft-ready`: the response contains the mode's complete document structure and may proceed to validation and rendering.

### `needs-information`

```json
{
  "case_id": "case-001",
  "mode": "patent",
  "status": "needs-information",
  "known_facts": ["confirmed fact"],
  "missing_facts": ["missing core fact"],
  "conflicts": [
    {
      "field": "field or material fact",
      "evidence_values": ["value and source A", "value and source B"],
      "resolution_required": "smallest confirmation needed"
    }
  ],
  "questions": ["smallest question needed to continue"]
}
```

Do not include `documents` in this state. Patent mode allows at most five questions; software-copyright mode allows at most six. Every question must resolve a listed missing fact or conflict rather than request broad background. Use an empty `conflicts` array when the gate was triggered only by missing information.

### `draft-ready`

```json
{
  "case_id": "case-001",
  "mode": "software-copyright",
  "software_type": "application",
  "status": "draft-ready",
  "documents": {
    "registration-info": {
      "sections": {
        "软件全称": "...",
        "版本号": "V1.0"
      }
    },
    "operation-manual": {
      "sections": {
        "软件名称与版本": "...",
        "功能模块操作": "...",
        "界面截图及说明": "actual screenshot references and descriptions"
      }
    },
    "detailed-design": {
      "sections": {
        "软件名称与版本": "...",
        "总体架构": "...",
        "软件模块设计": "..."
      }
    },
    "source-code": {
      "sections": {
        "软件名称与版本": "...",
        "编程语言": "...",
        "源程序总行数": "...",
        "源程序正文": "project-owned source code"
      }
    }
  },
  "evidence_map": [
    {
      "fact_id": "S-F001",
      "statement": "material fact used in a document",
      "basis_type": "artifact",
      "source_refs": ["source_inventory.files[0]"],
      "used_in": ["source-code.源程序正文"]
    }
  ],
  "conflicts": [],
  "differentiation": [],
  "sources": ["stable identifier"],
  "limitations": ["preliminary machine-assisted draft; professional review required"]
}
```

Every `draft-ready` response requires a non-empty `evidence_map` and an empty `conflicts` array. Allowed `basis_type` values are:

- `user-confirmed`: explicitly supplied or confirmed by the project owner;
- `artifact`: established by source code, screenshot, diagram, inventory, log, or other supplied artifact;
- `public-source`: established by a traceable record in `prior_art.json`;
- `pending-administrative`: a non-technical field intentionally represented as `[待补充]`.

Each evidence entry must identify the exact input or artifact in `source_refs` and every target document section in `used_in`. Model inference is not an evidence type.

Patent `draft-ready` responses also require:

```json
{
  "risk_assessment": {
    "closest_single_reference": "stable source identifier or none-captured",
    "single_reference_risk": "high, medium, low, or unknown",
    "combination_risk": "high, medium, low, or unknown",
    "reasoning": "evidence-grounded explanation",
    "unresolved_questions": ["remaining professional-review question"]
  }
}
```

Software-copyright `draft-ready` responses also require:

```json
{
  "source_selection": {
    "project_qualifying_line_count": 12000,
    "submitted_source_line_count": 3000,
    "selection_strategy": "first-last-continuous",
    "selected_files": ["src/main.js"],
    "excluded_files": [
      {"path": "vendor/library.js", "reason": "third-party dependency"}
    ]
  },
  "artifact_preflight": {
    "screenshots_verified_actual": true,
    "screenshot_framing_verified": true,
    "source_inventory_verified": true,
    "secrets_scan_status": "passed",
    "third_party_exclusions_reviewed": true,
    "notes": []
  }
}
```

`registration-info.源程序量` equals `project_qualifying_line_count`. `source-code.源程序总行数` equals `submitted_source_line_count` and the actual number of non-heading lines in `源程序正文`. The submitted count must not exceed the project qualifying count.

For patent mode, `documents` must contain exactly `technical-disclosure` with these required sections:

- 申请类别
- 申请人
- 发明人或设计人
- 联系人及联系方式
- 发明创造名称
- 背景技术及现有技术的缺陷和不足
- 具体的技术方案描述
- 本发明创造的优点
- 具体实施方式及附图

Patent `technical-disclosure` also requires a `disclosure_profile` for long-form rendering:

```json
{
  "写作路由": {
    "背景组织": "three-part or integrated",
    "技术方案组织": "overall-prose, stepwise-method, or hybrid",
    "工程实现证据": "omit or include"
  },
  "所属技术领域": "technical field and technical object",
  "背景技术": {
    "技术背景": "required by the three-part route",
    "最接近的现有技术": "required by the three-part route",
    "现有技术的缺陷和不足": "required by the three-part route"
  },
  "发明内容": {
    "要解决的技术问题": "...",
    "总体技术方案": "route-appropriate overall solution",
    "关键点及对应技术效果": [
      {
        "关键点": "concrete feature and relationship",
        "技术效果": "causal technical effect",
        "evidence_refs": ["case_json.known_features[0]"]
      }
    ],
    "本发明创造的优点": [
      "first feature-mechanism-effect chain",
      "second feature-mechanism-effect chain",
      "third feature-mechanism-effect chain",
      "fourth feature-mechanism-effect chain"
    ]
  },
  "具体实施方式": [
    {"标题": "系统架构", "正文": "...", "步骤": ["S1 ...", "S2 ..."]}
  ],
  "表格": [
    {
      "表号": "表1",
      "标题": "...",
      "表头": ["列1", "列2"],
      "数据行": [["值1", "值2"]],
      "关联小节": "具体实施方式.实施例",
      "用途": "experimental-result or technical-definition",
      "优先级": "high, normal, or low",
      "表前分页": false,
      "evidence_refs": ["artifact ID or source ID"]
    }
  ],
  "附图": [
    {
      "图号": "图1",
      "标题": "...",
      "类型": "flowchart",
      "说明": "...",
      "关联小节": "具体实施方式.系统架构",
      "用途": "technical-structure or experimental-result",
      "生成器": "altair for chart figures",
      "chart_spec": {
        "data": {"values": [{"group": "confirmed group", "value": 1}]},
        "mark": "bar",
        "encoding": {
          "x": {"field": "group", "type": "nominal"},
          "y": {"field": "value", "type": "quantitative"}
        }
      },
      "image_path": "optional verified relative path",
      "artifact_id": "optional verified artifact ID",
      "evidence_class": "generated-technical-figure or actual-runtime-screenshot",
      "排版": {
        "宽度": "full, medium, or compact",
        "前置分页": false
      },
      "diagram": {
        "direction": "horizontal, vertical, or grid",
        "nodes": ["confirmed node A", "confirmed node B"],
        "edges": [[0, 1, "confirmed relationship"]]
      }
    }
  ],
  "工程实现证据": {
    "代码资产": [
      {"artifact_id": "CODE-001", "路径": "app/server.py", "用途": "module purpose", "语言": "Python", "行数": 1, "sha256": "verified SHA-256"}
    ],
    "接口契约": [
      {"接口ID": "API-001", "方法": "POST", "路径": "/api/v1/example", "请求": "request fields", "响应": "response fields", "异常": "error states", "实现证据": ["CODE-001"]}
    ],
    "端到端工作流": [
      {"步骤": "W1", "输入": "input", "处理": "operation", "输出": "output", "接口或模块": "API-001", "证据": ["CODE-001"]}
    ],
    "资产预检": {"状态": "passed", "报告路径": "artifact-preflight.json", "截图为真实运行界面": true, "技术附图为确定性生成": true, "密钥扫描": "passed"}
  },
  "检索附件": {
    "检索日期": "YYYY-MM-DD",
    "检索数据库": ["CNIPA Patent Search and Analysis System"],
    "检索式": ["query actually used"],
    "保留记录": ["stable source ID"],
    "最接近记录对比": "...",
    "检索局限": "..."
  }
}
```

For `背景组织=integrated`, replace the three background fields in the example with `现有技术状况描述与评价` and `现有技术存在的问题和缺点`; add `发明形成过程` only when actual development evidence exists. `工程实现证据` is required only when `写作路由.工程实现证据=include`, which must come from an explicit user/template request for API, interface, code, runnable workflow, runtime screenshot, or reproducibility evidence. It is omitted by default even when code or figures exist. `actual-runtime-screenshot` means an unaltered capture of a running implementation, not a mockup or image-model output. Its inventory `capture` object must contain `route`, `viewport`, `captured_at`, `state`, and `framing_review`; the review names the subject and sets `full_subject_visible`, `centered`, `text_readable`, `no_occlusion`, and `no_scroll_cutoff` to true. Patent-critical diagrams should use `generated-technical-figure` and be deterministically generated from reviewed structured facts.

The example `S1` and `S2` identifiers illustrate syntax only. There is no required `S1-S24` range. Use as many consecutive, non-padding steps as the evidenced end-to-end sequence actually needs. The patent and software-copyright prompts must remain mode-isolated; content and vocabulary are governed by `references/reference-style-benchmark.md`.

When supplied evidence contains quantitative experimental results, set relevant tables and chart figures to `用途=experimental-result` and `优先级=high`. A chart figure uses `类型=chart`, `生成器=altair`, a self-contained Vega-Lite-compatible `chart_spec`, and exact `evidence_refs`. Altair is the default only for quantitative charts; structural technical diagrams continue to use the deterministic diagram renderer. Never populate experimental values from model inference.

The renderer remains backward compatible with V1.2 and V1.3 drafts, but V1.4 production drafts must provide this profile. Figure layout defaults to continuous flow; `前置分页` is reserved for a genuinely complex tall figure or actual screenshot. Tables, figures, parameters, development history, and effects must be evidence-grounded; the profile is not permission to lengthen a disclosure through invention or repetition.

For application-software copyright mode, `documents` must contain all four document IDs:

- `registration-info`
- `operation-manual`
- `detailed-design`
- `source-code`

The exact required sections for each document are authoritative in `assets/template-manifest.json`. Update this contract and the manifest together if the project owner supplies revised templates.
