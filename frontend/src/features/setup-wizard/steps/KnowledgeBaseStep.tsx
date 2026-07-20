import { useEffect, useState, type FormEvent } from "react";
import { Globe, Plus, Trash2, Upload } from "lucide-react";
import { useCrawlWebsite, useSaveKnowledgeBase } from "../../../api/setup-wizard";
import { Button } from "../../../components/ui/Button";
import { Input } from "../../../components/ui/Input";
import { Textarea } from "../../../components/ui/Textarea";
import { getDomain, getErrorMessage } from "../../../lib/utils";
import { StepCard } from "../StepCard";
import { StepFooter } from "../StepFooter";
import type { StepComponentProps } from "../types";

export function KnowledgeBaseStep({ orgId, setupState, onBack, onNext }: StepComponentProps) {
  const kb = setupState.knowledge_base;
  const [name, setName] = useState(kb?.name ?? "General FAQ");
  const [chunks, setChunks] = useState<string[]>(kb?.chunks.map((c) => c.content) ?? [""]);
  const [crawlUrl, setCrawlUrl] = useState("");

  const saveKnowledgeBase = useSaveKnowledgeBase(orgId);
  const crawlWebsite = useCrawlWebsite(orgId);

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

      <form onSubmit={handleSubmit} className="space-y-4">
        <Input label="Knowledge base name" value={name} onChange={(e) => setName(e.target.value)} required />

        <div className="flex items-center justify-between">
          <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
            {chunks.filter((c) => c.trim()).length} chunk{chunks.filter((c) => c.trim()).length === 1 ? "" : "s"}
          </p>
          <Button type="button" variant="ghost" size="sm" title="Coming soon">
            <Upload className="h-4 w-4" />
            Bulk Import
          </Button>
        </div>

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
    </StepCard>
  );
}
