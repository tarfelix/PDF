import { useState } from "react";
import { usePdfStore } from "@/stores/pdf-store";
import { redact } from "@/api/client";
import { ToolWrapper } from "@/components/shared/ToolWrapper";

const PATTERNS = [
  { id: "cpf", label: "CPF (XXX.XXX.XXX-XX)" },
  { id: "cnpj", label: "CNPJ (XX.XXX.XXX/XXXX-XX)" },
  { id: "email", label: "E-mail" },
  { id: "date", label: "Data (DD/MM/AAAA)" },
];

export function RedactTool() {
  const { files, setLoading, setError, setResult } = usePdfStore();
  const [keywords, setKeywords] = useState("");
  const [ignoreCase, setIgnoreCase] = useState(true);
  const [selectedPatterns, setSelectedPatterns] = useState<Set<string>>(new Set());

  const file = files[0];

  const togglePattern = (id: string) => {
    setSelectedPatterns((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleRedact = async () => {
    if (!file) return;
    const kws = keywords.split(",").map((k) => k.trim()).filter(Boolean);
    if (kws.length === 0 && selectedPatterns.size === 0) {
      setError("Informe pelo menos uma palavra-chave ou padrao");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await redact({
        file_id: file.file_id,
        keywords: kws,
        ignore_case: ignoreCase,
        patterns: [...selectedPatterns],
      });
      setResult(res.result_file_id, res.filename);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao redactar");
    }
  };

  return (
    <ToolWrapper
      title="Redacao (Tarja)"
      description="Aplique tarja preta em textos sensiveis — LGPD compliance."
    >
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Palavras-chave</label>
        <textarea
          value={keywords}
          onChange={(e) => setKeywords(e.target.value)}
          placeholder="Separe por virgula: nome, endereco, telefone"
          rows={3}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-[#5BA8D9] focus:border-transparent outline-none resize-none"
        />
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={ignoreCase} onChange={(e) => setIgnoreCase(e.target.checked)} className="rounded" />
        Ignorar maiusculas/minusculas
      </label>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Padroes automaticos</label>
        <div className="grid grid-cols-2 gap-2">
          {PATTERNS.map((p) => (
            <label key={p.id} className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={selectedPatterns.has(p.id)}
                onChange={() => togglePattern(p.id)}
                className="rounded"
              />
              {p.label}
            </label>
          ))}
        </div>
      </div>

      <button
        onClick={handleRedact}
        disabled={!file}
        className="px-4 py-2 bg-[#025791] text-white rounded-lg hover:bg-[#1A7CC5] disabled:opacity-50 text-sm font-medium"
      >
        Aplicar Redacao
      </button>
    </ToolWrapper>
  );
}
