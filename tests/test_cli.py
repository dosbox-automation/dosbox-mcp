# This file is part of the dosbox-mcp Project.
# License: GPL-2.0-or-later. Contact: dosbox-mcp@trinity2k.net
#

import httpx
import pytest

from dosbox_mcp import cli
from dosbox_mcp.connection import Connection


@pytest.fixture
def config_path(tmp_path, monkeypatch):
    path = tmp_path / "config.toml"
    monkeypatch.setenv("DOSBOX_MCP_CONFIG", str(path))
    return path


class TestSetup:
    def test_init_writes_template(self, config_path, capsys):
        assert cli.main(["setup", "--init"]) == 0
        assert config_path.is_file()
        assert "binary" in config_path.read_text(encoding="utf-8")
        assert str(config_path) in capsys.readouterr().out

    def test_init_refuses_overwrite(self, config_path, capsys):
        config_path.write_text("port = 9000\n", encoding="utf-8")
        assert cli.main(["setup", "--init"]) != 0
        assert "exists" in capsys.readouterr().err

    def test_flags_write_config(self, config_path, capsys):
        code = cli.main(["setup", "--binary", "/opt/dosbox/dosbox",
                         "--port", "9000", "--mode", "observe"])
        assert code == 0
        text = config_path.read_text(encoding="utf-8")
        assert "/opt/dosbox/dosbox" in text
        assert "port = 9000" in text
        assert "observe" in text

    def test_no_args_prints_current_config(self, config_path, capsys):
        assert cli.main(["setup"]) == 0
        out = capsys.readouterr().out
        assert "port" in out
        assert "8386" in out

    def test_no_args_reports_a_bad_config(self, config_path, capsys):
        config_path.write_text("port = = 1\n", encoding="utf-8")
        assert cli.main(["setup"]) == 2
        assert "malformed" in capsys.readouterr().err

    def test_bad_value_fails_loudly(self, config_path, capsys):
        assert cli.main(["setup", "--port", "99999"]) == 2
        assert "range" in capsys.readouterr().err


class TestProbe:
    def test_reports_config_error(self, config_path, capsys):
        config_path.write_text("port = = 1\n", encoding="utf-8")
        assert cli.main(["probe"]) == 2
        assert "malformed" in capsys.readouterr().err

    def test_no_binary_and_nothing_listening(self, config_path, capsys,
                                             monkeypatch):
        def refused(request):
            raise httpx.ConnectError("connection refused")

        def factory(config):
            return Connection(config, transport=httpx.MockTransport(refused))

        monkeypatch.setattr(cli, "_connection_factory", factory)
        monkeypatch.delenv("DOSBOX_TOKEN_FILE", raising=False)
        assert cli.main(["probe"]) == 1
        out = capsys.readouterr().out
        assert "no binary configured" in out
        assert "not connected" in out

    def test_attaches_to_running_instance(self, config_path, capsys,
                                          monkeypatch, tmp_path):
        token_file = tmp_path / "tok"
        token_file.write_text("0" * 64, encoding="utf-8")
        monkeypatch.setenv("DOSBOX_TOKEN_FILE", str(token_file))

        def routes(request):
            if request.url.path == "/api/v1/dosbox/info":
                return httpx.Response(200, json={
                    "version": "0.84-da3", "features": {"memory": True},
                    "mcp_protocol": "1.0",
                })
            return httpx.Response(404)

        def factory(config):
            return Connection(config, transport=httpx.MockTransport(routes))

        monkeypatch.setattr(cli, "_connection_factory", factory)
        assert cli.main(["probe"]) == 0
        out = capsys.readouterr().out
        assert "0.84-da3" in out
        assert "1.0" in out


def test_default_command_serves(monkeypatch):
    called = []
    monkeypatch.setattr(cli, "_serve", lambda: called.append(True) or 0)
    assert cli.main([]) == 0
    assert called == [True]
