"use client";

/**
 * Node Configuration Panel — Slide-out editor for each node type.
 *
 * Renders a form tailored to the selected node's type.
 * Changes are applied immediately to the node data.
 */

import { useCallback } from "react";
import { X, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import type {
  FlowNode,
  FlowNodeData,
  ConversationNodeData,
  FunctionNodeData,
  LogicSplitNodeData,
  TransferNodeData,
  PressDigitNodeData,
  ExtractVariableNodeData,
  SmsNodeData,
  EndingNodeData,
  LogicCondition,
  ResponseMapping,
} from "../../../types/flow";
import { NODE_TYPE_METADATA } from "../../../types/flow";

interface NodeConfigPanelProps {
  node: FlowNode;
  onUpdate: (nodeId: string, data: Partial<FlowNodeData>) => void;
  onClose: () => void;
  embedded?: boolean;
}

export function NodeConfigPanel({ node, onUpdate, onClose, embedded = false }: NodeConfigPanelProps) {
  const nodeData = node.data as unknown as FlowNodeData;
  const meta = NODE_TYPE_METADATA[nodeData.nodeType];

  const update = useCallback(
    (partial: Partial<FlowNodeData>) => {
      onUpdate(node.id, partial);
    },
    [node.id, onUpdate]
  );

  return (
    <div className={embedded ? "rounded-xl border bg-background" : "flex h-full w-[360px] flex-col border-l bg-background"}>
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-4">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            Node Editor
          </p>
          <h3 className="mt-1 text-sm font-semibold">{meta.label} Configuration</h3>
          <p className="text-xs text-muted-foreground">{meta.description}</p>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Body */}
      <ScrollArea className={embedded ? "max-h-[calc(100vh-420px)] px-4 py-3" : "flex-1 px-4 py-3"}>
        <div className="space-y-4">
          {/* Label — shared across all nodes */}
          <div className="space-y-1.5">
            <Label htmlFor="node-label" className="text-xs">Node Label</Label>
            <Input
              id="node-label"
              value={nodeData.label}
              onChange={(e) => update({ label: e.target.value } as Partial<FlowNodeData>)}
              placeholder="Enter node label"
            />
          </div>

          <Separator />

          {/* Type-specific fields */}
          {nodeData.nodeType === "conversation" && (
            <ConversationFields
              data={nodeData as ConversationNodeData}
              onUpdate={update}
            />
          )}
          {nodeData.nodeType === "function" && (
            <FunctionFields
              data={nodeData as FunctionNodeData}
              onUpdate={update}
            />
          )}
          {nodeData.nodeType === "logic_split" && (
            <LogicSplitFields
              data={nodeData as LogicSplitNodeData}
              onUpdate={update}
            />
          )}
          {nodeData.nodeType === "transfer" && (
            <TransferFields
              data={nodeData as TransferNodeData}
              onUpdate={update}
            />
          )}
          {nodeData.nodeType === "press_digit" && (
            <PressDigitFields
              data={nodeData as PressDigitNodeData}
              onUpdate={update}
            />
          )}
          {nodeData.nodeType === "extract_variable" && (
            <ExtractVariableFields
              data={nodeData as ExtractVariableNodeData}
              onUpdate={update}
            />
          )}
          {nodeData.nodeType === "sms" && (
            <SmsFields data={nodeData as SmsNodeData} onUpdate={update} />
          )}
          {nodeData.nodeType === "ending" && (
            <EndingFields data={nodeData as EndingNodeData} onUpdate={update} />
          )}
        </div>
      </ScrollArea>
    </div>
  );
}

// ── Conversation Fields ─────────────────────────────────────

