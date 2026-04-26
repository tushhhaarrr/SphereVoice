"use client";

/**
 * Prompt Editor — Monaco Editor wrapper for writing agent system prompts.
 *
 * Features:
 * - Syntax highlighting for `{{variable}}` placeholders
 * - Autocomplete suggestions for known variables
 * - Character count
 * - Variable extraction / display
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Editor, { type OnMount, type Monaco } from "@monaco-editor/react";
import type { editor as MonacoEditor, IPosition, languages } from "monaco-editor";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { AlertTriangle, Check, Copy, Database, Pencil, Plus, Search, Settings, Trash2, Variable } from "lucide-react";

// ── Types ───────────────────────────────────────────────────

export type VariableCategory = "system" | "crm" | "custom";

export interface PromptVariable {
  name: string;
  description: string;
  defaultValue: string;
  /** Variable category for grouped display. Defaults to "custom". */
  category?: VariableCategory;
}

export interface PromptEditorProps {
  /** Current prompt text */
  value: string;
  /** Callback when prompt changes */
  onChange: (value: string) => void;
  /** Available variables for autocomplete */
  variables?: PromptVariable[];
  /** CRM fields available for the user to pick from (not auto-merged into variables) */
  crmFieldsForPicker?: PromptVariable[];
  /** Called when a new variable is defined */
  onAddVariable?: (variable: PromptVariable) => void;
  /** Called when a variable's default value changes */
  onVariableChange?: (name: string, defaultValue: string) => void;
  /** Called to remove a custom variable */
  onVariableRemove?: (name: string) => void;
  /** Editor height (default: "400px") */
  height?: string;
  /** Read-only mode */
  readOnly?: boolean;
  /** Placeholder text */
  placeholder?: string;
}

// ── Constants ───────────────────────────────────────────────

const LANGUAGE_ID = "SphereVoice-prompt";

const DEFAULT_VARIABLES: PromptVariable[] = [
  // System variables — auto-populated at call time
  { name: "agent_name", description: "Display name of this agent", defaultValue: "AI Assistant", category: "system" },
  { name: "company_name", description: "Name of the client company", defaultValue: "", category: "system" },
  { name: "caller_name", description: "Name of the caller (if known)", defaultValue: "", category: "system" },
  { name: "caller_number", description: "Phone number of the caller", defaultValue: "", category: "system" },
  { name: "current_date", description: "Today's date", defaultValue: "", category: "system" },
  { name: "current_time", description: "Current time", defaultValue: "", category: "system" },
  // CRM variables — populated from the tenant's connected CRM.
  // Real CRM fields (Full_Name, Email, Company, etc.) are injected dynamically
  // via useCrmFieldVariables hook in agent-detail-page.tsx. No hardcoded fakes.
  // Custom variables — user-defined defaults
  { name: "business_hours", description: "Business operating hours", defaultValue: "9am-5pm", category: "custom" },
  { name: "transfer_number", description: "Number to transfer calls to", defaultValue: "", category: "custom" },
];

const VARIABLE_PATTERN = /\{\{(\w+)\}\}/g;

// ── Helpers ─────────────────────────────────────────────────

export function extractVariables(text: string): string[] {
  const matches = text.matchAll(VARIABLE_PATTERN);
  const seen = new Set<string>();
  const result: string[] = [];
  for (const match of matches) {
    const name = match[1];
    if (!seen.has(name)) {
      seen.add(name);
      result.push(name);
    }
  }
  return result;
}

// ── CRM Field Picker ────────────────────────────────────────

interface CrmFieldPickerProps {
  fields: PromptVariable[];
  existingVarNames: Set<string>;
  onSelect: (field: PromptVariable) => void;
}

