"use client";

import {
    useCallback,
    useEffect,
    useMemo,
    useRef,
    useState,
} from "react";
import type { PromptVariable } from "./prompt-editor";

// ── Helpers ─────────────────────────────────────────────────

/** Invisible mirror div used to measure caret position inside a textarea. */
const MIRROR_STYLES = [
    "fontFamily",
    "fontSize",
    "fontWeight",
    "fontStyle",
    "letterSpacing",
    "lineHeight",
    "textTransform",
    "wordSpacing",
    "textIndent",
    "whiteSpace",
    "wordWrap",
    "overflowWrap",
    "tabSize",
    "padding",
    "paddingTop",
    "paddingRight",
    "paddingBottom",
    "paddingLeft",
    "borderWidth",
    "boxSizing",
] as const;

function getCaretCoordinates(
    textarea: HTMLTextAreaElement,
    position: number
): { top: number; left: number; height: number } {
    const mirror = document.createElement("div");
    const style = window.getComputedStyle(textarea);

    mirror.style.position = "absolute";
    mirror.style.visibility = "hidden";
    mirror.style.overflow = "hidden";
    mirror.style.width = style.width;
    mirror.style.height = "auto";

    for (const prop of MIRROR_STYLES) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (mirror.style as any)[prop] = (style as any)[prop];
    }

    const text = textarea.value.substring(0, position);
    mirror.textContent = text;

    const span = document.createElement("span");
    span.textContent = textarea.value.substring(position) || ".";
    mirror.appendChild(span);

    document.body.appendChild(mirror);

    const { offsetTop: top, offsetLeft: left, offsetHeight: height } = span;

    document.body.removeChild(mirror);

    return {
        top: top - textarea.scrollTop,
        left,
        height,
    };
}

// Category labels & order for grouping
const CATEGORY_ORDER: Record<string, number> = {
    system: 0,
    crm: 1,
    custom: 2,
};

const CATEGORY_LABELS: Record<string, string> = {
    system: "System",
    crm: "CRM",
    custom: "Custom",
};

// ── Component ───────────────────────────────────────────────

interface VariableSuggestTextareaProps {
    id?: string;
    value: string;
    onChange: (value: string) => void;
    variables: PromptVariable[];
    placeholder?: string;
    className?: string;
    minHeight?: string;
}

