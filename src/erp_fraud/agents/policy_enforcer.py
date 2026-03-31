"""PolicyEnforcer para controlar llamadas a tools por agente/nodo (RF15b-03)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from .tool_call_logging import ToolCallLogger


class PolicyConfigError(ValueError):
    """Error de configuración de políticas."""


class ToolPolicyDeniedError(PermissionError):
    """La policy deniega la llamada a la tool."""


def _load_yaml_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"No existe fichero YAML: {path}")
    try:
        import yaml  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("No se puede leer YAML sin PyYAML instalado") from exc

    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PolicyConfigError(f"{path}: el YAML debe contener un objeto raíz")
    return payload


@dataclass(frozen=True)
class ToolCallDecision:
    """Resultado de evaluación de policy para una llamada de tool."""

    allowed: bool
    reason: str


class PolicyEnforcer:
    """Enforcer de allowlist/denylist y límites de llamadas por agente."""

    def __init__(
        self,
        *,
        policy_payload: dict[str, Any],
        tools_registry_payload: dict[str, Any] | None = None,
        tool_call_logger: ToolCallLogger | None = None,
    ) -> None:
        self.policy_payload = dict(policy_payload)
        self.tools_registry_payload = dict(tools_registry_payload or {})
        self.tool_call_logger = tool_call_logger
        self._validate_policy_payload()
        self._validate_registry_payload()
        self._agent_call_count: dict[str, int] = {}
        self._agent_tool_call_count: dict[tuple[str, str], int] = {}

    @classmethod
    def from_yaml(
        cls,
        *,
        policy_path: str | Path = "config/agent_policies.yaml",
        tools_registry_path: str | Path | None = "config/tools_registry.yaml",
        tool_call_log_path: str | Path | None = None,
    ) -> "PolicyEnforcer":
        payload = _load_yaml_dict(Path(policy_path))
        registry_payload: dict[str, Any] | None = None
        if tools_registry_path:
            registry_payload = _load_yaml_dict(Path(tools_registry_path))
        logger = ToolCallLogger(tool_call_log_path) if tool_call_log_path else None
        return cls(
            policy_payload=payload,
            tools_registry_payload=registry_payload,
            tool_call_logger=logger,
        )

    def _validate_policy_payload(self) -> None:
        agents = self.policy_payload.get("agents")
        if not isinstance(agents, dict) or not agents:
            raise PolicyConfigError("agent_policies.yaml: falta objeto 'agents'")

        default_policy = self.policy_payload.get("default_policy")
        if not isinstance(default_policy, dict):
            raise PolicyConfigError("agent_policies.yaml: falta objeto 'default_policy'")

    def _validate_registry_payload(self) -> None:
        if not self.tools_registry_payload:
            return
        tools = self.tools_registry_payload.get("tools")
        if not isinstance(tools, dict):
            raise PolicyConfigError("tools_registry.yaml: falta objeto 'tools'")

    def _get_agent_policy(self, agent_id: str) -> dict[str, Any]:
        if not isinstance(agent_id, str) or not agent_id.strip():
            raise PolicyConfigError("agent_id debe ser string no vacío")
        agents = self.policy_payload.get("agents", {})
        agent_policy = agents.get(agent_id)
        if not isinstance(agent_policy, dict):
            raise ToolPolicyDeniedError(f"Agente no definido en policy: {agent_id}")
        return agent_policy

    def _registry_has_tool(self, tool_id: str) -> bool:
        if not self.tools_registry_payload:
            return True
        tools = self.tools_registry_payload.get("tools", {})
        return isinstance(tools, dict) and tool_id in tools

    def _registry_tool_enabled(self, tool_id: str) -> bool:
        if not self.tools_registry_payload:
            return True
        tools = self.tools_registry_payload.get("tools", {})
        if not isinstance(tools, dict):
            return False
        tool_payload = tools.get(tool_id, {})
        if not isinstance(tool_payload, dict):
            return False
        enabled = tool_payload.get("enabled", True)
        return bool(enabled)

    def evaluate_tool_call(self, *, agent_id: str, tool_id: str) -> ToolCallDecision:
        """Evalúa si un agente puede usar una tool concreta."""
        if not isinstance(tool_id, str) or not tool_id.strip():
            return ToolCallDecision(allowed=False, reason="tool_id inválido")
        if not self._registry_has_tool(tool_id):
            return ToolCallDecision(allowed=False, reason=f"Tool no registrada: {tool_id}")
        if not self._registry_tool_enabled(tool_id):
            return ToolCallDecision(allowed=False, reason=f"Tool deshabilitada: {tool_id}")

        agent_policy = self._get_agent_policy(agent_id)
        allowed = agent_policy.get("allowed_tools", [])
        denied = agent_policy.get("denied_tools", [])
        if not isinstance(allowed, list):
            return ToolCallDecision(allowed=False, reason=f"Policy inválida para agente={agent_id}")
        if tool_id not in allowed:
            return ToolCallDecision(
                allowed=False,
                reason=f"Tool '{tool_id}' no permitida para agente '{agent_id}'",
            )
        if isinstance(denied, list) and tool_id in denied:
            return ToolCallDecision(
                allowed=False,
                reason=f"Tool '{tool_id}' está en denylist para agente '{agent_id}'",
            )
        return ToolCallDecision(allowed=True, reason="allowed")

    def _check_call_limits(self, *, agent_id: str, tool_id: str) -> None:
        default_policy = self.policy_payload.get("default_policy", {})
        agent_policy = self._get_agent_policy(agent_id)
        limits = agent_policy.get("limits", {})
        if not isinstance(limits, dict):
            raise PolicyConfigError(f"agent_policies.yaml: limits inválido para agente={agent_id}")

        max_tool_calls = limits.get("max_tool_calls", default_policy.get("max_tool_calls", 0))
        if isinstance(max_tool_calls, bool):
            raise PolicyConfigError(f"max_tool_calls inválido para agente={agent_id}")
        if int(max_tool_calls) > 0:
            current = self._agent_call_count.get(agent_id, 0)
            if current >= int(max_tool_calls):
                raise ToolPolicyDeniedError(
                    f"Agente '{agent_id}' superó max_tool_calls={int(max_tool_calls)}"
                )

        per_tool = limits.get("max_calls_per_tool", {})
        if per_tool is not None and not isinstance(per_tool, dict):
            raise PolicyConfigError(f"max_calls_per_tool inválido para agente={agent_id}")
        if isinstance(per_tool, dict) and tool_id in per_tool:
            max_calls_tool = int(per_tool[tool_id])
            current_tool = self._agent_tool_call_count.get((agent_id, tool_id), 0)
            if current_tool >= max_calls_tool:
                raise ToolPolicyDeniedError(
                    f"Agente '{agent_id}' superó max_calls_per_tool para '{tool_id}'={max_calls_tool}"
                )

    def enforce_tool_call(self, *, agent_id: str, tool_id: str) -> None:
        """Valida policy y registra la llamada si está permitida."""
        decision = self.evaluate_tool_call(agent_id=agent_id, tool_id=tool_id)
        if not decision.allowed:
            raise ToolPolicyDeniedError(decision.reason)
        self._check_call_limits(agent_id=agent_id, tool_id=tool_id)
        self._agent_call_count[agent_id] = self._agent_call_count.get(agent_id, 0) + 1
        key = (agent_id, tool_id)
        self._agent_tool_call_count[key] = self._agent_tool_call_count.get(key, 0) + 1

    def enforce_and_call(
        self,
        *,
        agent_id: str,
        tool_id: str,
        tool_callable: Callable[..., Any],
        node_id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Intercepta la llamada a la tool, aplica policy y ejecuta."""
        started = perf_counter()
        try:
            self.enforce_tool_call(agent_id=agent_id, tool_id=tool_id)
        except Exception as exc:
            if self.tool_call_logger is not None:
                self.tool_call_logger.log_tool_call(
                    tool_id=tool_id,
                    agent_id=agent_id,
                    params=kwargs,
                    status="DENIED",
                    duration_ms=int((perf_counter() - started) * 1000),
                    node_id=node_id,
                    error_summary=f"{type(exc).__name__}: {exc}",
                )
            raise

        try:
            result = tool_callable(**kwargs)
        except Exception as exc:
            if self.tool_call_logger is not None:
                self.tool_call_logger.log_tool_call(
                    tool_id=tool_id,
                    agent_id=agent_id,
                    params=kwargs,
                    status="ERROR",
                    duration_ms=int((perf_counter() - started) * 1000),
                    node_id=node_id,
                    error_summary=f"{type(exc).__name__}: {exc}",
                )
            raise

        if self.tool_call_logger is not None:
            self.tool_call_logger.log_tool_call(
                tool_id=tool_id,
                agent_id=agent_id,
                params=kwargs,
                status="OK",
                duration_ms=int((perf_counter() - started) * 1000),
                node_id=node_id,
            )
        return result
