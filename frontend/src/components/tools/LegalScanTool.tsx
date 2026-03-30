import { useState } from "react";
import { usePdfStore } from "@/stores/pdf-store";
import { scan, extract, type ScanPiece } from "@/api/client";
import { ToolWrapper } from "@/components/shared/ToolWrapper";
import { Scale, Search } from "lucide-react";

export function LegalScanTool() {
  const { files, scanPieces, setScanPieces, setLoading, setError, setResult, loading } = usePdfStore();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [scanned, setScanned] = useState(false);

  const file = files[0];

  const handleScan = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const res = await scan(file.file_id);
      setScanPieces(res.pieces);
      setScanned(true);
      // Auto-select pre-selected pieces
      const presel = new Set(
        res.pieces
          .filter((p: ScanPiece) => p.preselect)
          .map((p: ScanPiece) => p.unique_id ?? p.id)
      );
      setSelected(presel);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro no scan");
    } finally {
      setLoading(false);
    }
  };

  const togglePiece = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleExtract = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const segments = scanPieces
        .filter((p) => selected.has(p.unique_id ?? p.id))
        .map((p) => ({
          name: p.title,
          start: p.start_page_0_idx,
          end: p.end_page_0_idx,
        }));

      if (segments.length === 0) {
        setError("Selecione pelo menos uma peca");
        return;
      }

      const res = await extract({
        file_id: file.file_id,
        segments,
      });
      setResult(res.result_file_id, res.filename);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao extrair");
    }
  };

  return (
    <ToolWrapper
      title="Pecas Juridicas"
      description="Detecta automaticamente pecas juridicas (sentencas, recursos, etc.) no PDF."
    >
      {!scanned ? (
        <button
          onClick={handleScan}
          disabled={!file || loading}
          className="flex items-center gap-2 px-4 py-2 bg-[#025791] text-white rounded-lg hover:bg-[#1A7CC5] disabled:opacity-50 text-sm font-medium"
        >
          <Search className="w-4 h-4" />
          Escanear documento
        </button>
      ) : (
        <>
          <div className="text-sm text-gray-500 mb-2">
            {scanPieces.length} peca{scanPieces.length !== 1 ? "s" : ""} encontrada{scanPieces.length !== 1 ? "s" : ""}
          </div>

          <div className="space-y-1 max-h-80 overflow-y-auto">
            {scanPieces.map((piece) => {
              const id = piece.unique_id ?? piece.id;
              return (
                <label
                  key={id}
                  className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-gray-50 cursor-pointer text-sm"
                >
                  <input
                    type="checkbox"
                    checked={selected.has(id)}
                    onChange={() => togglePiece(id)}
                    className="rounded"
                  />
                  <Scale className="w-3.5 h-3.5 text-[#025791] shrink-0" />
                  <span className="flex-1">{piece.display_text}</span>
                  <span className="text-xs text-gray-400">
                    {piece.source === "bookmark_filter" ? "Marcador" : "Conteudo"}
                  </span>
                </label>
              );
            })}
          </div>

          {scanPieces.length > 0 && (
            <div className="flex gap-2">
              <button
                onClick={() => setSelected(new Set(scanPieces.map((p) => p.unique_id ?? p.id)))}
                className="text-xs text-[#5BA8D9] hover:underline"
              >
                Selecionar tudo
              </button>
              <button
                onClick={() => setSelected(new Set())}
                className="text-xs text-gray-500 hover:underline"
              >
                Limpar selecao
              </button>
            </div>
          )}

          <button
            onClick={handleExtract}
            disabled={selected.size === 0 || loading}
            className="px-4 py-2 bg-[#025791] text-white rounded-lg hover:bg-[#1A7CC5] disabled:opacity-50 text-sm font-medium"
          >
            Extrair {selected.size} peca{selected.size !== 1 ? "s" : ""} selecionada{selected.size !== 1 ? "s" : ""}
          </button>
        </>
      )}
    </ToolWrapper>
  );
}
