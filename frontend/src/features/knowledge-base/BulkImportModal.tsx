import { useEffect, useRef, useState } from "react";
import { AxiosError } from "axios";
import { FileText, Upload, Check, AlertCircle } from "lucide-react";
import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";
import { useBulkImportKnowledge, type BulkImportInput } from "../../api/kb-import";

export interface BulkImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  orgId: string;
  onImported?: (chunksCreated: number) => void;
}

type Format = "csv" | "markdown" | "text";

const FORMATS: { key: Format; label: string; hint: string; accept: string }[] = [
  {
    key: "csv",
    label: "CSV",
    hint: "Rows of `content` or `title,content`",
    accept: ".csv,text/csv",
  },
  {
    key: "markdown",
    label: "Markdown",
    hint: "Chunks split on H1/H2 headings",
    accept: ".md,.markdown,text/markdown",
  },
  {
    key: "text",
    label: "Plain text / paste",
    hint: "Whole payload becomes one chunk",
    accept: ".txt,text/plain",
  },
];

export function BulkImportModal({
  isOpen,
  onClose,
  orgId,
  onImported,
}: BulkImportModalProps) {
  const [format, setFormat] = useState<Format>("csv");
  const [content, setContent] = useState<string>("");
  const [filename, setFilename] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const importMutation = useBulkImportKnowledge(orgId);

  useEffect(() => {
    if (isOpen) {
      setFormat("csv");
      setContent("");
      setFilename(null);
      setErrorMessage(null);
      importMutation.reset();
    }
  }, [isOpen]);

  const handleFilePicked = async (file: File) => {
    // Client-side read so the server never sees the raw file — just the
    // extracted text. Keeps the backend deps light (no pypdf, no python-docx).
    setErrorMessage(null);
    setFilename(file.name);
    // Auto-detect format from extension if the user hasn't already picked.
    const ext = file.name.split(".").pop()?.toLowerCase();
    if (ext === "md" || ext === "markdown") setFormat("markdown");
    else if (ext === "csv") setFormat("csv");
    else if (ext === "txt") setFormat("text");

    try {
      const text = await file.text();
      setContent(text);
    } catch {
      setErrorMessage("Could not read the file. Try pasting the content directly instead.");
    }
  };

  const handleSubmit = () => {
    setErrorMessage(null);
    if (!content.trim()) {
      setErrorMessage("Add some content or upload a file to import.");
      return;
    }
    const payload: BulkImportInput = { format, content };
    importMutation.mutate(payload, {
      onSuccess: (data) => {
        onImported?.(data.chunks_created);
      },
      onError: (err) => {
        if (err instanceof AxiosError) {
          const detail = (err.response?.data as { detail?: string } | undefined)?.detail;
          setErrorMessage(detail ?? "Import failed. Please try again.");
        } else {
          setErrorMessage("Import failed. Please try again.");
        }
      },
    });
  };

  const success = importMutation.isSuccess && importMutation.data;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Bulk import knowledge base">
      {success ? (
        <div className="space-y-4">
          <div className="flex items-start gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4 dark:border-emerald-500/30 dark:bg-emerald-500/10">
            <Check className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600 dark:text-emerald-400" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-emerald-800 dark:text-emerald-200">
                Imported {importMutation.data.chunks_created} chunk
                {importMutation.data.chunks_created === 1 ? "" : "s"}
              </p>
              <p className="mt-1 text-xs text-emerald-700 dark:text-emerald-300">
                Into knowledge base: {importMutation.data.knowledge_base_name}
              </p>
              {importMutation.data.errors.length > 0 && (
                <ul className="mt-2 space-y-1 text-xs text-emerald-700 dark:text-emerald-300">
                  {importMutation.data.errors.map((e, i) => (
                    <li key={i}>• {e}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={onClose}>
              Done
            </Button>
            <Button
              onClick={() => {
                importMutation.reset();
                setContent("");
                setFilename(null);
              }}
            >
              Import more
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Format picker as a segmented control */}
          <div>
            <p className="mb-2 text-sm font-medium text-slate-700 dark:text-slate-300">
              Import format
            </p>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              {FORMATS.map((f) => {
                const isActive = f.key === format;
                return (
                  <button
                    key={f.key}
                    type="button"
                    onClick={() => setFormat(f.key)}
                    className={`rounded-lg border p-3 text-left transition-colors ${
                      isActive
                        ? "border-indigo-500 bg-indigo-50 dark:border-indigo-400 dark:bg-indigo-500/10"
                        : "border-slate-200 bg-white hover:border-slate-300 dark:border-slate-700 dark:bg-slate-800 dark:hover:border-slate-600"
                    }`}
                  >
                    <p
                      className={`text-sm font-semibold ${
                        isActive
                          ? "text-indigo-700 dark:text-indigo-300"
                          : "text-slate-900 dark:text-slate-100"
                      }`}
                    >
                      {f.label}
                    </p>
                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                      {f.hint}
                    </p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* File picker + drop hint */}
          <div>
            <input
              ref={fileInputRef}
              type="file"
              accept={FORMATS.find((f) => f.key === format)?.accept}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleFilePicked(file);
              }}
              className="hidden"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="flex w-full items-center gap-3 rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-600 transition-colors hover:border-indigo-400 hover:bg-indigo-50/30 dark:border-slate-700 dark:bg-slate-800/50 dark:text-slate-300 dark:hover:border-indigo-500 dark:hover:bg-indigo-500/5"
            >
              {filename ? (
                <>
                  <FileText className="h-5 w-5 text-indigo-500" />
                  <span className="flex-1 truncate font-medium text-slate-900 dark:text-slate-100">
                    {filename}
                  </span>
                  <span className="text-xs text-slate-500 dark:text-slate-400">
                    click to change
                  </span>
                </>
              ) : (
                <>
                  <Upload className="h-5 w-5" />
                  <span className="flex-1">
                    Click to upload a file, or paste content below
                  </span>
                </>
              )}
            </button>
          </div>

          {/* Content editor */}
          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
              Content
            </label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder={
                format === "csv"
                  ? "title,content\nOur hours,Monday–Friday 9–5\nParking,Free street parking out front"
                  : format === "markdown"
                  ? "## Our hours\nMonday–Friday 9–5.\n\n## Parking\nFree street parking out front."
                  : "Paste any block of text here — it will be stored as a single chunk."
              }
              rows={10}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 font-mono text-xs text-slate-900 shadow-sm transition-shadow focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:focus:ring-offset-slate-900"
            />
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              {content.length.toLocaleString()} characters
            </p>
          </div>

          {errorMessage && (
            <div className="flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-300">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <p>{errorMessage}</p>
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} isLoading={importMutation.isPending}>
              <Upload className="h-4 w-4" />
              Import {content.trim() ? `(${content.length.toLocaleString()} chars)` : ""}
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
