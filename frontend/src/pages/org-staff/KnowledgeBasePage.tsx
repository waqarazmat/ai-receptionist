import { useMemo, useState } from "react";
import { BookOpen, Plus } from "lucide-react";
import { motion } from "framer-motion";
import { useAddChunk, useDeleteChunk, useOrgKnowledgeBase } from "../../api/knowledge-base";
import { EmptyState } from "../../components/shared/EmptyState";
import { SearchInput } from "../../components/shared/SearchInput";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Modal } from "../../components/ui/Modal";
import { Skeleton } from "../../components/ui/Skeleton";
import { Textarea } from "../../components/ui/Textarea";
import { ChunkRow } from "../../features/knowledge-base/ChunkRow";
import { itemFadeUp, staggerContainer } from "../../lib/motion";
import { formatDateTime } from "../../lib/utils";
import type { KnowledgeChunk } from "../../types/knowledge-base";

export default function KnowledgeBasePage() {
  const { data, isLoading } = useOrgKnowledgeBase();
  const addChunk = useAddChunk();
  const deleteChunk = useDeleteChunk();

  const [search, setSearch] = useState("");
  const [isAdding, setIsAdding] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newContent, setNewContent] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<KnowledgeChunk | null>(null);

  const chunks = data?.chunks ?? [];

  const filteredChunks = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return chunks;
    return chunks.filter(
      (chunk) => chunk.content.toLowerCase().includes(query) || chunk.title?.toLowerCase().includes(query),
    );
  }, [chunks, search]);

  const lastUpdated = useMemo(
    () =>
      chunks.reduce<string | null>((latest, chunk) => {
        if (!latest || chunk.updated_at > latest) return chunk.updated_at;
        return latest;
      }, null),
    [chunks],
  );

  const handleAdd = () => {
    if (!newContent.trim()) return;
    addChunk.mutate(
      { title: newTitle.trim() || null, content: newContent.trim() },
      {
        onSuccess: () => {
          setNewTitle("");
          setNewContent("");
          setIsAdding(false);
        },
      },
    );
  };

  const handleConfirmDelete = () => {
    if (!deleteTarget) return;
    deleteChunk.mutate(deleteTarget.id, { onSuccess: () => setDeleteTarget(null) });
  };

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">Knowledge Base</h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {chunks.length} chunk{chunks.length === 1 ? "" : "s"}
            {lastUpdated && <> · last updated {formatDateTime(lastUpdated)}</>}
          </p>
        </div>
        <Button type="button" onClick={() => setIsAdding((prev) => !prev)}>
          <Plus className="h-4 w-4" />
          Add Chunk
        </Button>
      </div>

      {isAdding && (
        <div className="mt-4 space-y-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50 p-4">
          <Input label="Title (optional)" value={newTitle} onChange={(e) => setNewTitle(e.target.value)} />
          <Textarea
            label="Content"
            value={newContent}
            onChange={(e) => setNewContent(e.target.value)}
            placeholder="e.g. We are open Monday to Friday, 9am to 5pm."
            rows={4}
          />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" size="sm" onClick={() => setIsAdding(false)}>
              Cancel
            </Button>
            <Button type="button" size="sm" isLoading={addChunk.isPending} onClick={handleAdd} disabled={!newContent.trim()}>
              Save Chunk
            </Button>
          </div>
        </div>
      )}

      <div className="mt-4 max-w-sm">
        <SearchInput value={search} onChange={setSearch} placeholder="Search chunks…" />
      </div>

      <div className="mt-4 space-y-3">
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-20 w-full rounded-xl" />
            ))}
          </div>
        ) : filteredChunks.length === 0 ? (
          <EmptyState
            icon={<BookOpen className="h-10 w-10" />}
            title="No knowledge chunks"
            description={search ? "Try a different search." : "Add a chunk to start building the knowledge base."}
          />
        ) : (
          <motion.div className="space-y-3" variants={staggerContainer(0.03)} initial="hidden" animate="show">
            {filteredChunks.map((chunk) => (
              <motion.div key={chunk.id} variants={itemFadeUp}>
                <ChunkRow chunk={chunk} onDelete={setDeleteTarget} />
              </motion.div>
            ))}
          </motion.div>
        )}
      </div>

      <Modal isOpen={Boolean(deleteTarget)} onClose={() => setDeleteTarget(null)} title="Delete chunk?">
        <p className="text-sm text-slate-600 dark:text-slate-300">
          This will permanently remove this chunk from the knowledge base. This can't be undone.
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={() => setDeleteTarget(null)}>
            Cancel
          </Button>
          <Button type="button" variant="danger" isLoading={deleteChunk.isPending} onClick={handleConfirmDelete}>
            Delete
          </Button>
        </div>
      </Modal>
    </div>
  );
}
