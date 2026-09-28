# -*- coding: utf-8 -*-
"""產生 ui/direction.html——單一離線網頁，內嵌部署模型（direction.PARAMS：v3.2 修正後資料之常規套組＋2021–2023 重新校準），
瀏覽器內直接計算。  python make_direction_html.py
格式符合 Artifact 頁面規格（不自帶 html/head/body、淺深雙主題 token、手機先顯示結果、開啟即載入真實示範受試者），
同一個檔案可離線開啟，也可直接發布成私人連結（2026-09-27 已發布）。

JS 端的數學與 direction.py 逐行對應：
  raw  = mean_folds( sigmoid( ((x∨median − mean)/scale) · coef + intercept ) )
  cal  = 線性內插 raw 於 (isotonic_x, isotonic_y)，兩端夾住（同 np.interp）
  cal  = sigmoid(a + b·logit(clip(cal, 0.001)))（v3.1 重新校準；模型無 recalibration 欄位則略過）
  band = cal ≥ t_high → 傾向；cal ≤ t_low → 不傾向；否則不確定
  drivers = mean_folds(z·coef) 取 |值| 前四且非缺項
產生後以 verify_direction_html.py 對同一病人比對 Python 與 JS 輸出。

用詞規則（專案 UI 鐵則）：無第二人稱、無紅黃綠燈、無等級、無建議、無單一綜合分數。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
from nhanes_cohort import DERIVED, FEATURE_LABELS   # noqa: E402

LABEL = {**FEATURE_LABELS, **DERIVED, "age": "年齡", "sex": "性別"}
UNIT = {
    "LBXSAL": "g/dL", "LBXSATSI": "U/L", "LBXSASSI": "U/L", "LBXSAPSI": "U/L", "LBXSBU": "mg/dL",
    "LBXSCA": "mg/dL", "LBXSCH": "mg/dL", "LBXSC3SI": "mmol/L", "LBXSGTSI": "U/L", "LBXSGL": "mg/dL",
    "LBXSIR": "ug/dL", "LBXSLDSI": "U/L", "LBXSPH": "mg/dL", "LBXSTB": "mg/dL", "LBXSTP": "g/dL",
    "LBXSTR": "mg/dL", "LBXSUA": "mg/dL", "LBXSCR": "mg/dL", "LBXSNASI": "mmol/L", "LBXSKSI": "mmol/L",
    "LBXSCLSI": "mmol/L", "LBXSOSSI": "mmol/kg", "LBXSGB": "g/dL", "LBXWBCSI": "10³/uL",
    "LBXRBCSI": "10⁶/uL", "LBXHGB": "g/dL", "LBXMCVSI": "fL", "LBXMCHSI": "pg", "LBXMC": "g/dL",
    "LBXRDW": "%", "LBXPLTSI": "10³/uL", "LBXMPSI": "fL", "LBXCRP": "mg/dL", "LBXBAP": "ug/L",
    "URXUMA": "ug/mL", "URXUCR": "mg/dL", "LBXTC": "mg/dL", "LBXTR": "mg/dL", "LBDLDL": "mg/dL", "LBDHDL": "mg/dL",
    "LBXBPB": "ug/dL", "LBXBCD": "ug/L", "LBXFER": "ng/mL", "LBXFOL": "ng/mL", "LBXB12": "pg/mL",
    "LBXMMA": "umol/L", "LBXTHG": "ug/L", "LBXRBF": "ng/mL", "LBXCOT": "ng/mL", "LBDVIDMS": "nmol/L",
    "LBXPT21": "pg/mL", "LBXHCT": "%", "LBXHCY": "umol/L", "ACR": "mg/g", "eGFR": "mL/min/1.73m²", "NLR": "比值", "age": "歲",
    "sex": "1=男 2=女",
}
GROUPS = [
    ("生化", "LBXSAL LBXSGB LBXSTP LBXSBU LBXSCR LBXSUA LBXSNASI LBXSKSI LBXSCLSI LBXSCA LBXSPH "
             "LBXSC3SI LBXSOSSI LBXSATSI LBXSASSI LBXSAPSI LBXSGTSI LBXSTB LBXSLDSI LBXSGL LBXSIR "
             "LBXSCH LBXSTR".split()),
    ("血球", "LBXWBCSI LBXLYPCT LBXMOPCT LBXNEPCT LBXEOPCT LBXBAPCT LBXRBCSI LBXHGB LBXHCT LBXMCVSI "
             "LBXMCHSI LBXMC LBXRDW LBXPLTSI LBXMPSI".split()),
    ("尿液與腎功能", "URXUMA URXUCR ACR eGFR".split()),
    ("脂質與發炎", "LBXTC LBDHDL LBXTR LBDLDL LBXCRP LBXBAP NLR".split()),
    ("營養／微量元素", "LBXFER LBXFOL LBXB12 LBXMMA LBXHCY LBXRBF LBDVIDMS LBXPT21 LBXCOT LBXBPB LBXBCD LBXTHG".split()),
    ("人口學", "age sex".split()),
]

HTML = r"""<meta charset="utf-8">
<title>腎臟指標異常病因線索</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{--ink:#1b2129;--sub:#56606c;--line:#d5dbe2;--bg:#f4f6f8;--card:#ffffff;--acc:#2f5f8f;--accs:#e3ecf5;--onacc:#ffffff;
 --sans:"PingFang TC","Microsoft JhengHei","Noto Sans TC","Heiti TC",system-ui,sans-serif;
 --mono:"IBM Plex Mono",ui-monospace,Consolas,"Microsoft JhengHei",monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--ink:#e5e9ee;--sub:#a2acb8;--line:#323a44;--bg:#111418;--card:#1a1f25;--acc:#8ab8e3;--accs:#1e2e3f;--onacc:#0c1520;color-scheme:dark}}
:root[data-theme="dark"]{--ink:#e5e9ee;--sub:#a2acb8;--line:#323a44;--bg:#111418;--card:#1a1f25;--acc:#8ab8e3;--accs:#1e2e3f;--onacc:#0c1520;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;font:15px/1.6 var(--sans);color:var(--ink);background:var(--bg)}
.page{max-width:1280px;margin:0 auto;padding-inline:clamp(16px,3vw,28px);padding-block:0 32px}
header{padding-block:22px 14px;border-bottom:1px solid var(--line)}
h1{margin:0;font-size:21px;line-height:1.35;text-wrap:balance}
header p{margin:6px 0 0;color:var(--sub);font-size:13.5px;max-width:72ch}
main{display:grid;grid-template-columns:minmax(0,1fr) 400px;gap:20px;padding-block:20px}
@media(max-width:960px){main{grid-template-columns:minmax(0,1fr)}#out{order:-1;position:static}}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 16px}
details{border-top:1px solid var(--line);padding-block:6px}details:first-of-type{border-top:0}
summary{cursor:pointer;font-weight:600;padding-block:6px;color:var(--acc)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:8px 14px;padding-block:6px 4px}
label{display:flex;flex-direction:column;font-size:12.5px;color:var(--sub)}
label b{color:var(--ink);font-weight:500}label small{font:11px/1.5 var(--mono);letter-spacing:.01em}
input{margin-top:3px;padding:6px 8px;border:1px solid var(--line);border-radius:5px;background:var(--card);color:var(--ink);font:14px var(--mono);font-variant-numeric:tabular-nums;width:100%}
input:focus-visible{outline:2px solid var(--acc);outline-offset:1px}
.bar{display:flex;flex-wrap:wrap;gap:10px;margin-block:4px 12px}
.bar button{flex:1 1 120px;padding:9px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--ink);font:inherit;cursor:pointer}
.bar button.p{background:var(--acc);color:var(--onacc);border-color:var(--acc)}
.bar button:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
#out{position:sticky;top:calc(env(safe-area-inset-top,0px) + 16px);align-self:start}
#out h2{font-size:16px;margin:0 0 4px}.note{color:var(--sub);font-size:12.5px;margin:0 0 12px}
.demo{background:var(--accs);border-radius:6px;padding:8px 10px;color:var(--ink)}
.axis{border:1px solid var(--line);border-radius:6px;padding:12px 14px;margin-bottom:12px;display:grid;gap:6px}
.axis h3{margin:0;font-size:15px;display:flex;flex-wrap:wrap;gap:4px 10px;justify-content:space-between;align-items:baseline}
.axis h3 span{font-size:12.5px;color:var(--sub);font-weight:400}
.meter{position:relative;height:10px;background:var(--accs);border-radius:5px;overflow:hidden}
.meter i{display:block;height:100%;background:var(--acc)}
.meter::after{content:"";position:absolute;left:50%;top:0;bottom:0;width:2px;margin-left:-1px;background:var(--ink);opacity:.55}
.scale{display:flex;justify-content:space-between;font:11px var(--mono);color:var(--sub)}
.row{display:flex;flex-wrap:wrap;gap:6px 12px;align-items:center}
.band{display:inline-block;font-weight:700;font-size:14px;padding:1px 12px;border-radius:999px;border:1px solid var(--acc);color:var(--acc)}
.band.b2{background:var(--acc);color:var(--onacc)}.band.b0{border-color:var(--line);background:var(--accs);color:var(--ink)}
.band.bx{border-style:dashed;border-color:var(--sub);color:var(--sub)}
.prob{color:var(--sub);font-size:13px;font-variant-numeric:tabular-nums}
.thr{font-size:12px;color:var(--sub)}
.drv{margin:2px 0 0;padding:0;list-style:none;font-size:13px}.drv li{display:flex;justify-content:space-between;gap:10px;padding:2px 0;border-top:1px dashed var(--line)}
.drv li span:last-child{color:var(--sub);font-family:var(--mono);font-variant-numeric:tabular-nums}.miss{font-size:12px;color:var(--sub)}
.empty{color:var(--sub);text-align:center;padding:40px 10px}
footer{color:var(--sub);font-size:12px;padding-block:14px 0;border-top:1px solid var(--line)}
</style>
<div class="page" lang="zh-Hant">
<header><h1>腎臟指標異常之病因線索（肝炎病毒感染／糖尿病）</h1>
<p>輸入常規檢驗數值，輸出兩個共存標籤的相對傾向：這組數值與肝炎病毒感染（HBsAg 或 HCV RNA 陽性）或糖尿病標籤者相比像不像。v3.2 只用常規檢驗（血球、生化、血脂、尿液與年齡性別；開發資料已依 CDC 文件修正跨週期量尺），機率已依 NHANES 2021–2023 更新校準。共存標籤不等於腎損傷病因；留空項目以開發資料中位數補入並標明。非診斷工具。</p></header>
<main>
<section class="card" aria-label="檢驗數值">
  <div class="bar"><button class="p" id="run">計算方向</button><button id="demo">載入示範數值</button><button id="clr">清除</button></div>
  <div id="form"></div>
</section>
<aside class="card" id="out" aria-live="polite"><div class="empty">尚未輸入數值</div></aside>
</main>
<footer>模型 v3.2（2026-09-27）：常規套組邏輯迴歸（肝炎軸 __NF_HEP__ 項、糖尿病軸 __NF_DM__ 項），以修正後之 NHANES 1999–2018 腎臟指標異常成人開發（肝炎軸 n=__N_HEP__、糖尿病軸 n=__N_DM__；標籤三值，未知者不納入；2017–2018 年生化值已依 CDC 回推式換回 1999–2016 年之量尺）。判別：內部巢狀外層 AUROC 肝炎 __AUC_HEP__、糖尿病 __AUC_DM__；NHANES 2021–2023（事後評估，此資料先前已用於 v3 之一次性外部確認與 v3.1 重新校準）AUROC 肝炎 __XAUC_HEP__（僅 __XPOS_HEP__ 名陽性，95% CI __XCI_HEP__）、糖尿病 __XAUC_DM__（95% CI __XCI_DM__）。以同一批 2021–2023 資料更新校準：肝炎軸__RM_HEP__、糖尿病軸__RM_DM__；事前機率改為 2021–2023 腎臟指標異常成人之比例（肝炎 __PRIOR_HEP__、糖尿病 __PRIOR_DM__）。依抽樣設計切半 200 次之交叉驗證，糖尿病軸測試半之平均預測／實際比例中位數 __CV_DM__；仍無獨立資料驗證。分區：傾向＝勝算達事前勝算 2 倍以上，不傾向＝0.5 倍以下（相當於概似比 2 與 0.5）；常規套組有值不足一半時標示「資料不足」。輸入值以開發資料之檢驗量尺為準，不同實驗室之方法可能有數個百分點差異。肝炎軸訊號幾乎全來自 C 型肝炎（僅 B 肝 AUROC __HBV_AUC__）。免疫軸因公開資料缺乏關鍵檢驗而未納入。輸出為排序線索，不構成診斷或建議。</footer>
<script>
const M=__MODEL__, L=__LABELS__, U=__UNITS__, G=__GROUPS__, DEMO=__DEMO__, DEMO_META=__DEMO_META__;
const all=[...new Set(Object.values(M.axes).flatMap(a=>a.features))];
const med={};for(const a of Object.values(M.axes))a.features.forEach((f,i)=>{med[f]=a.ensemble.reduce((s,fp)=>s+fp.medians[i],0)/a.ensemble.length});
const form=document.getElementById('form');
for(const [g,fs] of G){const d=document.createElement('details');d.open=(g==='生化'||g==='血球');
 d.innerHTML=`<summary>${g}（${fs.length}）</summary><div class="grid">`+fs.map(f=>`<label><b>${L[f]||f}</b><small>${f}${U[f]?'　'+U[f]:''}　中位 ${fmt(med[f])}</small><input type="number" step="any" inputmode="decimal" id="f-${f}" data-f="${f}" placeholder="留空＝中位數"></label>`).join('')+'</div>';form.appendChild(d)}
function fmt(v){return v==null||isNaN(v)?'—':(Math.abs(v)>=100?v.toFixed(0):Math.abs(v)>=10?v.toFixed(1):v.toFixed(2))}
function read(){const o={};form.querySelectorAll('input').forEach(i=>{if(i.value!=='')o[i.dataset.f]=+i.value});return o}
/*MATH-START*/
function sig(t){return 1/(1+Math.exp(-t))}
function recal(a,p){const r=a.recalibration;if(!r)return p;const c=Math.min(Math.max(p,1e-3),1-1e-3);return sig(r.a+r.b*Math.log(c/(1-c)))}
function interp(x,xs,ys){if(x<=xs[0])return ys[0];if(x>=xs[xs.length-1])return ys[ys.length-1];let i=1;while(xs[i]<x)i++;const t=(x-xs[i-1])/(xs[i]-xs[i-1]);return ys[i-1]+t*(ys[i]-ys[i-1])}
function predict(v){const res={};for(const [name,a] of Object.entries(M.axes)){const ff=a.features,n=ff.length;const x=ff.map(f=>f in v?v[f]:NaN);const miss=ff.filter((f,i)=>isNaN(x[i]));
 const basic=a.basic_panel.filter(f=>!isNaN(x[ff.indexOf(f)])).length/a.basic_panel.length;const oor=ff.filter((f,i)=>!isNaN(x[i])&&(x[i]<a.train_min[i]||x[i]>a.train_max[i]));
 let raw=0;const contrib=new Array(n).fill(0);
 for(const fp of a.ensemble){let t=fp.intercept;for(let i=0;i<n;i++){const xi=isNaN(x[i])?fp.medians[i]:x[i];const z=(xi-fp.mean[i])/fp.scale[i];t+=z*fp.coef[i];contrib[i]+=z*fp.coef[i]}raw+=sig(t)}
 raw/=a.ensemble.length;for(let i=0;i<n;i++)contrib[i]/=a.ensemble.length;
 const cal=recal(a,interp(raw,a.isotonic_x,a.isotonic_y));const band=basic<0.5?'資料不足':cal>=a.t_high?'傾向':cal<=a.t_low?'不傾向':'不確定';
 const or_=(cal>0&&cal<1)?(cal/(1-cal))/(a.prevalence/(1-a.prevalence)):(cal<=0?0:Infinity);
 const order=[...contrib.keys()].filter(i=>!isNaN(x[i])).sort((p,q)=>Math.abs(contrib[q])-Math.abs(contrib[p])).slice(0,4);
 res[name]={title:a.title,cal,prev:a.prevalence,or:or_,band,basic,oor,miss:miss.length,n,drivers:order.map(i=>({f:ff[i],name:L[ff[i]]||ff[i],val:x[i],push:contrib[i]>0?'→推向':'←推離'}))}}return res}
/*MATH-END*/
function band_cls(b){return b==='傾向'?'b2':b==='不傾向'?'b0':b==='資料不足'?'bx':'b1'}
function pc(p){return (p*100).toFixed(p<0.05?2:1)+'%'}
function render(res,note){const o=document.getElementById('out');o.innerHTML='<h2>病因線索</h2>'+(note?`<p class="note demo">${note}</p>`:'')+'<p class="note">共存標籤之相對傾向，非診斷。每軸獨立判定；量尺為相對事前勝算（概似比）0.25–4 倍之對數刻度，中線＝與事前機率相同（2021–2023 年腎臟指標異常成人之比例）。</p>'+Object.entries(res).map(([k,a])=>{const w=Math.max(0,Math.min(1,(Math.log2(Math.max(a.or,1e-9))+2)/4))*100;const ax=M.axes[k];
 return `<div class="axis"><h3>${a.title}<span>事前機率 ${pc(a.prev)}</span></h3><div class="meter" role="img" aria-label="相對事前勝算 ×${isFinite(a.or)?a.or.toFixed(2):'—'}"><i style="width:${w.toFixed(0)}%"></i></div><div class="scale"><span>×0.25</span><span>×1</span><span>×4</span></div><div class="row"><span class="band ${band_cls(a.band)}">${a.band}</span><span class="prob">校準機率 ${(a.cal*100).toFixed(2)}%　相對事前勝算 ×${isFinite(a.or)?a.or.toFixed(2):'—'}</span></div><div class="thr">門檻：傾向 ≥ ${pc(ax.t_high)}、不傾向 ≤ ${pc(ax.t_low)}</div><ul class="drv">${a.drivers.map(d=>`<li><span>${d.push} ${d.name}</span><span>${fmt(d.val)}</span></li>`).join('')}</ul>${a.miss?`<div class="miss">缺 ${a.miss}/${a.n} 項，以中位數補入（常規套組有值 ${(a.basic*100).toFixed(0)}%）</div>`:''}${a.oor.length?`<div class="miss">超出開發資料範圍：${a.oor.map(f=>L[f]||f).join('、')}（請核對單位）</div>`:''}</div>`}).join('')}
function fill(v){form.querySelectorAll('input').forEach(i=>{i.value=i.dataset.f in v?v[i.dataset.f]:''})}
function showDemo(){fill(DEMO);render(predict(DEMO),'示範數值：'+DEMO_META+'。僅展示輸出形式，不代表準確率；修改任一數值後按「計算方向」重算。')}
document.getElementById('run').onclick=()=>{const v=read();if(!Object.keys(v).length){document.getElementById('out').innerHTML='<div class="empty">尚未輸入數值</div>';return}render(predict(v))};
document.getElementById('demo').onclick=showDemo;
document.getElementById('clr').onclick=()=>{fill({});document.getElementById('out').innerHTML='<div class="empty">尚未輸入數值</div>'};
if(Object.keys(DEMO).length)showDemo();
</script>
</div>
"""


def main():
    from direction import PARAMS
    M = json.load(open(PARAMS, encoding="utf-8"))
    J = lambda *p: json.load(open(os.path.join(ROOT, *p), encoding="utf-8"))
    E, XX = J("results", "v3_2_eval.json")["axes"], J("results", "v3_2_external.json")
    X = XX["axes"]
    xb = lambda k: X[k]["models"]["LR_routine"]
    cv = XX["recalibration_cv"]["v3.2"]["糖尿病"]["random_summary"]["oe_recal"]
    rm = lambda k: {"截距更新": "只更新截距（事件太少，不估斜率）" if M["axes"][k]["recalibration"]["n_pos"] < 100 else "只更新截距",
                    "截距與斜率更新": "更新截距與斜率"}[M["axes"][k]["recalibration"]["method"]]
    feats = sorted({f for a in M["axes"].values() for f in a["features"]})
    groups = [(g, [f for f in fs if f in feats]) for g, fs in GROUPS]
    groups = [(g, fs) for g, fs in groups if fs]
    listed = {f for _, fs in groups for f in fs}
    rest = [f for f in feats if f not in listed]
    if rest:
        groups.append(("其他", rest))
    # 示範數值：保留集中一位 B/C 肝陽性者（與 direction.py demo 同一位，可對照）
    demo = json.load(open(os.path.join(ROOT, "params", "direction_demo_patient.json"),
                          encoding="utf-8")) if os.path.exists(
        os.path.join(ROOT, "params", "direction_demo_patient.json")) else {}
    ex_p = os.path.join(ROOT, "params", "direction_demo_expected.json")
    ex = json.load(open(ex_p, encoding="utf-8")) if os.path.exists(ex_p) else {}
    lab = ex.get("labels", {})
    tags = [t for k, t in (("hcv3", "HCV RNA 陽性"), ("hbv3", "HBsAg 陽性")) if lab.get(k) == 1] + \
        (["糖尿病標籤陽性"] if lab.get("dm3") == 1 else ["無糖尿病標籤"] if lab.get("dm3") == 0 else [])
    meta = (f"NHANES {ex['cycle'].replace('-', '–')} 真實受試者（SEQN {ex['SEQN']}；{'、'.join(tags)}）"
            if ex else "NHANES 真實受試者")
    html = (HTML.replace("__MODEL__", json.dumps(M, ensure_ascii=False))
                .replace("__DEMO_META__", json.dumps(meta, ensure_ascii=False))
                .replace("__LABELS__", json.dumps(LABEL, ensure_ascii=False))
                .replace("__UNITS__", json.dumps(UNIT, ensure_ascii=False))
                .replace("__GROUPS__", json.dumps(groups, ensure_ascii=False))
                .replace("__DEMO__", json.dumps(demo, ensure_ascii=False))
                .replace("__NF_HEP__", str(len(M["axes"]["肝炎"]["features"])))
                .replace("__NF_DM__", str(len(M["axes"]["糖尿病"]["features"])))
                .replace("__N_HEP__", f"{M['axes']['肝炎']['n']:,}").replace("__N_DM__", f"{M['axes']['糖尿病']['n']:,}")
                .replace("__AUC_HEP__", f"{E['肝炎']['models']['LR_routine']['repeats']['mean']['auroc']:.3f}")
                .replace("__AUC_DM__", f"{E['糖尿病']['models']['LR_routine']['repeats']['mean']['auroc']:.3f}")
                .replace("__CV_DM__", f"{cv['median']:.2f}（2.5–97.5 百分位 {cv['p2_5']:.2f}–{cv['p97_5']:.2f}）")
                .replace("__XAUC_HEP__", f"{xb('肝炎')['auroc']:.3f}").replace("__XAUC_DM__", f"{xb('糖尿病')['auroc']:.3f}")
                .replace("__XCI_HEP__", "–".join(f"{v:.3f}" for v in xb("肝炎")["ci95"]["auroc"]))
                .replace("__XCI_DM__", "–".join(f"{v:.3f}" for v in xb("糖尿病")["ci95"]["auroc"]))
                .replace("__XPOS_HEP__", str(X["肝炎"]["n_pos"]))
                .replace("__RM_HEP__", rm("肝炎")).replace("__RM_DM__", rm("糖尿病"))
                .replace("__PRIOR_HEP__", f"{100 * M['axes']['肝炎']['prevalence']:.2f}%")
                .replace("__PRIOR_DM__", f"{100 * M['axes']['糖尿病']['prevalence']:.1f}%")
                .replace("__HBV_AUC__", f"{E['肝炎']['single_label_LR_routine']['僅B型_HBsAg']['auroc']:.3f}"))
    assert "__" not in html.split("<script>")[0], "頁面文字仍有未填入的欄位"
    os.makedirs(os.path.join(ROOT, "ui"), exist_ok=True)
    out = os.path.join(ROOT, "ui", "direction.html")
    open(out, "w", encoding="utf-8").write(html)
    print(f"[完成] {out}  ({len(html)//1024} KB，{len(feats)} 個輸入欄位，{len(groups)} 組)")


if __name__ == "__main__":
    main()
