"use client";

/**
 * Flow Canvas — React Flow canvas with drag-and-drop, zoom/pan, and grid snapping.
 *
 * Main interactive canvas for the conversation flow builder.
 * Wraps @xyflow/react with custom theme, node types, and event handlers.
 *
 * Features:
 * - Custom themed nodes (8 types)
 * - Drag from palette to add nodes
 * - Click to select/configure
 * - Edge connections with validation
 * - Grid snapping
 * - Auto-save support (30s interval)
 * - Undo/redo (delegated to parent via callbacks)
 */

import {
  useEffect,
  useCallback,
  useMemo,
  useRef,
  useState,
  type DragEvent,
  type MouseEvent,
} from "react";
import {
  ReactFlow,
  Background,
  Controls,
  addEdge,
  useNodesState,
  useEdgesState,
  type Connection,
  type OnConnect,
  type OnNodesChange,
  type OnEdgesChange,
  BackgroundVariant,
  MarkerType,
  Panel,
  type ReactFlowInstance,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { flowNodeTypes } from "./nodes";
import { NodePalette } from "./node-palette";
import { validateFlow } from "./validation";
import {
  createDefaultNodeData,
  type FlowNode,
  type FlowEdge,
  type FlowNodeData,
  type LogicSplitNodeData,
  type FlowNodeType,
  type FlowValidationResult,
} from "../../types/flow";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  AlertTriangle,
  CheckCircle,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";

// ── Props ───────────────────────────────────────────────────

interface FlowCanvasProps {
  initialNodes: FlowNode[];
  initialEdges: FlowEdge[];
  onNodesChange: (nodes: FlowNode[]) => void;
  onEdgesChange: (edges: FlowEdge[]) => void;
  onSelectedNodeChange?: (nodeId: string | null) => void;
  onValidationResult?: (result: FlowValidationResult) => void;
}

function getEdgeLabel(edge: FlowEdge, nodes: FlowNode[]): string {
  const sourceNode = nodes.find((node) => node.id === edge.source);
  if (!sourceNode) {
    return "Transition";
  }

  if (sourceNode.type === "logic_split") {
    const data = sourceNode.data as LogicSplitNodeData;
    const handleId = edge.sourceHandle;

    if (handleId) {
      const condition = data.conditions.find((item) => item.targetHandleId === handleId);
      if (condition) {
        return condition.variableName || `Branch ${handleId.replace("output-", "")}`;
      }
      const defaultIndex = `output-${data.conditions.length}`;
      if (handleId === defaultIndex) {
        return "Default";
      }
    }

    return "Branch";
  }

  return "Transition";
}

// ── Component ───────────────────────────────────────────────

export function FlowCanvas({
  initialNodes,
  initialEdges,
  onNodesChange: onNodesChangeCallback,
  onEdgesChange: onEdgesChangeCallback,
  onSelectedNodeChange,
  onValidationResult,
}: FlowCanvasProps) {
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const [reactFlowInstance, setReactFlowInstance] = useState<ReactFlowInstance<FlowNode, FlowEdge> | null>(null);

  const [nodes, setNodes, onNodesChange] = useNodesState<FlowNode>(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<FlowEdge>(initialEdges);
  const [showPalette, setShowPalette] = useState(true);
  const [validation, setValidation] = useState<FlowValidationResult | null>(null);

  const entryNode = useMemo(
    () =>
      nodes.find(
        (node) => node.type === "conversation" && Boolean((node.data as FlowNodeData).isEntryNode)
      ) ?? null,
    [nodes]
  );

  const displayEdges = useMemo(
    () =>
      edges.map((edge) => ({
        ...edge,
        animated: false,
        style: {
          stroke: "rgba(15, 23, 42, 0.28)",
          strokeWidth: 1.8,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 14,
          height: 14,
          color: "rgba(15, 23, 42, 0.3)",
        },
      })),
    [edges]
  );

  useEffect(() => {
    setNodes(initialNodes);
  }, [initialNodes, setNodes]);

  useEffect(() => {
    setEdges(initialEdges);
  }, [initialEdges, setEdges]);

  // Unique node ID counter
  const nodeIdCounter = useRef(initialNodes.length + 1);

  // ── Edge connection ───────────────────────────────────────

  const onConnect: OnConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) => {
        const newEdges = addEdge(
          {
            ...connection,
            animated: true,
            style: { strokeWidth: 2 },
          },
          eds
        );
        onEdgesChangeCallback(newEdges as FlowEdge[]);
        return newEdges;
      });
    },
    [setEdges, onEdgesChangeCallback]
  );

  // ── Node changes ──────────────────────────────────────────

  const handleNodesChange: OnNodesChange<FlowNode> = useCallback(
    (changes) => {
      onNodesChange(changes);
      // We need to use a setTimeout to get the updated nodes after React state update
      setTimeout(() => {
        setNodes((currentNodes) => {
          onNodesChangeCallback(currentNodes);
          return currentNodes;
        });
      }, 0);
    },
    [onNodesChange, onNodesChangeCallback, setNodes]
  );

  const handleEdgesChange: OnEdgesChange<FlowEdge> = useCallback(
    (changes) => {
      onEdgesChange(changes);
      setTimeout(() => {
        setEdges((currentEdges) => {
          onEdgesChangeCallback(currentEdges);
          return currentEdges;
        });
      }, 0);
    },
    [onEdgesChange, onEdgesChangeCallback, setEdges]
  );

  // ── Drag & Drop from Palette ──────────────────────────────

  const onDragOver = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const onDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();

      const nodeType = event.dataTransfer.getData("application/SphereVoice-flow-node") as FlowNodeType;
      if (!nodeType || !reactFlowInstance || !reactFlowWrapper.current) return;

      const bounds = reactFlowWrapper.current.getBoundingClientRect();
      const position = reactFlowInstance.screenToFlowPosition({
        x: event.clientX - bounds.left,
        y: event.clientY - bounds.top,
      });

      const id = `node_${nodeIdCounter.current++}`;
      const label = `${nodeType.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())} ${nodeIdCounter.current - 1}`;
      const data = createDefaultNodeData(nodeType, label);

      const newNode: FlowNode = {
        id,
        type: nodeType,
        position,
        data: data as FlowNode["data"],
      };

      setNodes((nds) => {
        const updated = [...nds, newNode];
        onNodesChangeCallback(updated);
        return updated;
      });
    },
    [reactFlowInstance, setNodes, onNodesChangeCallback]
  );

  // ── Node Selection ────────────────────────────────────────

  const onNodeClick = useCallback(
    (_event: MouseEvent, node: FlowNode) => {
      onSelectedNodeChange?.(node.id);
    },
    [onSelectedNodeChange]
  );

  const onPaneClick = useCallback(() => {
    onSelectedNodeChange?.(null);
  }, [onSelectedNodeChange]);

  // ── Validation ────────────────────────────────────────────

  const runValidation = useCallback(() => {
    const result = validateFlow(nodes as FlowNode[], edges as FlowEdge[]);
    setValidation(result);
    onValidationResult?.(result);
    return result;
  }, [nodes, edges, onValidationResult]);

  // ── Render ────────────────────────────────────────────────

  return (
    <div className="flex h-full overflow-hidden rounded-[24px] border border-slate-200 bg-[#f6f5f3] shadow-sm">
      {/* Left: Node Palette */}
      {showPalette && (
        <div className="w-[236px] shrink-0 overflow-y-auto border-r border-slate-200 bg-[#faf9f7] p-0">
          <NodePalette />
        </div>
      )}

      {/* Center: Canvas */}
      <div
        ref={reactFlowWrapper}
        className="relative flex-1 bg-[#f6f5f3]"
      >
        <ReactFlow<FlowNode, FlowEdge>
          nodes={nodes}
          edges={displayEdges}
          onNodesChange={handleNodesChange}
          onEdgesChange={handleEdgesChange}
          onConnect={onConnect}
          onInit={setReactFlowInstance}
          onDrop={onDrop}
          onDragOver={onDragOver}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          nodeTypes={flowNodeTypes}
          snapToGrid
          snapGrid={[15, 15]}
          fitView
          deleteKeyCode={["Backspace", "Delete"]}
          className="bg-[#f6f5f3]"
        >
          <Background
            variant={BackgroundVariant.Dots}
            gap={22}
            size={1}
            className="!bg-transparent"
            color="rgba(15, 23, 42, 0.08)"
          />
          <Controls className="!overflow-hidden !rounded-xl !border !border-slate-200 !bg-white !shadow-sm" />

          {/* Top-left controls */}
          <Panel position="top-left" className="rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
            <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowPalette(!showPalette)}
              title={showPalette ? "Hide palette" : "Show palette"}
              className="h-8 border-slate-200 bg-white px-2"
            >
              {showPalette ? (
                <PanelLeftClose className="h-4 w-4" />
              ) : (
                <PanelLeftOpen className="h-4 w-4" />
              )}
            </Button>
            </div>
          </Panel>

          <Panel position="top-center" className="pointer-events-none mt-3">
            <div className="min-w-[320px] rounded-[20px] border border-slate-200 bg-white px-4 py-3 shadow-sm">
              <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                Begin
              </div>
              <div className="mt-1 text-[15px] font-semibold text-slate-900">
                {entryNode ? entryNode.data.label : "Choose a starting conversation node"}
              </div>
              <div className="mt-1 text-xs text-slate-500">
                {entryNode
                  ? "Calls enter the flow here before following transitions and branches."
                  : "Mark one conversation node as the entry point to anchor the canvas."}
              </div>
            </div>
          </Panel>

          {/* Top-right: Validation */}
          <Panel position="top-right" className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
            <Button
              variant="outline"
              size="sm"
              onClick={runValidation}
              className="h-8 border-slate-200 bg-white"
            >
              Validate
            </Button>
            {validation && (
              <Badge
                variant={validation.valid ? "default" : "destructive"}
                className="flex items-center gap-1 rounded-full px-2.5 py-1"
              >
                {validation.valid ? (
                  <>
                    <CheckCircle className="h-3 w-3" />
                    Valid
                  </>
                ) : (
                  <>
                    <AlertTriangle className="h-3 w-3" />
                    {validation.errors.length} error{validation.errors.length !== 1 ? "s" : ""}
                  </>
                )}
              </Badge>
            )}
          </Panel>

          {/* Bottom: Validation errors */}
          {validation && !validation.valid && (
            <Panel position="bottom-center" className="max-w-lg">
              <div className="rounded-[20px] border border-slate-200 bg-white p-4 shadow-sm">
                <h4 className="text-xs font-semibold uppercase tracking-[0.16em] text-destructive">Validation Errors</h4>
                <ul className="mt-2 space-y-1">
                  {validation.errors.map((err, i) => (
                    <li key={i} className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/40 dark:text-red-200">
                      {err.message}
                    </li>
                  ))}
                </ul>
                {validation.warnings.length > 0 && (
                  <>
                    <h4 className="mt-3 text-xs font-semibold uppercase tracking-[0.16em] text-amber-700 dark:text-amber-300">Warnings</h4>
                    <ul className="mt-2 space-y-1">
                      {validation.warnings.map((warn, i) => (
                        <li key={i} className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-700 dark:bg-amber-950/30 dark:text-amber-200">
                          {warn.message}
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            </Panel>
          )}
        </ReactFlow>

        {nodes.length === 0 && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center p-6">
            <div className="max-w-md rounded-[20px] border border-slate-200 bg-white p-6 text-center shadow-sm">
              <h3 className="text-base font-semibold text-slate-900">
                Start by dropping your first step
              </h3>
              <p className="mt-2 text-sm leading-6 text-slate-500">
                Build the call from left to right: add an opening conversation node, branch with logic, then finish with a transfer or ending step.
              </p>
              <div className="mt-4 flex flex-wrap items-center justify-center gap-2 text-xs text-slate-500">
                <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1">
                  Drag from palette
                </span>
                <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1">
                  Connect handles
                </span>
                <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1">
                  Run validation
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

    </div>
  );
}