function ConversationFields({
  data,
  onUpdate,
}: {
  data: ConversationNodeData;
  onUpdate: (partial: Partial<FlowNodeData>) => void;
}) {
  return (
    <>
      <div className="flex items-center justify-between">
        <Label htmlFor="is-entry" className="text-xs">Entry (Start) Node</Label>
        <Switch
          id="is-entry"
          checked={data.isEntryNode}
          onCheckedChange={(checked: boolean) =>
            onUpdate({ isEntryNode: checked } as Partial<FlowNodeData>)
          }
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="system-prompt" className="text-xs">System Prompt</Label>
        <Textarea
          id="system-prompt"
          value={data.systemPrompt}
          onChange={(e) =>
            onUpdate({ systemPrompt: e.target.value } as Partial<FlowNodeData>)
          }
          placeholder="System instructions for this step..."
          rows={4}
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="instructions" className="text-xs">Instructions</Label>
        <Textarea
          id="instructions"
          value={data.instructions}
          onChange={(e) =>
            onUpdate({ instructions: e.target.value } as Partial<FlowNodeData>)
          }
          placeholder="What should the AI do at this step?"
          rows={3}
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="timeout" className="text-xs">Timeout (seconds)</Label>
        <Input
          id="timeout"
          type="number"
          min={0}
          value={data.timeoutSeconds}
          onChange={(e) =>
            onUpdate({ timeoutSeconds: Number(e.target.value) } as Partial<FlowNodeData>)
          }
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="voice-override" className="text-xs">Voice Override (optional)</Label>
        <Input
          id="voice-override"
          value={data.voiceOverride || ""}
          onChange={(e) =>
            onUpdate({ voiceOverride: e.target.value || null } as Partial<FlowNodeData>)
          }
          placeholder="Voice ID override for this node"
        />
      </div>
    </>
  );
}

// ── Function Fields ─────────────────────────────────────────

function FunctionFields({
  data,
  onUpdate,
}: {
  data: FunctionNodeData;
  onUpdate: (partial: Partial<FlowNodeData>) => void;
}) {
  const addMapping = useCallback(() => {
    onUpdate({
      responseMapping: [
        ...data.responseMapping,
        { jsonPath: "", variableName: "" },
      ],
    } as Partial<FlowNodeData>);
  }, [data.responseMapping, onUpdate]);

  const removeMapping = useCallback(
    (index: number) => {
      onUpdate({
        responseMapping: data.responseMapping.filter((_, i) => i !== index),
      } as Partial<FlowNodeData>);
    },
    [data.responseMapping, onUpdate]
  );

  const updateMapping = useCallback(
    (index: number, field: keyof ResponseMapping, value: string) => {
      const updated = [...data.responseMapping];
      updated[index] = { ...updated[index], [field]: value };
      onUpdate({ responseMapping: updated } as Partial<FlowNodeData>);
    },
    [data.responseMapping, onUpdate]
  );

  return (
    <>
      <div className="space-y-1.5">
        <Label htmlFor="endpoint-url" className="text-xs">Endpoint URL</Label>
        <Input
          id="endpoint-url"
          value={data.endpointUrl}
          onChange={(e) =>
            onUpdate({ endpointUrl: e.target.value } as Partial<FlowNodeData>)
          }
          placeholder="https://api.example.com/webhook"
        />
      </div>
      <div className="space-y-1.5">
        <Label className="text-xs">HTTP Method</Label>
        <Select
          value={data.method}
          onValueChange={(val: string) =>
            onUpdate({ method: val as FunctionNodeData["method"] } as Partial<FlowNodeData>)
          }
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="GET">GET</SelectItem>
            <SelectItem value="POST">POST</SelectItem>
            <SelectItem value="PUT">PUT</SelectItem>
            <SelectItem value="DELETE">DELETE</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="body-template" className="text-xs">Body Template (JSON)</Label>
        <Textarea
          id="body-template"
          value={data.bodyTemplate}
          onChange={(e) =>
            onUpdate({ bodyTemplate: e.target.value } as Partial<FlowNodeData>)
          }
          placeholder='{"key": "{{variable}}"}'
          rows={4}
          className="font-mono text-xs"
        />
      </div>
      <div className="space-y-1.5">
        <Label className="text-xs">Error Handling</Label>
        <Select
          value={data.errorHandling}
          onValueChange={(val: string) =>
            onUpdate({ errorHandling: val as FunctionNodeData["errorHandling"] } as Partial<FlowNodeData>)
          }
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="continue">Continue</SelectItem>
            <SelectItem value="retry">Retry</SelectItem>
            <SelectItem value="end_call">End Call</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="timeout-ms" className="text-xs">Timeout (ms)</Label>
        <Input
          id="timeout-ms"
          type="number"
          min={100}
          value={data.timeoutMs}
          onChange={(e) =>
            onUpdate({ timeoutMs: Number(e.target.value) } as Partial<FlowNodeData>)
          }
        />
      </div>
      <Separator />
      <div>
        <div className="flex items-center justify-between">
          <Label className="text-xs">Response Mappings</Label>
          <Button variant="ghost" size="sm" onClick={addMapping}>
            <Plus className="mr-1 h-3 w-3" /> Add
          </Button>
        </div>
        {data.responseMapping.map((mapping, i) => (
          <div key={i} className="mt-2 flex gap-2">
            <Input
              value={mapping.jsonPath}
              onChange={(e) => updateMapping(i, "jsonPath", e.target.value)}
              placeholder="$.data.field"
              className="flex-1 text-xs"
            />
            <Input
              value={mapping.variableName}
              onChange={(e) => updateMapping(i, "variableName", e.target.value)}
              placeholder="variable_name"
              className="flex-1 text-xs"
            />
            <Button
              variant="ghost"
              size="icon"
              onClick={() => removeMapping(i)}
              className="shrink-0"
            >
              <Trash2 className="h-3 w-3" />
            </Button>
          </div>
        ))}
      </div>
    </>
  );
}

