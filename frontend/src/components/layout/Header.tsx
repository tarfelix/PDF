import { usePdfStore } from "@/stores/pdf-store";
import { RotateCcw } from "lucide-react";

export function Header() {
  const { files, reset } = usePdfStore();

  return (
    <header className="bg-gradient-to-r from-[#022340] via-[#025791] to-[#1A7CC5] text-white px-6 py-3 shadow-lg">
      <div className="flex items-center justify-between max-w-[1600px] mx-auto">
        <div className="flex items-center gap-4">
          <img
            src="/logo-white.png"
            alt="Soares, Picon"
            className="h-10 w-auto object-contain"
          />
          <div className="hidden sm:block border-l border-white/20 pl-4">
            <h1 className="text-base font-semibold tracking-tight leading-tight">
              Editor de PDF
            </h1>
            <p className="text-[11px] text-blue-200/70 leading-tight">
              Ferramentas de manipulacao de documentos
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {files.length > 0 && (
            <button
              onClick={reset}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-white/10 hover:bg-white/20 rounded-md transition-colors"
            >
              <RotateCcw className="w-3 h-3" />
              Novo projeto
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
