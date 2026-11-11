# This file is part of the dosbox-mcp Project.
# License: GPL-2.0-or-later. Contact: dosbox-mcp@trinity2k.net
#

import os

import pytest

from dosbox_mcp.config import (
    Config,
    ToolProtectedKey,
    update_config_file,
    validate_base_url,
    write_config_template,
)


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8386",
    "http://localhost:8386",
    "https://[::1]:8386",
])
def test_loopback_urls_accepted(url):
    assert validate_base_url(url) == url


@pytest.mark.parametrize("url", [
    "http://10.0.0.5:8386",
    "http://example.com:8386",
    "ftp://127.0.0.1:8386",
    "127.0.0.1:8386",
])
def test_non_loopback_or_bad_scheme_rejected(url):
    with pytest.raises(ValueError):
        validate_base_url(url)


class TestConfigLoad:
    def test_defaults_without_config_file(self, monkeypatch):
        monkeypatch.delenv("DOSBOX_TOKEN_FILE", raising=False)
        cfg = Config.load()
        assert cfg.port == 8386
        assert cfg.base_url == "http://127.0.0.1:8386"
        assert cfg.mode == "full"
        assert cfg.headless is False
        assert cfg.binary is None
        assert cfg.protocol is None
        assert cfg.token_file is None

    def test_toml_values_loaded(self, tmp_path, monkeypatch):
        toml = tmp_path / "config.toml"
        toml.write_text(
            'binary = "/opt/dosbox/dosbox"\n'
            "port = 9000\n"
            "headless = true\n"
            'protocol = "1.0"\n'
            'mode = "observe"\n'
            f'token_file = "{tmp_path / "tok"}"\n',
            encoding="utf-8",
        )
        monkeypatch.setenv("DOSBOX_MCP_CONFIG", str(toml))
        monkeypatch.delenv("DOSBOX_TOKEN_FILE", raising=False)
        cfg = Config.load()
        assert str(cfg.binary) == "/opt/dosbox/dosbox"
        assert cfg.port == 9000
        assert cfg.base_url == "http://127.0.0.1:9000"
        assert cfg.headless is True
        assert cfg.protocol == "1.0"
        assert cfg.mode == "observe"
        assert cfg.token_file == tmp_path / "tok"

    def test_toml_paths_expand_the_home_folder(self, tmp_path, monkeypatch):
        # The config template shows token_file starting with ~.
        toml = tmp_path / "config.toml"
        toml.write_text('token_file = "~/emulator/api_token"\n'
                        'binary = "~/bin/dosbox-automation"\n', encoding="utf-8")
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        monkeypatch.setenv("DOSBOX_MCP_CONFIG", str(toml))
        monkeypatch.delenv("DOSBOX_TOKEN_FILE", raising=False)
        cfg = Config.load()
        assert cfg.token_file == tmp_path / "emulator" / "api_token"
        assert cfg.binary == tmp_path / "bin" / "dosbox-automation"

    @pytest.mark.skipif(os.name == "nt", reason="Windows maps ~user to a profile path without checking it")
    def test_an_unknown_home_folder_is_a_config_error(self, tmp_path, monkeypatch):
        toml = tmp_path / "config.toml"
        toml.write_text('token_file = "~nosuchuser_zq/api_token"\n', encoding="utf-8")
        monkeypatch.setenv("DOSBOX_MCP_CONFIG", str(toml))
        monkeypatch.delenv("DOSBOX_TOKEN_FILE", raising=False)
        with pytest.raises(ValueError, match="token_file"):
            Config.load()

    def test_env_token_file_expands_the_home_folder(self, tmp_path, monkeypatch):
        # An MCP client's JSON env block reaches the bridge without a shell.
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        monkeypatch.setenv("DOSBOX_MCP_CONFIG", str(tmp_path / "none.toml"))
        monkeypatch.setenv("DOSBOX_TOKEN_FILE", "~/emulator/api_token")
        assert Config.load().token_file == tmp_path / "emulator" / "api_token"
        if os.name != "nt":
            monkeypatch.setenv("DOSBOX_TOKEN_FILE", "~nosuchuser_zq/api_token")
            with pytest.raises(ValueError, match="DOSBOX_TOKEN_FILE"):
                Config.load()

    def test_env_url_overrides_toml_port(self, tmp_path, monkeypatch):
        toml = tmp_path / "config.toml"
        toml.write_text("port = 9000\n", encoding="utf-8")
        monkeypatch.setenv("DOSBOX_MCP_CONFIG", str(toml))
        monkeypatch.setenv("DOSBOX_API_URL", "http://127.0.0.1:7777")
        cfg = Config.load()
        assert cfg.base_url == "http://127.0.0.1:7777"

    def test_env_token_file_overrides_toml(self, tmp_path, monkeypatch):
        toml = tmp_path / "config.toml"
        toml.write_text(f'token_file = "{tmp_path / "toml_tok"}"\n', encoding="utf-8")
        env_tok = tmp_path / "env_tok"
        monkeypatch.setenv("DOSBOX_MCP_CONFIG", str(toml))
        monkeypatch.setenv("DOSBOX_TOKEN_FILE", str(env_tok))
        cfg = Config.load()
        assert cfg.token_file == env_tok

    def test_unknown_toml_key_rejected(self, tmp_path, monkeypatch):
        toml = tmp_path / "config.toml"
        toml.write_text("headles = true\n", encoding="utf-8")
        monkeypatch.setenv("DOSBOX_MCP_CONFIG", str(toml))
        with pytest.raises(ValueError, match="headles"):
            Config.load()

    @pytest.mark.parametrize("line", [
        'mode = "root"',
        "port = 0",
        "port = 65536",
        'port = "8386"',
        'protocol = "banana"',
        'protocol = "1.0.0"',
        "headless = 1",
    ])
    def test_invalid_values_rejected(self, line, tmp_path, monkeypatch):
        toml = tmp_path / "config.toml"
        toml.write_text(line + "\n", encoding="utf-8")
        monkeypatch.setenv("DOSBOX_MCP_CONFIG", str(toml))
        with pytest.raises(ValueError):
            Config.load()

    def test_malformed_toml_rejected(self, tmp_path, monkeypatch):
        toml = tmp_path / "config.toml"
        toml.write_text("port = = 1\n", encoding="utf-8")
        monkeypatch.setenv("DOSBOX_MCP_CONFIG", str(toml))
        with pytest.raises(ValueError):
            Config.load()


