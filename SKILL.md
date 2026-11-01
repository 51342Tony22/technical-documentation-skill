---
name: draft-patent-copyright
description: Build a computer-related patent technical disclosure or a complete application-software copyright material package from a user's idea by routing to one fixed mode-specific prompt, collecting traceable public evidence, filling the supplied templates, and validating every required document. Use for Chinese patent technical disclosures, software copyright registration information, operation manuals, detailed design specifications, source-code documents, or testing this dual-mode IP workflow.
---

# Draft Patent And Software Copyright Materials

Use one isolated workflow for each case. Never load or combine both mode prompts in the same drafting run. This Skill uses the V1.8 patent-form routing workflow and the existing software-copyright workflow. Its JSON contracts are internal pipeline data; user-facing replies must be natural Chinese unless the user explicitly asks for JSON.

## Preconditions

1. Read `references/data-contracts.md` for the input and intermediate formats.
2. Read `references/template-map.md` before filling any supplied DOCX.
3. Read `references/reference-style-benchmark.md` to enforce the patent/soft-copyright content and vocabulary boundary.
4. Run `python3 scripts/check_setup.py` to identify missing prompts or templates.
5. Stop before substantive drafting when the selected mode prompt still contains `PROMPT_STATUS: PLACEHOLDER`.

## Workflow

### 1. Confirm The Mode And Intake

- Set `mode` to exactly `patent` or `software-copyright`.
- Ask only for missing information that materially affects the technical content or required registration fields.
- Preserve the user's original idea, technical direction, known features, constraints, and named contributors in the case record.
- Classify `case_nature` as `owned-confidential`, `owned-internal-test`, `public-benchmark`, or `synthetic-evaluation`. Record whether ownership and artifact use are confirmed.
- A `public-benchmark` may test retrieval and comparison, but must not be rendered or represented as the user's filing material.
- Record material contradictions rather than resolving them by preference. A draft-ready result must have an empty `conflicts` array.
- Treat application software as requiring both an operation manual and a detailed design specification.
- Do not treat a business goal, desired result, or abstract algorithm as a complete technical solution.

### 2. Perform Preliminary Search

Read `references/search-and-differentiation.md` and follow it completely.

- When API search is enabled, read `references/search-api.md` and run `python3 scripts/search_public_records.py CASE_JSON --output PRIOR_ART_JSON`.
- Default to `gpt-5.6` only when the configured account exposes that model. Keep the model configurable through `OPENAI_SEARCH_MODEL`.
- Read credentials only from `OPENAI_API_KEY` or one-time standard input. Never write credentials to the workspace, cache, report, trace, sample, or package.

- Generate Chinese and English query groups from the technical problem, components, actions, data flow, and claimed effects.
- Search current domestic and international patent/public literature sources when browsing or a connected search tool is available.
- For Chinese records, use the CNIPA Patent Search and Analysis System as the preferred verification source; supplement with WIPO PATENTSCOPE and EPO Espacenet. Treat Google Patents as a convenience cross-check rather than the authority for Chinese legal status.
- Keep the exact query log, access limitations, retained record IDs, family/citation expansion, and database verification status for the disclosure's internal search appendix.
- Record a stable URL, publication number or source identifier, title, date, jurisdiction, and relevant feature for every cited result.
- Never invent search results, identifiers, dates, claims, or coverage.
- Clearly label the result as a preliminary search, not a legal novelty opinion or authorization guarantee.

### 3. Compare Substantive Features

- Store normalized search records using `prior_art.json` from `references/data-contracts.md`.
- Run `python3 scripts/validate_prior_art.py PRIOR_ART_JSON --case CASE_JSON` before generating the overlap report.
- Run `python3 scripts/prior_art_report.py CASE_JSON PRIOR_ART_JSON --output REPORT.md` for a reproducible first-pass overlap report.
- When a compatible analysis model is configured, run `python3 scripts/analyze_public_records.py CASE_JSON PRIOR_ART_JSON --output MODEL_ANALYSIS_JSON`. This step analyzes only the supplied verified records and is not a replacement for retrieval.
- Review the underlying records yourself; the script score is a triage signal, not a legal conclusion.
- Distinguish genuine technical differences from wording changes. Do not disguise copied or known technology through paraphrasing.
- Ask the user to confirm any new technical feature that was not present in their intake before including it as their solution.

### 4. Load Exactly One Fixed Prompt

