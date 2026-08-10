import { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { SimulationResult } from "../types";
import { getDrugClassColor } from "../utils/colorSchemes";

interface MedicationMeta {
  generic_name: string;
  therapeutic_min_ng_ml?: number | null;
  therapeutic_max_ng_ml?: number | null;
  drug_class: string;
}

interface Props {
  result: SimulationResult | null;
  medications: MedicationMeta[];
}

const MARGIN = { top: 20, right: 20, bottom: 40, left: 55 };

export default function ConcentrationPlot({ result, medications }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    const svgEl = svgRef.current;
    if (!container || !svgEl) return;
    if (!result) return;

    const draw = () => {
      const totalW = container.clientWidth;
      const totalH = Math.max(container.clientHeight, 300);
      const width = totalW - MARGIN.left - MARGIN.right;
      const height = totalH - MARGIN.top - MARGIN.bottom;

      const svg = d3.select(svgEl).attr("width", totalW).attr("height", totalH);
      svg.selectAll("*").remove();

      const g = svg
        .append("g")
        .attr("transform", `translate(${MARGIN.left},${MARGIN.top})`);

      const timeDays = result.time_hours.map((h) => h / 24);

      const allConc = Object.values(result.concentrations).flat();
      const maxConc = d3.max(allConc) ?? 100;

      const xScale = d3
        .scaleLinear()
        .domain([0, d3.max(timeDays) ?? 1])
        .range([0, width]);

      const yScale = d3
        .scaleLinear()
        .domain([0, maxConc * 1.1])
        .range([height, 0]);

      g.append("g")
        .attr("transform", `translate(0,${height})`)
        .call(d3.axisBottom(xScale).ticks(8))
        .append("text")
        .attr("x", width / 2)
        .attr("y", 34)
        .attr("fill", "#64748b")
        .attr("text-anchor", "middle")
        .attr("font-size", 11)
        .text("Time (days)");

      g.append("g")
        .call(d3.axisLeft(yScale).ticks(6))
        .append("text")
        .attr("x", -height / 2)
        .attr("y", -42)
        .attr("fill", "#64748b")
        .attr("text-anchor", "middle")
        .attr("font-size", 11)
        .attr("transform", "rotate(-90)")
        .text("Concentration (ng/mL)");

      const medByName = new Map(medications.map((m) => [m.generic_name, m]));

      for (const med of medications) {
        const tMin = med.therapeutic_min_ng_ml;
        const tMax = med.therapeutic_max_ng_ml;
        if (tMin != null && tMax != null) {
          g.append("rect")
            .attr("x", 0)
            .attr("y", yScale(tMax))
            .attr("width", width)
            .attr("height", yScale(tMin) - yScale(tMax))
            .attr("fill", "#16A34A")
            .attr("opacity", 0.08);
        }
      }

      for (const ev of result.dose_events) {
        const dayX = ev.time_h / 24;
        g.append("line")
          .attr("x1", xScale(dayX))
          .attr("x2", xScale(dayX))
          .attr("y1", 0)
          .attr("y2", height)
          .attr("stroke", "#94a3b8")
          .attr("stroke-width", 1)
          .attr("stroke-dasharray", "4 3");
        g.append("text")
          .attr("x", xScale(dayX) + 3)
          .attr("y", 10)
          .attr("fill", "#94a3b8")
          .attr("font-size", 9)
          .text(`${ev.drug_name} ${ev.dose_mg}mg`);
      }

      const line = d3
        .line<[number, number]>()
        .x((d) => xScale(d[0]))
        .y((d) => yScale(d[1]))
        .curve(d3.curveMonotoneX);

      for (const [drugName, values] of Object.entries(result.concentrations)) {
        const med = medByName.get(drugName);
        const color = getDrugClassColor(med?.drug_class ?? "");
        const points: [number, number][] = timeDays.map((t, i) => [t, values[i]]);

        g.append("path")
          .datum(points)
          .attr("d", line)
          .attr("fill", "none")
          .attr("stroke", color)
          .attr("stroke-width", 2);
      }
    };

    draw();

    const ro = new ResizeObserver(() => draw());
    ro.observe(container);
    return () => ro.disconnect();
  }, [result, medications]);

  if (!result) {
    return (
      <div className="flex h-64 items-center justify-center rounded-lg border border-dashed border-slate-300 text-sm text-slate-400">
        Run a simulation to view concentration curves.
      </div>
    );
  }

  return (
    <div ref={containerRef} className="h-80 w-full">
      <svg ref={svgRef} className="block h-full w-full" />
    </div>
  );
}