// ── Logic Split Fields ──────────────────────────────────────

function LogicSplitFields({
  data,
  onUpdate,
}: {
  data: LogicSplitNodeData;
  onUpdate: (partial: Partial<FlowNodeData>) => void;
}) {
  const addCondition = useCallback(() => {
    const newCondition: LogicCondition = {
      id: `cond_${Date.now()}`,
      variableName: "",
      operator: "equals",
      value: "",
      targetHandleId: `output-${data.conditions.length}`,
    };
    onUpdate({
      conditions: [...data.conditions, newCondition],
    } as Partial<FlowNodeData>);
  }, [data.conditions, onUpdate]);

  const removeCondition = useCallback(
    (index: number) => {
      onUpdate({
        conditions: data.conditions.filter((_, i) => i !== index),
      } as Partial<FlowNodeData>);
    },
    [data.conditions, onUpdate]
  );

  const updateCondition = useCallback(
    (index: number, field: keyof LogicCondition, value: string) => {
      const updated = [...data.conditions];
      updated[index] = { ...updated[index], [field]: value };
      onUpdate({ conditions: updated } as Partial<FlowNodeData>);
    },
    [data.conditions, onUpdate]
  );

  return (
    <>
      <div>
        <div className="flex items-center justify-between">
          <Label className="text-xs">Conditions</Label>
          <Button variant="ghost" size="sm" onClick={addCondition}>
            <Plus className="mr-1 h-3 w-3" /> Add Condition
          </Button>
        </div>
        {data.conditions.map((cond, i) => (
          <div key={cond.id} className="mt-3 space-y-2 rounded-md border p-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium">Condition {i + 1}</span>
              <Button variant="ghost" size="icon" onClick={() => removeCondition(i)}>
                <Trash2 className="h-3 w-3" />
              </Button>
            </div>
            <Input
              value={cond.variableName}
              onChange={(e) => updateCondition(i, "variableName", e.target.value)}
              placeholder="Variable name"
              className="text-xs"
            />
            <Select
              value={cond.operator}
              onValueChange={(val: string) => updateCondition(i, "operator", val)}
            >
              <SelectTrigger className="text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="equals">equals</SelectItem>
                <SelectItem value="not_equals">not equals</SelectItem>
                <SelectItem value="contains">contains</SelectItem>
                <SelectItem value="not_contains">not contains</SelectItem>
                <SelectItem value="greater_than">greater than</SelectItem>
                <SelectItem value="less_than">less than</SelectItem>
                <SelectItem value="regex">regex</SelectItem>
                <SelectItem value="is_empty">is empty</SelectItem>
                <SelectItem value="is_not_empty">is not empty</SelectItem>
              </SelectContent>
            </Select>
            <Input
              value={cond.value}
              onChange={(e) => updateCondition(i, "value", e.target.value)}
              placeholder="Value"
              className="text-xs"
            />
          </div>
        ))}
        <p className="mt-2 text-[10px] text-muted-foreground">
          Last output handle is always the &quot;default&quot; path.
        </p>
      </div>
    </>
  );
}

