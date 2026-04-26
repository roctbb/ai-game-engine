def test_run_watch_context_returns_renderer_metadata(client, teacher_headers) -> None:
    games = client.get("/api/v1/games", headers=teacher_headers).json()
    game = next(item for item in games if item["slug"] == "maze_escape_v1")

    team = client.post(
        "/api/v1/teams",
        headers=teacher_headers,
        json={
            "game_id": game["game_id"],
            "name": "Watch Team",
            "captain_user_id": "captain-watch",
        },
    ).json()

    run = client.post(
        "/api/v1/runs",
        headers=teacher_headers,
        json={
            "team_id": team["team_id"],
            "game_id": game["game_id"],
            "requested_by": "captain-watch",
            "run_kind": "single_task",
        },
    ).json()

    response = client.get(f"/api/v1/runs/{run['run_id']}/watch-context")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == run["run_id"]
    assert payload["game_slug"] == "maze_escape_v1"
    assert payload["game_title"] == game["title"]
    assert payload["renderer_entrypoint"] == "renderer/index.html"
    assert payload["renderer_url"] == "/api/v1/renderers/maze_escape_v1/renderer/index.html"
    assert payload["renderer_protocol"] == "v1"
    assert payload["participants"] == [
        {
            "run_id": run["run_id"],
            "team_id": team["team_id"],
            "display_name": "Watch Team",
            "captain_user_id": "captain-watch",
            "is_current": True,
        }
    ]


def test_private_catalog_requires_session(client) -> None:
    response = client.get("/api/v1/games", headers={"X-Test-No-Session": "1"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_renderer_asset_endpoint_serves_renderer_files(client) -> None:
    html_response = client.get("/api/v1/renderers/maze_escape_v1/renderer/index.html")
    assert html_response.status_code == 200
    assert "text/html" in html_response.headers.get("content-type", "")
    assert "Maze Escape Renderer" in html_response.text

    svg_response = client.get("/api/v1/renderers/maze_escape_v1/renderer/maze.svg")
    assert svg_response.status_code == 200
    assert "svg" in svg_response.headers.get("content-type", "")
    assert "<svg" in svg_response.text


def test_renderer_asset_endpoint_blocks_non_renderer_paths(client) -> None:
    response = client.get("/api/v1/renderers/maze_escape_v1/engine.py")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
