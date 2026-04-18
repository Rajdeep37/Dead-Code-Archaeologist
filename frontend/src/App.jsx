import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AnalysisProvider } from "./context/AnalysisContext";
import Header from "./components/Header";
import AnalyzePage from "./pages/AnalyzePage";
import VerdictDetailPage from "./pages/VerdictDetailPage";

export default function App() {
  return (
    <BrowserRouter>
      <AnalysisProvider>
        <div className="app-layout">
          <Header />
          <main className="main-container">
            <Routes>
              <Route path="/" element={<AnalyzePage />} />
              <Route path="/verdict/:file/:name" element={<VerdictDetailPage />} />
            </Routes>
          </main>
        </div>
      </AnalysisProvider>
    </BrowserRouter>
  );
}