"""End-to-end API tests: contract, filtering, sorting, and error locations."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

BRIGHT_CENTER = [[0, 0, 0], [0, 9, 0], [0, 0, 0]]
TWO_HOLES = [
    [0, 0, 0, 0, 0],
    [0, 9, 0, 4, 0],
    [0, 0, 0, 0, 0],
]


def post(payload):
    return client.post("/api/v1/barcode", json=payload)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_happy_path_single_bar():
    response = post({"matrix": BRIGHT_CENTER, "min_persistence": 1})
    assert response.status_code == 200
    body = response.json()
    assert body["matrix"] == {"height": 3, "width": 3}
    assert body["min_persistence"] == 1
    assert body["bar_count"] == 1
    (bar,) = body["bars"]
    assert bar["birth_value"] == 0
    assert bar["death_value"] == 9
    assert bar["persistence"] == 9

    birth_edge = bar["birth_edge"]
    assert birth_edge["kind"] in ("horizontal", "vertical")
    assert birth_edge["value"] == 0
    assert len(birth_edge["endpoints"]) == 2

    death_square = bar["death_square"]
    assert death_square["value"] == 9
    assert len(death_square["corners"]) == 4

    cycle = bar["birth_cycle"]
    assert cycle["edge_count"] == len(cycle["edges"]) == 8
    # Edges are listed in the fixed filtration (reduction) order.
    orders = [edge["order"] for edge in cycle["edges"]]
    assert orders == sorted(orders)
    # The birth edge is the youngest edge of its own birth cycle.
    assert cycle["edges"][-1]["order"] == birth_edge["order"]


def test_cycle_is_even_degree_over_the_wire():
    body = post({"matrix": BRIGHT_CENTER, "min_persistence": 0}).json()
    for bar in body["bars"]:
        parity = {}
        for edge in bar["birth_cycle"]["edges"]:
            for endpoint in edge["endpoints"]:
                key = tuple(endpoint)
                parity[key] = parity.get(key, 0) ^ 1
        assert not any(parity.values())


def test_min_persistence_filters():
    assert post({"matrix": BRIGHT_CENTER, "min_persistence": 9}).json()["bar_count"] == 1
    assert post({"matrix": BRIGHT_CENTER, "min_persistence": 10}).json()["bar_count"] == 0


def test_bars_sorted_by_persistence_descending():
    body = post({"matrix": TWO_HOLES, "min_persistence": 0}).json()
    persistences = [bar["persistence"] for bar in body["bars"]]
    assert persistences == sorted(persistences, reverse=True)
    assert persistences == [9, 4]


def test_zero_persistence_bars_are_excluded():
    body = post({"matrix": [[5, 5], [5, 5]], "min_persistence": 0}).json()
    assert body["bar_count"] == 0
    assert body["bars"] == []


def test_error_matrix_not_a_list():
    response = post({"matrix": "nope", "min_persistence": 0})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_MATRIX"


def test_error_height_out_of_range():
    for matrix in ([[1, 2]], [[1, 2]] * 97):
        response = post({"matrix": matrix, "min_persistence": 0})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_DIMENSIONS"


def test_error_width_out_of_range():
    response = post({"matrix": [[1], [2]], "min_persistence": 0})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_DIMENSIONS"
    response = post({"matrix": [[1] * 97] * 2, "min_persistence": 0})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_DIMENSIONS"


def test_error_non_rectangular_locates_row():
    response = post({"matrix": [[1, 2, 3], [4, 5], [6, 7, 8]], "min_persistence": 0})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "NON_RECTANGULAR"
    assert error["location"]["row"] == 1


def test_error_value_out_of_range_locates_cell():
    matrix = [[0, 0, 0], [0, 70000, 0], [0, 0, 0]]
    response = post({"matrix": matrix, "min_persistence": 0})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALUE_OUT_OF_RANGE"
    assert error["location"] == {"row": 1, "col": 1, "value": 70000}

    matrix[1][1] = 0
    matrix[2][0] = -1
    response = post({"matrix": matrix, "min_persistence": 0})
    assert response.json()["error"]["location"]["row"] == 2
    assert response.json()["error"]["location"]["col"] == 0


def test_error_non_integer_value_locates_cell():
    for bad in (1.5, "7", None, True, [1]):
        matrix = [[0, 0], [0, 0]]
        matrix[1][0] = bad
        response = post({"matrix": matrix, "min_persistence": 0})
        assert response.status_code == 422, bad
        error = response.json()["error"]
        assert error["code"] == "INVALID_VALUE_TYPE"
        assert error["location"] == {"row": 1, "col": 0}


def test_error_row_not_a_list():
    response = post({"matrix": [[1, 2], 3], "min_persistence": 0})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "INVALID_ROW"
    assert error["location"]["row"] == 1


def test_error_min_persistence():
    for bad, code in (
        (-1, "MIN_PERSISTENCE_OUT_OF_RANGE"),
        (65536, "MIN_PERSISTENCE_OUT_OF_RANGE"),
        (1.5, "INVALID_MIN_PERSISTENCE"),
        (True, "INVALID_MIN_PERSISTENCE"),
        ("3", "INVALID_MIN_PERSISTENCE"),
    ):
        response = post({"matrix": BRIGHT_CENTER, "min_persistence": bad})
        assert response.status_code == 422, bad
        assert response.json()["error"]["code"] == code


def test_error_missing_fields():
    response = post({"min_persistence": 0})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "MISSING_FIELD"
    response = post({"matrix": BRIGHT_CENTER})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "MISSING_FIELD"


def test_error_body_not_an_object():
    response = client.post(
        "/api/v1/barcode",
        content="[1, 2, 3]",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PAYLOAD"


def test_error_body_not_json():
    response = client.post(
        "/api/v1/barcode",
        content="{not json",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_JSON"


def test_max_size_matrix_is_accepted():
    matrix = [[(r * 96 + c) % 65536 for c in range(96)] for r in range(96)]
    response = post({"matrix": matrix, "min_persistence": 0})
    assert response.status_code == 200
    body = response.json()
    assert body["matrix"] == {"height": 96, "width": 96}
    assert body["bar_count"] == len(body["bars"])
