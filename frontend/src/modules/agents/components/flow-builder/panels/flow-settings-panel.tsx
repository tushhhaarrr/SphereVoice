"use client";

/**
 * Flow Settings Panel — Global flow configuration.
 *
 * Controls execution mode (Flex vs Rigid), global prompt, and variables.
 */

import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import type { ExecutionMode } from "../../../types/flow";

interface FlowSettingsPanelProps {
  executionMode: ExecutionMode;
  globalPrompt: string;
  onExecutionModeChange: (mode: ExecutionMode) => void;
  onGlobalPromptChange: (prompt: string) => void;
}

export function FlowSettingsPanel({
  executionMode,
  globalPrompt,
  onExecutionModeChange,
  onGlobalPromptChange,
}: FlowSettingsPanelProps) {
  return (
    <div className="space-y-5 rounded-xl border bg-background p-4 shadow-sm">
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
          Flow Settings
        </h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Set global execution rules that apply across the full conversation.
        </p>
      </div>

      {/* Execution Mode */}
      <div className="space-y-1.5">
        <Label className="text-xs">Execution Mode</Label>
        <Select
          value={executionMode}
          onValueChange={(val: string) =>
            onExecutionModeChange(val as ExecutionMode)
          }
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="flex">
              <div>
                <span className="font-medium">Flex</span>
                <span className="ml-1 text-xs text-muted-foreground">
                  — AI jumps between nodes based on context
                </span>
              </div>
            </SelectItem>
            <SelectItem value="rigid">
              <div>
                <span className="font-medium">Rigid</span>
                <span className="ml-1 text-xs text-muted-foreground">
                  — Sequential step-by-step execution
                </span>
              </div>
            </SelectItem>
          </SelectContent>
        </Select>
        <p className="text-[10px] text-muted-foreground">
          {executionMode === "flex"
            ? "AI can navigate between nodes based on conversation context and user intent."
            : "Nodes are executed sequentially following the edge connections."}
        </p>
      </div>

      <Separator />

      {/* Global Prompt */}
      <div className="space-y-1.5">
        <Label htmlFor="global-prompt" className="text-xs">Global Prompt</Label>
        <Textarea
          id="global-prompt"
          value={globalPrompt}
          onChange={(e) => onGlobalPromptChange(e.target.value)}
          placeholder="System-level instructions that apply to all nodes in this flow..."
          rows={5}
        />
        <p className="text-[10px] text-muted-foreground">
          This prompt is prepended to every node&apos;s system prompt during execution.
        </p>
      </div>
    </div>
  );
}
