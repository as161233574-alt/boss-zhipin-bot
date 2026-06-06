"""LLM Client 测试。"""
import pytest


class TestLLMClient:
    def test_load_ai_config_structure(self):
        from interview.llm_client import _load_ai_config
        cfg = _load_ai_config()
        assert "api_key" in cfg
        assert "base_url" in cfg
        assert "model" in cfg

    def test_config_cache(self):
        from interview.llm_client import _config_cache, _CONFIG_TTL
        assert _CONFIG_TTL == 60.0
        assert "data" in _config_cache
        assert "ts" in _config_cache

    def test_get_client_returns_client(self):
        from interview.llm_client import _get_client
        import httpx
        client = _get_client()
        assert isinstance(client, httpx.Client)

    def test_get_client_singleton(self):
        from interview.llm_client import _get_client
        c1 = _get_client()
        c2 = _get_client()
        assert c1 is c2

    def test_cosine_similarity_identical(self):
        from interview.llm_client import cosine_similarity
        v = [1.0, 2.0, 3.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_cosine_similarity_orthogonal(self):
        from interview.llm_client import cosine_similarity
        assert cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)

    def test_cosine_similarity_opposite(self):
        from interview.llm_client import cosine_similarity
        assert cosine_similarity([1, 0], [-1, 0]) == pytest.approx(-1.0)

    def test_cosine_similarity_zero_vec(self):
        from interview.llm_client import cosine_similarity
        assert cosine_similarity([0, 0], [1, 2]) == 0.0

    def test_parse_json_from_llm(self):
        from interview.llm_client import parse_json_from_llm
        result = parse_json_from_llm('some text {"score": 85} more text')
        assert result == {"score": 85}

    def test_parse_json_from_llm_no_json(self):
        from interview.llm_client import parse_json_from_llm
        assert parse_json_from_llm("no json here") is None

    def test_parse_json_from_llm_invalid(self):
        from interview.llm_client import parse_json_from_llm
        assert parse_json_from_llm("{broken json") is None
