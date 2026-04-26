/**
 * Flow Builder types — Conversation Flow node types, edge types, and flow configuration.
 *
 * Mirrors the backend flow_engine.py data structures for the
 * React Flow visual conversation flow builder.
 */

import type { Node, Edge } from "@xyflow/react";

// ── Node Type Enum ──────────────────────────────────────────

export const FLOW_NODE_TYPES = [
  "conversation",
  "function",
  "logic_split",
  "transfer",
  "press_digit",
  "extract_variable",
  "sms",
  "ending",
] as const;

export type FlowNodeType = (typeof FLOW_NODE_TYPES)[number];

// ── Execution Modes ─────────────────────────────────────────

export type ExecutionMode = "flex" | "rigid";

// ── Node Data Structures ────────────────────────────────────

/** Base data every flow node carries. */
export interface FlowNodeDataBase {
  /** Index signature required for @xyflow/react Node<T> compatibility. */
  [key: string]: unknown;
  label: string;
  nodeType: FlowNodeType;
}

/** Conversation Node — AI speaks and listens. */
export interface ConversationNodeData extends FlowNodeDataBase {
  nodeType: "conversation";
  systemPrompt: string;
  instructions: string;
  expectedResponses: string[];
  timeoutSeconds: number;
  voiceOverride: string | null;
  isEntryNode: boolean;
}

/** Function Node — Calls an external API or webhook. */
export interface FunctionNodeData extends FlowNodeDataBase {
  nodeType: "function";
  endpointUrl: string;
  method: "GET" | "POST" | "PUT" | "DELETE";
  headers: Record<string, string>;
  bodyTemplate: string;
  responseMapping: ResponseMapping[];
  errorHandling: "continue" | "retry" | "end_call";
  retryCount: number;
  timeoutMs: number;
}

export interface ResponseMapping {
  jsonPath: string;
  variableName: string;
}

/** Logic Split Node — Branches based on conditions. */
export interface LogicSplitNodeData extends FlowNodeDataBase {
  nodeType: "logic_split";
  conditions: LogicCondition[];
  defaultPath: string;
}

export interface LogicCondition {
  id: string;
  variableName: string;
  operator: "equals" | "not_equals" | "contains" | "not_contains" | "greater_than" | "less_than" | "regex" | "is_empty" | "is_not_empty";
  value: string;
  targetHandleId: string;
}

/** Call Transfer Node — Transfers to human or phone number. */
export interface TransferNodeData extends FlowNodeDataBase {
  nodeType: "transfer";
  transferTo: string;
  transferMessage: string;
  warmTransfer: boolean;
}

/** Press Digit Node — Sends DTMF tones. */
export interface PressDigitNodeData extends FlowNodeDataBase {
  nodeType: "press_digit";
  digits: string;
  delayMs: number;
}

/** Extract Variable Node — Pulls structured data from conversation. */
export interface ExtractVariableNodeData extends FlowNodeDataBase {
  nodeType: "extract_variable";
  variableName: string;
  extractionPrompt: string;
  variableType: "text" | "number" | "boolean" | "date" | "email" | "phone";
  required: boolean;
  retryPrompt: string;
  maxRetries: number;
}

/** SMS Node — Sends SMS during call. */
export interface SmsNodeData extends FlowNodeDataBase {
  nodeType: "sms";
  toNumber: string;
  messageTemplate: string;
  useCallerNumber: boolean;
}

/** Ending Node — Terminates conversation. */
export interface EndingNodeData extends FlowNodeDataBase {
  nodeType: "ending";
  endingMessage: string;
  reason: "completed" | "transferred" | "error" | "no_response" | "custom";
  customReason: string;
}

/** Union of all node data types. */
export type FlowNodeData =
  | ConversationNodeData
  | FunctionNodeData
  | LogicSplitNodeData
  | TransferNodeData
  | PressDigitNodeData
  | ExtractVariableNodeData
  | SmsNodeData
  | EndingNodeData;

// ── React Flow typed aliases ────────────────────────────────

export type FlowNode = Node<FlowNodeData, FlowNodeType>;
export type FlowEdge = Edge;

// ── Flow Configuration (stored in agent.config) ─────────────

export interface FlowConfig {
  executionMode: ExecutionMode;
  nodes: FlowNode[];
  edges: FlowEdge[];
  globalPrompt: string;
  variables: FlowVariable[];
}

export interface FlowVariable {
  name: string;
  description: string;
  defaultValue: string;
}

// ── Validation ──────────────────────────────────────────────

export interface FlowValidationResult {
  valid: boolean;
  errors: FlowValidationError[];
  warnings: FlowValidationWarning[];
}

export interface FlowValidationError {
  nodeId: string | null;
  message: string;
  type: "no_start_node" | "no_ending_node" | "orphan_node" | "missing_required_field" | "unreachable_ending" | "duplicate_entry";
}

