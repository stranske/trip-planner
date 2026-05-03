from pathlib import Path


def test_frontend_prereq_checks_use_local_npm_exec_without_resolution() -> None:
    script_path = Path("scripts/check_full_stack_runtime.sh")
    content = script_path.read_text(encoding="utf-8")

    assert "npm --prefix frontend exec --no -- vitest --version" in content
    assert "npm --prefix frontend exec --no -- vite --version" in content
