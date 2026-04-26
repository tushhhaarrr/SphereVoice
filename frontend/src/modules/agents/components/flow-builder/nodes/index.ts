/**
 * Node type registry — maps FlowNodeType to React components.
 *
 * Used by React Flow's `nodeTypes` prop to render custom nodes.
 */

import { ConversationNode } from "./conversation-node";
import { FunctionNode } from "./function-node";
import { LogicSplitNode } from "./logic-split-node";
import { TransferNode } from "./transfer-node";
import { PressDigitNode } from "./press-digit-node";
import { ExtractVariableNode } from "./extract-variable-node";
import { SmsNode } from "./sms-node";
import { EndingNode } from "./ending-node";

export const flowNodeTypes = {
  conversation: ConversationNode,
  function: FunctionNode,
  logic_split: LogicSplitNode,
  transfer: TransferNode,
  press_digit: PressDigitNode,
  extract_variable: ExtractVariableNode,
  sms: SmsNode,
  ending: EndingNode,
} as const;

export {
  ConversationNode,
  FunctionNode,
  LogicSplitNode,
  TransferNode,
  PressDigitNode,
  ExtractVariableNode,
  SmsNode,
  EndingNode,
};
