import { useState } from "react";
import {
  Upload,
  Scale,
  Hash,
  EyeOff,
  LayoutGrid,
  Scissors,
  Zap,
  Merge,
  Image,
  GitCompare,
  ChevronRight,
  ChevronLeft,
  X,
  Sparkles,
  Shield,
  FileText,
  ArrowRight,
} from "lucide-react";

interface OnboardingProps {
  onComplete: () => void;
}

interface Step {
  icon: React.ElementType;
  iconBg: string;
  title: string;
  subtitle: string;
  content: React.ReactNode;
}

export function Onboarding({ onComplete }: OnboardingProps) {
  const [currentStep, setCurrentStep] = useState(0);

  const steps: Step[] = [
    {
      icon: Sparkles,
      iconBg: "bg-gradient-to-br from-[#025791] to-[#1A7CC5]",
      title: "Bem-vindo ao Editor de PDF",
      subtitle: "Soares, Picon Sociedade de Advogados",
      content: (
        <div className="space-y-6">
          <p className="text-[#2d5a7b] text-base leading-relaxed">
            Uma ferramenta completa para manipulacao de documentos PDF,
            desenvolvida especialmente para o fluxo de trabalho juridico.
          </p>
          <div className="grid grid-cols-3 gap-3">
            {[
              { icon: Shield, label: "LGPD Compliance", desc: "Redacao segura de dados sensiveis" },
              { icon: Scale, label: "Pecas Juridicas", desc: "Deteccao automatica inteligente" },
              { icon: Zap, label: "Rapido e Seguro", desc: "Processamento local sem nuvem" },
            ].map((feat) => (
              <div key={feat.label} className="bg-[#EAF4FC] rounded-xl p-4 text-center">
                <div className="w-10 h-10 rounded-lg bg-[#025791] flex items-center justify-center mx-auto mb-2">
                  <feat.icon className="w-5 h-5 text-white" />
                </div>
                <div className="text-xs font-semibold text-[#003761]">{feat.label}</div>
                <div className="text-[10px] text-[#5c7d99] mt-0.5">{feat.desc}</div>
              </div>
            ))}
          </div>
        </div>
      ),
    },
    {
      icon: Upload,
      iconBg: "bg-gradient-to-br from-[#025791] to-[#5BA8D9]",
      title: "1. Carregue seus documentos",
      subtitle: "Arraste e solte ou clique para selecionar",
      content: (
        <div className="space-y-4">
          <div className="bg-[#EAF4FC] rounded-xl p-5 border-2 border-dashed border-[#A8D4F0]">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-[#025791] flex items-center justify-center shrink-0">
                <Upload className="w-6 h-6 text-white" />
              </div>
              <div>
                <p className="font-medium text-[#003761]">Arraste PDFs ou imagens para a area de upload</p>
                <p className="text-sm text-[#5c7d99] mt-1">
                  Suporta PDF, JPG, PNG e TIFF. Multiplos arquivos de uma vez.
                </p>
              </div>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="bg-white border border-gray-200 rounded-lg p-3">
              <FileText className="w-4 h-4 text-[#025791] mb-1" />
              <p className="font-medium text-[#003761]">1 PDF</p>
              <p className="text-xs text-[#5c7d99]">Acessa todas as ferramentas de edicao individual</p>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-3">
              <Merge className="w-4 h-4 text-[#025791] mb-1" />
              <p className="font-medium text-[#003761]">Multiplos PDFs</p>
              <p className="text-xs text-[#5c7d99]">Ativa a ferramenta de mesclagem com reordenacao</p>
            </div>
          </div>
        </div>
      ),
    },
    {
      icon: Scale,
      iconBg: "bg-gradient-to-br from-[#025791] to-[#1A7CC5]",
      title: "2. Analise - Pecas Juridicas",
      subtitle: "Deteccao automatica de pecas no PDF",
      content: (
        <div className="space-y-4">
          <p className="text-sm text-[#2d5a7b]">
            O sistema escaneia o documento e identifica automaticamente pecas juridicas
            como peticoes, sentencas, acordaos e recursos.
          </p>
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            <div className="px-4 py-2 bg-[#EAF4FC] border-b border-[#D4EAFA] text-xs font-semibold text-[#025791]">
              Pecas detectadas automaticamente
            </div>
            <div className="p-3 space-y-2">
              {["Peticao Inicial (Pags. 1-15)", "Contestacao (Pags. 16-32)", "Sentenca (Pags. 33-45)", "Recurso (Pags. 46-58)"].map((piece) => (
                <div key={piece} className="flex items-center gap-2 text-sm">
                  <div className="w-4 h-4 rounded border-2 border-[#025791] bg-[#025791] flex items-center justify-center">
                    <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>
                  </div>
                  <Scale className="w-3.5 h-3.5 text-[#025791]" />
                  <span className="text-[#003761]">{piece}</span>
                </div>
              ))}
            </div>
          </div>
          <p className="text-xs text-[#5c7d99]">
            Selecione as pecas desejadas e extraia como PDF individual ou ZIP.
          </p>
        </div>
      ),
    },
    {
      icon: EyeOff,
      iconBg: "bg-gradient-to-br from-[#DC2626] to-[#991B1B]",
      title: "3. Edicao - Redacao e Numeracao",
      subtitle: "Proteja dados sensiveis e organize documentos",
      content: (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-3">
            <div className="bg-white border border-gray-200 rounded-xl p-4">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-8 h-8 rounded-lg bg-red-100 flex items-center justify-center">
                  <EyeOff className="w-4 h-4 text-red-600" />
                </div>
                <div>
                  <p className="font-medium text-[#003761]">Redacao (Tarja Preta)</p>
                  <p className="text-xs text-[#5c7d99]">LGPD Compliance</p>
                </div>
              </div>
              <ul className="text-sm text-[#2d5a7b] space-y-1 ml-11">
                <li>Oculte CPF, CNPJ, e-mails e datas automaticamente</li>
                <li>Adicione palavras-chave personalizadas</li>
                <li>Redacao permanente — dados removidos de fato</li>
              </ul>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-4">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-8 h-8 rounded-lg bg-[#EAF4FC] flex items-center justify-center">
                  <Hash className="w-4 h-4 text-[#025791]" />
                </div>
                <div>
                  <p className="font-medium text-[#003761]">Numeracao Bates</p>
                  <p className="text-xs text-[#5c7d99]">Carimbo sequencial</p>
                </div>
              </div>
              <ul className="text-sm text-[#2d5a7b] space-y-1 ml-11">
                <li>Padrao configuravel: "Doc. 1 - Fls. 1"</li>
                <li>6 posicoes (topo/rodape x esq/centro/dir)</li>
                <li>Tamanho e fonte ajustaveis</li>
              </ul>
            </div>
          </div>
        </div>
      ),
    },
    {
      icon: Scissors,
      iconBg: "bg-gradient-to-br from-[#025791] to-[#5BA8D9]",
      title: "4. Transformar - Dividir, Extrair, Remover",
      subtitle: "Manipule paginas com precisao",
      content: (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            {[
              { icon: LayoutGrid, title: "Editor Visual", desc: "Veja miniaturas de cada pagina. Selecione, rotacione e reordene visualmente." },
              { icon: Scissors, title: "Dividir PDF", desc: "Por contagem de paginas, tamanho em MB, ou pelos marcadores do documento." },
              { icon: FileText, title: "Extrair / Remover", desc: "Informe intervalos (ex: 1-5, 10, 15-20) para extrair ou remover paginas." },
              { icon: Zap, title: "Otimizar", desc: "Comprima PDFs com 3 perfis. Edite metadados e proteja com senha AES-256." },
            ].map((item) => (
              <div key={item.title} className="bg-white border border-gray-200 rounded-xl p-4">
                <div className="w-8 h-8 rounded-lg bg-[#EAF4FC] flex items-center justify-center mb-2">
                  <item.icon className="w-4 h-4 text-[#025791]" />
                </div>
                <p className="font-medium text-sm text-[#003761]">{item.title}</p>
                <p className="text-xs text-[#5c7d99] mt-1">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      ),
    },
    {
      icon: Merge,
      iconBg: "bg-gradient-to-br from-[#025791] to-[#1A7CC5]",
      title: "5. Utilidades Extras",
      subtitle: "Mesclar, converter imagens e comparar versoes",
      content: (
        <div className="space-y-4">
          <div className="space-y-3">
            {[
              { icon: Merge, title: "Mesclar PDFs", desc: "Combine multiplos PDFs em um so. Reordene com setas antes de mesclar. Opcao de senha." },
              { icon: Image, title: "Imagens para PDF", desc: "Converta JPG, PNG ou TIFF em PDF. Arraste varias imagens para um documento unico." },
              { icon: GitCompare, title: "Comparar Versoes", desc: "Carregue dois PDFs e veja as diferencas textuais destacadas lado a lado." },
            ].map((item) => (
              <div key={item.title} className="flex items-start gap-3 bg-white border border-gray-200 rounded-xl p-4">
                <div className="w-8 h-8 rounded-lg bg-[#EAF4FC] flex items-center justify-center shrink-0">
                  <item.icon className="w-4 h-4 text-[#025791]" />
                </div>
                <div>
                  <p className="font-medium text-sm text-[#003761]">{item.title}</p>
                  <p className="text-xs text-[#5c7d99] mt-0.5">{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      ),
    },
    {
      icon: ArrowRight,
      iconBg: "bg-gradient-to-br from-[#10b981] to-[#059669]",
      title: "Pronto para comecar!",
      subtitle: "Tudo configurado",
      content: (
        <div className="space-y-6 text-center">
          <div className="w-20 h-20 mx-auto rounded-2xl bg-gradient-to-br from-[#10b981] to-[#059669] flex items-center justify-center shadow-lg">
            <svg className="w-10 h-10 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
          </div>
          <div>
            <p className="text-[#003761] font-medium text-base">
              Voce esta pronto para usar o Editor de PDF!
            </p>
            <p className="text-sm text-[#5c7d99] mt-2">
              Comece carregando um documento PDF na area de upload.
              A sidebar esquerda mostra todas as ferramentas disponiveis.
            </p>
          </div>
          <div className="bg-[#EAF4FC] rounded-xl p-4 text-left">
            <p className="text-xs font-semibold text-[#025791] mb-2">Dicas rapidas:</p>
            <ul className="text-xs text-[#2d5a7b] space-y-1.5">
              <li className="flex items-start gap-2">
                <span className="text-[#025791] font-bold mt-px">1.</span>
                Carregue 1 PDF para acessar todas as ferramentas de edicao
              </li>
              <li className="flex items-start gap-2">
                <span className="text-[#025791] font-bold mt-px">2.</span>
                Carregue multiplos PDFs para usar a ferramenta de mesclagem
              </li>
              <li className="flex items-start gap-2">
                <span className="text-[#025791] font-bold mt-px">3.</span>
                Imagens e Comparacao funcionam sem PDF carregado
              </li>
              <li className="flex items-start gap-2">
                <span className="text-[#025791] font-bold mt-px">4.</span>
                Use "Novo projeto" no topo para limpar e comecar do zero
              </li>
            </ul>
          </div>
        </div>
      ),
    },
  ];

  const step = steps[currentStep]!;
  const isLast = currentStep === steps.length - 1;
  const isFirst = currentStep === 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#022340]/70 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-xl overflow-hidden">
        {/* Header */}
        <div className="relative px-6 pt-6 pb-4">
          <button
            onClick={onComplete}
            className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 p-1 rounded-lg hover:bg-gray-100 transition-colors"
            title="Pular tutorial"
          >
            <X className="w-5 h-5" />
          </button>

          <div className="flex items-center gap-3 mb-3">
            <div className={`w-10 h-10 rounded-xl ${step.iconBg} flex items-center justify-center shadow-md`}>
              <step.icon className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-[#003761]">{step.title}</h2>
              <p className="text-xs text-[#5c7d99]">{step.subtitle}</p>
            </div>
          </div>

          {/* Progress dots */}
          <div className="flex gap-1.5">
            {steps.map((_, i) => (
              <div
                key={i}
                className={`h-1 rounded-full transition-all ${
                  i === currentStep
                    ? "bg-[#025791] w-6"
                    : i < currentStep
                      ? "bg-[#5BA8D9] w-3"
                      : "bg-gray-200 w-3"
                }`}
              />
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="px-6 pb-4 max-h-[50vh] overflow-y-auto">
          {step.content}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-100 flex items-center justify-between">
          <button
            onClick={() => setCurrentStep((s) => s - 1)}
            disabled={isFirst}
            className="flex items-center gap-1 text-sm text-[#5c7d99] hover:text-[#003761] disabled:invisible transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
            Anterior
          </button>

          <span className="text-xs text-[#5c7d99]">
            {currentStep + 1} de {steps.length}
          </span>

          {isLast ? (
            <button
              onClick={onComplete}
              className="flex items-center gap-1.5 px-5 py-2 bg-[#025791] text-white rounded-lg hover:bg-[#022340] transition-all font-medium text-sm shadow-sm"
            >
              Comecar
              <ArrowRight className="w-4 h-4" />
            </button>
          ) : (
            <button
              onClick={() => setCurrentStep((s) => s + 1)}
              className="flex items-center gap-1.5 px-4 py-2 bg-[#025791] text-white rounded-lg hover:bg-[#022340] transition-all font-medium text-sm shadow-sm"
            >
              Proximo
              <ChevronRight className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
