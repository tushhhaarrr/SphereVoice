from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path
from typing import Any


def _clean_text(value: str | None) -> str:
    return (value or "").strip()


def _conversation_data(node: dict[str, Any], start_node_id: str) -> dict[str, Any]:
    prompt = _clean_text(node.get("instruction", {}).get("text"))
    return {
        "label": _clean_text(node.get("name")) or "Conversation",
        "nodeType": "conversation",
        "prompt": prompt,
        "systemPrompt": "",
        "instructions": prompt,
        "expectedResponses": [],
        "timeoutSeconds": 30,
        "voiceOverride": None,
        "isEntryNode": str(node.get("id")) == start_node_id,
        "retellType": node.get("type"),
    }


def _transfer_data(node: dict[str, Any]) -> dict[str, Any]:
    transfer_number = _clean_text(node.get("transfer_destination", {}).get("number"))
    transfer_message = _clean_text(node.get("instruction", {}).get("text")) or "Please hold while I transfer your call."
    transfer_type = _clean_text(node.get("transfer_option", {}).get("type"))
    global_condition = _clean_text(node.get("global_node_setting", {}).get("condition"))
    mapped_transfer_type = "warm" if transfer_type == "warm_transfer" else "cold"
    return {
        "label": _clean_text(node.get("name")) or "Transfer Call",
        "nodeType": "transfer",
        "phoneNumber": transfer_number,
        "transferType": mapped_transfer_type,
        "messageBeforeTransfer": transfer_message,
        "globalCondition": global_condition,
        "retellType": node.get("type"),
    }


def _ending_data(node: dict[str, Any]) -> dict[str, Any]:
    message = _clean_text(node.get("instruction", {}).get("text")) or "Politely end the call"
    return {
        "label": _clean_text(node.get("name")) or "End Call",
        "nodeType": "ending",
        "endMessage": message,
        "reason": "completed",
        "customReason": "",
        "retellType": node.get("type"),
    }


def _has_incoming_edges(raw_nodes: list[dict[str, Any]], node_id: str) -> bool:
    for raw_node in raw_nodes:
        if not isinstance(raw_node, dict):
            continue

        for edge in raw_node.get("edges", []):
            if isinstance(edge, dict) and _clean_text(edge.get("destination_node_id")) == node_id:
                return True

        skip_response_edge = raw_node.get("skip_response_edge")
        if isinstance(skip_response_edge, dict) and _clean_text(skip_response_edge.get("destination_node_id")) == node_id:
            return True

        transfer_edge = raw_node.get("edge")
        if isinstance(transfer_edge, dict) and _clean_text(transfer_edge.get("destination_node_id")) == node_id:
            return True

    return False


def _is_unsupported_global_transfer(node: dict[str, Any], raw_nodes: list[dict[str, Any]]) -> bool:
    if _clean_text(node.get("type")) != "transfer_call":
        return False

    node_id = _clean_text(node.get("id"))
    global_condition = _clean_text(node.get("global_node_setting", {}).get("condition"))
    return bool(global_condition) and not _has_incoming_edges(raw_nodes, node_id)


def _prune_unreachable_graph(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    start_node_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    node_ids = {str(node.get("id", "")) for node in nodes}
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in node_ids}

    for edge in edges:
        source = _clean_text(edge.get("source"))
        target = _clean_text(edge.get("target"))
        if source in adjacency and target in adjacency:
            adjacency[source].add(target)

    reachable: set[str] = set()
    if start_node_id in adjacency:
        queue: deque[str] = deque([start_node_id])
        while queue:
            current = queue.popleft()
            if current in reachable:
                continue
            reachable.add(current)
            queue.extend(adjacency.get(current, set()) - reachable)

    pruned_node_ids = sorted(node_ids - reachable)
    pruned_nodes = [node for node in nodes if _clean_text(node.get("id")) in reachable]
    pruned_edges = [
        edge for edge in edges
        if _clean_text(edge.get("source")) in reachable and _clean_text(edge.get("target")) in reachable
    ]
    return pruned_nodes, pruned_edges, pruned_node_ids