- For `patent`, read only `references/patent-prompt.md`.
- For `software-copyright`, read only `references/software-copyright-prompt.md`.
- Treat the selected fixed prompt as the drafting specification while preserving higher-priority truthfulness requirements.
- Do not dynamically rewrite, merge, or optimize the fixed prompt unless the user explicitly requests prompt maintenance. When prompt maintenance is requested, update the mode-boundary benchmark and the relevant versioned prompt together, then run the full regression suite.

### 4A. Build And Verify Patent Artifacts When Requested

Read `references/patent-artifact-workflow.md` when the patent case includes code, interfaces, diagrams, screenshots, or a runnable prototype.

- A runnable prototype or code asset does not automatically add an engineering-evidence chapter. Enable that chapter only when the user explicitly requests API/interface/code/runtime evidence or the supplied template requires it.

- Treat runnable code, deterministic technical figures, and actual UI screenshots as different evidence classes.
- Generate patent architecture, flow, sequence, data-structure, and formula figures from confirmed structured facts. Prefer deterministic SVG/PNG generation over free-form image generation.
- When confirmed quantitative experiment data exists, prioritize an exact-value result table and a complementary data figure in the relevant implementation/result discussion. Use Altair by default for line, bar, point/scatter, area, box-plot, and heatmap figures; keep structural diagrams on the deterministic diagram renderer. Never infer or manufacture experiment values.
- Capture a UI screenshot only from an actual running implementation. Record the route, viewport, capture time, state/action, file hash, and framing review. The declared evidentiary subject must be fully visible, centered within a safe margin, readable, unobstructed, and free of scroll or edge truncation.
- Never use an image model to fabricate a product screen, test result, waveform, instrument output, or implementation evidence.
- Run `python3 scripts/preflight_patent_artifacts.py INVENTORY_JSON --artifact-root ARTIFACT_ROOT --output PREFLIGHT_JSON` before rendering a code-backed patent sample.
- A generated conceptual illustration may be included only as non-evidentiary material and must be labeled as such; it must not replace a technical drawing or actual screenshot.

### 5. Draft To The Structured Contract

- Produce one drafting response matching `references/data-contracts.md`.
- When its internal status is `needs-information`, do not paste the raw JSON into the conversation. Explain the missing facts in natural Chinese, ask the listed questions directly, update the case record with confirmed answers, and repeat this stage. Do not render templates yet.
- Proceed to document rendering only when its status is `draft-ready` and `scripts/validate_draft.py` reports `render_ready: true`.
- Keep every factual technical statement grounded in the intake or explicitly confirmed follow-up information.
- Require a field-level `evidence_map` for every material fact. Model inference is not evidence.
- For patent mode, draft only `technical-disclosure`; do not draft claims, an abstract, or a final patent application.
- For patent mode, populate `technical-disclosure.disclosure_profile.写作路由` first. Choose three-part or integrated background organization, choose overall prose, stepwise method, or hybrid technical-solution organization from the invention object, and default the engineering-evidence route to `omit`. Separately cover technical field, prior-art evaluation, overall solution, key technical points, at least four evidence-grounded numbered advantages, route-appropriate implementation subsections, high-priority experiment tables/Altair charts when data supports them, other useful figures, and an internal search appendix. Populate `工程实现证据` only for the explicit include route. Never lengthen a disclosure through repetition or invented facts.
- For software-copyright mode, draft `registration-info`, `operation-manual`, `detailed-design`, and `source-code` as four separate documents.
- Use screenshots supplied from the actual software. Never fabricate interface screenshots or claim that a screen was tested when it was not.
- Use the project's actual source code. Never retain or reuse the Java sample code from the layout template.
- Keep the software name, version, features, environment, terminology, screenshots, and code identity consistent across all four documents.
- For software source, distinguish project qualifying lines from lines included in the source document; validate both through `source_selection`.
- Require screenshot-origin/screenshot-framing/source/secret/third-party `artifact_preflight` before software rendering.
- Run `python3 scripts/preflight_software_artifacts.py SOURCE_INVENTORY --source-root PROJECT_ROOT --screenshot IMAGE --confirm-actual-screenshots --confirm-complete-framing --output PREFLIGHT.json`; use the framing confirmation only after every image has been visually checked for complete subject coverage, centering, readability and edge cutoffs, then copy its verified `artifact_preflight` and source counts into the draft.
- Avoid claims that the work is guaranteed original, novel, registrable, patentable, or legally compliant.

