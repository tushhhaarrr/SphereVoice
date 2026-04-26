/**
 * Assign Agent Dialog — pick an agent to assign to a phone number.
 */

"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAgents } from "@/modules/agents";

import { useAssignAgent } from "../hooks/use-phone-numbers";

interface AssignAgentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  numberId: string;
  phoneNumber: string;
  currentAgentId: string | null;
  tenantId?: string;
  tenantName?: string;
}

export function AssignAgentDialog({
  open,
  onOpenChange,
  numberId,
  phoneNumber,
  currentAgentId,
  tenantId,
  tenantName,
}: AssignAgentDialogProps) {
  const [selectedAgentId, setSelectedAgentId] = useState<string>(
    currentAgentId ?? "none",
  );

  const { data: agentsData, isLoading: agentsLoading } = useAgents({
    limit: 100,
    tenantId,
  });
  const assignMutation = useAssignAgent();

  async function handleSave() {
    await assignMutation.mutateAsync({
      numberId,
      body: {
        agent_id: selectedAgentId === "none" ? null : selectedAgentId,
      },
    });
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Assign Agent</DialogTitle>
          <DialogDescription>
            Choose an agent to handle calls on{" "}
            <span className="font-mono font-medium">{phoneNumber}</span>
            {tenantId ? ` for ${tenantName ?? "this workspace"}` : ""}.
          </DialogDescription>
        </DialogHeader>

        <div className="py-4">
          {agentsLoading ? (
            <div className="flex justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <Select
              value={selectedAgentId}
              onValueChange={setSelectedAgentId}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select an agent" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">None (unassign)</SelectItem>
                {agentsData?.agents?.map((agent) => (
                  <SelectItem key={agent.id} value={agent.id}>
                    {agent.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={assignMutation.isPending || agentsLoading}
          >
            {assignMutation.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