class TestUpdateConfigFile:
    def test_creates_file_with_values(self, tmp_path):
        path = tmp_path / "config.toml"
        update_config_file(path, {"port": 9000, "headless": True})
        text = path.read_text(encoding="utf-8")
        assert "port = 9000" in text
        assert "headless = true" in text

    def test_preserves_human_comments(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text(
            "# my carefully tuned setup\n"
            "port = 9000\n"
            '# the win31 binary, do not change\n'
            'binary = "/opt/dosbox/dosbox"\n',
            encoding="utf-8",
        )
        update_config_file(path, {"port": 9001})
        text = path.read_text(encoding="utf-8")
        assert "# my carefully tuned setup" in text
        assert "# the win31 binary, do not change" in text
        assert "port = 9001" in text
        assert 'binary = "/opt/dosbox/dosbox"' in text

    def test_validates_values(self, tmp_path):
        path = tmp_path / "config.toml"
        with pytest.raises(ValueError):
            update_config_file(path, {"port": 99999})
        assert not path.exists()

    def test_unknown_key_rejected(self, tmp_path):
        with pytest.raises(ValueError, match="unknown"):
            update_config_file(tmp_path / "c.toml", {"prot": "1.0"})

    @pytest.mark.parametrize("key,value", [
        ("binary", "/some/other/binary"),
        ("mode", "full"),
    ])
    def test_protected_keys_rejected_when_flagged(self, key, value, tmp_path):
        # bridge_setup path: binary (code execution) and mode (privilege)
        # must be rejected loudly, not written.
        path = tmp_path / "config.toml"
        with pytest.raises(ToolProtectedKey, match=key):
            update_config_file(path, {key: value}, tool_facing=True)
        assert not path.exists()

    def test_protected_keys_allowed_for_cli(self, tmp_path):
        # The human-facing CLI may set anything.
        path = tmp_path / "config.toml"
        update_config_file(path, {"binary": "/opt/dosbox/dosbox",
                                  "mode": "observe"})
        text = path.read_text(encoding="utf-8")
        assert "/opt/dosbox/dosbox" in text
        assert "observe" in text


class TestConfigTemplate:
    def test_template_is_commented_and_loadable(self, tmp_path, monkeypatch):
        path = tmp_path / "config.toml"
        write_config_template(path)
        text = path.read_text(encoding="utf-8")
        assert text.count("#") >= 6
        for key in ("binary", "port", "headless", "protocol", "mode",
                    "token_file"):
            assert key in text
        monkeypatch.setenv("DOSBOX_MCP_CONFIG", str(path))
        monkeypatch.delenv("DOSBOX_TOKEN_FILE", raising=False)
        cfg = Config.load()
        assert cfg.port == 8386

    def test_template_refuses_to_overwrite(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text("port = 9000\n", encoding="utf-8")
        with pytest.raises(FileExistsError):
            write_config_template(path)
