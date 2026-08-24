import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Chat from "./pages/Chat";
import { HealthBadge } from "./components/HealthBadge";

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50 flex flex-col">
        <nav className="bg-slate-900 text-white p-4 shadow-md flex justify-between items-center">
          <div className="font-bold text-xl tracking-wide flex items-center gap-2">
            <span className="text-blue-400">Agent</span>Ready Gateway
          </div>
          <div className="flex gap-4 font-medium items-center">
            <Link to="/" className="hover:text-blue-300 transition">Dashboard</Link>
            <Link to="/chat" className="hover:text-blue-300 transition">Agent Chat</Link>
            <HealthBadge />
          </div>
        </nav>
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/chat" element={<Chat />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
