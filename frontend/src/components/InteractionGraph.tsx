import { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { InteractionRow, RegimenItem } from "../types";
import { drugClassColor, severityStroke, buildGraphLinks } from "../utils/graphLayout";

interface Props {
  regimen: RegimenItem[];
  interactions: InteractionRow[];
  onSelectInteraction: (row: InteractionRow) => void;
  onSelectMedication: (id: number) => void;
}

interface NodeDatum extends d3.SimulationNodeDatum {
  id: number;
  label: string;
  drugClass: string;
}

interface LinkDatum extends d3.SimulationLinkDatum<NodeDatum> {
  severity: string;
  row: InteractionRow;
  strokeStyle: ReturnType<typeof severityStroke>;
}

export default function InteractionGraph({
  regimen,
  interactions,
  onSelectInteraction,
  onSelectMedication,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    const svgEl = svgRef.current;
    if (!container || !svgEl) return;

    const width = container.clientWidth;
    const height = Math.max(container.clientHeight, 300);

    const svg = d3
      .select(svgEl)
      .attr("width", width)
      .attr("height", height);
    svg.selectAll("*").remove();

    if (regimen.length === 0) return;

    const nodes: NodeDatum[] = regimen.map((m) => ({
      id: m.id,
      label: m.generic_name,
      drugClass: m.drug_class,
    }));

    const graphLinks = buildGraphLinks(regimen, interactions);
    const nodeById = new Map(nodes.map((n) => [n.id, n]));

    const links: LinkDatum[] = graphLinks
      .filter((l) => nodeById.has(l.drug_a_id) && nodeById.has(l.drug_b_id))
      .map((l) => ({
        source: nodeById.get(l.drug_a_id)!,
        target: nodeById.get(l.drug_b_id)!,
        severity: l.severity,
        row: l.row,
        strokeStyle: l.stroke,
      }));

    const g = svg.append("g");

    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 4])
      .on("zoom", (event) => {
        g.attr("transform", event.transform);
      });
    svg.call(zoom);

    const simulation = d3
      .forceSimulation<NodeDatum>(nodes)
      .force(
        "link",
        d3
          .forceLink<NodeDatum, LinkDatum>(links)
          .id((d) => d.id)
          .distance(120)
      )
      .force("charge", d3.forceManyBody().strength(-300))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide(40));

    const linkSel = g
      .append("g")
      .selectAll<SVGLineElement, LinkDatum>("line")
      .data(links)
      .join("line")
      .attr("stroke", (d) => d.strokeStyle.stroke)
      .attr("stroke-width", (d) => d.strokeStyle.width)
      .attr("stroke-dasharray", (d) => d.strokeStyle.dash)
      .attr("class", (d) =>
        d.severity.toLowerCase() === "critical" ? "edge-critical" : ""
      )
      .attr("cursor", "pointer")
      .on("click", (_event, d) => onSelectInteraction(d.row));

    const nodeSel = g
      .append("g")
      .selectAll<SVGGElement, NodeDatum>("g")
      .data(nodes)
      .join("g")
      .attr("cursor", "pointer")
      .on("click", (_event, d) => onSelectMedication(d.id))
      .call(
        d3
          .drag<SVGGElement, NodeDatum>()
          .on("start", (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          })
      );

    nodeSel
      .append("circle")
      .attr("r", 22)
      .attr("fill", (d) => drugClassColor(d.drugClass))
      .attr("stroke", "#fff")
      .attr("stroke-width", 2);

    nodeSel
      .append("text")
      .text((d) => {
        const name = d.label;
        return name.length > 12 ? name.slice(0, 11) + "…" : name;
      })
      .attr("text-anchor", "middle")
      .attr("dy", 36)
      .attr("class", "text-[10px] fill-slate-600 font-medium pointer-events-none select-none");

    simulation.on("tick", () => {
      linkSel
        .attr("x1", (d) => (d.source as NodeDatum).x!)
        .attr("y1", (d) => (d.source as NodeDatum).y!)
        .attr("x2", (d) => (d.target as NodeDatum).x!)
        .attr("y2", (d) => (d.target as NodeDatum).y!);

      nodeSel.attr("transform", (d) => `translate(${d.x},${d.y})`);
    });

    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width: w, height: h } = entry.contentRect;
        svg.attr("width", w).attr("height", Math.max(h, 300));
        simulation.force("center", d3.forceCenter(w / 2, Math.max(h, 300) / 2));
        simulation.alpha(0.3).restart();
      }
    });
    ro.observe(container);

    return () => {
      simulation.stop();
      ro.disconnect();
    };
  }, [regimen, interactions, onSelectInteraction, onSelectMedication]);

  return (
    <div ref={containerRef} className="relative h-full min-h-[350px] w-full">
      <svg ref={svgRef} className="block h-full w-full" />
      <p className="absolute bottom-2 left-3 text-[10px] text-slate-400 select-none pointer-events-none">
        Drag nodes · Scroll to zoom · Click edge or node for details
      </p>
    </div>
  );
}
