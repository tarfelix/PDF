import { useState } from "react";
import { Header } from "@/components/layout/Header";
import { Sidebar } from "@/components/layout/Sidebar";
import { FileUpload } from "@/components/layout/FileUpload";
import { Onboarding } from "@/components/onboarding/Onboarding";
import { LoginPage } from "@/components/auth/LoginPage";
import { usePdfStore } from "@/stores/pdf-store";
import { useAuthStore } from "@/stores/auth-store";
import { HelpCircle } from "lucide-react";

import { LegalScanTool } from "@/components/tools/LegalScanTool";
import { BatesTool } from "@/components/tools/BatesTool";
import { RedactTool } from "@/components/tools/RedactTool";
import { VisualEditorTool } from "@/components/tools/VisualEditorTool";
import { RemoveTool } from "@/components/tools/RemoveTool";
import { ExtractTool } from "@/components/tools/ExtractTool";
import { SplitTool } from "@/components/tools/SplitTool";
import { OptimizeTool } from "@/components/tools/OptimizeTool";
import { MergeTool } from "@/components/tools/MergeTool";
import { ConverterTool } from "@/components/tools/ConverterTool";
import { DiffTool } from "@/components/tools/DiffTool";

const TOOL_COMPONENTS: Record<string, React.ComponentType> = {
  legal: LegalScanTool,
  bates: BatesTool,
  redact: RedactTool,
  visual: VisualEditorTool,
  remove: RemoveTool,
  extract: ExtractTool,
  split: SplitTool,
  optimize: OptimizeTool,
  merge: MergeTool,
  converter: ConverterTool,
  diff: DiffTool,
};

const ONBOARDING_KEY = "pdf-editor-onboarding-done";

export default function App() {
  const { activeTool } = usePdfStore();
  const { token } = useAuthStore();
  const ActiveComponent = TOOL_COMPONENTS[activeTool];

  const [showOnboarding, setShowOnboarding] = useState(() => {
    return !localStorage.getItem(ONBOARDING_KEY);
  });

  const completeOnboarding = () => {
    localStorage.setItem(ONBOARDING_KEY, "true");
    setShowOnboarding(false);
  };

  const reopenOnboarding = () => {
    setShowOnboarding(true);
  };

  if (!token) {
    return <LoginPage />;
  }

  return (
    <div className="h-screen flex flex-col bg-[#f0f4f8]">
      {showOnboarding && <Onboarding onComplete={completeOnboarding} />}

      <Header />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-6">
          <div className="max-w-4xl mx-auto space-y-5">
            <FileUpload />
            {ActiveComponent && <ActiveComponent />}
          </div>
        </main>
      </div>

      {/* Help button to reopen onboarding */}
      <button
        onClick={reopenOnboarding}
        className="fixed bottom-5 right-5 w-10 h-10 rounded-full bg-[#025791] text-white shadow-lg hover:bg-[#022340] transition-all hover:scale-105 flex items-center justify-center z-40"
        title="Ajuda / Tutorial"
      >
        <HelpCircle className="w-5 h-5" />
      </button>
    </div>
  );
}
