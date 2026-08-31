"""Tests for the regex intent engine."""

import pytest

from app.intent.engine import IntentEngine


@pytest.fixture
def engine():
    return IntentEngine()


class TestDockerIntents:
    def test_deploy_nginx(self, engine):
        result = engine.detect("deploy nginx on port 8080")
        assert result.intent == "docker.deploy"
        assert result.entities["image"] == "nginx"
        assert result.entities["port"] == 8080
        assert result.confidence > 0.5

    def test_deploy_without_port(self, engine):
        result = engine.detect("run redis")
        assert result.intent == "docker.deploy"
        assert result.entities["image"] == "redis"

    def test_list_containers(self, engine):
        assert engine.detect("list all containers").intent == "docker.list"
        assert engine.detect("show me running containers").intent == "docker.list"

    def test_stop_container(self, engine):
        result = engine.detect("stop nginx-web")
        assert result.intent == "docker.stop"
        assert result.entities["container"] == "nginx-web"


class TestLogsIntents:
    def test_analyze_logs(self, engine):
        result = engine.detect("analyze logs at /var/log/app.log")
        assert result.intent == "logs.analyze"
        assert result.entities["path"] == "/var/log/app.log"

    def test_find_errors(self, engine):
        result = engine.detect("find errors in app.log")
        assert result.intent == "logs.errors"


class TestFileIntents:
    def test_count_lines(self, engine):
        result = engine.detect("count lines in package.json")
        assert result.intent == "file.count"
        assert result.entities["what"] == "lines"
        assert result.entities["path"] == "package.json"

    def test_read_file(self, engine):
        result = engine.detect("read file config.yaml")
        assert result.intent == "file.read"
        assert result.entities["path"] == "config.yaml"


class TestSystemIntents:
    def test_system_health(self, engine):
        assert engine.detect("system health").intent == "system.health"

    def test_disk_usage(self, engine):
        assert engine.detect("disk usage").intent == "system.disk"

    def test_memory_usage(self, engine):
        assert engine.detect("memory usage").intent == "system.memory"


class TestKubernetesIntents:
    def test_list_pods(self, engine):
        result = engine.detect("list pods in default namespace")
        assert result.intent == "k8s.list_pods"
        assert result.entities["namespace"] == "default"

    def test_scale(self, engine):
        result = engine.detect("scale web to 5")
        assert result.intent == "k8s.scale"
        assert result.entities["replicas"] == 5


class TestUnknown:
    def test_empty_command(self, engine):
        assert engine.detect("").intent == "unknown"

    def test_gibberish(self, engine):
        assert engine.detect("blorp fnord quux").intent == "unknown"


class TestDestructive:
    def test_stop_is_destructive(self, engine):
        assert engine.is_destructive("docker.stop") is True

    def test_list_is_not_destructive(self, engine):
        assert engine.is_destructive("docker.list") is False
