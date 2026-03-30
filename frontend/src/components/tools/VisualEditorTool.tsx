import { useState, useEffect, useCallback } from "react";
import { usePdfStore } from "@/stores/pdf-store";
import { getThumbnails, extract, remove, rotate, type Thumbnail } from "@/api/client";
import { ToolWrapper } from "@/components/shared/ToolWrapper";
import { RotateCw, Check, Trash2, FileOutput, Loader2 } from "lucide-react";

const PAGE_BATCH = 20;

export function VisualEditorTool() {
  const { files, setLoading, setError, setResult, loading } = usePdfStore();
  const [thumbs, setThumbs] = useState<Thumbnail[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [rotations, setRotations] = useState<Record<number, number>>({});
  const [loadedPages, setLoadedPages] = useState(0);
  const [loadingThumbs, setLoadingThumbs] = useState(false);

  const file = files[0];
  const totalPages = file?.pages ?? 0;

  const loadMore = useCallback(async () => {
    if (!file || loadingThumbs) return;
    setLoadingThumbs(true);
    try {
      const res = await getThumbnails(file.file_id, loadedPages, loadedPages + PAGE_BATCH - 1);
      setThumbs((prev) => [...prev, ...res.thumbnails]);
      setLoadedPages((prev) => prev + res.thumbnails.length);
    } catch {
      // ignore
    } finally {
      setLoadingThumbs(false);
    }
  }, [file, loadedPages, loadingThumbs]);

  useEffect(() => {
    if (file && thumbs.length === 0) {
      loadMore();
    }
  }, [file]);

  const togglePage = (page: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(page)) next.delete(page);
      else next.add(page);
      return next;
    });
  };

  const rotatePage = (page: number) => {
    setRotations((prev) => ({
      ...prev,
      [page]: ((prev[page] ?? 0) + 90) % 360,
    }));
  };

  const handleExtractSelected = async () => {
    if (!file || selected.size === 0) return;
    setLoading(true);
    setError(null);
    try {
      const res = await extract({
        file_id: file.file_id,
        page_indices: [...selected].sort((a, b) => a - b),
      });
      setResult(res.result_file_id, res.filename);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro");
    }
  };

  const handleRemoveSelected = async () => {
    if (!file || selected.size === 0) return;
    setLoading(true);
    setError(null);
    try {
      const res = await remove({
        file_id: file.file_id,
        page_indices: [...selected].sort((a, b) => a - b),
      });
      setResult(res.result_file_id, res.filename);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro");
    }
  };

  const handleApplyRotations = async () => {
    if (!file) return;
    const active = Object.fromEntries(
      Object.entries(rotations).filter(([_, v]) => v !== 0)
    );
    if (Object.keys(active).length === 0) return;
    setLoading(true);
    setError(null);
    try {
      const res = await rotate({ file_id: file.file_id, rotations: active });
      setResult(res.result_file_id, res.filename);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro");
    }
  };

  return (
    <ToolWrapper
      title="Editor Visual"
      description="Selecione, rotacione, extraia ou remova paginas visualmente."
    >
      {/* Actions bar */}
      <div className="flex flex-wrap gap-2">
        <button onClick={() => setSelected(new Set(thumbs.map((t) => t.page)))}
          className="text-xs px-2 py-1 bg-gray-100 rounded hover:bg-gray-200">
          Selecionar tudo
        </button>
        <button onClick={() => setSelected(new Set())}
          className="text-xs px-2 py-1 bg-gray-100 rounded hover:bg-gray-200">
          Limpar selecao
        </button>
        {selected.size > 0 && (
          <>
            <button onClick={handleExtractSelected} disabled={loading}
              className="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded hover:bg-blue-200 flex items-center gap-1">
              <FileOutput className="w-3 h-3" /> Extrair {selected.size}
            </button>
            <button onClick={handleRemoveSelected} disabled={loading}
              className="text-xs px-2 py-1 bg-red-100 text-red-700 rounded hover:bg-red-200 flex items-center gap-1">
              <Trash2 className="w-3 h-3" /> Remover {selected.size}
            </button>
          </>
        )}
        {Object.values(rotations).some((v) => v !== 0) && (
          <button onClick={handleApplyRotations} disabled={loading}
            className="text-xs px-2 py-1 bg-green-100 text-green-700 rounded hover:bg-green-200 flex items-center gap-1">
            <RotateCw className="w-3 h-3" /> Aplicar rotacoes
          </button>
        )}
      </div>

      {/* Thumbnail grid */}
      <div className="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 lg:grid-cols-8 gap-3">
        {thumbs.map((t) => (
          <div key={t.page} className="relative group">
            <button
              onClick={() => togglePage(t.page)}
              className={`block w-full rounded-lg overflow-hidden border-2 transition-colors ${
                selected.has(t.page) ? "border-[#5BA8D9] ring-2 ring-blue-200" : "border-gray-200 hover:border-gray-400"
              }`}
            >
              <img
                src={t.data}
                alt={`Pagina ${t.page + 1}`}
                className="w-full h-auto"
                style={{ transform: `rotate(${rotations[t.page] ?? 0}deg)` }}
              />
              {selected.has(t.page) && (
                <div className="absolute top-1 left-1 bg-[#5BA8D9] text-white rounded-full w-5 h-5 flex items-center justify-center">
                  <Check className="w-3 h-3" />
                </div>
              )}
            </button>
            <div className="flex items-center justify-between mt-1">
              <span className="text-xs text-gray-500">{t.page + 1}</span>
              <button
                onClick={() => rotatePage(t.page)}
                className="p-0.5 text-gray-400 hover:text-[#025791] rounded"
                title="Rotacionar 90°"
              >
                <RotateCw className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Load more */}
      {loadedPages < totalPages && (
        <button
          onClick={loadMore}
          disabled={loadingThumbs}
          className="w-full py-2 text-sm text-[#025791] hover:bg-gray-50 rounded-lg border border-gray-200 flex items-center justify-center gap-2"
        >
          {loadingThumbs ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
          Carregar mais ({totalPages - loadedPages} restantes)
        </button>
      )}
    </ToolWrapper>
  );
}