### 6. Render Every Required Template

- Read `assets/template-manifest.json` and render every `output_documents` entry for the selected mode.
- Preserve each supplied template's section order, page setup, recurring header/footer, and required fields.
- Bind `draft.json.documents[DOCUMENT_ID].sections` to the matching template; do not silently drop unmatched content.
- For application software, never merge the operation manual and detailed design specification.
- Replace all sample names, versions, screenshots, diagrams, code, examples, and customer data.
- Patent rendering follows the supplied 13-page reference's page geometry and continuous long-form style. Figures flow continuously at an aspect-ratio-aware size; only a genuinely complex tall figure or actual screenshot may request a fresh page. It may produce fewer or more pages depending on verified technical substance; do not pad to a fixed length.
- Visually inspect every rendered page before delivery. Correct legacy-font substitutions where Chinese text is missing.
- On macOS headless rendering, set `FONTCONFIG_FILE=assets/fontconfig-macos.xml` so LibreOffice can discover and embed system Chinese fonts.
- If any required template is absent, stop document delivery and report the precise missing asset.

### 7. Validate And Deliver

- Run `python3 scripts/validate_draft.py DRAFT_JSON` and resolve all errors.
- Run `python3 scripts/scan_delivery_secrets.py DELIVERY_PATH` before creating the final archive.
- Stop delivery when validation reports `render_ready: false`.
- Deliver patent mode as one DOCX named `专利技术交底书.docx`.
- Deliver software-copyright mode as four completed case DOCX files plus the fixed customer-material checklist, and run `python3 scripts/package_deliverables.py OUTPUT_DIR OUTPUT_ZIP` to create `软件著作权登记材料.zip`.
- Deliver the preliminary search report and validation result alongside the requested document package.
- Keep inventor/authorship attribution separate from drafting assistance; do not infer contributors from file authorship or workflow participation.
- Keep machine-readable draft objects in the working directory or pass them directly between scripts. In normal Codex conversation, report progress, missing inputs, validation failures and output paths in natural Chinese. Show raw JSON only when the user explicitly requests the structured contract or a script/debugging task requires it.

## Resources

- `references/patent-prompt.md`: fixed V1.8 routed patent technical-disclosure prompt.
- `references/software-copyright-prompt.md`: fixed V1.5 application-software copyright prompt with template-aligned TOC, layout, screenshot framing, design-diagram, table, and supporting-checklist rules.
- `references/reference-style-benchmark.md`: sample-grounded mode routing, content boundary, vocabulary, and screenshot rules.
- `references/search-and-differentiation.md`: search, evidence, and comparison rules.
- `references/search-api.md`: Responses API web-search configuration and credential isolation.
- `references/data-contracts.md`: JSON contracts and required documents.
- `references/template-map.md`: supplied-template roles, geometry, slots, and fidelity notes.
- `assets/template-manifest.json`: deliverable and template requirements.
- `assets/templates/`: normalized DOCX templates used for generation.
- `assets/source-originals/`: untouched original `.doc` and ZIP source files.
- `assets/fontconfig-macos.xml`: Chinese-font discovery for macOS headless DOCX QA.
- `scripts/check_setup.py`: readiness and template-integrity check.
- `scripts/prior_art_report.py`: deterministic first-pass overlap report.
- `scripts/analyze_public_records.py`: credential-isolated DeepSeek V4 Pro analysis of supplied verified records.
- `scripts/search_public_records.py`: GPT-5.6/API-backed source-verified public-record retrieval.
- `scripts/validate_prior_art.py`: search provenance, record schema, benchmark, and secret-field validation.
- `scripts/scan_delivery_secrets.py`: recursive credential scan for directories and Office/ZIP archives.
- `scripts/preflight_software_artifacts.py`: screenshot, source hash/line-count, secret, and third-party preflight.
- `scripts/requirements-altair.txt`: optional Altair and PNG-export dependencies for quantitative patent charts.
- `scripts/validate_draft.py`: required-document and required-section validation.
- `scripts/render_patent_disclosure.py`: validated patent-draft to supplied-DOCX renderer.
- `scripts/render_software_copyright.py`: validated application-software draft to four supplied-DOCX renderers.
- `scripts/package_deliverables.py`: deterministic software package builder.
