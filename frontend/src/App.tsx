import { useState } from "react";
import ImageUpload from "@/components/ImageUpload";
import LiveDetection from "@/components/LiveDetection";
import History from "@/components/History";

type Tab = "image" | "live" | "history";

export default function App() {
  const [tab, setTab] = useState<Tab>("image");

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-800 px-6 py-4">
        <h1 className="text-2xl font-bold">🔍 PCB Defect Detection</h1>
        <p className="text-sm text-slate-400">Platalarning yaroqliligini aniqlash tizimi</p>
      </header>

      <nav className="flex gap-2 px-6 pt-4">
        <button
          onClick={() => setTab("image")}
          className={`px-4 py-2 rounded-t-lg text-sm font-medium ${
            tab === "image" ? "bg-slate-800 text-white" : "text-slate-400 hover:text-white"
          }`}
        >
          Rasm yuklash
        </button>
        <button
          onClick={() => setTab("live")}
          className={`px-4 py-2 rounded-t-lg text-sm font-medium ${
            tab === "live" ? "bg-slate-800 text-white" : "text-slate-400 hover:text-white"
          }`}
        >
          Real-time
        </button>
        <button
          onClick={() => setTab("history")}
          className={`px-4 py-2 rounded-t-lg text-sm font-medium ${
            tab === "history" ? "bg-slate-800 text-white" : "text-slate-400 hover:text-white"
          }`}
        >
          Tarix
        </button>
      </nav>

      <main className="bg-slate-800/50">
        {tab === "image" && <ImageUpload />}
        {tab === "live" && <LiveDetection />}
        {tab === "history" && <History />}
      </main>
    </div>
  );
}
