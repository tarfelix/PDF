import { usePdfStore } from "@/stores/pdf-store";
import { useAuthStore } from "@/stores/auth-store";
import { RotateCcw, LogOut, User } from "lucide-react";

export function Header() {
  const { files, reset } = usePdfStore();
  const { user, logout } = useAuthStore();

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

          {user && (
            <div className="flex items-center gap-2 border-l border-white/20 pl-3">
              <div className="flex items-center gap-1.5 text-xs text-blue-100">
                <User className="w-3.5 h-3.5" />
                <span className="hidden md:inline">{user.name}</span>
              </div>
              <button
                onClick={logout}
                className="flex items-center gap-1 px-2 py-1 text-xs text-blue-200/80 hover:text-white hover:bg-white/10 rounded transition-colors"
                title="Sair"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
