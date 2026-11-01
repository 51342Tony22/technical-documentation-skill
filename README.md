# Technical Documentation Automation Skill

A reusable Codex Skill for two technical-document workflows:

1. Patent technical disclosures grounded in supplied technical facts and captured public references.
2. Application-software copyright materials, including registration information, operation manual, design specification, and selected source code.

The implementation combines mode-specific prompts, document templates, evidence contracts, deterministic preflight checks, document validation, rendering, and delivery-package checks. Technical disclosures and generated registration materials require substantive human review before external use.

## Contents

- `SKILL.md`: workflow entry point and routing instructions.
- `references/`: mode prompts, data contracts, search interfaces, and template mapping.
- `scripts/`: setup checks, retrieval helpers, validators, DOCX generation, packaging, and regression tests.
- `assets/templates/`: the DOCX templates required by the manifest.
- `assets/template-manifest.json`: template identities and integrity hashes.

This snapshot uses the currently installed local Skill. It includes subsequent prompt/checker adjustments beyond the archived V1.8.2 delivery package. Historical claims of 42 passing tests describe that earlier package; current validation is recorded in `VALIDATION.md`.

## Install and validate

Clone this repository into the personal Skill directory using the folder name `draft-patent-copyright`, or copy it into that directory. A Python environment with `python-docx` is required for the document scripts; Altair chart dependencies are listed separately in `scripts/requirements-altair.txt`.

```bash
python -m pip install python-docx
python scripts/check_setup.py
python scripts/test_skill.py
```

Invoke the installed Skill through Codex with an explicitly selected patent or software-copyright task. Follow the relevant input contract before generating deliverables. Provider keys belong in local environment variables; documentation uses placeholders.

Original supplier archives, filled client examples, source-code submissions, private screenshots, and recordings are excluded. Template files remain necessary runtime assets and have not been assigned a new open-source license.

`SOURCE_SNAPSHOT.json` records selected files as of 2026-11-01. Sensitive literals in API documentation have been replaced with placeholders in this upload copy.
