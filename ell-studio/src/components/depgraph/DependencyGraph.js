import React, {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import ReactFlow, {
  Panel,
  useNodesState,
  useEdgesState,
  useReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  ReactFlowProvider,
} from "reactflow";


import { Link } from "react-router-dom";

import "reactflow/dist/style.css";

// import { Card } from "../components/Card";
// import { BiCube } from "react-icons/bi";


import { useLayoutedElements, getInitialGraph } from "./graphUtils";


function LMPNode({ data }) {
  const { lmp } = data;
  const onChange = useCallback((evt) => {}, []);

  return (
    <>
      <Handle type="source" position={Position.Top} />
      <div height="30px" key={lmp.lmp_id}>
        <Link to={`/studio/lmp/${lmp.lmp_id}`}>
          {/* <LMPCardTitle lmp={lmp} /> */}
          {lmp.name}
        </Link>
      </div>
      <Handle type="target" position={Position.Bottom} id="a" />
      {/* <Handle type="source" position={Position.Bottom} id="b" style={handleStyle} /> */}
    </>
  );
}

const LayoutFlow = ({ initialNodes, initialEdges }) => {
  const { fitView } = useReactFlow();
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  // const [initialised, { toggle, isRunning }] = useLayoutedElements();
  // const [didInitialSimulation, setDidInitialSimulation] = useState(false);

  // // Start the simulation automatically when the initialized is good & run it for like 1second
  // useEffect(() => {
  //   if (initialised && !didInitialSimulation) {
  //     setDidInitialSimulation(true);
  //     toggle();
  //     setTimeout(() => {
  //       toggle();
  //     }, 2000);
  //   }
  // }, [initialised, didInitialSimulation]);

  const nodeTypes = useMemo(() => ({ lmp: LMPNode }), []);


  return (
    
    <div style={{ height: 600 }}>
    <ReactFlow
      nodes={initialNodes}
      edges={initialEdges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      nodeTypes={nodeTypes}
  
    >
      <Panel>
        
      </Panel>
      <Controls />

      <Background />
    </ReactFlow>
    </div>
  );
};


export function DependencyGraph({ lmps, ...rest }) {
  // construct ndoes from LMPS
  const { initialEdges, initialNodes } = useMemo(
    () => getInitialGraph(lmps),
    [lmps]
  );

  return (
    <div
      className="h-600px w-full rounded-lg border border-gray-700"
      {...rest}
    >
      <ReactFlowProvider>
        <LayoutFlow initialEdges={initialEdges} initialNodes={initialNodes} />
      </ReactFlowProvider>
    </div>
  );
}