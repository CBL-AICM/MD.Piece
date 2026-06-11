# Vercel Connect → GitHub token（Node function）

App runtime 需要呼叫 GitHub API 時，用 [`@vercel/connect`](https://www.npmjs.com/package/@vercel/connect)
在伺服器端換一把 scoped GitHub token，不必把 PAT 寫死進環境變數。

- 函式：`api/github-token.js`（Vercel Node runtime，與 Python 後端 `api/index.py` 並存）
- 端點：`GET /api/github-token`
- 依賴：根目錄 `package.json` 的 `@vercel/connect`

## 運作原理

`getToken('github/mdpiece', { subject: { type: 'app' } })` 會：
1. 用 Vercel runtime 注入的 `VERCEL_OIDC_TOKEN`（經 `@vercel/oidc`）認證「呼叫端的 Vercel 專案」；
2. 拿這個 OIDC token 去 Vercel Connect 換一把對 `github/mdpiece` connector 的 scoped 憑證；
3. 回傳 token 字串，拿去打 `https://api.github.com`。

> ⚠️ **只能在 Vercel 部署裡跑**。本機 / 非 Vercel 環境沒有 `VERCEL_OIDC_TOKEN`，`getToken` 會失敗。

## 先決條件（兩項都只能在 Vercel 後台設定）

1. **啟用專案 OIDC**：Vercel Dashboard → 專案 → Settings → Security → 開啟 OIDC / Secure backend access。
2. **安裝 GitHub Connect connector**：建立 / 安裝一個 uid 為 `github/mdpiece` 的 Vercel Connect GitHub connector，
   並授權給 app principal。connector uid 不同時，設環境變數 `GITHUB_CONNECTOR` 覆寫。

未安裝 connector → 端點回 `412 {"error":"connector_not_installed"}`。

## 測試

部署後：
```bash
curl https://<你的新部署網址>/api/github-token
# 成功：{"ok":true,"repo":"CBL-AICM/MD.Piece","private":...}
# connector 沒裝：HTTP 412
# 其他失敗：HTTP 500，detail 內有原因
```

## 改成你實際的操作

`api/github-token.js` 內的 `fetch('https://api.github.com/repos/...')` 只是「證明 token 可用」的範例。
把那段換成你真正要做的 GitHub 操作（建立 issue、讀檔、commit…），token 取得與錯誤處理可沿用。
告訴我你要的具體操作，我可以直接幫你改這段。
