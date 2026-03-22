-- Supabase migration: 建立 experiments 表（autoresearch 實驗結果）
-- 執行方式：在 Supabase Dashboard → SQL Editor 貼上執行

CREATE TABLE IF NOT EXISTS experiments (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  name TEXT NOT NULL,
  model_config_summary TEXT,
  val_bpb DOUBLE PRECISION,
  train_loss DOUBLE PRECISION,
  steps INTEGER,
  duration_seconds DOUBLE PRECISION,
  notes TEXT,
  colab_url TEXT,
  kept BOOLEAN,
  submitted_at TIMESTAMPTZ DEFAULT NOW()
);

-- 建立索引加速查詢
CREATE INDEX IF NOT EXISTS idx_experiments_submitted_at ON experiments (submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_experiments_val_bpb ON experiments (val_bpb) WHERE val_bpb IS NOT NULL;

-- 啟用 RLS（Row Level Security）
ALTER TABLE experiments ENABLE ROW LEVEL SECURITY;

-- 允許所有使用者讀取和寫入（開發階段）
CREATE POLICY "Allow all access to experiments"
  ON experiments FOR ALL
  USING (true)
  WITH CHECK (true);
