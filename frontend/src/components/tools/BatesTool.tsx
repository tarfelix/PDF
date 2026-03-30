import { useState } from "react";
import { usePdfStore } from "@/stores/pdf-store";
import { bates } from "@/api/client";
import { ToolWrapper } from "@/components/shared/ToolWrapper";

const POSITIONS = [
  { value: "top_left", label: "Topo esquerdo" },
  { value: "top_center", label: "Topo centro" },
  { value: "top_right", label: "Topo direito" },
  { value: "bottom_left", label: "Rodape esquerdo" },
  { value: "bottom_center", label: "Rodape centro" },
  { value: "bottom_right", label: "Rodape direito" },
];

export function BatesTool() {
  const { files, setLoading, setError, setResult } = usePdfStore();
  const [pattern, setPattern] = useState("Doc. {doc_idx} - Fls. {page_idx}");
  const [docIdx, setDocIdx] = useState(1);
  const [pageIdx, setPageIdx] = useState(1);
  const [position, setPosition] = useState("bottom_right");
  const [fontSize, setFontSize] = useState(10);

  const file = files[0];

  const handleBates = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const res = await bates({
        file_id: file.file_id,
        text_pattern: pattern,
        start_doc_idx: docIdx,
        start_page_idx: pageIdx,
        position,
        font_size: fontSize,
      });
      setResult(res.result_file_id, res.filename);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao aplicar Bates");
    }
  };

  return (
    <ToolWrapper
      title="Numeracao Bates"
      description="Adicione numeracao sequencial (Bates Numbering) em cada pagina."
    >
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Padrao do texto</label>
        <input
          type="text"
          value={pattern}
          onChange={(e) => setPattern(e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-[#5BA8D9] focus:border-transparent outline-none"
        />
        <p className="text-xs text-gray-400 mt-1">Use {"{doc_idx}"} e {"{page_idx}"} como variaveis</p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Inicio Doc</label>
          <input type="number" value={docIdx} onChange={(e) => setDocIdx(+e.target.value)} min={1}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-[#5BA8D9] outline-none" />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Inicio Pagina</label>
          <input type="number" value={pageIdx} onChange={(e) => setPageIdx(+e.target.value)} min={1}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-[#5BA8D9] outline-none" />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Posicao</label>
        <select
          value={position}
          onChange={(e) => setPosition(e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-[#5BA8D9] outline-none"
        >
          {POSITIONS.map((p) => (
            <option key={p.value} value={p.value}>{p.label}</option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Tamanho da fonte: {fontSize}pt</label>
        <input type="range" min={6} max={24} value={fontSize} onChange={(e) => setFontSize(+e.target.value)}
          className="w-full" />
      </div>

      <button
        onClick={handleBates}
        disabled={!file}
        className="px-4 py-2 bg-[#025791] text-white rounded-lg hover:bg-[#1A7CC5] disabled:opacity-50 text-sm font-medium"
      >
        Aplicar Numeracao
      </button>
    </ToolWrapper>
  );
}
