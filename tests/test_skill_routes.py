def test_skill_routes_exist():
    from sieve.api.skills.routes import router

    paths = [r.path for r in router.routes]
    assert "/api/skills/" in paths  # list
    assert "/api/skills/{skill_id}" in paths  # get, update, delete
    assert "/api/skills/compile" in paths
    assert "/api/skills/{skill_id}/export" in paths
    assert "/api/skills/{skill_id}/recompile" in paths
