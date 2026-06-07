// 共用照片裁切器（vanilla JS，無外部依賴）
//
// window.openCropper(file, options) -> Promise<File>
//   options.aspect        鎖定長寬比（例：1 = 正方形頭像）；省略 = 自由裁切
//   options.title         對話框標題
//   options.outputMaxEdge 輸出最長邊上限（px，預設 2400）
//   options.quality       JPEG 品質（預設 0.92）
//   options.allowSkip     是否顯示「用原圖」按鈕（預設 true）
//
// 設計重點：
// - 所有上傳入口都先把 File 交給這支，使用者裁切 / 旋轉後拿到新的 JPEG File，
//   下游壓縮 / OCR / 預覽邏輯完全不用改（它們本來就吃 File）。
// - HEIC（iPhone 預設）瀏覽器畫不出來，這裡會先用 app.js 的 memoConvertHeicToJpeg
//   轉成 JPEG 再顯示；按「用原圖」拿到的也是可顯示的 JPEG，不會把 HEIC 漏到下游。
// - 使用者按「取消」或 Esc → reject(new Error('cancelled'))，呼叫端可安靜中止。
(function() {
  'use strict';
  if (window.openCropper) return;

  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

  function injectStyles() {
    if (document.getElementById('mdp-cropper-style')) return;
    var css = [
      '.mdp-crop-overlay{position:fixed;inset:0;background:rgba(0,0,0,.72);z-index:2147483600;display:flex;align-items:center;justify-content:center;padding:16px}',
      '.mdp-crop-dialog{background:var(--bg-card,#1c1c22);color:var(--text,#fff);border-radius:14px;padding:16px;max-width:620px;width:100%;box-shadow:0 12px 40px rgba(0,0,0,.5)}',
      '.mdp-crop-title{font-weight:700;font-size:1.05rem;margin-bottom:4px}',
      '.mdp-crop-hint{font-size:.8rem;opacity:.7;margin-bottom:12px}',
      '.mdp-crop-stage{display:flex;align-items:center;justify-content:center}',
      '.mdp-crop-imgwrap{position:relative;touch-action:none;-webkit-user-select:none;user-select:none;max-width:100%}',
      '.mdp-crop-img{display:block;-webkit-user-drag:none;user-select:none;pointer-events:none}',
      '.mdp-crop-box{position:absolute;border:2px solid #fff;box-shadow:0 0 0 9999px rgba(0,0,0,.45);cursor:move;box-sizing:border-box}',
      '.mdp-crop-handle{position:absolute;width:18px;height:18px;background:#fff;border-radius:50%;border:2px solid #4aa3ff;box-sizing:border-box}',
      '.mdp-h-nw{left:-10px;top:-10px;cursor:nwse-resize}',
      '.mdp-h-ne{right:-10px;top:-10px;cursor:nesw-resize}',
      '.mdp-h-sw{left:-10px;bottom:-10px;cursor:nesw-resize}',
      '.mdp-h-se{right:-10px;bottom:-10px;cursor:nwse-resize}',
      '.mdp-crop-actions{display:flex;gap:8px;justify-content:flex-end;margin-top:14px;flex-wrap:wrap}',
      '.mdp-crop-btn{display:inline-flex;align-items:center;gap:6px;padding:8px 14px;border-radius:8px;font-size:.9rem;font-weight:600;cursor:pointer;border:1px solid transparent}',
      '.mdp-crop-btn i{width:16px;height:16px}',
      '.mdp-crop-primary{background:#4aa3ff;color:#fff}',
      '.mdp-crop-secondary{background:transparent;color:var(--text,#fff);border-color:rgba(255,255,255,.3)}',
      '@media (max-width:480px){.mdp-crop-actions{justify-content:stretch}.mdp-crop-btn{flex:1;justify-content:center}}'
    ].join('');
    var s = document.createElement('style');
    s.id = 'mdp-cropper-style';
    s.textContent = css;
    document.head.appendChild(s);
  }

  // HEIC → JPEG（沿用 app.js 的 helper，沒有就原樣回傳）
  function ensureDisplayable(file) {
    try {
      if (typeof memoIsHeic === 'function' && memoIsHeic(file) &&
          typeof memoConvertHeicToJpeg === 'function') {
        if (typeof showToast === 'function') showToast('照片是 HEIC 格式，正在轉檔…', 'info');
        return memoConvertHeicToJpeg(file);
      }
    } catch (_) { /* noop */ }
    return Promise.resolve(file);
  }

  function loadImage(src) {
    return new Promise(function(resolve, reject) {
      var img = new Image();
      img.onload = function() { resolve(img); };
      img.onerror = function() { reject(new Error('image load failed')); };
      img.src = src;
    });
  }

  function mkBtn(label, icon, kind) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'mdp-crop-btn ' + (kind === 'primary' ? 'mdp-crop-primary' : 'mdp-crop-secondary');
    b.innerHTML = '<i data-lucide="' + icon + '"></i><span>' + label + '</span>';
    return b;
  }

  window.openCropper = function(file, options) {
    options = options || {};
    var aspect = (typeof options.aspect === 'number' && options.aspect > 0) ? options.aspect : null;
    var title = options.title || '裁切照片';
    var outMax = options.outputMaxEdge || 2400;
    var quality = options.quality || 0.92;
    var allowSkip = options.allowSkip !== false;
    var originalFile = file;

    return new Promise(function(resolve, reject) {
      if (!file) { reject(new Error('no file')); return; }
      injectStyles();

      ensureDisplayable(file).then(function(usable) {
        var objUrl = URL.createObjectURL(usable);
        loadImage(objUrl).then(function(img) {
          buildUI(img, usable, objUrl);
        }).catch(function() {
          try { URL.revokeObjectURL(objUrl); } catch (_) {}
          // 圖片載入失敗 → 不擋使用者，直接用原圖
          resolve(originalFile);
        });
      }).catch(function() {
        resolve(originalFile);
      });

      function buildUI(img, usable, objUrl) {
        var workImg = img; // 旋轉時換成旋轉後的圖

        var overlay = document.createElement('div');
        overlay.className = 'mdp-crop-overlay';
        var dialog = document.createElement('div');
        dialog.className = 'mdp-crop-dialog';
        overlay.appendChild(dialog);

        var titleEl = document.createElement('div');
        titleEl.className = 'mdp-crop-title';
        titleEl.textContent = title;
        dialog.appendChild(titleEl);

        var hint = document.createElement('div');
        hint.className = 'mdp-crop-hint';
        hint.textContent = aspect ? '拖曳方框移動，拉四角調整大小（固定正方形）' : '拖曳方框移動，拉四角調整裁切範圍';
        dialog.appendChild(hint);

        var stage = document.createElement('div');
        stage.className = 'mdp-crop-stage';
        dialog.appendChild(stage);

        var imgWrap = document.createElement('div');
        imgWrap.className = 'mdp-crop-imgwrap';
        stage.appendChild(imgWrap);

        var imageEl = document.createElement('img');
        imageEl.className = 'mdp-crop-img';
        imageEl.src = objUrl;
        imageEl.draggable = false;
        imgWrap.appendChild(imageEl);

        var boxEl = document.createElement('div');
        boxEl.className = 'mdp-crop-box';
        ['nw', 'ne', 'sw', 'se'].forEach(function(h) {
          var hd = document.createElement('div');
          hd.className = 'mdp-crop-handle mdp-h-' + h;
          hd.dataset.handle = h;
          boxEl.appendChild(hd);
        });
        imgWrap.appendChild(boxEl);

        var actions = document.createElement('div');
        actions.className = 'mdp-crop-actions';
        var btnRotate = mkBtn('旋轉 90°', 'rotate-cw', 'secondary');
        var btnSkip = allowSkip ? mkBtn('用原圖', 'image', 'secondary') : null;
        var btnCancel = mkBtn('取消', 'x', 'secondary');
        var btnOk = mkBtn('完成裁切', 'check', 'primary');
        actions.appendChild(btnRotate);
        if (btnSkip) actions.appendChild(btnSkip);
        actions.appendChild(btnCancel);
        actions.appendChild(btnOk);
        dialog.appendChild(actions);

        document.body.appendChild(overlay);
        if (window.lucide && lucide.createIcons) { try { lucide.createIcons(); } catch (_) {} }

        var dispW, dispH, box;

        function layout() {
          var maxW = Math.min(window.innerWidth * 0.86, 560);
          var maxH = window.innerHeight * 0.58;
          var nW = workImg.naturalWidth, nH = workImg.naturalHeight;
          var sc = Math.min(maxW / nW, maxH / nH, 1);
          dispW = Math.max(80, Math.round(nW * sc));
          dispH = Math.max(80, Math.round(nH * sc));
          imgWrap.style.width = dispW + 'px';
          imgWrap.style.height = dispH + 'px';
          imageEl.style.width = dispW + 'px';
          imageEl.style.height = dispH + 'px';
          resetBox();
        }

        function resetBox() {
          if (aspect) {
            var w = Math.min(dispW, dispH * aspect);
            var h = w / aspect;
            if (h > dispH) { h = dispH; w = h * aspect; }
            box = { x: (dispW - w) / 2, y: (dispH - h) / 2, w: w, h: h };
          } else {
            box = { x: dispW * 0.08, y: dispH * 0.08, w: dispW * 0.84, h: dispH * 0.84 };
          }
          drawBox();
        }

        function drawBox() {
          boxEl.style.left = box.x + 'px';
          boxEl.style.top = box.y + 'px';
          boxEl.style.width = box.w + 'px';
          boxEl.style.height = box.h + 'px';
        }

        var drag = null;
        function onDown(e, handle) {
          e.preventDefault();
          e.stopPropagation();
          drag = { handle: handle, sx: e.clientX, sy: e.clientY,
                   box: { x: box.x, y: box.y, w: box.w, h: box.h } };
          document.addEventListener('pointermove', onMove, { passive: false });
          document.addEventListener('pointerup', onUp);
        }
        function onMove(e) {
          if (!drag) return;
          e.preventDefault();
          var dx = e.clientX - drag.sx, dy = e.clientY - drag.sy;
          if (drag.handle === 'move') moveBox(drag.box, dx, dy);
          else resizeBox(drag.handle, drag.box, dx, dy);
          drawBox();
        }
        function onUp() {
          drag = null;
          document.removeEventListener('pointermove', onMove);
          document.removeEventListener('pointerup', onUp);
        }

        function moveBox(sb, dx, dy) {
          box.x = clamp(sb.x + dx, 0, dispW - sb.w);
          box.y = clamp(sb.y + dy, 0, dispH - sb.h);
          box.w = sb.w; box.h = sb.h;
        }

        function resizeBox(handle, sb, dx, dy) {
          var minS = 40;
          if (aspect) {
            // 鎖比例：以對角為錨點，從拖曳角往外算
            var ax = handle.indexOf('w') >= 0 ? sb.x + sb.w : sb.x;
            var ay = handle.indexOf('n') >= 0 ? sb.y + sb.h : sb.y;
            var dirX = handle.indexOf('e') >= 0 ? 1 : -1;
            var dirY = handle.indexOf('s') >= 0 ? 1 : -1;
            var cornerX = handle.indexOf('e') >= 0 ? sb.x + sb.w : sb.x;
            var cornerY = handle.indexOf('s') >= 0 ? sb.y + sb.h : sb.y;
            var cx = cornerX + dx, cy = cornerY + dy;
            var w = Math.max(Math.abs(cx - ax), Math.abs(cy - ay) * aspect);
            var maxX = dirX > 0 ? dispW - ax : ax;
            var maxY = dirY > 0 ? dispH - ay : ay;
            if (w > maxX) w = maxX;
            var h = w / aspect;
            if (h > maxY) { h = maxY; w = h * aspect; }
            if (w < minS) { w = minS; h = w / aspect; }
            box.w = w; box.h = h;
            box.x = dirX > 0 ? ax : ax - w;
            box.y = dirY > 0 ? ay : ay - h;
          } else {
            var right = sb.x + sb.w, bottom = sb.y + sb.h;
            var x = sb.x, y = sb.y, bw = sb.w, bh = sb.h;
            if (handle.indexOf('e') >= 0) bw = clamp(sb.w + dx, minS, dispW - sb.x);
            if (handle.indexOf('s') >= 0) bh = clamp(sb.h + dy, minS, dispH - sb.y);
            if (handle.indexOf('w') >= 0) { x = clamp(sb.x + dx, 0, right - minS); bw = right - x; }
            if (handle.indexOf('n') >= 0) { y = clamp(sb.y + dy, 0, bottom - minS); bh = bottom - y; }
            box.x = x; box.y = y; box.w = bw; box.h = bh;
          }
        }

        boxEl.addEventListener('pointerdown', function(e) {
          if (e.target && e.target.dataset && e.target.dataset.handle) return;
          onDown(e, 'move');
        });
        Array.prototype.forEach.call(boxEl.querySelectorAll('.mdp-crop-handle'), function(hd) {
          hd.addEventListener('pointerdown', function(e) { onDown(e, hd.dataset.handle); });
        });

        btnRotate.addEventListener('click', function() {
          var nW = workImg.naturalWidth, nH = workImg.naturalHeight;
          var c = document.createElement('canvas');
          c.width = nH; c.height = nW;
          var ctx = c.getContext('2d');
          ctx.translate(c.width / 2, c.height / 2);
          ctx.rotate(Math.PI / 2);
          ctx.drawImage(workImg, -nW / 2, -nH / 2);
          var url = c.toDataURL('image/jpeg', 0.95);
          loadImage(url).then(function(ni) {
            workImg = ni;
            imageEl.src = url;
            layout();
          });
        });

        function cleanup() {
          window.removeEventListener('resize', layout);
          document.removeEventListener('keydown', onKey);
          try { URL.revokeObjectURL(objUrl); } catch (_) {}
          if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
        }
        function onKey(e) {
          if (e.key === 'Escape') { cleanup(); reject(new Error('cancelled')); }
        }
        document.addEventListener('keydown', onKey);

        btnCancel.addEventListener('click', function() { cleanup(); reject(new Error('cancelled')); });
        overlay.addEventListener('pointerdown', function(e) {
          if (e.target === overlay) { cleanup(); reject(new Error('cancelled')); }
        });
        // 「用原圖」回傳可顯示的檔案（HEIC 已轉 JPEG），不重新編碼
        if (btnSkip) btnSkip.addEventListener('click', function() { cleanup(); resolve(usable); });

        btnOk.addEventListener('click', function() {
          try {
            var factor = workImg.naturalWidth / dispW;
            var sx = Math.round(box.x * factor), sy = Math.round(box.y * factor);
            var sw = Math.max(1, Math.round(box.w * factor)), sh = Math.max(1, Math.round(box.h * factor));
            var scale = Math.min(1, outMax / Math.max(sw, sh));
            var outW = Math.max(1, Math.round(sw * scale)), outH = Math.max(1, Math.round(sh * scale));
            var c = document.createElement('canvas');
            c.width = outW; c.height = outH;
            var ctx = c.getContext('2d');
            ctx.fillStyle = '#fff'; // 白底，避免透明 PNG 變黑
            ctx.fillRect(0, 0, outW, outH);
            ctx.drawImage(workImg, sx, sy, sw, sh, 0, 0, outW, outH);
            var name = (originalFile.name || 'photo').replace(/\.(heic|heif|png|webp)$/i, '') + '.jpg';
            if (c.toBlob) {
              c.toBlob(function(blob) {
                cleanup();
                resolve(blob ? new File([blob], name, { type: 'image/jpeg' }) : originalFile);
              }, 'image/jpeg', quality);
            } else {
              var durl = c.toDataURL('image/jpeg', quality);
              cleanup();
              resolve(dataUrlToFile(durl, name));
            }
          } catch (err) {
            cleanup();
            resolve(originalFile);
          }
        });

        layout();
        window.addEventListener('resize', layout);
      }

      function dataUrlToFile(durl, name) {
        var arr = durl.split(',');
        var mime = (arr[0].match(/:(.*?);/) || [])[1] || 'image/jpeg';
        var bstr = atob(arr[1]);
        var n = bstr.length;
        var u8 = new Uint8Array(n);
        while (n--) u8[n] = bstr.charCodeAt(n);
        return new File([u8], name, { type: mime });
      }
    });
  };
})();
