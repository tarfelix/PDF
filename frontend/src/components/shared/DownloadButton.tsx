import { Download } from "lucide-react";
import { downloadUrl } from "@/api/client";

interface Props {
  fileId: string;
  filename: string;
  className?: string;
}

export function DownloadButton({ fileId, filename, className }: Props) {
  return (
    <a
      href={downloadUrl(fileId)}
      download={filename}
      className={`inline-flex items-center gap-2 px-5 py-2.5 bg-[#025791] text-white rounded-lg hover:bg-[#022340] transition-all font-medium text-sm shadow-sm hover:shadow-md ${className ?? ""}`}
    >
      <Download className="w-4 h-4" />
      Baixar {filename}
    </a>
  );
}
