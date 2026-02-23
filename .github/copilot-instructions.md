# GitHub Copilot Instructions for the CDC‑Dashboard Repository

This repository is a small but feature‑rich **AI‑driven COVID‑19 dashboard**.  Your goal as an AI coding agent is to make changes that fit into the existing modular architecture, honour the data‑flow and follow the conventions already established by the human author.

---
## 🔍 Big‑Picture Architecture

1. **Data ingestion → processing → analysis → dashboard.**
   - `data_ingest.py` fetches a CSV from the CDC API and writes `cdc_data.csv`.
   - `processing.py` contains simple filters (e.g. `filter_recent_years`).
   - `analysis.py` aggregates by year (`summarize_covid_deaths`).
   - `dashboard.py` uses Matplotlib to plot the summary; the Streamlit UI in `app.py` calls all of these.

2. **Streamlit user interface (`app.py`).**
   - Buttons drive the flow (fetch, build/load vector DB, run RAG query).
   - RAG functionality is co‑located here for simplicity but duplicates logic in `rag_pipeline.py`.

3. **RAG / vector‑store modules.**
   - `rag_pipeline.py` and `vector_database.py` show how Chroma/Embeddings are initialized, persisted, and queried.
   - `langchain_utils.py` and `prompt_templates.py` contain reusable LLM helpers and prompt builders.

4. **Agentic & prompt engineering support.**
   - Future LangGraph/crewai agents belong here; refer to the example in `requirements.txt` and `prompt_templates.py` for patterns.

5. **Deployment & orchestration.**
   - A Docker‑Compose stack is implied by the README/docs (not present yet).  Airflow DAGs should be placed under `airflow/dags/` when added; the Python packages in `requirements.txt` reflect this.

> **Data flow summary:** CSV download → pandas → summary dataframe → Matplotlib/Streamlit for EDA; text strings from the same data are split, embedded, and stored in Chroma for semantic queries.

---
## 🛠 Developer Workflows

- **Environment setup:**
  ```sh
  python -m venv .venv           # Python 3.10+ (see workspace `.python-version`)
  source .venv/bin/activate
  pip install -r requirements.txt
  ```
  `deps.txt`/`old_packages.txt` are legacy; `requirements.txt` is authoritative.

- **Run the UI:**
  ```sh
  streamlit run app.py           # launches the interactive dashboard
  # or
  python main.py                 # quick CLI exercise used in tests/examples
  ```

- **Build/query the vector store:**
  ```sh
  python rag_pipeline.py         # creates `chroma_db` and demonstrates a query
  ```
  The Streamlit app repeats this logic.

- **Lint & format:**
  - `black` is used for formatting. Run `black .` before committing.
  - `flake8` checks for style; configuration is minimal but enforced via CI.

- **Testing:**
  - There are no project tests yet.  New modules should include simple `pytest` functions under a `tests/` directory.
  - Use `python -m pytest -q` to run whatever tests exist.

- **Airflow:**
  - When you add DAGs they should import from `data_ingest`, `processing`, etc.
  - The DAG schedule and dependencies live in `airflow/dags/`, but the repo currently has no DAGs; refer to the `docs/project_plan.md` for the envisioned daily ETL.

- **Deployment:**
  - The README in `/docs` explains the Docker‑Compose stack (`Dockerfile`, `docker-compose.yml` not yet committed).
  - Streamlit Cloud is the target environment; lightweight images are required because build timeouts have happened in the past.

- **Environment variables:**
  - The only required env var is `OPENAI_API_KEY`.  `app.py` and `rag_pipeline.py` both read it directly; add it to GitHub Actions secrets for CI.

---
## 🧩 Project‑Specific Conventions

- **Modular naming:** each file exports a single domain‑specific function (e.g. `fetch_cdc_data`, `filter_recent_years`).  Keep this pattern when adding new capabilities.

- **Print/logging:** lightweight stdout `print` statements are used for debugging rather than logging frameworks.

- **Vector‑store directories:**
  - `chroma_cdc_data` is the default for the UI; `rag_pipeline` uses `chroma_db`.  When extending, pass `persist_dir` as an argument.

- **Prompt templates:** store one functional prompt per helper in `prompt_templates.py` and call them from UI or agent code rather than hard‑coding strings.

- **Requirements file style:** sections separated by comments to group related dependencies.  Add new packages in the appropriate block.

- **Data files** are minimal (`cdc_data.csv`); treat them as ephemeral and regenerate rather than commit large datasets.

---
## 🔗 Integration Points & External Dependencies

- **CDC open data** is the sole external data source; the default `fetch_cdc_data` URL can be overridden for testing.

- **LangChain / OpenAI** are used for all LLM functionality.  The `langchain-*` packages are pinned tightly; be cautious when updating because breaking changes are common.

- **Chroma** or `faiss-cpu` backends are optional; the code currently only uses Chroma.

- **Airflow** is listed in dependencies; actual orchestration code should depend only on the functions in this repo so that DAGs remain simple.

- **Docker** is used for deployment; tests should avoid relying on Docker unless explicitly marked.

---
## ✅ When You’re Stuck or Adding Features

1. **Scan for similar code** – many modules serve as templates (see `rag_pipeline.py` for any LangChain work, `vector_database.py` for embedding helpers, etc.).
2. **Follow the existing data flow.**  New features should not break the core `fetch → process → summarize → plot` pipeline.
3. **Update documentation.**  Add short examples to the README or `docs/` when you add new functionality, and mention any new environment variables.
4. **Ask for clarification.**  If uncertain about the “why” behind a structural decision, refer to `docs/project_plan.md` or ask the human maintainer (@nvnmpudi‑droid).  The architecture is intentionally simple to make onboarding fast.

---

Please ask the user if any sections are unclear or if other project details should be added.