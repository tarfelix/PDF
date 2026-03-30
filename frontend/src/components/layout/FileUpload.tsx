import { useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, X, FileText, Plus } from "lucide-react";
import { usePdfStore } from "@/stores/pdf-store";
import { uploadFiles } from "@/api/client";
import { formatBytes } from "@/lib/utils";

export function FileUpload() {
  const { files, setFiles, addFiles, clearFiles, setLoading, setError, loading } = usePdfStore();

  const onDrop = useCallback(
    async (accepted: File[]) => {
      if (accepted.length === 0) return;
      setLoading(true);
      setError(null);
      try {
        const results = await uploadFiles(accepted);
        if (files.length === 0) {
          setFiles(results);
        } else {
          addFiles(results);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Erro ao carregar arquivo");
      } finally {
        setLoading(false);
      }
    },
    [files.length, setFiles, addFiles, setLoading, setError]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "image/jpeg": [".jpg", ".jpeg"],
      "image/png": [".png"],
      "image/tiff": [".tif", ".tiff"],
    },
  });

  if (files.length > 0) {
    return (
      <div className="bg-white rounded-xl border border-gray-200/80 p-4 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-[#EAF4FC] flex items-center justify-center">
              <FileText className="w-3.5 h-3.5 text-[#025791]" />
            </div>
            <span className="text-sm font-semibold text-[#003761]">
              {files.length} arquivo{files.length > 1 ? "s" : ""} carregado{files.length > 1 ? "s" : ""}
            </span>
          </div>
          <button
            onClick={clearFiles}
            className="text-xs text-red-500 hover:text-red-700 flex items-center gap-1 px-2 py-1 rounded-md hover:bg-red-50 transition-colors"
          >
            <X className="w-3 h-3" /> Limpar
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {files.map((f) => (
            <div
              key={f.file_id}
              className="flex items-center gap-2 bg-[#EAF4FC] rounded-lg px-3 py-2 text-xs border border-[#D4EAFA]"
            >
              <FileText className="w-3.5 h-3.5 text-[#025791]" />
              <span className="max-w-[180px] truncate font-medium text-[#003761]">{f.filename}</span>
              {f.pages !== undefined && (
                <span className="text-[#5c7d99] bg-white/60 px-1.5 py-0.5 rounded text-[10px]">{f.pages} pag.</span>
              )}
              <span className="text-[#5c7d99] text-[10px]">{formatBytes(f.size_bytes)}</span>
            </div>
          ))}
        </div>
        <div
          {...getRootProps()}
          className="mt-3 border border-dashed border-[#A8D4F0] rounded-lg p-2 text-center text-xs text-[#5c7d99] hover:border-[#025791] hover:text-[#025791] hover:bg-[#EAF4FC] cursor-pointer transition-all flex items-center justify-center gap-1"
        >
          <input {...getInputProps()} />
          <Plus className="w-3.5 h-3.5" />
          Adicionar mais arquivos
        </div>
      </div>
    );
  }

  return (
    <div
      {...getRootProps()}
      className={`border-2 border-dashed rounded-2xl p-14 text-center cursor-pointer transition-all bg-white shadow-sm ${
        isDragActive
          ? "border-[#025791] bg-[#EAF4FC] shadow-md"
          : "border-[#A8D4F0] hover:border-[#025791] hover:bg-[#EAF4FC]/50"
      }`}
    >
      <input {...getInputProps()} />
      <div className={`w-16 h-16 mx-auto mb-4 rounded-2xl flex items-center justify-center ${
        isDragActive ? "bg-[#025791]" : "bg-[#EAF4FC]"
      }`}>
        <Upload className={`w-7 h-7 ${isDragActive ? "text-white" : "text-[#025791]"}`} />
      </div>
      {loading ? (
        <p className="text-[#2d5a7b] font-medium">Carregando...</p>
      ) : isDragActive ? (
        <p className="text-[#025791] font-semibold text-lg">Solte os arquivos aqui</p>
      ) : (
        <>
          <p className="text-[#003761] font-semibold text-lg">
            Arraste PDFs ou imagens aqui
          </p>
          <p className="text-sm text-[#5c7d99] mt-1.5">
            ou clique para selecionar arquivos
          </p>
          <div className="flex items-center justify-center gap-3 mt-4">
            <span className="text-[10px] uppercase tracking-wider font-semibold text-[#A8D4F0] bg-[#EAF4FC] px-2 py-1 rounded">PDF</span>
            <span className="text-[10px] uppercase tracking-wider font-semibold text-[#A8D4F0] bg-[#EAF4FC] px-2 py-1 rounded">JPG</span>
            <span className="text-[10px] uppercase tracking-wider font-semibold text-[#A8D4F0] bg-[#EAF4FC] px-2 py-1 rounded">PNG</span>
            <span className="text-[10px] uppercase tracking-wider font-semibold text-[#A8D4F0] bg-[#EAF4FC] px-2 py-1 rounded">TIFF</span>
          </div>
        </>
      )}
    </div>
  );
}
