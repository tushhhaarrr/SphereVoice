"use client";

/**
 * Publish Confirmation Dialog — Confirm before publishing an agent version.
 *
 * Shows validation result and allows optional description.
 */

import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle,
  Loader2,
  Rocket,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import type { FlowValidationResult } from "../types/flow";

interface PublishDialogProps {
  agentName: string;
  currentVersion: number;
  validation: FlowValidationResult | null;
  isPublishing: boolean;
  onPublish: () => void | Promise<void>;
  onValidate: () => FlowValidationResult;
  trigger?: React.ReactNode;
}

export function PublishDialog({
  agentName,
  currentVersion,
  validation,
  isPublishing,
  onPublish,
  onValidate,
  trigger,
}: PublishDialogProps) {
  const [open, setOpen] = useState(false);
  const [localValidation, setLocalValidation] = useState<FlowValidationResult | null>(validation);

  const handleOpenChange = (isOpen: boolean) => {
    setOpen(isOpen);
    if (isOpen) {
      // Run validation when dialog opens
      const result = onValidate();
      setLocalValidation(result);
    }
  };

  const handlePublish = async () => {
    try {
      await onPublish();
      setOpen(false);
    } catch {
      // Leave the dialog open so the user can retry after the surfaced error.
    }
  };

  const displayValidation = localValidation ?? validation;
  const isValid = displayValidation?.valid ?? false;
  const hasErrors = (displayValidation?.errors.length ?? 0) > 0;
  const hasWarnings = (displayValidation?.warnings.length ?? 0) > 0;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button size="sm">
            <Rocket className="mr-1 h-3.5 w-3.5" />
            Publish
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Publish Agent</DialogTitle>
          <DialogDescription>
            Publish &ldquo;{agentName}&rdquo; as version {currentVersion + 1}.
            This creates an immutable snapshot.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Validation Status */}
          {displayValidation && (
            <div
              className={`rounded-lg border p-3 ${
                isValid
                  ? "border-green-200 bg-green-50 dark:bg-green-950"
                  : "border-red-200 bg-red-50 dark:bg-red-950"
              }`}
            >
              <div className="flex items-center gap-2">
                {isValid ? (
                  <CheckCircle className="h-4 w-4 text-green-600" />
                ) : (
                  <AlertTriangle className="h-4 w-4 text-red-600" />
                )}
                <span className={`text-sm font-medium ${isValid ? "text-green-700" : "text-red-700"}`}>
                  {isValid ? "Flow is valid" : "Flow has errors"}
                </span>
              </div>

              {hasErrors && (
                <ul className="mt-2 space-y-1">
                  {displayValidation.errors.map((err, i) => (
                    <li key={i} className="text-xs text-red-600">
                      {err.message}
                    </li>
                  ))}
                </ul>
              )}

              {hasWarnings && (
                <ul className="mt-2 space-y-1">
                  {displayValidation.warnings.map((warn, i) => (
                    <li key={i} className="text-xs text-yellow-600">
                      {warn.message}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => void handlePublish()}
            disabled={isPublishing || hasErrors}
          >
            {isPublishing ? (
              <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
            ) : (
              <Rocket className="mr-1 h-3.5 w-3.5" />
            )}
            Publish v{currentVersion + 1}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
