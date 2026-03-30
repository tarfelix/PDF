import { useState } from "react";
import { usePdfStore } from "@/stores/pdf-store";
import { optimize } from "@/api/client";
import { ToolWrapper } from "@/components/shared/ToolWrapper";
import { PasswordInput } from "@/components/shared/PasswordInput";
import { formatBytes } from "@/lib/utils";

const PROFILES = [
  { value: "light", label: "Leve", desc: "Compressao basica" },
  { value: "recommended", label: "Recomendado", desc: "Bom equilibrio" },
  { value: "maximum", label: "Maximo", desc: "Menor tamanho possivel" },
];

export function OptimizeTool() {
  const { files, setLoading, setError, setResult } = usePdfStore();
  const [profile, setProfile] = useState("recommended");
  const [password, setPassword] = useState("");
  const [removeAnnotations, setRemoveAnnotations] = useState(false);
  const [metadata, setMetadata] = useState({ title: "", author: "", subject: "" });
  const [reduction, setReduction] = useState<number | null>(null);

  const file = files[0];

  const handleOptimize = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setReduction(null);
    try {
      const meta: Record<string, string> = {};
      if (metadata.title) meta.title = metadata.title;
      if (metadata.author) meta.author = metadata.author;
      if (metadata.subject) meta.subject = metadata.subject;

      const res = await optimize({
        file_id: file.file_id,
        profile,
        password: password || undefined,
        remove_annotations: removeAnnotations,
        metadata: Object.keys(meta).length > 0 ? meta : undefined,
      });
      setResult(res.result_file_id, res.filename);
      setReduction(res.reduction_percent);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao otimizar");
    }
  };

  return (
    <ToolWrapper
      title="Otimizar PDF"
      description="Comprima e otimize o PDF. Edite metadados e proteja com senha."
    >
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Perfil de compressao</label>
        <div className="flex gap-2">
          {PROFILES.map((p) => (
            <button
              key={p.value}
              onClick={() => setProfile(p.value)}
              className={`flex-1 p-3 rounded-lg border text-left ${
                profile === p.value
                  ? "border-[#5BA8D9] bg-[#EAF4FC]"
                  : "border-gray-200 hover:bg-gray-50"
              }`}
            >
              <div className="text-sm font-medium">{p.label}</div>
              <div className="text-xs text-gray-500">{p.desc}</div>
            </button>
          ))}
        </div>
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={removeAnnotations} onChange={(e) => setRemoveAnnotations(e.target.checked)} className="rounded" />
        Remover anotacoes
      </label>

      <div className="space-y-2">
        <label className="block text-sm font-medium text-gray-700">Metadados (opcional)</label>
        <input type="text" placeholder="Titulo" value={metadata.title} onChange={(e) => setMetadata({ ...metadata, title: e.target.value })}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-[#5BA8D9] outline-none" />
        <input type="text" placeholder="Autor" value={metadata.author} onChange={(e) => setMetadata({ ...metadata, author: e.target.value })}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-[#5BA8D9] outline-none" />
        <input type="text" placeholder="Assunto" value={metadata.subject} onChange={(e) => setMetadata({ ...metadata, subject: e.target.value })}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-[#5BA8D9] outline-none" />
      </div>

      <PasswordInput value={password} onChange={setPassword} />

      <button
        onClick={handleOptimize}
        disabled={!file}
        className="px-4 py-2 bg-[#025791] text-white rounded-lg hover:bg-[#1A7CC5] disabled:opacity-50 text-sm font-medium"
      >
        Otimizar PDF
      </button>

      {reduction !== null && (
        <p className="text-sm text-green-600">
          Reducao de {reduction}% ({formatBytes(file?.size_bytes ?? 0)} original)
        </p>
      )}
    </ToolWrapper>
  );
}
