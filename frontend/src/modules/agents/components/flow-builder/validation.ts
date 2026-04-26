/**
 * Flow Validation — Checks flow integrity before publishing.
 *
 * Rules:
 * 1. Exactly one entry (start) node required
 * 2. At least one ending node required
 * 3. No orphan nodes (all nodes must be connected)
 * 4. All ending nodes must be reachable from start
 * 5. All required fields must be populated
 *
 * Returns < 2 seconds for flows up to 100 nodes.
 */

import type {
  FlowNode,
  FlowEdge,
  FlowValidationResult,
  FlowValidationError,
  FlowValidationWarning,
  ConversationNodeData,
  FunctionNodeData,
  ExtractVariableNodeData,
  TransferNodeData,
  SmsNodeData,
  PressDigitNodeData,
} from "../../types/flow";

export function validateFlow(
  nodes: FlowNode[],
  edges: FlowEdge[]
): FlowValidationResult {
  const errors: FlowValidationError[] = [];
  const warnings: FlowValidationWarning[] = [];

  if (nodes.length === 0) {
    errors.push({
      nodeId: null,
      message: "Flow has no nodes. Add at least a start and ending node.",
      type: "no_start_node",
    });
    return { valid: false, errors, warnings };
  }

  // 1. Check for exactly one entry node
  const entryNodes = nodes.filter(
    (n) =>
      n.type === "conversation" &&
      (n.data as unknown as ConversationNodeData).isEntryNode
  );

  if (entryNodes.length === 0) {
    errors.push({
      nodeId: null,
      message: "No start node found. Mark one Conversation node as the entry point.",
      type: "no_start_node",
    });
  } else if (entryNodes.length > 1) {
    for (const node of entryNodes.slice(1)) {
      errors.push({
        nodeId: node.id,
        message: `Duplicate entry node: "${(node.data as unknown as ConversationNodeData).label}". Only one start node is allowed.`,
        type: "duplicate_entry",
      });
    }
  }

  // 2. Check for at least one ending node
  const endingNodes = nodes.filter((n) => n.type === "ending");
  if (endingNodes.length === 0) {
    errors.push({
      nodeId: null,
      message: "No ending node found. Add at least one Ending node.",
      type: "no_ending_node",
    });
  }

  // 3. Check for orphan nodes (not connected to any edge)
  const connectedNodeIds = new Set<string>();
  for (const edge of edges) {
    connectedNodeIds.add(edge.source);
    connectedNodeIds.add(edge.target);
  }

  // Entry nodes with no incoming edges are OK (they're the start).
  // Ending nodes with no outgoing edges are OK (they're terminal).
  for (const node of nodes) {
    if (!connectedNodeIds.has(node.id)) {
      // Single-node flow is an orphan only if there are other nodes
      if (nodes.length > 1) {
        errors.push({
          nodeId: node.id,
          message: `Orphan node: "${node.data.label ?? node.id}" is not connected to any other node.`,
          type: "orphan_node",
        });
      }
    }
  }

  // 4. Check that ending nodes are reachable from start (BFS)
  if (entryNodes.length === 1 && endingNodes.length > 0) {
    const adjacency = new Map<string, string[]>();
    for (const edge of edges) {
      const existing = adjacency.get(edge.source) || [];
      existing.push(edge.target);
      adjacency.set(edge.source, existing);
    }

    const reachable = new Set<string>();
    const queue: string[] = [entryNodes[0].id];
    while (queue.length > 0) {
      const current = queue.shift()!;
      if (reachable.has(current)) continue;
      reachable.add(current);
      for (const neighbor of adjacency.get(current) || []) {
        if (!reachable.has(neighbor)) {
          queue.push(neighbor);
        }
      }
    }

    for (const endNode of endingNodes) {
      if (!reachable.has(endNode.id)) {
        errors.push({
          nodeId: endNode.id,
          message: `Ending node "${endNode.data.label ?? endNode.id}" is not reachable from the start node.`,
          type: "unreachable_ending",
        });
      }
    }
  }

  // 5. Check required fields per node type
  for (const node of nodes) {
    const label = (node.data.label as string) || node.id;

    switch (node.type) {
      case "conversation": {
        const cd = node.data as ConversationNodeData;
        if (!cd.systemPrompt && !cd.instructions) {
          warnings.push({
            nodeId: node.id,
            message: `Conversation node "${label}" has no prompt or instructions.`,
            type: "empty_prompt",
          });
        }
        break;
      }
      case "function": {
        const fd = node.data as FunctionNodeData;
        if (!fd.endpointUrl) {
          errors.push({
            nodeId: node.id,
            message: `Function node "${label}" is missing an endpoint URL.`,
            type: "missing_required_field",
          });
        }
        break;
      }
      case "extract_variable": {
        const ev = node.data as ExtractVariableNodeData;
        if (!ev.variableName) {
          errors.push({
            nodeId: node.id,
            message: `Extract Variable node "${label}" is missing a variable name.`,
            type: "missing_required_field",
          });
        }
        if (!ev.extractionPrompt) {
          errors.push({
            nodeId: node.id,
            message: `Extract Variable node "${label}" is missing an extraction prompt.`,
            type: "missing_required_field",
          });
        }
        break;
      }
      case "transfer": {
        const td = node.data as TransferNodeData;
        if (!td.transferTo) {
          errors.push({
            nodeId: node.id,
            message: `Transfer node "${label}" is missing a transfer destination.`,
            type: "missing_required_field",
          });
        }
        break;
      }
      case "sms": {
        const sd = node.data as SmsNodeData;
        if (!sd.messageTemplate) {
          errors.push({
            nodeId: node.id,
            message: `SMS node "${label}" is missing a message template.`,
            type: "missing_required_field",
          });
        }
        break;
      }
      case "press_digit": {
        const pd = node.data as PressDigitNodeData;
        if (!pd.digits) {
          errors.push({
            nodeId: node.id,
            message: `Press Digit node "${label}" is missing digits to send.`,
            type: "missing_required_field",
          });
        }
        break;
      }
    }
  }

  // 6. Warn on large flows
  if (nodes.length > 50) {
    warnings.push({
      nodeId: null,
      message: `Flow has ${nodes.length} nodes. Consider simplifying for better performance.`,
      type: "large_flow",
    });
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
  };
}
