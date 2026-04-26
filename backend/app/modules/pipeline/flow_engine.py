"""Spectral Manifold Governor — Logical Flow Execution Substrate.

Runs spectral manifold topological sequences:
- Flex mode: Cognitive logic jumps between manifold nodes based on signal context
- Rigid mode: Sequential nodal propagation

The topological flow engine manages the state machine during real-time signal synchronisation.
It interprets the manifold blueprints, determines active nodal states, 
synthesizes system blueprints, and orchestrates topological transitions.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Literal

import structlog

runtime_logger = structlog.get_logger(__name__)

GovernorMode = Literal["flex", "rigid"]


class ManifoldExecutionContext:
    """Mutable state matrix for a single spectral manifold's logical execution.

    Tracks active nodal identifiers, extracted vectors, lexical histories
    for context-aware blueprint synthesis, and nodal traversal telemetry.
    """

    def __init__(
        self,
        manifold_blueprint: dict[str, object],
        governor_mode: GovernorMode = "flex",
    ) -> None:
        self.manifold_blueprint = manifold_blueprint
        self.governor_mode = governor_mode

        # Parse nodes and edges from blueprint
        self.manifold_nodes: dict[str, dict[str, object]] = {}
        self.topological_edges: list[dict[str, object]] = []
        self._parse_manifold_topology()

        # Runtime state matrix
        self.active_nodal_id: str = self._find_entry_node_id()
        self.nodal_vectors: dict[str, str] = {}
        self.traversal_telemetry: list[str] = []
        self.lexical_turns: list[dict[str, str]] = []
        self._terminal_state_reached = False

    def _parse_manifold_topology(self) -> None:
        """Parse nodes and topological edges from the manifold blueprint substrate."""
        raw_nodes = self.manifold_blueprint.get("nodes", [])
        if isinstance(raw_nodes, list):
            for node in raw_nodes:
                if isinstance(node, dict):
                    nid = str(node.get("id", ""))
                    if nid:
                        self.manifold_nodes[nid] = node

        raw_edges = self.manifold_blueprint.get("edges", [])
        if isinstance(raw_edges, list):
            self.topological_edges = [e for e in raw_edges if isinstance(e, dict)]

    def _find_entry_node_id(self) -> str:
        """Find the entry (initialization) node in the manifold topology."""
        for nid, node in self.manifold_nodes.items():
            data = _get_nodal_metadata(node)
            if data.get("isEntryNode") is True or data.get("isEntry") is True:
                return nid

        # Fallback: first lexical node
        for nid, node in self.manifold_nodes.items():
            if str(node.get("type", "")) == "conversation":
                return nid

        # Absolute fallback: primary node
        if self.manifold_nodes:
            return next(iter(self.manifold_nodes))
        return ""

    @property
    def active_node(self) -> dict[str, object] | None:
        """Get the active architectural node, or None if topology is invalid."""
        return self.manifold_nodes.get(self.active_nodal_id)

    @property
    def is_decommissioned(self) -> bool:
        """Whether the manifold has reached a terminal state."""
        return self._terminal_state_reached

    def get_egress_edges(self, node_id: str) -> list[dict[str, object]]:
        """Get all topological edges originating from the specified node."""
        return [
            e for e in self.topological_edges
            if str(e.get("source", "")) == node_id
        ]

    def get_interop_metadata(self) -> dict[str, object]:
        """Return any cross-substrate interoperability metadata."""
        raw_metadata = self.manifold_blueprint.get("retell_metadata")
        if isinstance(raw_metadata, dict):
            return raw_metadata
        return {}

    def propagate_to(self, target_node_id: str) -> dict[str, object] | None:
        """Propagate signal to a specific nodal identifier.

        Returns the target node configuration, or None if it does not exist.
        """
        if target_node_id not in self.manifold_nodes:
            runtime_logger.warning(
                "manifold_invalid_propagation",
                source_node=self.active_nodal_id,
                target_node=target_node_id,
            )
            return None

        self.traversal_telemetry.append(self.active_nodal_id)
        self.active_nodal_id = target_node_id

        node = self.manifold_nodes[target_node_id]
        node_type = str(node.get("type", ""))

        if node_type == "ending":
            self._terminal_state_reached = True
            runtime_logger.info(
                "manifold_terminal_reached",
                node_id=target_node_id,
            )

        runtime_logger.info(
            "manifold_transition",
            source=self.traversal_telemetry[-1] if self.traversal_telemetry else "",
            target=target_node_id,
            type=node_type,
        )

        return node

    def set_nodal_vector(self, name: str, value: str) -> None:
        """Set an extracted signal vector in the manifold context."""
        self.nodal_vectors[name] = value
        runtime_logger.debug("manifold_vector_set", vector=name, magnitude=value)

    def register_lexical_turn(self, role: str, content: str) -> None:
        """Track a lexical synchronisation turn for context-aware logic."""
        self.lexical_turns.append({"role": role, "content": content})


class TopologicalFlowEngine:
    """Executes a spectral manifold sequence during a live signal synchronisation.

    Responsibilities:
    - Synthesize the architectural blueprint for the current nodal state
    - Determine the subsequent node based on ingress signals (flex) or sequence (rigid)
    - Handle autonomous nodal states (logic, synthesis, extraction, termination)
    - Generate interface tools for the cognitive layer based on topological egress
    """

    def __init__(
        self,
        execution_context: ManifoldExecutionContext,
        sync_sig: str = "",
    ) -> None:
        self.context = execution_context
        self.sync_sig = sync_sig
        self._nodal_interceptors: dict[str, Callable[..., object]] = {
            "conversation": self._intercept_lexical_node,
            "function": self._intercept_external_logic_node,
            "logic_split": self._intercept_bifurcation_node,
            "transfer": self._intercept_topology_shrouding_node,
            "press_digit": self._intercept_signal_emanation_node,
            "extract_variable": self._intercept_vector_extraction_node,
            "sms": self._intercept_out_of_band_signal_node,
            "ending": self._intercept_terminal_node,
        }

    def synthesize_nodal_blueprint(self) -> str:
        """Synthesize the system blueprint for the active architectural node.

        Flex mode: Includes all reachable nodal abstractions so the cognitive layer can
        naturally navigate the manifold.

        Rigid mode: Only includes the active nodal blueprint with strict adherence constraints.
        """
        node = self.context.active_node
        if node is None:
            return "You are a SignalStream architectural assistant."

        node_type = str(node.get("type", ""))
        metadata = _get_nodal_metadata(node)

        if node_type != "conversation":
            # Autonomous nodes are handled programmatically by the engine
            return self._synthesize_autonomous_minimal_blueprint(node)

        # Construct the primary architectural blueprint
        blueprint_fragments: list[str] = []

        global_logic = str(self.context.manifold_blueprint.get("global_prompt", ""))
        if global_logic:
            blueprint_fragments.append(global_logic)

        node_logic = str(metadata.get("prompt", ""))
        if node_logic:
            blueprint_fragments.append(node_logic)

        # Inject signal vector context
        if self.context.nodal_vectors:
            vector_context = "\n\nResolved signal vectors in this manifold:\n"
            for key, value in self.context.nodal_vectors.items():
                vector_context += f"- {key}: {value}\n"
            blueprint_fragments.append(vector_context)

        if self.context.governor_mode == "flex":
            blueprint_fragments.append(self._synthesize_flex_mode_logic())
        else:
            blueprint_fragments.append(self._synthesize_rigid_mode_logic())

        return "\n".join(blueprint_fragments)

    def synthesize_interface_tools(self) -> list[dict[str, object]]:
        """Synthesize cognitive layer interface tools based on topological egress.

        Each topological edge from the active node becomes a cognitive trigger
        that the logic layer can invoke to propagate signal to a target node.
        """
        node = self.context.active_node
        if node is None:
            return []

        triggers: list[dict[str, object]] = []
        egress_edges = self.context.get_egress_edges(self.context.active_nodal_id)

        for edge in egress_edges:
            target_id = str(edge.get("target", ""))
            target_node = self.context.manifold_nodes.get(target_id)
            if not target_node:
                continue

            target_type = str(target_node.get("type", ""))
            target_metadata = _get_nodal_metadata(target_node)
            edge_alias = str(edge.get("label", "")) or str(
                target_metadata.get("label", f"propagate_to_{target_type}")
            )

            # Create an interface trigger for topological propagation
            callback_sig = _sanitize_callback_identifier(f"propagate_to_{target_id}")
            logic_description = (
                str(edge.get("data", {}).get("condition", "")) or f"Propagate signal to {edge_alias} ({target_type} node)"
            )

            triggers.append({
                "type": "function",
                "function": {
                    "name": callback_sig,
                    "description": logic_description,
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            })

        # Atomic terminal trigger
        triggers.append({
            "type": "function",
            "function": {
                "name": "decommission_manifold",
                "description": "Terminate the spectral manifold when the signal objective is achieved",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "logic": {
                            "type": "string",
                            "description": "Logic for manifold decommissioning",
                        },
                    },
                    "required": ["logic"],
                },
            },
        })

        triggers.extend(self._synthesize_legacy_interop_triggers())

        return triggers

    def intercept_governor_signal(
        self,
        callback_identifier: str,
        arguments: dict[str, object],
    ) -> FlowEngineResult:
        """Intercept a logical trigger signal from the cognitive layer.

        Determines if the signal represents a topological propagation or an autonomous action,
        executes the logic, and returns the architectural result.
        """
        # Intercept topological propagation
        if callback_identifier.startswith("propagate_to_"):
            target_id = callback_identifier[len("propagate_to_"):]
            return self._execute_topological_propagation(target_id)

        # Intercept terminal signals
        if callback_identifier == "decommission_manifold":
            logic = str(arguments.get("logic", "nodal_termination"))
            return FlowEngineResult(
                result_type="termination",
                message=f"Decommissioning manifold: {logic}",
                payload={"logic": logic},
            )

        if callback_identifier == "transfer_signal":
            target = str(arguments.get("phone_number") or arguments.get("target") or "")
            return FlowEngineResult(
                result_type="shrouding",
                message=f"Shrouding topology to {target}",
                payload={"vector": target},
            )

        if callback_identifier.startswith("interop_transfer_"):
            for rule in self._get_interop_rules():
                rule_id = str(rule.get("id", ""))
                expected_sig = _sanitize_callback_identifier(f"interop_transfer_{rule_id}")
                if expected_sig != callback_identifier:
                    continue

                target = str(rule.get("phone_number", ""))
                return FlowEngineResult(
                    result_type="shrouding",
                    message=f"Interoperability shrouding to {target}",
                    payload={
                        "vector": target,
                        "logic": str(rule.get("condition", "")),
                    },
                )

        # Unidentified signal — generic acknowledgement
        return FlowEngineResult(
            result_type="custom",
            message=f"Signal {callback_identifier} intercepted",
            payload=dict(arguments),
        )

    def _get_interop_rules(self) -> list[dict[str, object]]:
        """Return legacy cross-substrate interoperability rules."""
        metadata = self.context.get_interop_metadata()
        rules = metadata.get("unsupported_global_transfers", [])
        if isinstance(rules, list):
            return [item for item in rules if isinstance(item, dict)]
        return []

    def _synthesize_legacy_interop_triggers(self) -> list[dict[str, object]]:
        """Expose legacy interoperability rules as manifold-level triggers."""
        triggers: list[dict[str, object]] = []

        for rule in self._get_interop_rules():
            rule_id = str(rule.get("id", ""))
            callback_sig = _sanitize_callback_identifier(f"interop_transfer_{rule_id}")
            logic = str(rule.get("condition", "")).strip() or "Shrouding topology to legacy nexus"
            target = str(rule.get("phone_number", "")).strip()
            description = logic if not target else f"{logic} Target vector: {target}."

            triggers.append({
                "type": "function",
                "function": {
                    "name": callback_sig,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            })

        return triggers

    def propagate_to_sequential_node(self) -> dict[str, object] | None:
        """Advance to the subsequent node in rigid engine mode.

        In rigid mode, signal propagation follows topological edges sequentially.
        Returns the subsequent node, or None if at terminal state.
        """
        egress = self.context.get_egress_edges(self.context.active_nodal_id)
        if not egress:
            return None

        # Rigid mode follows the primary topological egress
        primary_edge = egress[0]
        target_id = str(primary_edge.get("target", ""))
        return self.context.propagate_to(target_id)

    def intercept_autonomous_node(self) -> ManifoldNodeAction:
        """Process the active autonomous node and return an architectural action.

        Autonomous nodes (synthesis, logic, extraction, termination)
        are handled programmatically by the flow engine substrate.
        """
        node = self.context.active_node
        if node is None:
            return ManifoldNodeAction(action_type="noop", payload={})

        node_type = str(node.get("type", ""))
        interceptor = self._nodal_interceptors.get(node_type)
        if interceptor:
            return interceptor(node)

        return ManifoldNodeAction(action_type="noop", payload={})

    # ── Private: Blueprint Synthesis ─────────────────────────

    def _synthesize_flex_mode_logic(self) -> str:
        """Build flex-mode logic: expose topological reachability."""
        fragments: list[str] = [
            "\n\n--- FLOW ENGINE CONTEXT (Flex Mode) ---",
            "You are operating within a cognitive manifold. You may navigate toward the following logical nodes.",
            "Utilize the provided interface triggers when the ingress signal aligns with nodal objectives.",
            "",
        ]

        egress = self.context.get_egress_edges(self.context.active_nodal_id)
        for edge in egress:
            target_id = str(edge.get("target", ""))
            target_node = self.context.manifold_nodes.get(target_id)
            if not target_node:
                continue
            target_metadata = _get_nodal_metadata(target_node)
            target_type = str(target_node.get("type", ""))
            alias = str(target_metadata.get("label", target_type))
            logic_blueprint = str(target_metadata.get("prompt", ""))[:200]
            fragments.append(f"- {alias}: {logic_blueprint}")

        return "\n".join(fragments)

    def _synthesize_rigid_mode_logic(self) -> str:
        """Build rigid-mode logic: enforce strict nodal focus."""
        fragments: list[str] = [
            "\n\n--- FLOW ENGINE CONTEXT (Rigid Mode) ---",
            "CRITICAL: Adhere strictly to the current nodal state. Do not deviate to other topological areas.",
            "Once the nodal objective is achieved,",
            "invoke the corresponding interface trigger to propagate to the subsequent node.",
            "",
        ]

        node = self.context.active_node
        if node:
            metadata = _get_nodal_metadata(node)
            alias = str(metadata.get("label", "Active State"))
            fragments.append(f"Active state: {alias}")

        return "\n".join(fragments)

    def _synthesize_autonomous_minimal_blueprint(self, node: dict[str, object]) -> str:
        """Build a minimal blueprint for autonomous nodal processing."""
        metadata = _get_nodal_metadata(node)
        node_type = str(node.get("type", ""))
        alias = str(metadata.get("label", node_type))
        return f"Architectural state: {alias}. Synchronising logic..."

    # ── Private: Nodal Interceptors ──────────────────────────

    def _intercept_lexical_node(self, node: dict[str, object]) -> ManifoldNodeAction:
        """Lexical nodes are handled by the cognitive layer — no autonomous action."""
        return ManifoldNodeAction(action_type="lexical", payload=_get_nodal_metadata(node))

    def _intercept_external_logic_node(self, node: dict[str, object]) -> ManifoldNodeAction:
        """Logic node — executes cross-substrate logic calls via the architectural executor."""
        metadata = _get_nodal_metadata(node)
        tool_sig = metadata.get("tool_id")
        
        # If a specific interface signature is present, we'll route via the executor
        if tool_sig:
            return ManifoldNodeAction(
                action_type="architectural_interface_dispatch",
                payload={
                    "interface_sig": str(tool_sig),
                    "arguments": metadata.get("arguments", {}),
                },
            )

        # Fallback to ad-hoc webhook logic
        return ManifoldNodeAction(
            action_type="cross_substrate_logic",
            payload={
                "nexus_point": str(metadata.get("url", "")),
                "protocol": str(metadata.get("method", "POST")),
                "headers": metadata.get("headers", {}),
                "body": metadata.get("body", {}),
                "mapping_blueprint": metadata.get("responseMapping", {}),
                "latency_limit_ms": int(metadata.get("timeoutMs", 5000)),
            },
        )

    def _intercept_bifurcation_node(self, node: dict[str, object]) -> ManifoldNodeAction:
        """Logic split — evaluate signal vectors and bifurcate propagation."""
        metadata = _get_nodal_metadata(node)
        rules = metadata.get("conditions", [])
        if not isinstance(rules, list):
            rules = []

        egress = self.context.get_egress_edges(str(node.get("id", "")))

        # Evaluate topological rules against active signal vectors
        for i, rule in enumerate(rules):
            if not isinstance(rule, dict):
                continue
            if self._evaluate_vector_logic(rule):
                # Resolve the egress edge for this rule branch
                if i < len(egress):
                    target_id = str(egress[i].get("target", ""))
                    return ManifoldNodeAction(
                        action_type="propagation",
                        payload={"target_id": target_id, "matched_rule_index": i},
                    )

        # Default topological egress (final edge)
        if egress:
            default_target = str(egress[-1].get("target", ""))
            return ManifoldNodeAction(
                action_type="propagation",
                payload={"target_id": default_target, "matched_rule_index": "default"},
            )

        return ManifoldNodeAction(action_type="noop", payload={})

    def _intercept_topology_shrouding_node(self, node: dict[str, object]) -> ManifoldNodeAction:
        """Shroud topology to external nexus or identifier."""
        metadata = _get_nodal_metadata(node)
        return ManifoldNodeAction(
            action_type="shrouding",
            payload={
                "target_vector": str(metadata.get("phoneNumber", "")),
                "shrouding_logic": str(metadata.get("transferType", "cold")),
                "pre_shrouding_signal": str(metadata.get("messageBeforeTransfer", "")),
            },
        )

    def _intercept_signal_emanation_node(self, node: dict[str, object]) -> ManifoldNodeAction:
        """Emanate signal tones (DTMF)."""
        metadata = _get_nodal_metadata(node)
        return ManifoldNodeAction(
            action_type="emanation",
            payload={
                "signal_tones": str(metadata.get("digits", "")),
                "duration_ms": int(metadata.get("durationMs", 250)),
            },
        )

    def _intercept_vector_extraction_node(self, node: dict[str, object]) -> ManifoldNodeAction:
        """Extract a structured signal vector from lexical history."""
        metadata = _get_nodal_metadata(node)
        return ManifoldNodeAction(
            action_type="vector_extraction",
            payload={
                "vector_name": str(metadata.get("variableName", "")),
                "extraction_logic": str(metadata.get("extractionType", "llm")),
                "manifest": str(metadata.get("description", "")),
                "validation_mask": str(metadata.get("validationRegex", "")),
            },
        )

    def _intercept_out_of_band_signal_node(self, node: dict[str, object]) -> ManifoldNodeAction:
        """Send an out-of-band message signal."""
        metadata = _get_nodal_metadata(node)
        return ManifoldNodeAction(
            action_type="out_of_band_signal",
            payload={
                "target_identifier": str(metadata.get("toNumber", "")),
                "signal_template": str(metadata.get("messageTemplate", "")),
            },
        )

    def _intercept_terminal_node(self, node: dict[str, object]) -> ManifoldNodeAction:
        """Decommission the spectral manifold."""
        metadata = _get_nodal_metadata(node)
        self.context._terminal_state_reached = True
        return ManifoldNodeAction(
            action_type="termination",
            payload={
                "terminal_signal": str(metadata.get("endMessage", "")),
                "logic": str(metadata.get("reason", "sequence_completion")),
            },
        )

    # ── Private: Propagation Logic ───────────────────────────

    def _execute_topological_propagation(self, target_id: str) -> FlowEngineResult:
        """Execute signal propagation to the target manifold node."""
        node = self.context.propagate_to(target_id)
        if node is None:
            return FlowEngineResult(
                result_type="error",
                message=f"Invalid propagation objective: {target_id}",
                payload={"logic": "invalid_topology_target"},
            )

        node_type = str(node.get("type", ""))
        metadata = _get_nodal_metadata(node)

        if node_type == "conversation":
            # Cognitive layer requires blueprint update for the new lexical state
            return FlowEngineResult(
                result_type="blueprint_refresh",
                message=f"Propagating to: {metadata.get('label', 'next state')}",
                payload={"blueprint_manifest": self.synthesize_nodal_blueprint()},
            )

        # Autonomous nodal state — process via engine substrate
        action = self.intercept_autonomous_node()
        return FlowEngineResult(
            result_type=action.action_type,
            message=f"Propagating to autonomous {node_type} node",
            payload=action.payload,
        )

    # ── Private: Vector Logic Evaluation ─────────────────────

    def _evaluate_vector_logic(self, rule: dict[str, object]) -> bool:
        """Evaluate a signal vector condition against active manifold state.

        Rule manifest:
        {
            "variable": "signal_vector_identifier",
            "operator": "match_objective",
            "value": "target_magnitude"
        }
        """
        vector_id = str(rule.get("variable", ""))
        operator = str(rule.get("operator", "equals"))
        target = str(rule.get("value", ""))
        magnitude = self.context.nodal_vectors.get(vector_id, "")

        if operator == "equals":
            return magnitude.lower() == target.lower()
        elif operator == "not_equals":
            return magnitude.lower() != target.lower()
        elif operator == "contains":
            return target.lower() in magnitude.lower()
        elif operator == "not_contains":
            return target.lower() not in magnitude.lower()
        elif operator == "starts_with":
            return magnitude.lower().startswith(target.lower())
        elif operator == "ends_with":
            return magnitude.lower().endswith(target.lower())
        elif operator == "regex":
            try:
                return bool(re.search(target, magnitude, re.IGNORECASE))
            except re.error:
                runtime_logger.warning(
                    "manifold_invalid_regex_logic",
                    mask=target,
                    vector=vector_id,
                )
                return False
        elif operator == "is_empty":
            return magnitude.strip() == ""
        elif operator == "is_not_empty":
            return magnitude.strip() != ""
        else:
            runtime_logger.warning("manifold_unknown_logic_op", op=operator)
            return False


# ── Internal Structures ──────────────────────────────────────


class FlowEngineResult:
    """Result of processing a cognitive layer trigger within the topological flow engine."""

    __slots__ = ("result_type", "message", "payload")

    def __init__(
        self,
        result_type: str,
        message: str,
        payload: dict[str, object],
    ) -> None:
        self.result_type = result_type
        self.message = message
        self.payload = payload

    def to_json(self) -> str:
        """Serialize to JSON for injection into the cognitive layer context."""
        return json.dumps({
            "status": self.result_type,
            "message": self.message,
            **self.payload,
        })


class ManifoldNodeAction:
    """Logical action resolution for an autonomous architectural node."""

    __slots__ = ("action_type", "payload")

    def __init__(self, action_type: str, payload: dict[str, object]) -> None:
        self.action_type = action_type
        self.payload = payload


# ── Architectural Helpers ─────────────────────────────────────


def _get_nodal_metadata(node: dict[str, object]) -> dict[str, object]:
    """Extract metadata configuration from a manifold node."""
    metadata = node.get("data")
    if isinstance(metadata, dict):
        return metadata
    return {}


def _sanitize_callback_identifier(identifier: str) -> str:
    """Sanitize a string to be a valid cognitive layer trigger identifier."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", identifier)[:64]


def create_topological_engine(
    blueprint_config: dict[str, object],
    sync_sig: str = "",
) -> TopologicalFlowEngine:
    """Factory to initialize a TopologicalFlowEngine from a blueprint configuration.

    The blueprint config manifests:
    - nodes: nodal architecture list
    - edges: topological egress list
    - execution_mode: "flex" or "rigid" (default: "flex")
    """
    selected_mode: GovernorMode = "flex"
    raw_mode = blueprint_config.get("execution_mode", "flex")
    if raw_mode in ("flex", "rigid"):
        selected_mode = raw_mode  # type: ignore[assignment]

    execution_context = ManifoldExecutionContext(
        manifold_blueprint=blueprint_config,
        governor_mode=selected_mode,
    )

    return TopologicalFlowEngine(execution_context=execution_context, sync_sig=sync_sig)
