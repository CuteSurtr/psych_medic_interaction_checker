import { Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Simulator from "./pages/Simulator";
import CYP450View from "./pages/CYP450View";
import Scenarios from "./pages/Scenarios";
import Analysis from "./pages/Analysis";
import Report from "./pages/Report";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/simulator" element={<Simulator />} />
      <Route path="/cyp450" element={<CYP450View />} />
      <Route path="/analysis" element={<Analysis />} />
      <Route path="/scenarios" element={<Scenarios />} />
      <Route path="/report" element={<Report />} />
    </Routes>
  );
}
