PY ?= python
CLI := $(PY) -m repo_pulse.cli

.PHONY: install check migrate ingest transform enrich all app test

install:
	$(PY) -m pip install -r requirements.txt

check:
	$(CLI) check

migrate:
	$(CLI) migrate

ingest:
	$(CLI) ingest $(if $(SOURCE),--source $(SOURCE),)

transform:
	$(CLI) transform

enrich:
	$(CLI) enrich

# One process runs migrate -> ingest -> transform -> enrich; a failing step exits non-zero
# and make stops there.
all:
	$(CLI) all

app:
	$(PY) -m streamlit run app/streamlit_app.py

test:
	$(PY) -m pytest -q