// ── Transfer Fields ─────────────────────────────────────────

function TransferFields({
  data,
  onUpdate,
}: {
  data: TransferNodeData;
  onUpdate: (partial: Partial<FlowNodeData>) => void;
}) {
  return (
    <>
      <div className="space-y-1.5">
        <Label htmlFor="transfer-to" className="text-xs">Transfer To (phone number)</Label>
        <Input
          id="transfer-to"
          value={data.transferTo}
          onChange={(e) =>
            onUpdate({ transferTo: e.target.value } as Partial<FlowNodeData>)
          }
          placeholder="+15551234567"
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="transfer-message" className="text-xs">Transfer Message</Label>
        <Textarea
          id="transfer-message"
          value={data.transferMessage}
          onChange={(e) =>
            onUpdate({ transferMessage: e.target.value } as Partial<FlowNodeData>)
          }
          placeholder="Message before transfer..."
          rows={2}
        />
      </div>
      <div className="flex items-center justify-between">
        <Label htmlFor="warm-transfer" className="text-xs">Warm Transfer</Label>
        <Switch
          id="warm-transfer"
          checked={data.warmTransfer}
          onCheckedChange={(checked: boolean) =>
            onUpdate({ warmTransfer: checked } as Partial<FlowNodeData>)
          }
        />
      </div>
    </>
  );
}

// ── Press Digit Fields ──────────────────────────────────────

function PressDigitFields({
  data,
  onUpdate,
}: {
  data: PressDigitNodeData;
  onUpdate: (partial: Partial<FlowNodeData>) => void;
}) {
  return (
    <>
      <div className="space-y-1.5">
        <Label htmlFor="digits" className="text-xs">Digits to Send</Label>
        <Input
          id="digits"
          value={data.digits}
          onChange={(e) =>
            onUpdate({ digits: e.target.value } as Partial<FlowNodeData>)
          }
          placeholder="12345#"
          className="font-mono"
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="delay" className="text-xs">Delay Between Digits (ms)</Label>
        <Input
          id="delay"
          type="number"
          min={0}
          value={data.delayMs}
          onChange={(e) =>
            onUpdate({ delayMs: Number(e.target.value) } as Partial<FlowNodeData>)
          }
        />
      </div>
    </>
  );
}

// ── Extract Variable Fields ─────────────────────────────────

function ExtractVariableFields({
  data,
  onUpdate,
}: {
  data: ExtractVariableNodeData;
  onUpdate: (partial: Partial<FlowNodeData>) => void;
}) {
  return (
    <>
      <div className="space-y-1.5">
        <Label htmlFor="var-name" className="text-xs">Variable Name</Label>
        <Input
          id="var-name"
          value={data.variableName}
          onChange={(e) =>
            onUpdate({ variableName: e.target.value } as Partial<FlowNodeData>)
          }
          placeholder="appointment_date"
          className="font-mono text-xs"
        />
      </div>
      <div className="space-y-1.5">
        <Label className="text-xs">Variable Type</Label>
        <Select
          value={data.variableType}
          onValueChange={(val: string) =>
            onUpdate({ variableType: val as ExtractVariableNodeData["variableType"] } as Partial<FlowNodeData>)
          }
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="text">Text</SelectItem>
            <SelectItem value="number">Number</SelectItem>
            <SelectItem value="boolean">Boolean</SelectItem>
            <SelectItem value="date">Date</SelectItem>
            <SelectItem value="email">Email</SelectItem>
            <SelectItem value="phone">Phone</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="extraction-prompt" className="text-xs">Extraction Prompt</Label>
        <Textarea
          id="extraction-prompt"
          value={data.extractionPrompt}
          onChange={(e) =>
            onUpdate({ extractionPrompt: e.target.value } as Partial<FlowNodeData>)
          }
          placeholder="Ask the caller for their preferred date..."
          rows={3}
        />
      </div>
      <div className="flex items-center justify-between">
        <Label htmlFor="required" className="text-xs">Required</Label>
        <Switch
          id="required"
          checked={data.required}
          onCheckedChange={(checked: boolean) =>
            onUpdate({ required: checked } as Partial<FlowNodeData>)
          }
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="retry-prompt" className="text-xs">Retry Prompt</Label>
        <Input
          id="retry-prompt"
          value={data.retryPrompt}
          onChange={(e) =>
            onUpdate({ retryPrompt: e.target.value } as Partial<FlowNodeData>)
          }
          placeholder="Could you please repeat that?"
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="max-retries" className="text-xs">Max Retries</Label>
        <Input
          id="max-retries"
          type="number"
          min={0}
          max={10}
          value={data.maxRetries}
          onChange={(e) =>
            onUpdate({ maxRetries: Number(e.target.value) } as Partial<FlowNodeData>)
          }
        />
      </div>
    </>
  );
}