def _map_node(node: dict[str, Any], start_node_id: str) -> dict[str, Any] | None:
    node_type = _clean_text(node.get("type"))
    if node_type == "conversation":
        mapped_type = "conversation"
        data = _conversation_data(node, start_node_id)
    elif node_type == "transfer_call":
        mapped_type = "transfer"
        data = _transfer_data(node)
    elif node_type == "end":
        mapped_type = "ending"
        data = _ending_data(node)
    else:
        return None

    position = node.get("display_position", {})
    return {
        "id": str(node.get("id")),
        "type": mapped_type,
        "position": {
            "x": float(position.get("x", 0)),
            "y": float(position.get("y", 0)),
        },
        "data": data,
    }


def _append_edge(result: list[dict[str, Any]], source_id: str, edge: dict[str, Any], suffix: str = "") -> None:
    target_id = _clean_text(edge.get("destination_node_id"))
    if not target_id:
        return

    condition = _clean_text(edge.get("condition")) or _clean_text(edge.get("transition_condition", {}).get("prompt")) or "Transition"
    edge_id = _clean_text(edge.get("id")) or f"{source_id}-{target_id}{suffix}"
    result.append(
        {
            "id": f"{edge_id}{suffix}",
            "source": source_id,
            "target": target_id,
            "label": condition,
            "data": {
                "condition": condition,
            },
        }
    )


def convert_retell_template(payload: dict[str, Any]) -> dict[str, Any]:
    template = payload.get("conversation_flow", {})
    start_node_id = _clean_text(template.get("start_node_id"))
    raw_nodes = template.get("nodes", [])

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    unsupported_global_transfers: list[dict[str, Any]] = []

    for node in raw_nodes:
        if not isinstance(node, dict):
            continue

        if _is_unsupported_global_transfer(node, raw_nodes):
            unsupported_global_transfers.append({
                "id": _clean_text(node.get("id")),
                "name": _clean_text(node.get("name")) or "Transfer Call",
                "condition": _clean_text(node.get("global_node_setting", {}).get("condition")),
                "phone_number": _clean_text(node.get("transfer_destination", {}).get("number")),
                "failure_destination_node_id": _clean_text(node.get("edge", {}).get("destination_node_id")),
            })
            continue

        mapped = _map_node(node, start_node_id)
        if mapped is not None:
            nodes.append(mapped)

        source_id = _clean_text(node.get("id"))
        for edge in node.get("edges", []):
            if isinstance(edge, dict):
                _append_edge(edges, source_id, edge)

        skip_response_edge = node.get("skip_response_edge")
        if isinstance(skip_response_edge, dict):
            _append_edge(edges, source_id, skip_response_edge, suffix="-skip")

        transfer_edge = node.get("edge")
        if isinstance(transfer_edge, dict):
            _append_edge(edges, source_id, transfer_edge, suffix="-transfer")

    nodes, edges, pruned_unreachable_node_ids = _prune_unreachable_graph(nodes, edges, start_node_id)

    return {
        "name": _clean_text(payload.get("agent_name")) or "Imported Retell Template",
        "type": "conversation_flow",
        "language": payload.get("language", "en-US"),
        "voice_id": payload.get("voice_id"),
        "max_call_duration_seconds": int(payload.get("max_call_duration_ms", 3600000) / 1000),
        "extraction_fields": payload.get("post_call_analysis_data", []),
        "config": {
            "execution_mode": "flex",
            "global_prompt": _clean_text(template.get("global_prompt")),
            "nodes": nodes,
            "edges": edges,
            "retell_metadata": {
                "agent_id": payload.get("agent_id"),
                "conversation_flow_id": template.get("conversation_flow_id"),
                "start_node_id": start_node_id,
                "begin_tag_display_position": template.get("begin_tag_display_position"),
                "unsupported_global_transfers": unsupported_global_transfers,
                "pruned_unreachable_node_ids": pruned_unreachable_node_ids,
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert a Retell conversation-flow template into SphereVoice agent config.")
    parser.add_argument("input", type=Path, help="Path to the Retell template JSON file")
    parser.add_argument("output", type=Path, nargs="?", help="Path to write converted JSON")
    args = parser.parse_args()

    payload = json.loads(args.input.read_text())
    converted = convert_retell_template(payload)

    output_text = json.dumps(converted, indent=2)
    if args.output:
        args.output.write_text(output_text + "\n")
    else:
        print(output_text)


if __name__ == "__main__":
    main()