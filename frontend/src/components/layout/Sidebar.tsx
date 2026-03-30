import {
  Scale,
  Hash,
  EyeOff,
  LayoutGrid,
  Trash2,
  FileOutput,
  Scissors,
  Zap,
  Merge,
  Image,
  GitCompare,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { usePdfStore, type Tool } from "@/stores/pdf-store";

interface ToolItem {
  id: Tool;
  label: string;
  description: string;
  icon: React.ElementType;
  requiresSingle?: boolean;
  requiresNone?: boolean;
  requiresMultiple?: boolean;
  group: "analysis" | "edit" | "transform" | "utility";
}

const TOOLS: ToolItem[] = [
  { id: "legal", label: "Pecas Juridicas", description: "Detectar e extrair pecas", icon: Scale, requiresSingle: true, group: "analysis" },
  { id: "bates", label: "Numeracao Bates", description: "Carimbo sequencial", icon: Hash, requiresSingle: true, group: "edit" },
  { id: "redact", label: "Redacao (Tarja)", description: "LGPD - ocultar dados", icon: EyeOff, requiresSingle: true, group: "edit" },
  { id: "visual", label: "Editor Visual", description: "Selecionar e rotacionar", icon: LayoutGrid, requiresSingle: true, group: "edit" },
  { id: "remove", label: "Remover Paginas", description: "Deletar paginas", icon: Trash2, requiresSingle: true, group: "transform" },
  { id: "extract", label: "Extrair Paginas", description: "Separar paginas", icon: FileOutput, requiresSingle: true, group: "transform" },
  { id: "split", label: "Dividir PDF", description: "Separar em partes", icon: Scissors, requiresSingle: true, group: "transform" },
  { id: "optimize", label: "Otimizar", description: "Comprimir e proteger", icon: Zap, requiresSingle: true, group: "utility" },
  { id: "merge", label: "Mesclar PDFs", description: "Combinar arquivos", icon: Merge, requiresMultiple: true, group: "utility" },
  { id: "converter", label: "Imagens p/ PDF", description: "JPG, PNG, TIFF", icon: Image, requiresNone: true, group: "utility" },
  { id: "diff", label: "Comparar Versoes", description: "Diff lado a lado", icon: GitCompare, requiresNone: true, group: "utility" },
];

const GROUPS: { key: string; label: string }[] = [
  { key: "analysis", label: "Analise" },
  { key: "edit", label: "Edicao" },
  { key: "transform", label: "Transformar" },
  { key: "utility", label: "Utilidades" },
];

export function Sidebar() {
  const { files, activeTool, setActiveTool } = usePdfStore();
  const isSingle = files.length === 1 && files[0]?.pages !== undefined;
  const isMultiple = files.length > 1;

  return (
    <aside className="w-60 bg-white border-r border-gray-200/80 flex flex-col shrink-0 overflow-y-auto">
      <nav className="p-3 flex flex-col gap-1">
        {GROUPS.map((group) => {
          const groupTools = TOOLS.filter((t) => t.group === group.key);
          if (groupTools.length === 0) return null;

          return (
            <div key={group.key} className="mb-1">
              <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-[#5c7d99]">
                {group.label}
              </div>
              {groupTools.map((tool) => {
                let enabled = true;
                if (tool.requiresSingle) enabled = isSingle;
                else if (tool.requiresMultiple) enabled = isMultiple || files.length >= 1;

                const Icon = tool.icon;
                const isActive = activeTool === tool.id;

                return (
                  <button
                    key={tool.id}
                    onClick={() => enabled && setActiveTool(tool.id)}
                    disabled={!enabled}
                    className={cn(
                      "w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left transition-all group",
                      isActive
                        ? "bg-[#025791] text-white shadow-sm"
                        : enabled
                          ? "text-[#003761] hover:bg-[#EAF4FC]"
                          : "text-gray-300 cursor-not-allowed"
                    )}
                  >
                    <div className={cn(
                      "w-7 h-7 rounded-md flex items-center justify-center shrink-0 transition-colors",
                      isActive
                        ? "bg-white/20"
                        : enabled
                          ? "bg-[#EAF4FC] group-hover:bg-[#D4EAFA]"
                          : "bg-gray-50"
                    )}>
                      <Icon className={cn("w-3.5 h-3.5", isActive ? "text-white" : enabled ? "text-[#025791]" : "text-gray-300")} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className={cn("text-sm font-medium leading-tight", isActive ? "text-white" : "")}>{tool.label}</div>
                      <div className={cn("text-[10px] leading-tight truncate", isActive ? "text-blue-100/70" : "text-[#5c7d99]")}>
                        {tool.description}
                      </div>
                    </div>
                    {isActive && <ChevronRight className="w-3.5 h-3.5 text-white/50 shrink-0" />}
                  </button>
                );
              })}
            </div>
          );
        })}
      </nav>
    </aside>
  );
}
