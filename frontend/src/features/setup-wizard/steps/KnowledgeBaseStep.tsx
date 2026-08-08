import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { FileText, Globe, Plus, Trash2, Upload } from "lucide-react";
import {
  useClearKnowledgeBase,
  useCrawlWebsite,
  useSaveKnowledgeBase,
  useUploadKnowledgeBaseDocument,
} from "../../../api/setup-wizard";
import { Button } from "../../../components/ui/Button";
import { Input } from "../../../components/ui/Input";
import { Textarea } from "../../../components/ui/Textarea";
import { getDomain, getErrorMessage } from "../../../lib/utils";
import { BulkImportModal } from "../../knowledge-base/BulkImportModal";
import { StepCard } from "../StepCard";
import { StepFooter } from "../StepFooter";
import type { StepComponentProps } from "../types";

export function KnowledgeBaseStep({ orgId, setupState, onBack, onNext }: StepComponentProps) {
  const kb = setupState.knowledge_base;
  const [name, setName] = useState(kb?.name ?? "General FAQ");
  const [chunks, setChunks] = useState<string[]>(kb?.chunks.map((c) => c.content) ?? [""]);
  const [crawlUrl, setCrawlUrl] = useState("");
  const [isImportOpen, setIsImportOpen] = useState(false);
  const queryClient = useQueryClient();

  const saveKnowledgeBase = useSaveKnowledgeBase(orgId);
  const crawlWebsite = useCrawlWebsite(orgId);
  const uploadDoc = useUploadKnowledgeBaseDocument(orgId);
  const clearKb = useClearKnowledgeBase(orgId);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [confirmingClear, setConfirmingClear] = useState(false);

  const handleFileSelected = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    // Reset so selecting the same file again still fires onChange.
    e.target.value = "";
    if (file) uploadDoc.mutate(file);
  };

  const handleClearAll = () => {
    clearKb.mutate(undefined, {
      onSuccess: () => {
        setChunks([""]);
        setConfirmingClear(false);
      },
    });
  };

  // Re-sync the editable fields whenever the underlying setup state changes —
  // in particular after a website crawl invalidates and refetches it, so the
  // manual chunk list below picks up the newly-created chunks.
  useEffect(() => {
    if (setupState.knowledge_base) {
      setName(setupState.knowledge_base.name);
      setChunks(setupState.knowledge_base.chunks.map((c) => c.content));
    }
  }, [setupState.knowledge_base]);

  const handleCrawl = () => {
    const trimmedUrl = crawlUrl.trim();
    if (!trimmedUrl) return;
    crawlWebsite.mutate({ url: trimmedUrl });
  };

  const updateChunk = (index: number, content: string) =>
    setChunks((prev) => prev.map((c, i) => (i === index ? content : c)));

  const removeChunk = (index: number) => setChunks((prev) => prev.filter((_, i) => i !== index));

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const nonEmptyChunks = chunks.map((c) => c.trim()).filter(Boolean);
    saveKnowledgeBase.mutate(
      { name, chunks: nonEmptyChunks.map((content) => ({ content })) },
      { onSuccess: onNext },
    );
  };

  return (
    <StepCard
      title="Knowledge Base"
      description="Add the FAQs and information the AI should use to answer customer questions."
    >
      <div className="mb-6 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50 p-4">
        <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Import from Website</h4>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Crawl the business's website to automatically build the knowledge base.
        </p>

        <div className="mt-3 flex gap-2">
          <Input
            value={crawlUrl}
            onChange={(e) => setCrawlUrl(e.target.value)}
            placeholder="https://example.com"
            className="flex-1"
            disabled={crawlWebsite.isPending}
          />
          <Button
            type="button"
            variant="secondary"
            onClick={handleCrawl}
            isLoading={crawlWebsite.isPending}
            disabled={!crawlUrl.trim()}
          >
            <Globe className="h-4 w-4" />
            Crawl Website
          </Button>
        </div>

        {crawlWebsite.isPending && (
          <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">Crawling website... this may take up to 60 seconds.</p>
        )}

        {crawlWebsite.isSuccess &&
          (crawlWebsite.data.replaced_chunks > 0 ? (
            <p className="mt-3 rounded-md bg-emerald-50 dark:bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-300">
              Replaced {crawlWebsite.data.replaced_chunks} existing chunk
              {crawlWebsite.data.replaced_chunks === 1 ? "" : "s"} with {crawlWebsite.data.chunks_created} new chunk
              {crawlWebsite.data.chunks_created === 1 ? "" : "s"} from{" "}
              {getDomain(crawlWebsite.variables?.url ?? crawlUrl)}.
            </p>
          ) : (
            <p className="mt-3 rounded-md bg-emerald-50 dark:bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-300">
              Crawled {crawlWebsite.data.pages_crawled} page{crawlWebsite.data.pages_crawled === 1 ? "" : "s"},
              created {crawlWebsite.data.chunks_created} knowledge chunk
              {crawlWebsite.data.chunks_created === 1 ? "" : "s"}.
            </p>
          ))}

        {crawlWebsite.isError && (
          <p className="mt-3 rounded-md bg-red-50 dark:bg-red-500/10 px-3 py-2 text-sm text-red-600 dark:text-red-400">
            {getErrorMessage(crawlWebsite.error)}
          </p>
        )}
      </div>

      <div className="mb-6 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50 p-4">
        <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Upload a document</h4>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Upload a PDF, Word (DOCX), or text file — we'll extract the text and add it to the knowledge base.
        </p>

        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt,.md,.markdown"
          className="hidden"
          onChange={handleFileSelected}
        />
        <div className="mt-3">
          <Button
            type="button"
            variant="secondary"
            onClick={() => fileInputRef.current?.click()}
            isLoading={uploadDoc.isPending}
          >
            <FileText className="h-4 w-4" />
            Choose file
          </Button>
        </div>

        {uploadDoc.isPending && (
          <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">Reading document and building chunks…</p>
        )}

        {uploadDoc.isSuccess &&
          (uploadDoc.data.chunks_created > 0 ? (
            <p className="mt-3 rounded-md bg-emerald-50 dark:bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-300">
              Added {uploadDoc.data.chunks_created} chunk{uploadDoc.data.chunks_created === 1 ? "" : "s"} from{" "}
              {uploadDoc.data.filename}.
            </p>
          ) : (
            <p className="mt-3 rounded-md bg-amber-50 dark:bg-amber-500/10 px-3 py-2 text-sm text-amber-700 dark:text-amber-300">
              {uploadDoc.data.errors[0] ?? "No text could be extracted from that file."}
            </p>
          ))}

        {uploadDoc.isError && (
          <p className="mt-3 rounded-md bg-red-50 dark:bg-red-500/10 px-3 py-2 text-sm text-red-600 dark:text-red-400">
            {getErrorMessage(uploadDoc.error)}
          </p>
        )}
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <Input label="Knowledge base name" value={name} onChange={(e) => setName(e.target.value)} required />

        <div className="flex items-center justify-between">
          <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
            {chunks.filter((c) => c.trim()).length} chunk{chunks.filter((c) => c.trim()).length === 1 ? "" : "s"}
          </p>
          <div className="flex items-center gap-1">
            <Button type="button" variant="ghost" size="sm" onClick={() => setIsImportOpen(true)}>
              <Upload className="h-4 w-4" />
              Bulk import
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setConfirmingClear(true)}
              className="text-red-600 hover:bg-red-50 dark:hover:bg-red-500/10"
            >
              <Trash2 className="h-4 w-4" />
              Clear all
            </Button>
          </div>
        </div>

        {confirmingClear && (
          <div className="rounded-lg border border-red-200 dark:border-red-500/30 bg-red-50 dark:bg-red-500/10 p-4">
            <p className="text-sm text-red-700 dark:text-red-300">
              Delete <span className="font-semibold">all</span> knowledge chunks for this organization (manual,
              crawled, and uploaded)? This can't be undone.
            </p>
            <div className="mt-3 flex gap-2">
              <Button type="button" variant="danger" size="sm" onClick={handleClearAll} isLoading={clearKb.isPending}>
                Yes, clear knowledge base
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setConfirmingClear(false)}
                disabled={clearKb.isPending}
              >
                Cancel
              </Button>
            </div>
            {clearKb.isSuccess && (
              <p className="mt-2 text-sm text-red-700 dark:text-red-300">
                Deleted {clearKb.data.chunks_deleted} chunk{clearKb.data.chunks_deleted === 1 ? "" : "s"}.
              </p>
            )}
            {clearKb.isError && (
              <p className="mt-2 text-sm text-red-600 dark:text-red-400">{getErrorMessage(clearKb.error)}</p>
            )}
          </div>
        )}

        <div className="space-y-3">
          {chunks.map((content, index) => (
            <div key={index} className="flex gap-2">
              <Textarea
                value={content}
                onChange={(e) => updateChunk(index, e.target.value)}
                placeholder="e.g. We are open Monday to Friday, 9am to 5pm."
                rows={3}
                className="flex-1"
              />
              <button
                type="button"
                onClick={() => removeChunk(index)}
                className="mt-1 h-fit rounded-lg p-2 text-slate-400 dark:text-slate-500 hover:bg-red-50 hover:text-red-600"
                aria-label="Remove chunk"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>

        <Button type="button" variant="secondary" size="sm" onClick={() => setChunks((prev) => [...prev, ""])}>
          <Plus className="h-4 w-4" />
          Add Chunk
        </Button>

        <StepFooter onBack={onBack} isSaving={saveKnowledgeBase.isPending} />
      </form>

      <BulkImportModal
        isOpen={isImportOpen}
        onClose={() => setIsImportOpen(false)}
        orgId={orgId}
        onImported={() => {
          // Force a refetch of setup state so the freshly-imported chunks
          // show up in the manual editor below the import button.
          queryClient.invalidateQueries({ queryKey: ["setup-wizard", orgId] });
        }}
      />
    </StepCard>
  );
}
