import local_subagent.__main__ as cli


def test_main_runs_server(monkeypatch):
    calls: list[str] = []

    class FakeServer:
        def run(self) -> None:
            calls.append("run")

    monkeypatch.setattr(cli, "create_server", lambda: FakeServer())

    assert cli.main() == 0
    assert calls == ["run"]
