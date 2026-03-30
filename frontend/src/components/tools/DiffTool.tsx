import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { uploadFiles, diff } from "@/api/client";
import { usePdfStore } from "@/stores/pdf-store";
import { ToolWrapper } from "@/components/shared/ToolWrapper";
import { FileText, Upload } from "lucide-react";

export function DiffTool() {
  const { setLoading, setError, loading } = usePdfStore();
  const [fileA, setFileA] = useState<{ id: string; name: string } | null>(null);
  const [fileB, setFileB] = useState<{ id: string; name: string } | null>(null);
  const [htmlResult, setHtmlResult] = useState<string | null>(null);

  const uploadOne = useCallback(
    async (files: File[], setter: (v: { id: string; name: string }) => void) => {
      if (files.length === 0) return;
      setLoading(true);
      try {
        const results = await uploadFiles([files[0]!]);
        setter({ id: results[0]!.file_id, name: results[0]!.filename });
      } catch (e) {
        setError(e instanceof Error ? e.message : "Erro");
      } finally {
        setLoading(false);
      }
    },
    [setLoading, setError]
  );

  const dropA = useDropzone({
    onDrop: (f) => uploadOne(f, setFileA),
    accept: { "application/pdf": [".pdf"] },
    maxFiles: 1,
  });

  const dropB = useDropzone({
    onDrop: (f) => uploadOne(f, setFileB),
    accept: { "application/pdf": [".pdf"] },
    maxFiles: 1,
  });

  const handleCompare = async () => {
    if (!fileA || !fileB) return;
    setLoading(true);
    setError(null);
    setHtmlResult(null);
    try {
      const html = await diff({ file_id_a: fileA.id, file_id_b: fileB.id });
      setHtmlResult(html);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao comparar");
    } finally {
      setLoading(false);
    }
  };

  const FileDropZone = ({
    drop,
    file,
    label,
  }: {
    drop: ReturnType<typeof useDropzone>;
    file: { id: string; name: string } | null;
    label: string;
  }) => (
    <div
      {...drop.getRootProps()}
      className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center cursor-pointer hover:border-[#5BA8D9] transition-colors"
    >
      <input {...drop.getInputProps()} />
      {file ? (
        <div className="flex items-center justify-center gap-2 text-sm text-gray-600">
          <FileText className="w-4 h-4 text-[#025791]" />
          {file.name}
        </div>
      ) : (
        <>
          <Upload className="w-6 h-6 mx-auto text-gray-400 mb-1" />
          <p className="text-xs text-gray-500">{label}</p>
        </>
      )}
    </div>
  );

  return (
    <ToolWrapper
      title="Comparar Versoes"
      description="Compare o texto de dois PDFs lado a lado."
    >
      <div className="grid grid-cols-2 gap-3">
        <FileDropZone drop={dropA} file={fileA} label="PDF Original" />
        <FileDropZone drop={dropB} file={fileB} label="PDF Modificado" />
      </div>

      <button
        onClick={handleCompare}
        disabled={!fileA || !fileB || loading}
        className="px-4 py-2 bg-[#025791] text-white rounded-lg hover:bg-[#1A7CC5] disabled:opacity-50 text-sm font-medium"
      >
        Comparar
      </button>

      {htmlResult && (
        <div className="border border-gray-200 rounded-lg overflow-auto max-h-[500px]">
          <iframe
            srcDoc={htmlResult}
            className="w-full h-[500px] border-0"
            title="Diff result"
          />
        </div>
      )}
    </ToolWrapper>
  );
}