export function VariableSuggestTextarea({
    id,
    value,
    onChange,
    variables,
    placeholder,
    className,
    minHeight = "80px",
}: VariableSuggestTextareaProps) {
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const dropdownRef = useRef<HTMLDivElement>(null);
    const [showSuggestions, setShowSuggestions] = useState(false);
    const [selectedIndex, setSelectedIndex] = useState(0);
    const [filterText, setFilterText] = useState("");
    const [triggerStart, setTriggerStart] = useState(-1);
    const [dropdownPos, setDropdownPos] = useState({ top: 0, left: 0 });

    // Filter variables by typed text after `{`
    const filteredVariables = useMemo(() => {
        const lower = filterText.toLowerCase();
        const filtered = variables.filter((v) =>
            v.name.toLowerCase().includes(lower)
        );
        // Sort by category order, then name
        return filtered.sort((a, b) => {
            const catA = CATEGORY_ORDER[a.category ?? "custom"] ?? 2;
            const catB = CATEGORY_ORDER[b.category ?? "custom"] ?? 2;
            if (catA !== catB) return catA - catB;
            return a.name.localeCompare(b.name);
        });
    }, [variables, filterText]);

    // Group variables by category for rendering
    const groupedVariables = useMemo(() => {
        const groups: { category: string; label: string; vars: PromptVariable[] }[] = [];
        let currentCategory = "";
        for (const v of filteredVariables) {
            const cat = v.category ?? "custom";
            if (cat !== currentCategory) {
                currentCategory = cat;
                groups.push({
                    category: cat,
                    label: CATEGORY_LABELS[cat] ?? cat,
                    vars: [],
                });
            }
            groups[groups.length - 1].vars.push(v);
        }
        return groups;
    }, [filteredVariables]);

    // Insert the selected variable into the textarea value
    const insertVariable = useCallback(
        (variable: PromptVariable) => {
            const textarea = textareaRef.current;
            if (!textarea || triggerStart < 0) return;

            const cursorPos = textarea.selectionStart;
            const before = value.substring(0, triggerStart);
            const after = value.substring(cursorPos);
            const insertText = `{{${variable.name}}}`;

            const newValue = before + insertText + after;
            onChange(newValue);

            // Close dropdown
            setShowSuggestions(false);
            setTriggerStart(-1);
            setFilterText("");

            // Restore focus & cursor position after React re-renders
            requestAnimationFrame(() => {
                textarea.focus();
                const newPos = triggerStart + insertText.length;
                textarea.setSelectionRange(newPos, newPos);
            });
        },
        [value, onChange, triggerStart]
    );

    // Handle input changes — detect `{` trigger
    const handleChange = useCallback(
        (e: React.ChangeEvent<HTMLTextAreaElement>) => {
            const newValue = e.target.value;
            const cursorPos = e.target.selectionStart;
            onChange(newValue);

            // Check if we should open suggestions
            // Look backwards from cursor for a `{` that starts a variable
            const textBefore = newValue.substring(0, cursorPos);
            // Match a single `{` or `{{` followed optionally by partial variable name
            const triggerMatch = textBefore.match(/\{?\{(\w*)$/);

            if (triggerMatch) {
                const matchStart = cursorPos - triggerMatch[0].length;
                setTriggerStart(matchStart);
                setFilterText(triggerMatch[1]);
                setShowSuggestions(true);
                setSelectedIndex(0);

                // Position the dropdown near the caret
                const textarea = textareaRef.current;
                if (textarea) {
                    const coords = getCaretCoordinates(textarea, matchStart);
                    setDropdownPos({
                        top: coords.top + coords.height + 4,
                        left: coords.left,
                    });
                }
            } else {
                setShowSuggestions(false);
                setTriggerStart(-1);
                setFilterText("");
            }
        },
        [onChange]
    );

    // Keyboard navigation inside dropdown
    const handleKeyDown = useCallback(
        (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
            if (!showSuggestions || filteredVariables.length === 0) return;

            if (e.key === "ArrowDown") {
                e.preventDefault();
                setSelectedIndex((prev) =>
                    prev < filteredVariables.length - 1 ? prev + 1 : 0
                );
            } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setSelectedIndex((prev) =>
                    prev > 0 ? prev - 1 : filteredVariables.length - 1
                );
            } else if (e.key === "Enter" || e.key === "Tab") {
                e.preventDefault();
                insertVariable(filteredVariables[selectedIndex]);
            } else if (e.key === "Escape") {
                e.preventDefault();
                setShowSuggestions(false);
                setTriggerStart(-1);
                setFilterText("");
            }
        },
        [showSuggestions, filteredVariables, selectedIndex, insertVariable]
    );

    // Close dropdown when textarea loses focus
    const handleBlur = useCallback(() => {
        // Delay to allow click on dropdown item
        setTimeout(() => {
            if (
                !dropdownRef.current?.contains(document.activeElement) &&
                document.activeElement !== textareaRef.current
            ) {
                setShowSuggestions(false);
                setTriggerStart(-1);
                setFilterText("");
            }
        }, 150);
    }, []);

    // Scroll selected item into view
    useEffect(() => {
        if (!showSuggestions || !dropdownRef.current) return;
        const selected = dropdownRef.current.querySelector(
            `[data-index="${selectedIndex}"]`
        );
        selected?.scrollIntoView({ block: "nearest" });
    }, [selectedIndex, showSuggestions]);

    // Flatten index counter for grouped display
    let flatIndex = 0;

    return (
        <div className="relative">
            <textarea
                ref={textareaRef}
                id={id}
                className={
                    className ??
                    "flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                }
                style={{ minHeight }}
                placeholder={placeholder}
                value={value}
                onChange={handleChange}
                onKeyDown={handleKeyDown}
                onBlur={handleBlur}
            />

            {/* Variable Suggestion Dropdown */}
            {showSuggestions && filteredVariables.length > 0 && (
                <div
                    ref={dropdownRef}
                    className="absolute z-50 max-h-[240px] w-[280px] overflow-y-auto rounded-lg border border-border bg-popover shadow-lg"
                    style={{
                        top: dropdownPos.top,
                        left: Math.min(dropdownPos.left, 200), // prevent overflow
                    }}
                >
                    <div className="p-1">
                        {groupedVariables.map((group) => (
                            <div key={group.category}>
                                <div className="px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                                    {group.label}
                                </div>
                                {group.vars.map((v) => {
                                    const idx = flatIndex++;
                                    return (
                                        <button
                                            key={v.name}
                                            type="button"
                                            data-index={idx}
                                            className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors ${idx === selectedIndex
                                                    ? "bg-accent text-accent-foreground"
                                                    : "hover:bg-accent/50"
                                                }`}
                                            onMouseDown={(e) => {
                                                e.preventDefault(); // prevent blur
                                                insertVariable(v);
                                            }}
                                            onMouseEnter={() => setSelectedIndex(idx)}
                                        >
                                            <code className="rounded bg-muted px-1 py-0.5 text-xs font-mono text-primary">
                                                {`{{${v.name}}}`}
                                            </code>
                                            <span className="truncate text-xs text-muted-foreground">
                                                {v.description}
                                            </span>
                                        </button>
                                    );
                                })}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
