# Patent Artifact Workflow

Use this workflow only when a patent disclosure is supported by code, interfaces, diagrams, screenshots, logs, or a runnable prototype.

## Evidence Classes

1. `source-code`: project-owned implementation files. Record relative path, purpose, language, line count, and SHA-256.
2. `generated-technical-figure`: a deterministic figure generated from confirmed architecture, steps, data structures, formulas, or interface relationships. Record generator, blueprint, and SHA-256.
3. `actual-runtime-screenshot`: a screenshot captured from a running implementation. Record route, viewport, capture time, triggering action/state, framing review, and SHA-256.
4. `public-source`: a retrieved patent or public technical record with stable identifier and URL.
5. `conceptual-non-evidence`: optional illustrative material. Never use it to prove an implementation, result, measurement, or UI.

## Required Sequence

1. Inventory project-owned source and exclude dependencies, generated bundles, credentials, and third-party code.
2. Define interface contracts before drafting prose: method, route or topic, request fields, response fields, error states, and the module that implements the interface.
3. Define one end-to-end workflow linking input, processing, decision, state transition, output, and failure path.
4. Generate technical figures from a reviewed blueprint. Use Altair by default for confirmed quantitative experiment charts and the structural renderer for architecture, flow, sequence, module, data-structure, and formula figures. Do not ask an image model to invent labels, arrows, formulas, values, or component relationships.
5. Run the implementation, exercise the workflow, and capture only actual visible states. Screenshots must not contain secrets, personal data, or misleading production labels. Before acceptance, visually confirm that the declared subject is fully visible, centered with a safe margin, readable, unobstructed, and not cut by an edge or scroll container.
6. Build `artifact-inventory.json`, then run `scripts/preflight_patent_artifacts.py`.
7. Map each material statement or figure to an inventory artifact ID. Populate `disclosure_profile.工程实现证据` only when the writing route explicitly requests the dedicated engineering-evidence chapter.
8. Render the DOCX and visually inspect every page. Verify figure readability, captions, screenshot provenance, and page utilization.

## Screenshot Rule

A screenshot is implementation evidence only when the corresponding file exists, its hash is recorded, its origin is marked `actual-runtime-screenshot`, and the capture metadata identifies a reproducible route and state. Its `framing_review` must name the evidentiary subject and attest that `full_subject_visible`, `centered`, `text_readable`, `no_occlusion`, and `no_scroll_cutoff` are all true. These fields record a completed visual review; they are not inferred merely from image dimensions. A mockup, generated image, edited composite, cropped screen, or manually drawn screen must not be labeled as an actual screenshot.

If the whole application cannot fit in one readable image, capture separate unaltered runtime views with explicit subjects instead of cutting a subject in half. Every caption may rely only on controls, labels, nodes, links, and states that are completely visible in that screenshot.

## Image Generation Rule

Patent figures should normally be code-generated line drawings or exported vector diagrams. Free-form image generation is suitable only for clearly labeled conceptual illustrations outside the evidentiary chain. It must never generate or alter performance charts, logs, waveforms, screenshots, experimental results, or patent-critical component relationships.

## Experimental Figure And Table Rule

When verified experimental or measured data is present, prioritize both an exact-value result table and a complementary chart near the supported embodiment or result discussion. Generate quantitative charts with Altair from a self-contained, reviewed Vega-Lite-compatible `chart_spec`; disallow external data URLs and map every value to `evidence_refs`. If Altair or `vl-convert-python` is unavailable, retain the blueprint and report the dependency gap rather than substituting an image-model output or an unreviewed chart.
