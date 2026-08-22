# cerulean-beginnings

A build-scheduling tool for manufacturing assembly. Models a Bill of Materials + assembly
steps as a dependency graph, tracks live completion progress, and surfaces what's unlocked,
what's blocking progress, and where schedule risk actually is via Critical Path Method (CPM).

## Structure

- `core/` — pure Python algorithmic layer (models, parsing, graph construction, cycle
  detection, topological sort, CPM forward/backward pass, derived reporting). No FastAPI or
  file-system dependencies beyond loading the input JSON, so it's fully unit-testable on its
  own.
- `api/` — FastAPI layer. Thin wrapper around `core/` — no algorithm logic lives here.
- `frontend/` — single-page HTML/JS UI.
- `data/` — example dataset(s), JSON.
- `tests/` — pytest suite for the `core/` layer.

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate   # or source .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"
```

## Tests

```bash
pytest
```

## Run the API

```bash
uvicorn api.main:app --reload
```

Endpoints currently implemented (backed by `core/graph.py` — cycle detection, topological
sort, and reachability): `GET /steps`, `GET /steps/{id}`, `GET /steps/{id}/impact`,
`POST /steps/{id}/complete`, `POST /parts/{id}/increment`, `GET /build-order`,
`GET /validation`.

Not yet implemented, pending `core/cpm.py` and `core/derived.py`: `GET /critical-path`,
`GET /progress`, `GET /recommended-next`.
