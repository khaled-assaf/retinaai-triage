import { Route, Routes } from "react-router-dom";
import Layout from "./components/layout/Layout";
import CaseResultPage from "./pages/CaseResultPage";
import FollowupsPage from "./pages/FollowupsPage";
import LandingPage from "./pages/LandingPage";
import QueuePage from "./pages/QueuePage";
import ScreeningPage from "./pages/ScreeningPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<LandingPage />} />
        <Route path="screening" element={<ScreeningPage />} />
        <Route path="case/:id" element={<CaseResultPage />} />
        <Route path="queue" element={<QueuePage />} />
        <Route path="followups" element={<FollowupsPage />} />
        <Route path="*" element={<LandingPage />} />
      </Route>
    </Routes>
  );
}
