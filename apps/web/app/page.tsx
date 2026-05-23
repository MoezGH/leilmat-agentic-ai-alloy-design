import Link from "next/link";

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center gap-8 px-6">
      <div className="text-center space-y-3">
        <h1 className="text-5xl font-bold tracking-tight text-white">
          Leil<span className="text-brand-500">Mat</span>
        </h1>
        <p className="text-lg text-slate-400 max-w-md">
          AI-native alloy design. Predict properties, explore composition spaces,
          and let AI guide your materials discovery.
        </p>
      </div>

      <div className="flex gap-4">
        <Link
          href="/canvas"
          className="px-6 py-3 bg-brand-600 hover:bg-brand-500 text-white rounded-lg font-medium transition-colors"
        >
          Open Design Canvas
        </Link>
        <a
          href="/api/backend/docs"
          target="_blank"
          className="px-6 py-3 glass text-slate-300 hover:text-white rounded-lg font-medium transition-colors"
        >
          API Docs
        </a>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-8 w-full max-w-3xl">
        {features.map((f) => (
          <div key={f.title} className="panel p-4 space-y-1">
            <div className="text-brand-500 text-xl">{f.icon}</div>
            <div className="font-medium text-sm">{f.title}</div>
            <div className="text-xs text-slate-400">{f.desc}</div>
          </div>
        ))}
      </div>
    </main>
  );
}

const features = [
  { icon: "⚗️", title: "Property Prediction", desc: "ML models predict mechanical & thermal properties from composition" },
  { icon: "🔍", title: "Inverse Design", desc: "Target properties → Pareto-optimal alloy candidates" },
  { icon: "📊", title: "Phase Diagrams", desc: "Binary & ternary phase stability from Materials Project" },
  { icon: "🤖", title: "AI Copilot", desc: "Local + Global AI suggestions on every canvas element" },
];
