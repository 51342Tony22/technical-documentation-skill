# Supplied Template Map

Use these converted DOCX files as the working templates. Keep the original `.doc` and ZIP files unchanged in `assets/source-originals/`.

## Patent Technical Disclosure

- Template: `assets/templates/patent-technical-disclosure.docx`
- SHA-256: `adb922ad76ae4fbaeec1d79e9f0c42aaae2cec584d80583ea84b89bb62d7b67c`
- Reference rendered pages: 13; sections: 1.
- Page system: A4 portrait; 1.25-inch left/right margins and 1-inch top/bottom margins; centered page number.
- Role: long-form computer-related patent technical disclosure, not a final patent application.
- Editable slots: application metadata, technical field, prior-art evaluation, defects, invention-formation process, key points/effects, detailed embodiments, tables, figures, and search appendix.
- Preserve: page geometry, continuous narrative style, heading hierarchy, table/caption rhythm, footer, and annex sequence.
- Remove or replace: every reference-project name, person, contact detail, technical statement, formula, parameter, table value, screenshot, waveform, and drawing. The distributed template is rebuilt from a blank DOCX with matching page geometry, so no unreferenced reference-project media remains in its package.

## Software Registration Information

- Template: `assets/templates/software-registration-info.docx`
- SHA-256: `687c0f4ff05508bdf0dc356b59a3ecb5271806b4b3b760a080a8290f920e89c0`
- Rendered pages: 3; sections: 1.
- Page system: A4 portrait; 1.25-inch left/right margins and 1-inch top/bottom margins.
- Editable slots: software identity, dates, publication status, development method, copyright owner, environments, language, line count, purpose, industry, functions, and technical characteristics.
- Preserve: table grid, option fields, labels, and explanatory notes.
- Remove or replace: every preselected sample option and sample owner value that does not match the case.

## Software Operation Manual

- Template: `assets/templates/software-operation-manual.docx`
- SHA-256: `628379d89bf263d41040acdc36366eb500f2c7cae08061401eb180a3cd1a3f7d`
- Rendered pages: 17; sections: 2.
- Page system: A4 portrait; 1.25-inch left/right margins and 1-inch top/bottom margins.
- Role: step-by-step operation manual with full-window screenshots and matching explanatory text.
- Editable slots: cover, name/version, table of contents, introduction, software overview, requirements, module operations, screenshots, captions, and navigation steps.
- Preserve: heading hierarchy, page headers/footers, numbering, TOC structure, screenshot/caption rhythm, and section breaks.
- Remove or replace: the warehouse-management example, all screenshots, company names, functions, and old Windows requirements.

## Software Detailed Design Specification

- Template: `assets/templates/software-detailed-design.docx`
- SHA-256: `a10950e164a3d9685b01c9a3aabe3642da8def5d445e89eb66bfc84fbeb0245e`
- Rendered pages: 21; sections: 1.
- Page system: A4 portrait; 1.25-inch left/right margins and 1-inch top/bottom margins.
- Role: architecture, module, data, interface, algorithm, and flow design document.
- Editable slots: cover, TOC, introduction, background, architecture diagrams, modules, functions, constraints, data tables, interfaces, algorithms, flows, and exception handling.
- Preserve: heading hierarchy, table styles, diagram-caption patterns, page geometry, and footer behavior.
- Remove or replace: all production-simulation examples, diagrams, formulas, tables, software names, and project-specific data.

## Software Source Code

- Template: `assets/templates/software-source-code.docx`
- SHA-256: `e37a1e3da81c27fdafc878ba78e34d9838a804a4bc043f5166d0c5a6ad4462e5`
- Rendered pages: 60; sections: 1.
- Page system: A4 portrait; 1.25-inch left/right margins and 0.87-inch top/bottom margins.
- Role: source-code layout with repeated software name/version header and page numbers.
- Editable slots: repeated header and every source-code line on all 60 pages.
- Preserve: margins, code typography, header line, page numbering, and approximately 50 lines per page.
- Remove or replace: all bundled JUnit/FCKeditor Java sample code. Never reuse it as applicant source code.

## Materials Checklist

- Template: `assets/templates/software-materials-checklist.docx`
- SHA-256: `a3defb263532a04d4cf2c8668aba826aa1c50e574ebe0f5dc03b60f44f0fed18`
- Rendered pages: 3; sections: 1.
- Role: project-side reference for required screenshots, code-page layout, and supporting materials. Do not treat it as applicant-authored software content.

## Source Package

- Original ZIP: `assets/source-originals/software-package-original.zip`
- SHA-256: `68f00079e531eb594167f46251db1f816c7eb9afc78c250e9a7118887e73d452`

## Fidelity Notes

- The legacy source files use fonts that were unavailable in the headless render environment; rendered Chinese text showed substitution or missing-glyph boxes on some pages even though text extraction remained intact.
- Before delivering a generated document, use an available Chinese font consistently, rerender every page, and verify that no Chinese glyph is missing.
- Treat every supplied example as layout guidance only. Replace all sample prose, screenshots, diagrams, tables, names, dates, environments, and code with case-grounded material.
