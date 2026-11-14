# Travel Insurance Claims Portal

[Español](README.es.md)

A Flask web app that lists travel insurance claims, policies and clauses read from JSON files on disk, and lets
you run an **AI review agent** on each claim. The agent checks the claim line by line against the policy clauses
and returns a verdict: **Approved**, **Rejected** or **Validate** (needs a human; the agent adds a comment saying
what to check). All data is fictitious.

> The UI and the full documentation ([docs/DOCUMENTACION.md](docs/DOCUMENTACION.md)) are in Spanish.

## What it does

- **Claims list**: up to `MAX_RECLAMACIONES` (100) claims read from `data/claims.json`; search by ID, type, client,
  policy, destination or story text (accent and case insensitive), filter by type, sort and paginate.
- **Claim sheet**: a detailed story (who, what, when, where, how, how much), amount breakdown, the clause that
  applies with its payment requirements and payout percentage per situation, policy, payments and documents.
- **Policies**: 120 policies with plans, coverages, premium payments (some unpaid) and 20 clauses.
- **Review agent** with three interchangeable technologies, all calling the **same Ollama LLM**:

| Technology | How it works |
|---|---|
| **LangGraph** | A graph with one node per requirement plus a verdict node; requirements run in parallel (`LANGGRAPH_CONCURRENCIA`) and are marked live. |
| **Pydantic AI** | One call with typed output (Pydantic models) and automatic retry on invalid output. |
| **Claude Agent SDK** | The agent is *not* given the data: it searches and reads the JSON files itself with `Read`/`Grep`, in sanitized copies inside a temporary folder. |

**Decision criterion** (the same for the rules reviewer and the three agents): (1) the policy premium payments are up
to date; (2) the claim is validated against the insurance clauses (policy in force, coverage included, payout
situation, deadline, documents, coverage requirements, exclusions); (3) the outcome is *pay* (Approved), *do not
pay* (Rejected) or *review by hand* (Validate). The agent does not judge whether the story is plausible or unusual.

Each claim sheet has a button per technology, plus **Run all 3 and compare**, which shows verdict, payout, duration,
calls, tokens, agreement with the rules reviewer, and a per-line matrix highlighting disagreements. The list page
has a technology picker and a *Review* button on every row. Two baseline architectures (line by line, single call)
and a deterministic rules reviewer are also included.

## Agent results are virtual

Results are streamed to the browser while they are computed and live **only in the page**. Nothing is written to a
file or database (nor `localStorage`/`sessionStorage`); **refreshing the page resets everything**. If the browser
leaves mid-run, the server discards the run. `bench.py` prints its summary and stores nothing either.

## Quick start

```bash
pip install -r requirements.txt
pip install -r requirements-extra.txt   # LangGraph, Pydantic AI, Claude Agent SDK (optional)
cp .env.example .env                    # then fill in the values
sh scripts/instalar_hooks.sh            # enables the private-data check on commit and push
python3 generate_data.py                # regenerate the fictitious JSON data (optional)
python3 app.py                          # serves on HOST:PORT from .env
```

To use the agents you need an Ollama server (`OLLAMA_URL`, `OLLAMA_TOKEN`, `OLLAMA_MODEL`). The Claude Agent SDK
needs the server to accept the Anthropic Messages protocol, which Ollama does. With `AGENT_MODE=reglas` the app runs
without any LLM, using the rules reviewer.

## Configuration

**Everything variable lives in `.env`; the code has no default values.** If a required variable is missing the app
refuses to start and lists what is missing. `.env.example` documents every variable with no secrets. Main groups:

| Group | Variables |
|---|---|
| App and server | `APP_NAME`, `APP_TAGLINE`, `APP_USER_NAME`, `APP_USER_ROLE`, `HOST`, `PORT`, `FLASK_DEBUG`, `PER_PAGE_OPTIONS` |
| Data | `CLAIMS_FILE`, `POLICIES_FILE`, `CLAUSES_FILE`, `MAX_RECLAMACIONES` |
| Agent | `AGENT_MODE`, `AGENT_ARCH`, `MAX_CORRIDAS_SIMULTANEAS` |
| Ollama | `OLLAMA_URL`, `OLLAMA_TOKEN`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`, `OLLAMA_REINTENTOS`, `OLLAMA_TEMPERATURE` |
| Technologies | `LANGGRAPH_CONCURRENCIA`, `PYDANTIC_REINTENTOS`, `CLAUDE_SDK_MAX_TURNOS`, `CLAUDE_SDK_HERRAMIENTAS` |

## Benchmark and tests

```bash
python bench.py --n 10 --reglas --arq langgraph,pydantic_ai,claude_sdk   # compare technologies, prints a summary
python3 -m unittest discover -s tests                                     # regression and isolation tests
```

Agreement with the rules reviewer is a reference, not ground truth: the rules reviewer is deterministic but does not
judge the clause exclusions (only the LLM does, and it never rejects on its own), and LLM verdicts can vary between runs even at temperature 0.

## Safety: nothing private goes to GitHub

`scripts/validar_subida.py` runs on every commit and push (via `.githooks/`) and blocks the operation if it finds
secrets, tokens, URLs, IPs or default values hardcoded in code, real emails, personal paths, files such as `.env`,
or any value from your local `.env` inside a tracked file. It scans every commit being pushed, not just the last one.
Run it by hand with `python3 scripts/validar_subida.py --todo`. Hooks are local: each clone must run
`sh scripts/instalar_hooks.sh`.

## Project layout

| Path | Purpose |
|---|---|
| `app.py` | Flask routes, filters, pagination and the live review stream |
| `agent.py` | Review agent: lines to check, rules reviewer, LLM calls, statistics |
| `arq_langgraph.py`, `arq_pydantic_ai.py`, `arq_claude_sdk.py` | The three compared technologies |
| `config.py` | Reads and validates `.env`; the only place `os.environ` is read |
| `static/agente.js` | Browser client: receives the stream and draws lines, verdict, stats and comparison |
| `generate_data.py` | Generates the fictitious claims, policies and clauses |
| `corridas.py`, `bench.py` | In-memory statistics and the benchmark CLI |
| `scripts/`, `.githooks/` | Private-data validation and its git hooks |
| `tests/` | Regression and isolation tests |
