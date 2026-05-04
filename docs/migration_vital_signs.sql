-- Supabase migration: 建立 vital_signs 表（患者生理紀錄）
-- 患者端記錄體重、血壓、血糖、心率... 等都同步到此表，
-- 醫師端再依 patient_id 撈出來畫摺線圖。
-- 執行方式：在 Supabase Dashboard → SQL Editor 貼上執行

CREATE TABLE IF NOT EXISTS vital_signs (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  patient_id UUID NOT NULL,
  metric_id TEXT NOT NULL,        -- weight / bp / glucose / heart / temp / spo2 / waist / height / bmi / custom-xxx
  metric_name TEXT NOT NULL,      -- 顯示名稱（中文，例：「血壓」）
  unit TEXT,                      -- mmHg / mg/dL / kg ...
  value DOUBLE PRECISION NOT NULL,
  value2 DOUBLE PRECISION,        -- 雙值（如血壓的舒張壓）
  notes TEXT,
  recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 加速依患者 + 指標 + 時間查詢（畫摺線圖時最常用）
CREATE INDEX IF NOT EXISTS idx_vital_signs_patient_metric_time
  ON vital_signs (patient_id, metric_id, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_vital_signs_patient_time
  ON vital_signs (patient_id, recorded_at DESC);

-- RLS（開發階段先全開；正式上線後再用 auth.uid() 收斂）
ALTER TABLE vital_signs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all access to vital_signs"
  ON vital_signs FOR ALL
  USING (true)
  WITH CHECK (true);
