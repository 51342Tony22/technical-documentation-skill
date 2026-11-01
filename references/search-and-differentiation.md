# Preliminary Search And Differentiation

## Search Scope

Search current sources that are accessible and relevant to the case:

- First choice for Chinese records: the CNIPA Patent Search and Analysis System (`https://pss-system.cponline.cnipa.gov.cn/conventionalSearch`). Use it to confirm Chinese bibliographic data, full text, drawings, family/citation information, and legal-status display when accessible.
- International supplementation: WIPO PATENTSCOPE (`https://patentscope.wipo.int/search/en/search.jsf`) for PCT and participating national/regional collections.
- International family and broad prior-art supplementation: EPO Espacenet (`https://worldwide.espacenet.com/`).
- Convenience cross-check: Google Patents (`https://patents.google.com/`). Do not treat its legal-status display as the authoritative Chinese status record.
- Technical papers, standards, product documentation, and public software materials when relevant.

Do not state that a source was searched when it was unavailable, blocked, or returned no verifiable evidence.

When using the configured search API, follow `search-api.md`. API output is accepted only when each retained record URL is cross-checked against a source returned by the web-search call. The model is a query and extraction layer, not the underlying patent database.

Record both `sources_attempted` and `sources_verified`. A JavaScript, registration, rate-limit, or anti-bot failure must be recorded as an access limitation; it must not be reported as a completed database search.

## Query Construction

Create at least three query groups:

1. Problem query: technical object plus the problem being solved.
2. Structure query: key components, their relationships, and the operating sequence.
3. Effect query: mechanism plus measurable or observable technical effect.

For patent cases, add likely classification terms or IPC/CPC codes after finding an initial close record. Run both Chinese and English variants when the field has international publications.

Run the search in widening rounds:

1. Exact title and the most distinctive phrase.
2. Technical object + problem + core relationship.
3. Module/step synonyms and broader function terms.
4. IPC/CPC classification + distinctive feature.
5. Citation and patent-family expansion from the closest records.

Keep a query log with database, date, exact query, result count when visible, retained record IDs, and access notes. The long-form disclosure renders this log in the internal `检索附件`; it is not a substitute for a professional search report.

## Evidence Record

For every record used in the report, capture:

- `record_id`: publication number, DOI, standard number, repository ID, or another stable identifier.
- `title`, `source`, `url`, `publication_date`, and `jurisdiction` when available.
- `abstract`: a short, faithful summary rather than a long quotation.
- `matching_features`: the specific case features apparently disclosed by the source.
- `notes`: uncertainty, inaccessible claims, family relationships, or other limitations.

Omit uncertain metadata or mark it as unknown. Never guess identifiers or dates.

## Differentiation Rules

- Compare technical features, component relationships, process order, data flow, control logic, and technical effects.
- Treat synonyms and reordered wording as potentially equivalent.
- Do not call a wording-only change an innovation.
- Do not generate a feature solely to evade a search result. New features must be technically coherent and confirmed by the user as part of their solution.
- For software copyright, use search findings to avoid copying expression and documentation; do not present novelty as a registration requirement.
- Preserve adverse findings in the report even when they weaken the proposed application.

## Required Limitation

End each report with this meaning:

> This is a preliminary machine-assisted search and similarity analysis based on accessible public information. It is not a legal novelty, inventiveness, freedom-to-operate, patentability, or registration opinion. A patent professional or qualified reviewer should verify the final filing materials and search scope.

## Pilot Case Boundary

- `owned-confidential`: may proceed toward filing materials only after ownership and artifact-use authorization are confirmed.
- `owned-internal-test`: may produce internal draft materials, clearly marked as test material.
- `public-benchmark`: may test search recall and comparison against published ground truth; never produce or label it as the user's filing.
- `synthetic-evaluation`: may test the workflow and rendering, but does not count as a real owned business case.
