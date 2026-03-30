import { useState } from "react";
import { usePdfStore } from "@/stores/pdf-store";
import { merge } from "@/api/client";
import { ToolWrapper } from "@/components/shared/ToolWrapper";
import { PasswordInput } from "@/components/shared/PasswordInput";
import { GripVertical, ArrowUp, ArrowDown } from "lucide-react";

export function MergeTool() {
  const { files, setLoading, setError, setResult } = usePdfStore();
  const [order, setOrder] = useState<number[]>(() => files.map((_, i) => i));
  const [optimize, setOptimize] = useState(true);
  const [password, setPassword] = useState("");

  const moveUp = (idx: number) => {
    if (idx === 0) return;
    const next = [...order];
    [next[idx - 1]!, next[idx]!] = [next[idx]!, next[idx - 1]!];
    setOrder(next);
  };

  const moveDown = (idx: number) => {
    if (idx === order.length - 1) return;
    const next = [...order];
    [next[idx]!, next[idx + 1]!] = [next[idx + 1]!, next[idx]!];
    setOrder(next);
  };

  const handleMerge = async () => {
    setLoading(true);
    setError(null);
    try {
      const fileIds = order.map((i) => files[i]!.file_id);
      const res = await merge({
        file_ids: fileIds,
        optimize,
        password: password || undefined,
      });
      setResult(res.result_file_id, res.filename);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao mesclar");
    }
  };

  return (
    <ToolWrapper
      title="Mesclar PDFs"
      description="Combine multiplos PDFs em um unico arquivo. Arraste para reordenar."
    >
      <div className="space-y-2">
        {order.map((fileIdx, pos) => {
          const f = files[fileIdx];
          if (!f) return null;
          return (
            <div
              key={f.file_id}
              className="flex items-center gap-2 bg-gray-50 rounded-lg px-3 py-2 border border-gray-200"
            >
              <GripVertical className="w-4 h-4 text-gray-400" />
              <span className="text-sm flex-1 truncate">{f.filename}</span>
              <div className="flex gap-1">
                <button onClick={() => moveUp(pos)} className="p-1 hover:bg-gray-200 rounded" disabled={pos === 0}>
                  <ArrowUp className="w-3.5 h-3.5" />
                </button>
                <button onClick={() => moveDown(pos)} className="p-1 hover:bg-gray-200 rounded" disabled={pos === order.length - 1}>
                  <ArrowDown className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          );
        })}
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={optimize} onChange={(e) => setOptimize(e.target.checked)} className="rounded" />
        Otimizar resultado
      </label>

      <PasswordInput value={password} onChange={setPassword} />

      <button
        onClick={handleMerge}
        disabled={files.length < 2}
        className="px-4 py-2 bg-[#025791] text-white rounded-lg hover:bg-[#1A7CC5] disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
      >
        Mesclar {files.length} PDFs
      </button>
    </ToolWrapper>
  );
}
