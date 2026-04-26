"""Tests for Phase 6 — Single Prompt Agent.

Covers:
- Variable resolver (resolve_variables, extract_variable_names, get_builtin_variables)
- Test call endpoint (POST /api/v1/calls/test)
- VoicePipeline dynamic variables integration
- Orchestrator handle_test_call
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import TENANT_1_ID, auth_headers


# ── Variable Resolver Tests ──────────────────────────────────────────


class TestResolveVariables:
    """Tests for pipeline.variable_resolver.resolve_variables."""

    def test_resolve_simple_variable(self) -> None:
        """Resolves a single {{variable}} from agent defaults."""
        from app.modules.pipeline.variable_resolver import resolve_variables

        template = "Hello, {{name}}!"
        agent_defaults = [{"name": "name", "default_value": "Alice"}]
        result = resolve_variables(template, agent_defaults=agent_defaults)
        assert result == "Hello, Alice!"

    def test_resolve_multiple_variables(self) -> None:
        """Resolves multiple distinct variables."""
        from app.modules.pipeline.variable_resolver import resolve_variables

        template = "{{greeting}}, {{name}}! Welcome to {{company}}."
        defaults = [
            {"name": "greeting", "default_value": "Hi"},
            {"name": "name", "default_value": "Bob"},
            {"name": "company", "default_value": "Acme"},
        ]
        result = resolve_variables(template, agent_defaults=defaults)
        assert result == "Hi, Bob! Welcome to Acme."

    def test_call_overrides_take_priority(self) -> None:
        """Call-level overrides take priority over agent defaults."""
        from app.modules.pipeline.variable_resolver import resolve_variables

        template = "Hello, {{name}}!"
        defaults = [{"name": "name", "default_value": "Alice"}]
        overrides = {"name": "Bob"}
        result = resolve_variables(
            template, call_overrides=overrides, agent_defaults=defaults
        )
        assert result == "Hello, Bob!"

    def test_builtin_variables_resolved(self) -> None:
        """Built-in variables (current_date, current_time) are resolved."""
        from app.modules.pipeline.variable_resolver import (
            get_builtin_variables,
            resolve_variables,
        )

        template = "Today is {{current_date}}."
        builtins = get_builtin_variables()
        result = resolve_variables(template, builtin_vars=builtins)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert today in result

    def test_current_time_builtin(self) -> None:
        """Built-in current_time is resolved."""
        from app.modules.pipeline.variable_resolver import (
            get_builtin_variables,
            resolve_variables,
        )

        template = "Time: {{current_time}}"
        builtins = get_builtin_variables()
        result = resolve_variables(template, builtin_vars=builtins)
        # Should have colon from time format
        assert ":" in result
        assert "Time: " in result

    def test_unresolved_variable_left_in_place(self) -> None:
        """Variables without a value are left as {{var}} in the output."""
        from app.modules.pipeline.variable_resolver import resolve_variables

        template = "Hello, {{unknown_var}}!"
        result = resolve_variables(template)
        assert result == "Hello, {{unknown_var}}!"

    def test_empty_template(self) -> None:
        """Empty template returns empty string."""
        from app.modules.pipeline.variable_resolver import resolve_variables

        result = resolve_variables("", call_overrides={"name": "Alice"})
        assert result == ""

    def test_no_variables_in_template(self) -> None:
        """Template with no variables returns unchanged."""
        from app.modules.pipeline.variable_resolver import resolve_variables

        template = "Hello, world!"
        result = resolve_variables(template, call_overrides={"name": "Alice"})
        assert result == "Hello, world!"

    def test_agent_name_builtin(self) -> None:
        """agent_name is resolved from builtins when provided."""
        from app.modules.pipeline.variable_resolver import (
            get_builtin_variables,
            resolve_variables,
        )

        template = "I am {{agent_name}}."
        builtins = get_builtin_variables(agent_name="Sales Bot")
        result = resolve_variables(template, builtin_vars=builtins)
        assert result == "I am Sales Bot."

    def test_caller_number_builtin(self) -> None:
        """caller_number is resolved from builtins when provided."""
        from app.modules.pipeline.variable_resolver import (
            get_builtin_variables,
            resolve_variables,
        )

        template = "Calling from {{caller_number}}."
        builtins = get_builtin_variables(caller_number="+15551234567")
        result = resolve_variables(template, builtin_vars=builtins)
        assert result == "Calling from +15551234567."


class TestExtractVariableNames:
    """Tests for pipeline.variable_resolver.extract_variable_names."""

    def test_extract_single(self) -> None:
        from app.modules.pipeline.variable_resolver import extract_variable_names

        result = extract_variable_names("Hello {{name}}!")
        assert result == ["name"]

    def test_extract_multiple(self) -> None:
        from app.modules.pipeline.variable_resolver import extract_variable_names

        result = extract_variable_names("{{a}} and {{b}} and {{c}}")
        assert result == ["a", "b", "c"]

    def test_extract_deduplicates(self) -> None:
        from app.modules.pipeline.variable_resolver import extract_variable_names

        result = extract_variable_names("{{x}} {{x}} {{y}}")
        assert "x" in result
        assert "y" in result
        assert len(result) == 2

    def test_extract_none_found(self) -> None:
        from app.modules.pipeline.variable_resolver import extract_variable_names

        result = extract_variable_names("No variables here")
        assert result == []

    def test_extract_empty_string(self) -> None:
        from app.modules.pipeline.variable_resolver import extract_variable_names

        result = extract_variable_names("")
        assert result == []


class TestGetBuiltinVariables:
    """Tests for pipeline.variable_resolver.get_builtin_variables."""

    def test_default_builtins(self) -> None:
        from app.modules.pipeline.variable_resolver import get_builtin_variables

        builtins = get_builtin_variables()
        assert "current_date" in builtins
        assert "current_time" in builtins

    def test_builtins_with_agent_name(self) -> None:
        from app.modules.pipeline.variable_resolver import get_builtin_variables

        builtins = get_builtin_variables(agent_name="Test Bot")
        assert builtins["agent_name"] == "Test Bot"

    def test_builtins_with_caller_number(self) -> None:
        from app.modules.pipeline.variable_resolver import get_builtin_variables

        builtins = get_builtin_variables(caller_number="+1555000")
        assert builtins["caller_number"] == "+1555000"


class TestResolveAgentPrompt:
    """Tests for the convenience function resolve_agent_prompt."""

    def test_resolve_agent_prompt_basic(self) -> None:
        from app.modules.pipeline.variable_resolver import resolve_agent_prompt

        agent_config: dict = {
            "prompt": "Hello, {{name}}!",
            "variables": [
                {"name": "name", "default_value": "World"},
            ],
        }
        result = resolve_agent_prompt(agent_config)
        assert result == "Hello, World!"

    def test_resolve_agent_prompt_with_overrides(self) -> None:
        from app.modules.pipeline.variable_resolver import resolve_agent_prompt

        agent_config: dict = {
            "prompt": "Welcome, {{name}}!",
            "variables": [
                {"name": "name", "default_value": "Default"},
            ],
        }
        result = resolve_agent_prompt(agent_config, call_overrides={"name": "Override"})
        assert result == "Welcome, Override!"

    def test_resolve_agent_prompt_missing_config(self) -> None:
        from app.modules.pipeline.variable_resolver import resolve_agent_prompt

        result = resolve_agent_prompt({})
        # Falls back to default prompt when no prompt/system_prompt key
        assert result == "You are a helpful voice assistant."

    def test_resolve_agent_prompt_empty_prompt(self) -> None:
        from app.modules.pipeline.variable_resolver import resolve_agent_prompt

        # Empty string is falsy, so it falls back to system_prompt default
        result = resolve_agent_prompt({"prompt": ""})
        assert result == "You are a helpful voice assistant."


# ── Test Call Endpoint Tests ─────────────────────────────────────────


class TestTestCallEndpoint:
    """Tests for POST /api/v1/calls/test."""

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, client: AsyncClient) -> None:
        """Unauthenticated request to test call returns 401."""
        response = await client.post(
            "/api/v1/calls/test",
            json={"agent_id": str(uuid.uuid4())},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_agent_id_returns_422(
        self, client: AsyncClient, admin_user: MagicMock
    ) -> None:
        """Missing agent_id field returns 422 validation error."""
        from tests.conftest import auth_headers as make_auth_headers

        headers = make_auth_headers(admin_user)
        response = await client.post(
            "/api/v1/calls/test",
            json={},
            headers=headers,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_test_call_with_mock_orchestrator(
        self,
        client: AsyncClient,
        admin_user: MagicMock,
    ) -> None:
        """Test call endpoint returns expected fields when orchestrator succeeds."""
        from tests.conftest import auth_headers as make_auth_headers

        fake_call_id = uuid.uuid4()
        fake_room_name = f"test_{fake_call_id}"
        mock_result = {
            "call_id": str(fake_call_id),
            "token": "fake_lk_token",
            "room_name": fake_room_name,
            "livekit_url": "wss://localhost:7880",
        }

        headers = make_auth_headers(admin_user)

        with patch(
            "app.modules.calls.router.CallOrchestrator"
        ) as MockOrch:
            mock_instance = AsyncMock()
            mock_instance.handle_test_call.return_value = mock_result
            MockOrch.return_value = mock_instance

            response = await client.post(
                "/api/v1/calls/test",
                json={"agent_id": str(uuid.uuid4())},
                headers=headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert "call_id" in data
        assert "token" in data
        assert "room_name" in data
        assert "livekit_url" in data
        assert data["room_name"].startswith("test_")

    @pytest.mark.asyncio
    async def test_test_call_passes_dynamic_variables(
        self,
        client: AsyncClient,
        admin_user: MagicMock,
    ) -> None:
        """Dynamic variables from request body are forwarded to orchestrator."""
        from tests.conftest import auth_headers as make_auth_headers

        headers = make_auth_headers(admin_user)
        dynamic_vars = {"company_name": "Test Inc", "caller_name": "Jane"}

        captured_kwargs: dict = {}

        async def capture_handle_test_call(**kwargs: object) -> dict:
            captured_kwargs.update(kwargs)
            return {
                "call_id": str(uuid.uuid4()),
                "token": "tok",
                "room_name": "test_room",
                "livekit_url": "wss://localhost:7880",
            }

        with patch(
            "app.modules.calls.router.CallOrchestrator"
        ) as MockOrch:
            mock_instance = AsyncMock()
            mock_instance.handle_test_call = capture_handle_test_call
            MockOrch.return_value = mock_instance

            await client.post(
                "/api/v1/calls/test",
                json={
                    "agent_id": str(uuid.uuid4()),
                    "dynamic_variables": dynamic_vars,
                },
                headers=headers,
            )

        assert "dynamic_variables" in captured_kwargs
        assert captured_kwargs["dynamic_variables"] == dynamic_vars


# ── VoicePipeline Variable Integration Tests ─────────────────────────


class TestVoicePipelineDynamicVariables:
    """Tests for VoicePipeline dynamic variable integration."""

    def test_pipeline_accepts_dynamic_variables(self) -> None:
        """VoicePipeline constructor accepts dynamic_variables param."""
        from app.modules.pipeline.voice_pipeline import VoicePipeline

        mock_agent = MagicMock()
        mock_agent.name = "Test Agent"
        mock_agent.config = {"prompt": "Hello {{name}}", "variables": []}
        mock_agent.max_call_duration_seconds = 300

        pipeline = VoicePipeline(
            agent=mock_agent,
            call_id=uuid.uuid4(),
            livekit_url="wss://localhost:7880",
            livekit_token="fake_token",
            room_name="test_room",
            stt_service=MagicMock(),
            llm_service=MagicMock(),
            tts_service=MagicMock(),
            dynamic_variables={"name": "Test"},
        )
        assert pipeline.dynamic_variables == {"name": "Test"}

    def test_pipeline_default_dynamic_variables(self) -> None:
        """VoicePipeline defaults dynamic_variables to empty dict."""
        from app.modules.pipeline.voice_pipeline import VoicePipeline

        mock_agent = MagicMock()
        mock_agent.name = "Test Agent"
        mock_agent.config = {"prompt": "Hello", "variables": []}
        mock_agent.max_call_duration_seconds = 300

        pipeline = VoicePipeline(
            agent=mock_agent,
            call_id=uuid.uuid4(),
            livekit_url="wss://localhost:7880",
            livekit_token="fake_token",
            room_name="test_room",
            stt_service=MagicMock(),
            llm_service=MagicMock(),
            tts_service=MagicMock(),
        )
        assert pipeline.dynamic_variables == {}

    def test_build_system_prompt_resolves_variables(self) -> None:
        """_build_system_prompt resolves {{variables}} using variable_resolver."""
        from app.modules.pipeline.voice_pipeline import VoicePipeline

        mock_agent = MagicMock()
        mock_agent.name = "Sales Bot"
        mock_agent.type = "single_prompt"
        mock_agent.config = {
            "prompt": "I am {{agent_name}} for {{company}}.",
            "variables": [
                {"name": "company", "default_value": "WidgetCo"},
            ],
        }
        mock_agent.max_call_duration_seconds = 300

        pipeline = VoicePipeline(
            agent=mock_agent,
            call_id=uuid.uuid4(),
            livekit_url="wss://localhost:7880",
            livekit_token="fake_token",
            room_name="test_room",
            stt_service=MagicMock(),
            llm_service=MagicMock(),
            tts_service=MagicMock(),
            dynamic_variables={"company": "OverrideCo"},
        )
        prompt = pipeline._build_system_prompt()
        assert "Sales Bot" in prompt
        assert "OverrideCo" in prompt
        assert "WidgetCo" not in prompt  # Override should win

    def test_build_system_prompt_adds_default_browser_greeting(self) -> None:
        """Browser test calls auto-greet even when no explicit welcome message is configured."""
        from app.modules.pipeline.voice_pipeline import VoicePipeline

        mock_agent = MagicMock()
        mock_agent.name = "Sales Bot"
        mock_agent.type = "single_prompt"
        mock_agent.config = {
            "prompt": "You are {{agent_name}}.",
            "variables": [],
        }
        mock_agent.max_call_duration_seconds = 300

        pipeline = VoicePipeline(
            agent=mock_agent,
            call_id=uuid.uuid4(),
            livekit_url="wss://localhost:7880",
            livekit_token="fake_token",
            room_name="test_room",
            stt_service=MagicMock(),
            llm_service=MagicMock(),
            tts_service=MagicMock(),
            auto_greet_on_first_join=True,
        )

        prompt = pipeline._build_system_prompt()

        assert "Your opening greeting has already been spoken to the caller:" in prompt
        assert "Hello, this is Sales Bot. How can I help you today?" in prompt

    def test_build_system_prompt_uses_editor_default_when_config_empty(self) -> None:
        """Empty agent config should use the same richer fallback prompt as the editor."""
        from app.modules.pipeline.voice_pipeline import VoicePipeline

        mock_agent = MagicMock()
        mock_agent.name = "tetete"
        mock_agent.type = "single_prompt"
        mock_agent.config = {}
        mock_agent.max_call_duration_seconds = 300

        pipeline = VoicePipeline(
            agent=mock_agent,
            call_id=uuid.uuid4(),
            livekit_url="wss://localhost:7880",
            livekit_token="fake_token",
            room_name="test_room",
            stt_service=MagicMock(),
            llm_service=MagicMock(),
            tts_service=MagicMock(),
        )

        prompt = pipeline._build_system_prompt()

        assert "You are tetete, a friendly and helpful voice assistant for Acme Corp." in prompt
        assert "Business hours: 9am-5pm EST" in prompt
        assert "Transfer number: +15551234567" in prompt

    def test_user_turn_timeout_defaults_to_fast_response(self) -> None:
        """VoicePipeline default turn timeout is the safety-net value (5.0s)."""
        from app.modules.pipeline.voice_pipeline import VoicePipeline

        mock_agent = MagicMock()
        mock_agent.name = "Test Agent"
        mock_agent.config = {"prompt": "Hello", "variables": []}
        mock_agent.max_call_duration_seconds = 300

        pipeline = VoicePipeline(
            agent=mock_agent,
            call_id=uuid.uuid4(),
            livekit_url="wss://localhost:7880",
            livekit_token="fake_token",
            room_name="test_room",
            stt_service=MagicMock(),
            llm_service=MagicMock(),
            tts_service=MagicMock(),
        )

        assert pipeline._get_user_turn_stop_timeout_seconds() == 5.0

    def test_user_turn_timeout_uses_speech_responsiveness(self) -> None:
        """Higher responsiveness should shorten the end-of-turn timeout."""
        from app.modules.pipeline.voice_pipeline import VoicePipeline

        mock_agent = MagicMock()
        mock_agent.name = "Test Agent"
        mock_agent.config = {
            "prompt": "Hello",
            "variables": [],
            "settings": {
                "speech": {
                    "responsiveness": 1.0,
                }
            },
        }
        mock_agent.max_call_duration_seconds = 300

        pipeline = VoicePipeline(
            agent=mock_agent,
            call_id=uuid.uuid4(),
            livekit_url="wss://localhost:7880",
            livekit_token="fake_token",
            room_name="test_room",
            stt_service=MagicMock(),
            llm_service=MagicMock(),
            tts_service=MagicMock(),
        )

        assert pipeline._get_user_turn_stop_timeout_seconds() == 2.0