function CrmFieldPicker({ fields, existingVarNames, onSelect }: CrmFieldPickerProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    if (!search) return fields;
    const q = search.toLowerCase();
    return fields.filter(
      (f) =>
        f.name.toLowerCase().includes(q) ||
        f.description.toLowerCase().includes(q),
    );
  }, [fields, search]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 gap-1 px-2 text-xs text-blue-600 dark:text-blue-400"
        >
          <Database className="h-3 w-3" />
          CRM Fields
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-0" align="end">
        <div className="flex items-center gap-2 border-b px-3 py-2">
          <Search className="h-3.5 w-3.5 text-muted-foreground" />
          <input
            className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            placeholder="Search CRM fields..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            autoFocus
          />
        </div>
        <div className="max-h-64 overflow-y-auto p-1">
          {filtered.length === 0 ? (
            <p className="px-3 py-4 text-center text-xs text-muted-foreground">
              {search ? "No matching fields" : "No CRM fields available"}
            </p>
          ) : (
            filtered.map((f) => {
              const alreadyAdded = existingVarNames.has(f.name);
              return (
                <button
                  key={f.name}
                  type="button"
                  disabled={alreadyAdded}
                  className={cn(
                    "flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left transition-colors",
                    alreadyAdded
                      ? "opacity-50 cursor-not-allowed"
                      : "hover:bg-accent cursor-pointer",
                  )}
                  onClick={() => {
                    if (!alreadyAdded) {
                      onSelect(f);
                    }
                  }}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono text-xs font-medium truncate">
                        {f.name}
                      </span>
                      {alreadyAdded && (
                        <Check className="h-3 w-3 text-green-600 shrink-0" />
                      )}
                    </div>
                    <p className="text-[11px] text-muted-foreground truncate">
                      {f.description}
                    </p>
                  </div>
                </button>
              );
            })
          )}
        </div>
        {filtered.length > 0 && (
          <div className="border-t px-3 py-1.5">
            <p className="text-[10px] text-muted-foreground">
              Click a field to insert <code className="font-mono">{`{{field}}`}</code> into your prompt
            </p>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}

// ── Component ───────────────────────────────────────────────

export function PromptEditor({
  value,
  onChange,
  variables = DEFAULT_VARIABLES,
  crmFieldsForPicker = [],
  onAddVariable,
  onVariableChange,
  onVariableRemove,
  height = "400px",
  readOnly = false,
  placeholder = "Write your agent's system prompt here...\n\nUse {{variable_name}} to insert dynamic values.",
}: PromptEditorProps) {
  const editorRef = useRef<MonacoEditor.IStandaloneCodeEditor | null>(null);
  const monacoRef = useRef<Monaco | null>(null);
  const providerDisposablesRef = useRef<{ dispose(): void }[]>([]);
  const [isEditorReady, setIsEditorReady] = useState(false);

  // Custom autocomplete state
  const [showDropdown, setShowDropdown] = useState(false);
  const [dropdownPos, setDropdownPos] = useState({ top: 0, left: 0 });
  const [filterText, setFilterText] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [triggerColumn, setTriggerColumn] = useState(-1);
  const [triggerLine, setTriggerLine] = useState(-1);
  const editorContainerRef = useRef<HTMLDivElement>(null);

  const allVariables = useMemo(() => {
    // Start with defaults, then override with prop values (which carry
    // the user's edited defaultValue).  Props take priority so that
    // typing into the variable filler fields is immediately visible.
    const merged = DEFAULT_VARIABLES.map((d) => {
      const override = variables.find((v) => v.name === d.name);
      return override ? { ...d, ...override } : d;
    });
    // Add any prop variables that aren't in defaults (custom vars + CRM-mapped)
    for (const v of variables) {
      if (!merged.some((m) => m.name === v.name)) {
        merged.push(v);
      }
    }
    // Include CRM picker fields in autocomplete so typing {{ shows them
    for (const f of crmFieldsForPicker) {
      if (!merged.some((m) => m.name === f.name)) {
        merged.push(f);
      }
    }
    return merged;
  }, [variables, crmFieldsForPicker]);

  const usedVariables = useMemo(() => extractVariables(value), [value]);
  const characterCount = value.length;

  // ── Monaco Language Registration ────────────────────────

  const registerLanguage = useCallback(
    (monaco: Monaco) => {
      // Register custom language if not already done
      if (!monaco.languages.getLanguages().some((l: languages.ILanguageExtensionPoint) => l.id === LANGUAGE_ID)) {
        monaco.languages.register({ id: LANGUAGE_ID });
      }

      // Token provider for syntax highlighting
      monaco.languages.setMonarchTokensProvider(LANGUAGE_ID, {
        tokenizer: {
          root: [
            [/\{\{/, { token: "variable.bracket", next: "@variable" }],
            [/[^{]+/, "string"],
            [/\{/, "string"],
          ],
          variable: [
            [/\w+/, "variable.name"],
            [/\}\}/, { token: "variable.bracket", next: "@root" }],
            [/./, "variable.name"],
          ],
        },
      });

      // Define theme rules for variables
      monaco.editor.defineTheme("SphereVoice-prompt-theme", {
        base: "vs-dark",
        inherit: true,
        rules: [
          { token: "variable.bracket", foreground: "569CD6", fontStyle: "bold" },
          { token: "variable.name", foreground: "4EC9B0", fontStyle: "bold" },
          { token: "string", foreground: "D4D4D4" },
        ],
        colors: {
          "editor.background": "#0A0A0A",
          "editor.foreground": "#D4D4D4",
          "editor.lineHighlightBackground": "#1A1A2E",
          "editor.selectionBackground": "#264F78",
          "editorCursor.foreground": "#AEAFAD",
          "editorLineNumber.foreground": "#5A5A5A",
          "editorLineNumber.activeForeground": "#C6C6C6",
        },
      });

      // Dispose previous providers to avoid duplicates
      for (const d of providerDisposablesRef.current) d.dispose();
      providerDisposablesRef.current = [];

      // Register hover provider (keep for variable tooltips)
      providerDisposablesRef.current.push(monaco.languages.registerHoverProvider(LANGUAGE_ID, {
        provideHover: (model: MonacoEditor.ITextModel, position: IPosition) => {
          const line = model.getLineContent(position.lineNumber);
          const lineVariables = line.matchAll(VARIABLE_PATTERN);

          for (const match of lineVariables) {
            const startCol = (match.index ?? 0) + 1;
            const endCol = startCol + match[0].length;

            if (position.column >= startCol && position.column <= endCol) {
              const varName = match[1];
              const varDef = allVariables.find((v) => v.name === varName);

              return {
                range: {
                  startLineNumber: position.lineNumber,
                  endLineNumber: position.lineNumber,
                  startColumn: startCol,
                  endColumn: endCol,
                },
                contents: [
                  { value: `**\`{{${varName}}}\`**${varDef?.category ? ` · _${varDef.category === "crm" ? "CRM" : varDef.category === "system" ? "System" : "Custom"}_` : ""}` },
                  {
                    value: varDef
                      ? varDef.category === "crm"
                        ? `${varDef.description}\n\n_Populated from CRM contact data via campaign variable mapping_`
                        : `${varDef.description}${varDef.defaultValue ? `\n\nDefault: \`${varDef.defaultValue}\`` : ""}`
                      : "_Undefined variable — will be replaced at call time if provided_",
                  },
                ],
              };
            }
          }

          return null;
        },
      }));
    },
    [allVariables]
  );

  // ── Editor Mount ────────────────────────────────────────

  const handleEditorMount: OnMount = useCallback(
    (editor, monaco) => {
      editorRef.current = editor;
      monacoRef.current = monaco;
      registerLanguage(monaco);
      setIsEditorReady(true);

      // Focus editor on mount
      editor.focus();
    },
    [registerLanguage]
  );

  // ── {{ trigger detection (separate effect to avoid stale closures) ──
  useEffect(() => {
    const editor = editorRef.current;
    if (!editor || !isEditorReady) return;

    const contentDisposable = editor.onDidChangeModelContent(() => {
      const position = editor.getPosition();
      if (!position) return;
      const model = editor.getModel();
      if (!model) return;

      const lineContent = model.getLineContent(position.lineNumber);
      const textBefore = lineContent.substring(0, position.column - 1);
      const match = textBefore.match(/\{\{(\w*)$/);

      if (match) {
        const filter = match[1];
        const coords = editor.getScrolledVisiblePosition(position);
        const containerRect = editorContainerRef.current?.getBoundingClientRect();
        if (coords && containerRect) {
          setDropdownPos({
            top: containerRect.top + coords.top + coords.height + 4,
            left: containerRect.left + coords.left,
          });
        }
        setFilterText(filter);
        setTriggerColumn(position.column - match[0].length);
        setTriggerLine(position.lineNumber);
        setSelectedIndex(0);
        setShowDropdown(true);
      } else {
        setShowDropdown(false);
      }
    });

    const cursorDisposable = editor.onDidChangeCursorPosition(() => {
      // Re-check the trigger on every cursor move
      const position = editor.getPosition();
      if (!position) { setShowDropdown(false); return; }
      const model = editor.getModel();
      if (!model) { setShowDropdown(false); return; }

      const lineContent = model.getLineContent(position.lineNumber);
      const textBefore = lineContent.substring(0, position.column - 1);
      if (!/\{\{(\w*)$/.test(textBefore)) {
        setShowDropdown(false);
      }
    });

    const blurDisposable = editor.onDidBlurEditorWidget(() => {
      setTimeout(() => setShowDropdown(false), 200);
    });

    return () => {
      contentDisposable.dispose();
      cursorDisposable.dispose();
      blurDisposable.dispose();
    };
  }, [isEditorReady]);

  // Re-register completions when variables change
  useEffect(() => {
    if (monacoRef.current && isEditorReady) {
      registerLanguage(monacoRef.current);
    }
  }, [allVariables, isEditorReady, registerLanguage]);

  // ── Custom Autocomplete ──────────────────────────────────

  const CATEGORY_ORDER: Record<string, number> = { system: 0, crm: 1, custom: 2 };
  const CATEGORY_LABELS: Record<string, string> = { system: "System", crm: "CRM", custom: "Custom" };
  const CATEGORY_ICONS: Record<string, React.ElementType> = { system: Settings, crm: Database, custom: Variable };

  const filteredDropdownVars = useMemo(() => {
    const lower = filterText.toLowerCase();
    return allVariables
      .filter((v) => v.name.toLowerCase().includes(lower))
      .sort((a, b) => {
        const catA = CATEGORY_ORDER[a.category ?? "custom"] ?? 2;
        const catB = CATEGORY_ORDER[b.category ?? "custom"] ?? 2;
        if (catA !== catB) return catA - catB;
        return a.name.localeCompare(b.name);
      });
  }, [allVariables, filterText]);

  const groupedDropdownVars = useMemo(() => {
    const groups: { category: string; label: string; vars: PromptVariable[] }[] = [];
    let currentCat = "";
    for (const v of filteredDropdownVars) {
      const cat = v.category ?? "custom";
      if (cat !== currentCat) {
        currentCat = cat;
        groups.push({ category: cat, label: CATEGORY_LABELS[cat] ?? cat, vars: [] });
      }
      groups[groups.length - 1].vars.push(v);
    }
    return groups;
  }, [filteredDropdownVars]);

  const insertDropdownVariable = useCallback(
    (variable: PromptVariable) => {
      const editor = editorRef.current;
      if (!editor || triggerColumn < 0 || triggerLine < 0) return;

      const position = editor.getPosition();
      if (!position) return;

      const insertText = `{{${variable.name}}}`;
      editor.executeEdits("insert-variable", [
        {
          range: {
            startLineNumber: triggerLine,
            endLineNumber: position.lineNumber,
            startColumn: triggerColumn,
            endColumn: position.column,
          },
          text: insertText,
        },
      ]);

      setShowDropdown(false);
      setTriggerColumn(-1);
      setTriggerLine(-1);
      setFilterText("");
      editor.focus();
    },
    [triggerColumn, triggerLine]
  );

  // Keyboard navigation for dropdown
  useEffect(() => {
    if (!showDropdown || !editorRef.current) return;

    const disposable = editorRef.current.onKeyDown((e) => {
      if (!showDropdown) return;

      if (e.keyCode === 9 /* Escape */) {
        e.preventDefault();
        e.stopPropagation();
        setShowDropdown(false);
      } else if (e.keyCode === 18 /* DownArrow */) {
        e.preventDefault();
        e.stopPropagation();
        setSelectedIndex((prev) => Math.min(prev + 1, filteredDropdownVars.length - 1));
      } else if (e.keyCode === 16 /* UpArrow */) {
        e.preventDefault();
        e.stopPropagation();
        setSelectedIndex((prev) => Math.max(prev - 1, 0));
      } else if (e.keyCode === 3 /* Enter */ || e.keyCode === 2 /* Tab */) {
        if (filteredDropdownVars.length > 0) {
          e.preventDefault();
          e.stopPropagation();
          insertDropdownVariable(filteredDropdownVars[selectedIndex]);
        }
      }
    });

    return () => disposable.dispose();
  }, [showDropdown, filteredDropdownVars, selectedIndex, insertDropdownVariable]);

  // ── Insert Variable (from badge panel) ──────────────────

  const insertVariable = useCallback(
    (varName: string) => {
      const editor = editorRef.current;
      if (!editor) return;

      const position = editor.getPosition();
      if (!position) return;

      const insertText = `{{${varName}}}`;
      editor.executeEdits("insert-variable", [
        {
          range: {
            startLineNumber: position.lineNumber,
            endLineNumber: position.lineNumber,
            startColumn: position.column,
            endColumn: position.column,
          },
          text: insertText,
        },
      ]);

      editor.focus();
    },
    []
  );

  const copyToClipboard = useCallback(() => {
    navigator.clipboard.writeText(value).catch(() => {
      // Fallback: do nothing
    });
  }, [value]);

  // ── Render ──────────────────────────────────────────────

  return (
    <div className="space-y-3">
      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Variable className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">System Prompt</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">
            {characterCount.toLocaleString()} characters
          </span>
          <Separator orientation="vertical" className="h-4" />
          <Button
            variant="ghost"
            size="sm"
            onClick={copyToClipboard}
            className="h-7 px-2"
            title="Copy to clipboard"
          >
            <Copy className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* Editor */}
      <div ref={editorContainerRef} className="relative rounded-lg border border-border">
        <Editor
          height={height}
          language={LANGUAGE_ID}
          theme="SphereVoice-prompt-theme"
          value={value || ""}
          onChange={(v) => onChange(v ?? "")}
          onMount={handleEditorMount}
          options={{
            readOnly,
            minimap: { enabled: false },
            lineNumbers: "on",
            scrollBeyondLastLine: false,
            wordWrap: "on",
            wrappingStrategy: "advanced",
            fontSize: 14,
            lineHeight: 22,
            padding: { top: 12, bottom: 12 },
            suggestOnTriggerCharacters: false,
            quickSuggestions: false,
            suggest: { showWords: false, showSnippets: false },
            tabSize: 2,
            renderLineHighlight: "line",
            cursorBlinking: "smooth",
            cursorSmoothCaretAnimation: "on",
            smoothScrolling: true,
            overviewRulerBorder: false,
            hideCursorInOverviewRuler: true,
            scrollbar: {
              vertical: "auto",
              horizontal: "hidden",
              verticalScrollbarSize: 8,
            },
            placeholder,
          }}
        />

      </div>

      {/* Custom Variable Autocomplete Dropdown — rendered via portal to escape overflow */}
      {showDropdown && filteredDropdownVars.length > 0 && createPortal(
        <div
          className="fixed z-[9999] w-80 max-h-72 overflow-y-auto overscroll-contain rounded-lg border border-border bg-popover p-1 shadow-xl animate-in fade-in-0 zoom-in-95"
          style={{ top: dropdownPos.top, left: dropdownPos.left }}
          onMouseDown={(e) => e.preventDefault()}
        >
          {groupedDropdownVars.map((group) => {
            const Icon = CATEGORY_ICONS[group.category] ?? Variable;
            return (
              <div key={group.category}>
                <div className="flex items-center gap-1.5 px-2 pt-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">
                  <Icon className="h-3 w-3" />
                  {group.label}
                </div>
                {group.vars.map((v) => {
                  const flatIdx = filteredDropdownVars.indexOf(v);
                  return (
                    <button
                      key={v.name}
                      type="button"
                      className={cn(
                        "flex w-full flex-col gap-0.5 rounded-md px-2 py-1.5 text-left cursor-pointer transition-colors",
                        flatIdx === selectedIndex
                          ? "bg-accent text-accent-foreground"
                          : "text-popover-foreground hover:bg-accent/50"
                      )}
                      onMouseEnter={() => setSelectedIndex(flatIdx)}
                      onClick={() => insertDropdownVariable(v)}
                    >
                      <span className="font-mono text-xs font-medium">{`{{${v.name}}}`}</span>
                      {v.description && (
                        <span className="text-[11px] leading-tight text-muted-foreground">
                          {v.description}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            );
          })}
        </div>,
        document.body
      )}

      {/* Variables Panel — Editable default values for used variables */}
      <Card>
        <CardHeader className="py-3 px-4">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm">Variables</CardTitle>
            <div className="flex items-center gap-1">
              {onAddVariable && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 gap-1 px-2 text-xs"
                  onClick={() =>
                    onAddVariable({
                      name: "new_variable",
                      description: "Description",
                      defaultValue: "",
                      category: "custom",
                    })
                  }
                >
                  <Plus className="h-3 w-3" />
                  Add
                </Button>
              )}
              {onAddVariable && crmFieldsForPicker.length > 0 && (
                <CrmFieldPicker
                  fields={crmFieldsForPicker}
                  existingVarNames={new Set(allVariables.map((v) => v.name))}
                  onSelect={(field) => {
                    onAddVariable(field);
                    insertVariable(field.name);
                  }}
                />
              )}
            </div>
          </div>
        </CardHeader>
        <Separator />
        <CardContent className="p-2">
          <div className="space-y-3 p-2">
            {/* ── Used variables with editable default values ── */}
            {(() => {
              if (usedVariables.length === 0) return null;

              // Auto-filled system vars that don't need manual values
              const AUTO_FILLED_SET = new Set([
                "current_date", "current_time", "current_datetime",
                "caller_number", "caller_name",
              ]);

              const usedVarObjects = usedVariables.map((name) => {
                const v = allVariables.find((av) => av.name === name);
                return {
                  name,
                  description: v?.description ?? "",
                  defaultValue: v?.defaultValue ?? "",
                  category: v?.category ?? "custom",
                  isAutoFilled: AUTO_FILLED_SET.has(name),
                };
              });

              return (
                <div>
                  <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                    <Pencil className="h-3 w-3" />
                    Used in Prompt
                    <span className="text-[10px] font-normal">(set default values for calls)</span>
                  </div>
                  <div className="space-y-2">
                    {usedVarObjects.map((v) => (
                      <div key={v.name} className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => insertVariable(v.name)}
                          className="group shrink-0"
                          title="Click to insert at cursor"
                          disabled={readOnly}
                        >
                          <Badge
                            variant="outline"
                            className={cn(
                              "cursor-pointer font-mono text-[11px] transition-colors group-hover:bg-primary group-hover:text-primary-foreground",
                              v.category === "crm" && "border-blue-500/30",
                            )}
                          >
                            {v.name}
                          </Badge>
                        </button>
                        {v.isAutoFilled ? (
                          <span className="text-[11px] italic text-muted-foreground">auto-filled at call time</span>
                        ) : (
                          <Input
                            value={v.defaultValue}
                            onChange={(e) => onVariableChange?.(v.name, e.target.value)}
                            placeholder={v.description || `Default value for ${v.name}`}
                            className="h-7 text-xs"
                            disabled={readOnly}
                          />
                        )}
                        {v.category === "custom" && !v.isAutoFilled && onVariableRemove && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6 shrink-0 text-muted-foreground hover:text-destructive"
                            onClick={() => onVariableRemove(v.name)}
                            title="Remove variable"
                          >
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              );
            })()}

            {/* ── Available but unused variables (clickable badges) ── */}
            {(() => {
              const unusedVars = allVariables.filter((v) => !usedVariables.includes(v.name));
              if (unusedVars.length === 0) return null;

              const groups: { key: string; label: string; icon: React.ElementType; vars: PromptVariable[] }[] = [];
              const systemUnused = unusedVars.filter((v) => v.category === "system");
              const crmUnused = unusedVars.filter((v) => v.category === "crm");
              const customUnused = unusedVars.filter((v) => !v.category || v.category === "custom");

              if (systemUnused.length > 0) groups.push({ key: "system", label: "System", icon: Settings, vars: systemUnused });
              if (crmUnused.length > 0) groups.push({ key: "crm", label: "CRM", icon: Database, vars: crmUnused });
              if (customUnused.length > 0) groups.push({ key: "custom", label: "Custom", icon: Variable, vars: customUnused });

              return (
                <div>
                  <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                    <Variable className="h-3 w-3" />
                    Available
                    <span className="text-[10px] font-normal">(click to insert)</span>
                  </div>
                  {groups.map((group) => (
                    <div key={group.key} className="mb-2">
                      <div className="mb-1 flex items-center gap-1 text-[10px] uppercase tracking-wider text-muted-foreground/70">
                        <group.icon className="h-2.5 w-2.5" />
                        {group.label}
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {group.vars.map((v) => (
                          <button
                            key={v.name}
                            type="button"
                            onClick={() => insertVariable(v.name)}
                            className="group inline-flex items-center"
                            title={`${v.description}${v.defaultValue ? ` (default: ${v.defaultValue})` : ""}\nClick to insert`}
                            disabled={readOnly}
                          >
                            <Badge
                              variant="outline"
                              className="cursor-pointer font-mono text-[10px] opacity-60 transition-all group-hover:opacity-100 group-hover:bg-primary group-hover:text-primary-foreground"
                            >
                              {`{{${v.name}}}`}
                            </Badge>
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              );
            })()}
          </div>
        </CardContent>
      </Card>

      {/* Missing Default Values Warning */}
      {(() => {
        // Variables auto-populated at runtime — never need a default value
        const AUTO_FILLED = new Set([
          "current_date", "current_time", "current_datetime",
          "caller_number", "caller_name", "agent_name", "company_name",
        ]);
        const missing = usedVariables.filter((name) => {
          if (AUTO_FILLED.has(name)) return false;
          const v = allVariables.find((av) => av.name === name);
          return !v || !v.defaultValue;
        });
        if (missing.length === 0) return null;
        return (
          <div className="flex items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-500/30 dark:bg-amber-950/40 dark:text-amber-300">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <div>
              <span className="font-medium">Missing default values: </span>
              {missing.map((name, i) => (
                <span key={name}>
                  {i > 0 && ", "}
                  <code className="rounded bg-amber-200/50 px-1 py-0.5 font-mono dark:bg-amber-800/40">{`{{${name}}}`}</code>
                </span>
              ))}
              <span className="ml-1 text-amber-700 dark:text-amber-400">
                — set a default value in the Variables panel above, or these will be empty during calls.
              </span>
            </div>
          </div>
        );
      })()}

      {/* Used Variables Summary */}
      {usedVariables.length > 0 && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>Using:</span>
          {usedVariables.map((v) => (
            <Badge key={v} variant="secondary" className="font-mono text-[10px]">
              {v}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
