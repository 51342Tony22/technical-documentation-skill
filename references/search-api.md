# Search API Integration

Use `scripts/search_public_records.py` when an OpenAI API key and network access are available. The script calls the Responses API with the web-search tool, requests structured records, and rejects any record URL that is not present in the API's returned search sources.

The API is a discovery layer, not a patent-office database. For Chinese filing-oriented work, verify retained Chinese records in the CNIPA Patent Search and Analysis System when accessible. Use PATENTSCOPE and Espacenet to supplement PCT, family, citation, and foreign-publication coverage. Record any login, JavaScript, anti-bot, or rate-limit restriction instead of claiming that the database was searched successfully.

## Configuration

Set credentials outside the project:

```bash
export OPENAI_API_KEY="YOUR_API_KEY"
export OPENAI_SEARCH_MODEL="gpt-5.6"
```

Optional custom compatible endpoint:

```bash
export OPENAI_BASE_URL="https://api.openai.com/v1"
```

Do not put credentials in `case.json`, Prompt files, shell history, `.env` files inside the Skill, generated reports, screenshots, source inventories, or delivery archives. For a one-time local run, use `--api-key-stdin` so the key is not included in process arguments.

## Run

```bash
python3 scripts/search_public_records.py case.json \
  --output prior_art.json
```

The generated `prior_art.json` records the provider, model, API response ID, query groups, source-verification status, and token counts. It never records the credential or authorization header. The request uses `store: false`.

Validate the normalized result before reporting:

```bash
python3 scripts/validate_prior_art.py prior_art.json --case case.json
```

## Required Review

- Open every cited record before relying on its abstract or matching-feature list.
- Verify Chinese publication number, applicant, date, full text, drawings, and displayed legal status against CNIPA where accessible.
- Verify PCT records against WIPO PATENTSCOPE and use Espacenet for international family/citation supplementation.
- Treat Google Patents as a convenience cross-check only; do not use it as the sole authority for Chinese legal status.
- Prefer official patent-office or publisher pages where accessible.
- Preserve close or adverse records.
- Treat the API result as discovery evidence, not as a novelty, inventiveness, freedom-to-operate, or legal opinion.
- Run `scripts/scan_delivery_secrets.py DELIVERY_PATH` before packaging.

Official implementation references:

- `https://developers.openai.com/api/reference/typescript/resources/beta/subresources/responses/methods/create`
- `https://developers.openai.com/api/docs/models/gpt-5.6-sol`

## Compatible Analysis API

When retrieval records already exist, `scripts/analyze_public_records.py` can use an
OpenAI-compatible chat endpoint to rank and compare only those verified records. Its
default configuration is SiliconFlow with `deepseek-ai/DeepSeek-V4-Pro`:

```bash
export ANALYSIS_API_KEY="YOUR_API_KEY"
export ANALYSIS_MODEL="deepseek-ai/DeepSeek-V4-Pro"
python3 scripts/analyze_public_records.py case.json prior_art.json \
  --output model-analysis.json
```

For one-time use, pass `--api-key-stdin` instead of exporting a key. The output stores
the provider, model, response ID, source scope, and token totals, but never the key or
authorization header. This API stage performs comparison, not database retrieval; all
analyzed record IDs must already exist in the validated `prior_art.json`.
