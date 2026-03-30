import { useState } from "react";
import { usePdfStore } from "@/stores/pdf-store";
import { remove } from "@/api/client";
import { ToolWrapper } from "@/components/shared/ToolWrapper";
import { PageRangeInput } from "@/components/shared/PageRangeInput";
import { PasswordInput } from "@/components/shared/PasswordInput";

export function RemoveTool() {
  const { files, setLoading, setError, setResult } = usePdfStore();
  const [pages, setPages] = useState("");
  const [password, setPassword] = useState("");
  const [optimize, setOptimize] = useState(true);

  const file = files[0];

  const handleRemove = async () => {
    if (!file || !pages.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await remove({
        file_id: file.file_id,
        pages,
        optimize,
        password: password || undefined,
      });
      setResult(res.result_file_id, res.filename);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao remover");
    }
  };

  return (
    <ToolWrapper
      title="Remover Paginas"
      description="Remova paginas especificas do PDF."
    >
      <PageRangeInput value={pages} onChange={setPages} maxPages={file?.pages} label="Paginas para remover" />

      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={optimize} onChange={(e) => setOptimize(e.target.checked)} className="rounded" />
        Otimizar resultado
      </label>

      <PasswordInput value={password} onChange={setPassword} />

      <button
        onClick={handleRemove}
        disabled={!file || !pages.trim()}
        className="px-4 py-2 bg-[#025791] text-white rounded-lg hover:bg-[#1A7CC5] disabled:opacity-50 text-sm font-medium"
      >
        Remover Paginas
      </button>
    </ToolWrapper>
  );
}
