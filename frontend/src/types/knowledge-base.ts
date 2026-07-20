export interface KnowledgeChunk {
  id: string;
  knowledge_base_id: string;
  title: string | null;
  content: string;
  source_url: string | null;
  updated_at: string;
}

export interface OrgKnowledgeBase {
  knowledge_base_id: string | null;
  knowledge_base_name: string | null;
  chunks: KnowledgeChunk[];
}

export interface ChunkInput {
  title?: string | null;
  content: string;
}
