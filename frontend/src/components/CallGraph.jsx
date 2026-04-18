import { useMemo, useCallback } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
} from "reactflow";
import dagre from "dagre";
import "reactflow/dist/style.css";

const NODE_WIDTH = 180;
const NODE_HEIGHT = 40;

/** Convert adjacency dict → dagre-layouted ReactFlow nodes + edges. */
function buildLayout(graph) {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", nodesep: 40, ranksep: 60 });

  const allNodes = new Set(Object.keys(graph));
  // Include callees that may not be top-level keys
  for (const callees of Object.values(graph)) {
    for (const c of callees) allNodes.add(c);
  }

  for (const id of allNodes) {
    g.setNode(id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }

  const edges = [];
  for (const [caller, callees] of Object.entries(graph)) {
    for (const callee of callees) {
      const edgeId = `${caller}→${callee}`;
      g.setEdge(caller, callee);
      edges.push({
        id: edgeId,
        source: caller,
        target: callee,
        animated: false,
        style: { stroke: "#30363d", strokeWidth: 1.5 },
        markerEnd: { type: "arrowclosed", color: "#30363d" },
      });
    }
  }

  dagre.layout(g);

  const nodes = [];
  for (const id of allNodes) {
    const pos = g.node(id);
    const inDeg = (g.inEdges(id) || []).length;
    const outDeg = (g.outEdges(id) || []).length;

    // Color coding: no incoming calls = suspect (purple), leaf = subtle, normal = accent
    let borderColor = "#30363d";
    let bg = "#161b22";
    if (inDeg === 0 && outDeg > 0) {
      // root / entry point
      borderColor = "#3fb950";
      bg = "rgba(63, 185, 80, 0.08)";
    } else if (inDeg === 0 && outDeg === 0) {
      // isolated
      borderColor = "#f85149";
      bg = "rgba(248, 81, 73, 0.08)";
    } else if (outDeg === 0) {
      // leaf
      borderColor = "#8b949e";
      bg = "rgba(139, 148, 158, 0.06)";
    }

    nodes.push({
      id,
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 },
      data: { label: id },
      style: {
        background: bg,
        color: "#e6edf3",
        border: `1.5px solid ${borderColor}`,
        borderRadius: 6,
        fontSize: 12,
        fontFamily:
          '"SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace',
        padding: "6px 10px",
        width: NODE_WIDTH,
      },
    });
  }

  return { nodes, edges };
}

export default function CallGraph({ graph }) {
  const { nodes: layoutNodes, edges: layoutEdges } = useMemo(
    () => buildLayout(graph),
    [graph]
  );

  const [nodes, , onNodesChange] = useNodesState(layoutNodes);
  const [edges, , onEdgesChange] = useEdgesState(layoutEdges);

  const onInit = useCallback((instance) => {
    setTimeout(() => instance.fitView({ padding: 0.15 }), 50);
  }, []);

  return (
    <div className="callgraph-canvas">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onInit={onInit}
        fitView
        minZoom={0.2}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
        nodesDraggable
        nodesConnectable={false}
      >
        <Background color="#21262d" gap={20} size={1} />
        <Controls
          showInteractive={false}
          style={{ background: "#161b22", borderColor: "#30363d" }}
        />
        <MiniMap
          nodeColor={() => "#30363d"}
          maskColor="rgba(0, 0, 0, 0.6)"
          style={{ background: "#0d1117", borderColor: "#30363d" }}
        />
      </ReactFlow>
    </div>
  );
}
