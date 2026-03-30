import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { uploadFiles, imagesToPdf } from "@/api/client";
import { usePdfStore } from "@/stores/pdf-store";
import { ToolWrapper } from "@/components/shared/ToolWrapper";
import { Image, Upload } from "lucide-react";

export function ConverterTool() {
  const { setLoading, setError, setResult, loading } = usePdfStore();
  const [imageIds, setImageIds] = useState<{ id: string; name: string }[]>([]);

  const onDrop = useCallback(
    async (accepted: File[]) => {
      if (accepted.length === 0) return;
      setLoading(true);
      try {
        const results = await uploadFiles(accepted);
        setImageIds((prev) => [
          ...prev,
          ...results.map((r) => ({ id: r.file_id, name: r.filename })),
        ]);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Erro ao carregar");
      } finally {
        setLoading(false);
      }
    },
    [setLoading, setError]
  );

  const { getRootProps, getInputProps } = useDropzone({
    onDrop,
    accept: {
      "image/jpeg": [".jpg", ".jpeg"],
      "image/png": [".png"],
      "image/tiff": [".tif", ".tiff"],
    },
  });

  const handleConvert = async () => {
    if (imageIds.length === 0) return;
    setLoading(true);
    setError(null);
    try {
      const res = await imagesToPdf({ file_ids: imageIds.map((i) => i.id) });
      setResult(res.result_file_id, res.filename);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao converter");
    }
  };

  return (
    <ToolWrapper
      title="Imagens para PDF"
      description="Converta JPG, PNG ou TIFF em um unico PDF."
    >
      <div
        {...getRootProps()}
        className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:border-[#5BA8D9] transition-colors"
      >
        <input {...getInputProps()} />
        <Upload className="w-8 h-8 mx-auto text-gray-400 mb-2" />
        <p className="text-sm text-gray-600">Arraste imagens aqui ou clique para selecionar</p>
      </div>

      {imageIds.length > 0 && (
        <div className="space-y-1">
          {imageIds.map((img, i) => (
            <div key={img.id} className="flex items-center gap-2 text-sm text-gray-600 bg-gray-50 px-3 py-1.5 rounded">
              <Image className="w-3.5 h-3.5" />
              <span>{i + 1}. {img.name}</span>
            </div>
          ))}
        </div>
      )}

      <button
        onClick={handleConvert}
        disabled={imageIds.length === 0 || loading}
        className="px-4 py-2 bg-[#025791] text-white rounded-lg hover:bg-[#1A7CC5] disabled:opacity-50 text-sm font-medium"
      >
        Converter {imageIds.length} imagem{imageIds.length !== 1 ? "ns" : ""} para PDF
      </button>
    </ToolWrapper>
  );
}
