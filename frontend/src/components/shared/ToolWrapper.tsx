import { Loader2 } from "lucide-react";
import { usePdfStore } from "@/stores/pdf-store";
import { DownloadButton } from "./DownloadButton";

interface Props {
  title: string;
  description: string;
  children: React.ReactNode;
}

export function ToolWrapper({ title, description, children }: Props) {
  const { loading, error, resultFileId, resultFilename } = usePdfStore();

  return (
    <div className="bg-white rounded-xl border border-gray-200/80 shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-100">
        <h2 className="text-lg font-semibold text-[#003761]">{title}</h2>
        <p className="text-sm text-[#5c7d99] mt-0.5">{description}</p>
      </div>

      <div className="px-6 py-5 space-y-4">
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
            {error}
          </div>
        )}

        {children}

        {loading && (
          <div className="flex items-center gap-2 text-[#025791] py-2">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-sm font-medium">Processando...</span>
          </div>
        )}

        {resultFileId && resultFilename && (
          <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center shrink-0">
              <svg className="w-4 h-4 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-emerald-800">Pronto!</p>
            </div>
            <DownloadButton fileId={resultFileId} filename={resultFilename} />
          </div>
        )}
      </div>
    </div>
  );
}
