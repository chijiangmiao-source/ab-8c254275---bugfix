# Rock-Core CT H1 Persistence Service

Pure-backend analysis service that computes the **1-dimensional persistence
barcode** of a grayscale core-CT slice. Short-lived noise cracks die as
zero/low-persistence bars; real pores survive a long threshold interval and
show up as high-persistence bars with fully reproducible topological evidence
(birth edge, death square, and the exact birth-cycle edge set).

* No frontend, no online services, no persistent-homology libraries.
* The GF(2) sparse boundary reduction is implemented in-house
  (`app/persistence.py`) and cross-validated against independent
  persistent-Betti-number rank computations (`tests/`).
* Runs with Docker / Docker Compose; health check included; the host port is
  configurable through an environment variable.

## Mathematical model

For an `H x W` integer gray matrix `g` (2 ≤ H, W ≤ 96, 0 ≤ g ≤ 65535) the
lower-star cubical filtration is built from cells

| cell             | count              | filtration value                    |
|------------------|--------------------|-------------------------------------|
| vertex `(r,c)`   | `H * W`            | `g[r][c]`                           |
| horizontal edge  | `H * (W-1)`        | `max(g[r][c], g[r][c+1])`           |
| vertical edge    | `(H-1) * W`        | `max(g[r][c], g[r+1][c])`           |
| square `(r,c)`   | `(H-1) * (W-1)`    | max of the 4 corner vertices        |

Cells enter the filtration in ascending value; ties are broken by cell kind
(**vertex → horizontal edge → vertical edge → square**) and then by row and
column. This total order is a valid filtration (faces always precede their
cofaces), and it is the fixed order in which the GF(2) sparse boundary
reduction consumes the cells.

A 1-dimensional bar is a pair *(birth edge `e`, death square `s`)* produced by
the reduction. Only bars with `death_value > birth_value` and
`persistence = death_value - birth_value >= min_persistence` are reported.

For every bar the API returns the **birth cycle**: the reduced boundary of the
death square — a closed edge chain with three guaranteed properties:

1. at the birth threshold its edges form an even-degree closed chain
   (every grid vertex is incident to an even number of them);
2. it does not exist at any earlier threshold (the birth edge is the unique
   youngest edge of the chain);
3. it is annihilated exactly when the reported death square enters (the chain
   bounds no square combination below the death square, and bounds one — which
   includes the death square — at the death threshold).

Bars are sorted by persistence descending, ties adjudicated by birth value and
then cell (filtration) order.

## API

### `GET /health`

Liveness/readiness probe: `{"status": "ok"}`.

### `POST /api/v1/barcode`

Request body:

```json
{
  "matrix": [[0, 0, 0], [0, 9, 0], [0, 0, 0]],
  "min_persistence": 1
}
```

Response `200 OK` (abridged):

```json
{
  "matrix": {"height": 3, "width": 3},
  "min_persistence": 1,
  "bar_count": 1,
  "bars": [
    {
      "birth_value": 0,
      "death_value": 9,
      "persistence": 9,
      "birth_edge": {
        "kind": "vertical", "row": 1, "col": 2,
        "endpoints": [[1, 2], [2, 2]],
        "value": 0, "order": 25
      },
      "death_square": {
        "row": 1, "col": 1,
        "corners": [[1, 1], [1, 2], [2, 1], [2, 2]],
        "value": 9, "order": 44
      },
      "birth_cycle": {
        "edge_count": 8,
        "edges": [ {"kind": "horizontal", "row": 0, "col": 0, "endpoints": [[0,0],[0,1]], "value": 0, "order": 13}, "..."]
      }
    }
  ]
}
```

* `order` is the cell's position in the fixed filtration order — together with
  the documented tie-breaking rules it makes every reported artifact
  reproducible offline.
* `birth_cycle.edges` is listed in the fixed reduction (filtration) order; the
  last edge is always the birth edge.

### Errors

Invalid input yields a structured error with a precise location, HTTP 422
(or 400 for malformed bodies):

```json
{
  "error": {
    "code": "VALUE_OUT_OF_RANGE",
    "message": "matrix[1][0] = 70000 is outside the allowed gray range [0, 65535].",
    "location": {"row": 1, "col": 0, "value": 70000}
  }
}
```

Codes: `INVALID_JSON`, `INVALID_PAYLOAD`, `MISSING_FIELD`, `INVALID_MATRIX`,
`INVALID_DIMENSIONS`, `INVALID_ROW`, `NON_RECTANGULAR`, `INVALID_VALUE_TYPE`,
`VALUE_OUT_OF_RANGE`, `INVALID_MIN_PERSISTENCE`, `MIN_PERSISTENCE_OUT_OF_RANGE`.

## Run with Docker Compose

```bash
docker compose up --build
# service on http://localhost:8000  (GET /health, POST /api/v1/barcode)
```

Configure the **host** port through the environment:

```bash
API_PORT=9090 docker compose up --build   # http://localhost:9090
```

`APP_PORT` overrides the container-side listen port as well (the Compose port
mapping and healthcheck follow it automatically).

## Run with plain Docker

```bash
docker build -t core-ct-h1 .
docker run --rm -p 8000:8000 core-ct-h1
```

The image defines a `HEALTHCHECK` that probes `GET /health`.

## Local development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
.venv/bin/python -m pytest tests/ -q
```

The test-suite verifies, for every computed bar and on randomized and
structured matrices, the three topological guarantees above, and cross-checks
the full barcode against persistent Betti numbers computed with independent
GF(2) rank linear algebra.

## Layout

```
app/
  filtration.py    # lower-star cubical filtration + fixed cell order
  persistence.py   # in-house GF(2) sparse boundary reduction -> H1 bars
  service.py       # analysis pipeline, invariant re-checks, response payload
  validation.py    # request validation with located structured errors
  errors.py        # structured error type
  main.py          # FastAPI wiring: /health, /api/v1/barcode
tests/             # invariants, ground-truth cross-checks, API contract tests
```
