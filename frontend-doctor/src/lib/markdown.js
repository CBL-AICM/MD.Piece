// 極簡 Markdown → HTML（不引入 react-markdown）
// 支援：# / ## / ### 標題、**bold**、*italic*、- 列表、---、空行段落
// 安全：先 escape HTML，再做標記替換，避免 XSS
export function renderMarkdown(md) {
  if (!md) return ''
  const escaped = md
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  const lines = escaped.split('\n')
  const out = []
  let inList = false
  for (const raw of lines) {
    let line = raw
    const isList = /^\s*[-*]\s+/.test(line)
    if (isList && !inList) { out.push('<ul>'); inList = true }
    if (!isList && inList) { out.push('</ul>'); inList = false }

    if (/^---+\s*$/.test(line)) { out.push('<hr/>'); continue }
    if (/^###\s+/.test(line)) { out.push('<h3>' + inline(line.replace(/^###\s+/, '')) + '</h3>'); continue }
    if (/^##\s+/.test(line))  { out.push('<h2>' + inline(line.replace(/^##\s+/, '')) + '</h2>'); continue }
    if (/^#\s+/.test(line))   { out.push('<h1>' + inline(line.replace(/^#\s+/, '')) + '</h1>'); continue }
    if (isList) {
      out.push('<li>' + inline(line.replace(/^\s*[-*]\s+/, '')) + '</li>')
      continue
    }
    if (line.trim() === '') { out.push(''); continue }
    out.push('<p>' + inline(line) + '</p>')
  }
  if (inList) out.push('</ul>')
  // 連續空段壓成單一段落分隔
  return out.join('\n').replace(/(<\/p>)\n+(?=<p>)/g, '$1\n')
}

function inline(s) {
  return s
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\s][^*]*?)\*/g, '$1<em>$2</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
}
