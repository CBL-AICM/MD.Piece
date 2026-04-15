import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts'

const COLORS = {
  emotion: '#6ea8ff',
  symptom: '#ff6b81',
  adherence: '#3ddc97',
}

const LABELS = {
  emotion: '情緒分數',
  symptom: '症狀嚴重度',
  adherence: '服藥順從率 %',
}

export default function TrendChart({ data, lines = ['emotion', 'symptom', 'adherence'], height = 320 }) {
  return (
    <div style={{ width: '100%', height }}>
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 16, left: -8, bottom: 0 }}>
          <CartesianGrid stroke="#1e2a3a" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="date"
            stroke="#5a6572"
            tick={{ fill: '#8b97a6', fontSize: 12 }}
            tickLine={false}
            axisLine={{ stroke: '#1e2a3a' }}
          />
          <YAxis
            stroke="#5a6572"
            tick={{ fill: '#8b97a6', fontSize: 12 }}
            tickLine={false}
            axisLine={{ stroke: '#1e2a3a' }}
            domain={[0, 100]}
          />
          <Tooltip
            contentStyle={{
              background: '#121822',
              border: '1px solid #2a3a50',
              borderRadius: 10,
              color: '#e6edf3',
              fontSize: 13,
            }}
            labelStyle={{ color: '#8b97a6', marginBottom: 4 }}
          />
          <Legend
            iconType="circle"
            wrapperStyle={{ fontSize: 13, color: '#8b97a6', paddingTop: 8 }}
          />
          {lines.map((k) => (
            <Line
              key={k}
              type="monotone"
              dataKey={k}
              name={LABELS[k] ?? k}
              stroke={COLORS[k] ?? '#9a7bff'}
              strokeWidth={2}
              dot={{ r: 2.5, strokeWidth: 0, fill: COLORS[k] }}
              activeDot={{ r: 5, strokeWidth: 2, stroke: '#0a0e13' }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
