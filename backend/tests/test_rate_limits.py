def test_authenticated_reads_use_separate_higher_rate_limit(
    client_factory, settings_override
) -> None:
    settings_override(rate_limit_per_minute="2", rate_limit_read_per_minute="600")
    client = client_factory("rate-limited-user")

    for _ in range(61):
        response = client.get("/api/v1/projects")
        assert response.status_code == 200, response.text

    for index in range(2):
        response = client.post("/api/v1/projects", json={"name": f"write-{index}"})
        assert response.status_code == 201, response.text

    blocked = client.post("/api/v1/projects", json={"name": "write-blocked"})
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMITED"