export interface FlowValidationWarning {
  nodeId: string | null;
  message: string;
  type: "empty_prompt" | "no_expected_responses" | "large_flow";
}

// ── Node defaults factory ───────────────────────────────────

export function createDefaultNodeData(nodeType: FlowNodeType, label: string): FlowNodeData {
  switch (nodeType) {
    case "conversation":
      return {
        label,
        nodeType: "conversation",
        systemPrompt: "",
        instructions: "",
        expectedResponses: [],
        timeoutSeconds: 30,
        voiceOverride: null,
        isEntryNode: false,
      };
    case "function":
      return {
        label,
        nodeType: "function",
        endpointUrl: "",
        method: "POST",
        headers: {},
        bodyTemplate: "{}",
        responseMapping: [],
        errorHandling: "continue",
        retryCount: 0,
        timeoutMs: 5000,
      };
    case "logic_split":
      return {
        label,
        nodeType: "logic_split",
        conditions: [],
        defaultPath: "",
      };
    case "transfer":
      return {
        label,
        nodeType: "transfer",
        transferTo: "",
        transferMessage: "Please hold while I transfer your call.",
        warmTransfer: false,
      };
    case "press_digit":
      return {
        label,
        nodeType: "press_digit",
        digits: "",
        delayMs: 500,
      };
    case "extract_variable":
      return {
        label,
        nodeType: "extract_variable",
        variableName: "",
        extractionPrompt: "",
        variableType: "text",
        required: true,
        retryPrompt: "I didn't catch that. Could you please repeat?",
        maxRetries: 2,
      };
    case "sms":
      return {
        label,
        nodeType: "sms",
        toNumber: "",
        messageTemplate: "",
        useCallerNumber: true,
      };
    case "ending":
      return {
        label,
        nodeType: "ending",
        endingMessage: "Thank you for calling. Goodbye!",
        reason: "completed",
        customReason: "",
      };
  }
}

// ── Node visual metadata ────────────────────────────────────

export interface NodeTypeMetadata {
  type: FlowNodeType;
  label: string;
  description: string;
  icon: string;
  color: string;
  borderColor: string;
  bgColor: string;
  maxOutputs: number;
}

export const NODE_TYPE_METADATA: Record<FlowNodeType, NodeTypeMetadata> = {
  conversation: {
    type: "conversation",
    label: "Conversation",
    description: "AI speaks and listens to the caller",
    icon: "MessageSquare",
    color: "text-blue-600",
    borderColor: "border-blue-400",
    bgColor: "bg-blue-50 dark:bg-blue-950",
    maxOutputs: 1,
  },
  function: {
    type: "function",
    label: "Function",
    description: "Call an external API or webhook",
    icon: "Code",
    color: "text-purple-600",
    borderColor: "border-purple-400",
    bgColor: "bg-purple-50 dark:bg-purple-950",
    maxOutputs: 1,
  },
  logic_split: {
    type: "logic_split",
    label: "Logic Split",
    description: "Branch based on conditions",
    icon: "GitBranch",
    color: "text-orange-600",
    borderColor: "border-orange-400",
    bgColor: "bg-orange-50 dark:bg-orange-950",
    maxOutputs: 6,
  },
  transfer: {
    type: "transfer",
    label: "Call Transfer",
    description: "Transfer to human or phone number",
    icon: "PhoneForwarded",
    color: "text-green-600",
    borderColor: "border-green-400",
    bgColor: "bg-green-50 dark:bg-green-950",
    maxOutputs: 0,
  },
  press_digit: {
    type: "press_digit",
    label: "Press Digit",
    description: "Send DTMF tones",
    icon: "Hash",
    color: "text-teal-600",
    borderColor: "border-teal-400",
    bgColor: "bg-teal-50 dark:bg-teal-950",
    maxOutputs: 1,
  },
  extract_variable: {
    type: "extract_variable",
    label: "Extract Variable",
    description: "Pull structured data from conversation",
    icon: "Variable",
    color: "text-indigo-600",
    borderColor: "border-indigo-400",
    bgColor: "bg-indigo-50 dark:bg-indigo-950",
    maxOutputs: 1,
  },
  sms: {
    type: "sms",
    label: "SMS",
    description: "Send SMS during the call",
    icon: "MessageCircle",
    color: "text-pink-600",
    borderColor: "border-pink-400",
    bgColor: "bg-pink-50 dark:bg-pink-950",
    maxOutputs: 1,
  },
  ending: {
    type: "ending",
    label: "Ending",
    description: "End the conversation",
    icon: "Square",
    color: "text-red-600",
    borderColor: "border-red-400",
    bgColor: "bg-red-50 dark:bg-red-950",
    maxOutputs: 0,
  },
};