// ── SMS Fields ──────────────────────────────────────────────

function SmsFields({
  data,
  onUpdate,
}: {
  data: SmsNodeData;
  onUpdate: (partial: Partial<FlowNodeData>) => void;
}) {
  return (
    <>
      <div className="flex items-center justify-between">
        <Label htmlFor="use-caller" className="text-xs">Send to Caller Number</Label>
        <Switch
          id="use-caller"
          checked={data.useCallerNumber}
          onCheckedChange={(checked: boolean) =>
            onUpdate({ useCallerNumber: checked } as Partial<FlowNodeData>)
          }
        />
      </div>
      {!data.useCallerNumber && (
        <div className="space-y-1.5">
          <Label htmlFor="to-number" className="text-xs">To Number</Label>
          <Input
            id="to-number"
            value={data.toNumber}
            onChange={(e) =>
              onUpdate({ toNumber: e.target.value } as Partial<FlowNodeData>)
            }
            placeholder="+15551234567"
          />
        </div>
      )}
      <div className="space-y-1.5">
        <Label htmlFor="message-template" className="text-xs">Message Template</Label>
        <Textarea
          id="message-template"
          value={data.messageTemplate}
          onChange={(e) =>
            onUpdate({ messageTemplate: e.target.value } as Partial<FlowNodeData>)
          }
          placeholder="Hi {{caller_name}}, your appointment is confirmed for {{date}}."
          rows={3}
        />
      </div>
    </>
  );
}

// ── Ending Fields ───────────────────────────────────────────

function EndingFields({
  data,
  onUpdate,
}: {
  data: EndingNodeData;
  onUpdate: (partial: Partial<FlowNodeData>) => void;
}) {
  return (
    <>
      <div className="space-y-1.5">
        <Label className="text-xs">Ending Reason</Label>
        <Select
          value={data.reason}
          onValueChange={(val: string) =>
            onUpdate({ reason: val as EndingNodeData["reason"] } as Partial<FlowNodeData>)
          }
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="completed">Completed</SelectItem>
            <SelectItem value="transferred">Transferred</SelectItem>
            <SelectItem value="error">Error</SelectItem>
            <SelectItem value="no_response">No Response</SelectItem>
            <SelectItem value="custom">Custom</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {data.reason === "custom" && (
        <div className="space-y-1.5">
          <Label htmlFor="custom-reason" className="text-xs">Custom Reason</Label>
          <Input
            id="custom-reason"
            value={data.customReason}
            onChange={(e) =>
              onUpdate({ customReason: e.target.value } as Partial<FlowNodeData>)
            }
            placeholder="Enter custom reason"
          />
        </div>
      )}
      <div className="space-y-1.5">
        <Label htmlFor="ending-message" className="text-xs">Ending Message</Label>
        <Textarea
          id="ending-message"
          value={data.endingMessage}
          onChange={(e) =>
            onUpdate({ endingMessage: e.target.value } as Partial<FlowNodeData>)
          }
          placeholder="Thank you for calling. Goodbye!"
          rows={2}
        />
      </div>
    </>
  );
}
