import type { FlowEdge, FlowNode, FlowNodeData, FlowNodeType } from "../types/flow";

type UnknownRecord = Record<string, unknown>;

export interface RetellImportResult {
  name: string;
  nodes: FlowNode[];
  edges: FlowEdge[];
  globalPrompt: string;
  executionMode: "flex";
  language: string;
  extractionFields: Record<string, unknown>[];
  retellMetadata: Record<string, unknown>;
}

function asRecord(value: unknown): UnknownRecord {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as UnknownRecord)
    : {};
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function asNumber(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function hasIncomingEdges(rawNodes: unknown[], nodeId: string): boolean {
  return rawNodes.some((rawNode) => {
    const node = asRecord(rawNode);
    const directEdges = asArray(node.edges).some((edgeValue) => {
      const edge = asRecord(edgeValue);
      return asString(edge.destination_node_id) === nodeId;
    });

    const skipResponseEdge = asRecord(node.skip_response_edge);
    const transferEdge = asRecord(node.edge);

    return directEdges
      || asString(skipResponseEdge.destination_node_id) === nodeId
      || asString(transferEdge.destination_node_id) === nodeId;
  });
}

function sanitizeConversationData(node: UnknownRecord, startNodeId: string): FlowNode["data"] {
  const instruction = asString(asRecord(node.instruction).text);

  return {
    label: asString(node.name) || "Conversation",
    nodeType: "conversation",
    prompt: instruction,
    instructions: instruction,
    systemPrompt: "",
    expectedResponses: [],
    timeoutSeconds: 30,
    voiceOverride: null,
    isEntryNode: asString(node.id) === startNodeId,
    retellType: node.type,
  } as FlowNode["data"];
}

function sanitizeTransferData(node: UnknownRecord): FlowNode["data"] {
  const destination = asString(asRecord(asRecord(node.transfer_destination)).number);
  const instruction = asString(asRecord(node.instruction).text) || "Please hold while I transfer your call.";
  const transferType = asString(asRecord(node.transfer_option).type);
  const isWarm = transferType === "warm_transfer";

  return {
    label: asString(node.name) || "Transfer Call",
    nodeType: "transfer",
    transferTo: destination,
    phoneNumber: destination,
    transferMessage: instruction,
    messageBeforeTransfer: instruction,
    warmTransfer: isWarm,
    transferType: isWarm ? "warm" : "cold",
    globalCondition: asString(asRecord(node.global_node_setting).condition),
    retellType: node.type,
  } as FlowNode["data"];
}

function sanitizeEndingData(node: UnknownRecord): FlowNode["data"] {
  const endingMessage = asString(asRecord(node.instruction).text) || "Politely end the call";

  return {
    label: asString(node.name) || "End Call",
    nodeType: "ending",
    endingMessage,
    endMessage: endingMessage,
    reason: "completed",
    customReason: "",
    retellType: node.type,
  } as FlowNode["data"];
}

function mapRetellNode(node: UnknownRecord, startNodeId: string): FlowNode | null {
  const nodeType = asString(node.type);
  let mappedType: FlowNodeType;
  let data: FlowNode["data"];

  if (nodeType === "conversation") {
    mappedType = "conversation";
    data = sanitizeConversationData(node, startNodeId);
  } else if (nodeType === "transfer_call") {
    mappedType = "transfer";
    data = sanitizeTransferData(node);
  } else if (nodeType === "end") {
    mappedType = "ending";
    data = sanitizeEndingData(node);
  } else {
    return null;
  }

  const displayPosition = asRecord(node.display_position);

  return {
    id: asString(node.id),
    type: mappedType,
    position: {
      x: asNumber(displayPosition.x),
      y: asNumber(displayPosition.y),
    },
    data,
  } as FlowNode;
}

function appendEdge(edges: FlowEdge[], sourceId: string, edgeValue: unknown, suffix = ""): void {
  const edge = asRecord(edgeValue);
  const target = asString(edge.destination_node_id);

  if (!target) {
    return;
  }

  const transitionCondition = asRecord(edge.transition_condition);
  const label = asString(edge.condition) || asString(transitionCondition.prompt) || "Transition";
  const edgeId = asString(edge.id) || `${sourceId}-${target}${suffix}`;

  edges.push({
    id: `${edgeId}${suffix}`,
    source: sourceId,
    target,
    label,
    data: { condition: label },
  });
}

function pruneUnreachableGraph(nodes: FlowNode[], edges: FlowEdge[], startNodeId: string) {
  const reachable = new Set<string>();
  const adjacency = new Map<string, string[]>();

  for (const node of nodes) {
    adjacency.set(node.id, []);
  }

  for (const edge of edges) {
    const neighbors = adjacency.get(edge.source);
    if (neighbors && adjacency.has(edge.target)) {
      neighbors.push(edge.target);
    }
  }

  const queue: string[] = adjacency.has(startNodeId) ? [startNodeId] : [];
  while (queue.length > 0) {
    const current = queue.shift();
    if (!current || reachable.has(current)) {
      continue;
    }
    reachable.add(current);
    for (const neighbor of adjacency.get(current) ?? []) {
      if (!reachable.has(neighbor)) {
        queue.push(neighbor);
      }
    }
  }

  return {
    nodes: nodes.filter((node) => reachable.has(node.id)),
    edges: edges.filter((edge) => reachable.has(edge.source) && reachable.has(edge.target)),
    prunedNodeIds: nodes.filter((node) => !reachable.has(node.id)).map((node) => node.id),
  };
}

export function normalizeFlowNodesForEditor(nodes: FlowNode[]): FlowNode[] {
  return nodes.map((node) => {
    const data = asRecord(node.data);

    if (node.type === "conversation") {
      const instructions = asString(data.instructions) || asString(data.prompt);
      return {
        ...node,
        data: {
          ...node.data,
          instructions,
          prompt: asString(data.prompt) || instructions,
          systemPrompt: asString(data.systemPrompt),
          expectedResponses: Array.isArray(data.expectedResponses) ? data.expectedResponses : [],
          timeoutSeconds: typeof data.timeoutSeconds === "number" ? data.timeoutSeconds : 30,
          voiceOverride: typeof data.voiceOverride === "string" ? data.voiceOverride : null,
          isEntryNode: data.isEntryNode === true,
        } as FlowNodeData,
      } as FlowNode;
    }

    if (node.type === "transfer") {
      const transferTo = asString(data.transferTo) || asString(data.phoneNumber);
      const transferMessage = asString(data.transferMessage) || asString(data.messageBeforeTransfer);
      const transferType = asString(data.transferType);
      return {
        ...node,
        data: {
          ...node.data,
          transferTo,
          phoneNumber: transferTo,
          transferMessage,
          messageBeforeTransfer: transferMessage,
          warmTransfer: data.warmTransfer === true || transferType === "warm",
        } as FlowNodeData,
      } as FlowNode;
    }

    if (node.type === "ending") {
      const endingMessage = asString(data.endingMessage) || asString(data.endMessage);
      return {
        ...node,
        data: {
          ...node.data,
          endingMessage,
          endMessage: endingMessage,
        } as FlowNodeData,
      } as FlowNode;
    }

    return node;
  });
}

export function serializeFlowNodesForApi(nodes: FlowNode[]): FlowNode[] {
  return nodes.map((node) => {
    const data = asRecord(node.data);

    if (node.type === "conversation") {
      const instructions = asString(data.instructions);
      return {
        ...node,
        data: {
          ...node.data,
          prompt: instructions || asString(data.prompt) || asString(data.systemPrompt),
          instructions,
        } as FlowNodeData,
      } as FlowNode;
    }

    if (node.type === "transfer") {
      const transferTo = asString(data.transferTo) || asString(data.phoneNumber);
      const transferMessage = asString(data.transferMessage) || asString(data.messageBeforeTransfer);
      const isWarm = data.warmTransfer === true;
      return {
        ...node,
        data: {
          ...node.data,
          transferTo,
          phoneNumber: transferTo,
          transferMessage,
          messageBeforeTransfer: transferMessage,
          transferType: isWarm ? "warm" : "cold",
        } as FlowNodeData,
      } as FlowNode;
    }

    if (node.type === "ending") {
      const endingMessage = asString(data.endingMessage) || asString(data.endMessage);
      return {
        ...node,
        data: {
          ...node.data,
          endingMessage,
          endMessage: endingMessage,
        } as FlowNodeData,
      } as FlowNode;
    }

    return node;
  });
}

export function importRetellJson(source: string): RetellImportResult {
  const payload = asRecord(JSON.parse(source));
  const template = asRecord(payload.conversation_flow);
  const rawNodes = asArray(template.nodes);
  const startNodeId = asString(template.start_node_id);
  const nodes: FlowNode[] = [];
  const edges: FlowEdge[] = [];
  const unsupportedGlobalTransfers: Array<Record<string, unknown>> = [];

  for (const rawNodeValue of rawNodes) {
    const rawNode = asRecord(rawNodeValue);
    const rawType = asString(rawNode.type);
    const nodeId = asString(rawNode.id);
    const globalCondition = asString(asRecord(rawNode.global_node_setting).condition);
    const isUnsupportedGlobalTransfer = rawType === "transfer_call"
      && globalCondition.length > 0
      && !hasIncomingEdges(rawNodes, nodeId);

    if (isUnsupportedGlobalTransfer) {
      unsupportedGlobalTransfers.push({
        id: nodeId,
        name: asString(rawNode.name) || "Transfer Call",
        condition: globalCondition,
        phone_number: asString(asRecord(asRecord(rawNode.transfer_destination)).number),
        failure_destination_node_id: asString(asRecord(rawNode.edge).destination_node_id),
      });
      continue;
    }

    const mappedNode = mapRetellNode(rawNode, startNodeId);
    if (mappedNode) {
      nodes.push(mappedNode);
    }

    for (const edgeValue of asArray(rawNode.edges)) {
      appendEdge(edges, nodeId, edgeValue);
    }

    if (rawNode.skip_response_edge) {
      appendEdge(edges, nodeId, rawNode.skip_response_edge, "-skip");
    }

    if (rawNode.edge) {
      appendEdge(edges, nodeId, rawNode.edge, "-transfer");
    }
  }

  const pruned = pruneUnreachableGraph(nodes, edges, startNodeId);

  return {
    name: asString(payload.agent_name) || "Imported Retell Flow",
    nodes: normalizeFlowNodesForEditor(pruned.nodes),
    edges: pruned.edges,
    globalPrompt: asString(template.global_prompt),
    executionMode: "flex",
    language: asString(payload.language) || "en-US",
    extractionFields: asArray(payload.post_call_analysis_data) as Record<string, unknown>[],
    retellMetadata: {
      agent_id: payload.agent_id,
      conversation_flow_id: template.conversation_flow_id,
      start_node_id: startNodeId,
      begin_tag_display_position: template.begin_tag_display_position,
      unsupported_global_transfers: unsupportedGlobalTransfers,
      pruned_unreachable_node_ids: pruned.prunedNodeIds,
    },
  };
}