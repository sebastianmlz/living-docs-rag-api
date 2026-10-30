-- Un documento = un archivo .md del corpus. Nunca se borra: si desaparece del origen queda con deleted_at (tombstone).
CREATE TABLE documents (
    id           bigserial PRIMARY KEY,
    source       text        NOT NULL,                 -- de qué corpus viene ('fastapi-docs')
    path         text        NOT NULL,                 -- ruta relativa dentro del corpus
    title        text        NOT NULL,
    url          text        NOT NULL,                 -- página publicada, para citar
    content_hash text        NOT NULL,                 -- sha256 del markdown ya resuelto: detecta cambios
    version      integer     NOT NULL DEFAULT 1,       -- sube cada vez que cambia el contenido
    ingested_at  timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    deleted_at   timestamptz,
    UNIQUE (source, path)
);

-- Un chunk = un fragmento de un documento según una estrategia de chunking.
-- Las estrategias conviven en la misma tabla para poder compararlas con evals.
CREATE TABLE chunks (
    id           bigserial PRIMARY KEY,
    document_id  bigint  NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    strategy     text    NOT NULL,                     -- 'recursive' | 'markdown'
    ordinal      integer NOT NULL,                     -- posición dentro del documento
    heading_path text[]  NOT NULL DEFAULT '{}',        -- ['Query Parameters', 'Defaults']
    anchor       text,                                 -- '#defaults' para citar la sección exacta
    content      text    NOT NULL,
    token_count  integer NOT NULL,
    chunk_hash   text    NOT NULL,                     -- sha256 del texto que se embebe: permite reutilizar vectores
    -- Columna generada: Postgres mantiene el índice léxico solo, sin código en la app.
    tsv          tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    UNIQUE (document_id, strategy, ordinal)
);

CREATE INDEX chunks_strategy_idx ON chunks (strategy);
CREATE INDEX chunks_hash_idx ON chunks (chunk_hash);
CREATE INDEX chunks_tsv_idx ON chunks USING gin (tsv);

-- Los vectores van en tabla aparte, una fila por (chunk, modelo): así se pueden comparar modelos de embeddings
-- sobre los mismos chunks. La columna no fija dimensión porque cada modelo tiene la suya.
CREATE TABLE chunk_embeddings (
    chunk_id  bigint NOT NULL REFERENCES chunks (id) ON DELETE CASCADE,
    model     text   NOT NULL,
    embedding vector NOT NULL,
    PRIMARY KEY (chunk_id, model)
);

-- HNSW necesita una dimensión fija: un índice parcial por modelo, sobre la columna casteada.
-- Las consultas deben usar el mismo cast y el mismo filtro de modelo para que Postgres use el índice.
CREATE INDEX chunk_embeddings_gemma300m_hnsw ON chunk_embeddings
    USING hnsw ((embedding::vector(768)) vector_cosine_ops)
    WHERE model = 'google/embeddinggemma-300m';
