import { create } from "zustand";
import type { UploadResult, ScanPiece } from "@/api/client";

export type Tool =
  | "legal"
  | "bates"
  | "redact"
  | "visual"
  | "remove"
  | "extract"
  | "split"
  | "optimize"
  | "merge"
  | "converter"
  | "diff";

interface PdfState {
  // Uploaded files
  files: UploadResult[];
  activeTool: Tool;
  loading: boolean;
  error: string | null;
  resultFileId: string | null;
  resultFilename: string | null;

  // Legal scan results
  scanPieces: ScanPiece[];

  // Actions
  setFiles: (files: UploadResult[]) => void;
  addFiles: (files: UploadResult[]) => void;
  clearFiles: () => void;
  setActiveTool: (tool: Tool) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setResult: (fileId: string | null, filename: string | null) => void;
  setScanPieces: (pieces: ScanPiece[]) => void;
  reset: () => void;
}

const initialState = {
  files: [],
  activeTool: "legal" as Tool,
  loading: false,
  error: null,
  resultFileId: null,
  resultFilename: null,
  scanPieces: [],
};

export const usePdfStore = create<PdfState>((set) => ({
  ...initialState,

  setFiles: (files) => set({ files, resultFileId: null, resultFilename: null, error: null }),
  addFiles: (files) => set((s) => ({ files: [...s.files, ...files] })),
  clearFiles: () => set({ ...initialState }),
  setActiveTool: (activeTool) => set({ activeTool, resultFileId: null, resultFilename: null, error: null }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error, loading: false }),
  setResult: (resultFileId, resultFilename) => set({ resultFileId, resultFilename, loading: false, error: null }),
  setScanPieces: (scanPieces) => set({ scanPieces }),
  reset: () => set({ ...initialState }),
}));
