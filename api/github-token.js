// Vercel Node function：以 Vercel Connect 換取 GitHub token，並用它呼叫 GitHub API。
//
// 先決條件（缺一不可，兩項都只能在 Vercel 後台設定，無法由程式碼完成）：
//   1. 此 Vercel 專案已啟用 OIDC（Settings → Security）。@vercel/connect 內部
//      靠 @vercel/oidc 讀 runtime 注入的 VERCEL_OIDC_TOKEN——只有在「真的跑於
//      Vercel 部署」時才有，本機 / 非 Vercel 執行會丟錯。
//   2. 已安裝一個 uid 為 `github/mdpiece` 的 Vercel Connect GitHub connector
//      （可用環境變數 GITHUB_CONNECTOR 覆寫）。未安裝會回 412。
//
// 詳見 docs/VERCEL_CONNECT_GITHUB.md。
import { getToken, ConnectorInstallationRequiredError } from '@vercel/connect';

const CONNECTOR = process.env.GITHUB_CONNECTOR || 'github/mdpiece';

export default async function handler(req, res) {
  try {
    // 以 app 身分換一把 scoped GitHub token（非代表某使用者）。
    const token = await getToken(CONNECTOR, { subject: { type: 'app' } });

    // ── 用這把 token 呼叫 GitHub API ──────────────────────────────────────
    // 範例：讀 repo metadata 證明 token 真的能用。請把這段換成你實際要做的
    // 操作（建立 issue、讀檔、commit…），其餘 token 取得 / 錯誤處理可沿用。
    const gh = await fetch('https://api.github.com/repos/CBL-AICM/MD.Piece', {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: 'application/vnd.github+json',
        'User-Agent': 'md-piece',
      },
    });
    if (!gh.ok) {
      return res.status(502).json({ error: 'github_api_failed', status: gh.status });
    }
    const data = await gh.json();
    return res.status(200).json({ ok: true, repo: data.full_name, private: data.private });
  } catch (err) {
    // connector 尚未安裝 / 授權時 Connect 會丟這個——提示去 Vercel 後台安裝 GitHub connector。
    if (err instanceof ConnectorInstallationRequiredError) {
      return res.status(412).json({ error: 'connector_not_installed', detail: String(err.message) });
    }
    return res.status(500).json({ error: 'connect_token_failed', detail: String(err?.message || err) });
  }
}
