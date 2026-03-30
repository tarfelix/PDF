import { useState } from "react";
import { usePdfStore } from "@/stores/pdf-store";
import { split } from "@/api/client";
import { ToolWrapper } from "@/components/shared/ToolWrapper";

export function SplitTool() {
  const { files, setLoading, setError, setResult } = usePdfStore();
  const [mode, setMode] = useState<"count" | "size" | "bookmark">("count");
  const [value, setValue] = useState("5");
  const [optimize, setOptimize] = useState(true);

  const file = files[0];

  const handleSplit = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const res = await split({
        file_id: file.file_id,
        mode,
        value: parseFloat(value),
        optimize,
      });
      setResult(res.result_file_id, res.filename);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao dividir");
    }
  };

  const labels = {
    count: "Paginas por parte",
    size: "Tamanho maximo (MB)",
    bookmark: "Nivel do marcador",
  };

  return (
    <ToolWrapper
      title="Dividir PDF"
      description="Divida um PDF em partes menores por contagem, tamanho ou marcadores."
    >
      <div className="flex gap-2">
        {(["count", "size", "bookmark"] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              mode === m
                ? "bg-[#025791] text-white"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            }`}
          >
            {m === "count" ? "Por contagem" : m === "size" ? "Por tamanho" : "Por marcador"}
          </button>
        ))}
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {labels[mode]}
        </label>
        <input
          type="number"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          min={mode === "bookmark" ? 1 : 0.5}
          step={mode === "size" ? 0.5 : 1}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-[#5BA8D9] focus:border-transparent outline-none"
        />
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={optimize} onChange={(e) => setOptimize(e.target.checked)} className="rounded" />
        Otimizar partes
      </label>

      <button
        onClick={handleSplit}
        disabled={!file}
        className="px-4 py-2 bg-[#025791] text-white rounded-lg hover:bg-[#1A7CC5] disabled:opacity-50 text-sm font-medium"
      >
        Dividir PDF
      </button>
    </ToolWrapper>
  );
}
