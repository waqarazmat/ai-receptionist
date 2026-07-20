import { useState } from "react";
import { Pencil, Trash2 } from "lucide-react";
import { useUpdateChunk } from "../../api/knowledge-base";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Textarea } from "../../components/ui/Textarea";
import { formatDateTime } from "../../lib/utils";
import type { KnowledgeChunk } from "../../types/knowledge-base";

export interface ChunkRowProps {
  chunk: KnowledgeChunk;
  onDelete: (chunk: KnowledgeChunk) => void;
}

export function ChunkRow({ chunk, onDelete }: ChunkRowProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [title, setTitle] = useState(chunk.title ?? "");
  const [content, setContent] = useState(chunk.content);
  const updateChunk = useUpdateChunk();

  const handleSave = () => {
    if (!content.trim()) return;
    updateChunk.mutate(
      { id: chunk.id, data: { title: title.trim() || null, content: content.trim() } },
      { onSuccess: () => setIsEditing(false) },
    );
  };

  const handleCancel = () => {
    setTitle(chunk.title ?? "");
    setContent(chunk.content);
    setIsEditing(false);
  };

  if (isEditing) {
    return (
      <div className="space-y-3 rounded-lg border border-indigo-200 dark:border-indigo-500/30 bg-indigo-50/40 p-4">
        <Input label="Title (optional)" value={title} onChange={(e) => setTitle(e.target.value)} />
        <Textarea label="Content" value={content} onChange={(e) => setContent(e.target.value)} rows={4} />
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" size="sm" onClick={handleCancel}>
            Cancel
          </Button>
          <Button type="button" size="sm" isLoading={updateChunk.isPending} onClick={handleSave} disabled={!content.trim()}>
            Save
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-800 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          {chunk.title && <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{chunk.title}</p>}
          <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700 dark:text-slate-200">{chunk.content}</p>
          <p className="mt-2 text-xs text-slate-400 dark:text-slate-500">
            Updated {formatDateTime(chunk.updated_at)}
            {chunk.source_url && (
              <>
                {" · "}
                <a
                  href={chunk.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-indigo-600 hover:underline"
                >
                  Source
                </a>
              </>
            )}
          </p>
        </div>
        <div className="flex shrink-0 gap-1">
          <button
            type="button"
            onClick={() => setIsEditing(true)}
            className="rounded-lg p-2 text-slate-400 dark:text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-600"
            aria-label="Edit chunk"
          >
            <Pencil className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => onDelete(chunk)}
            className="rounded-lg p-2 text-slate-400 dark:text-slate-500 hover:bg-red-50 hover:text-red-600"
            aria-label="Delete chunk"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
