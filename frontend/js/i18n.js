// ─── i18n: 雙語（繁中 / English）切換 ─────────────────────
// 字典 + applyI18n + 切換按鈕邏輯。會同步：
//   1. 帶 data-i18n 的元素文字
//   2. 帶 data-i18n-placeholder 的 input placeholder
//   3. 帶 data-i18n-title 的 title 屬性
//   4. <html lang="..."> 屬性
//   5. 頁面標題（page-title）— 經 setPageTitleI18n 對應字典
// 語言選擇存於 localStorage('mdpiece_lang')，預設 zh-TW。

(function () {
  const DICT = {
    'zh-TW': {
      // landing
      'landing.prompt': '> INIT MD.PIECE',
      'landing.tagline': '將日常碎片拼起<br>醫起走出治療的迷霧',
      'landing.subTagline': 'Piece by Piece, Patient connects Doctor and Patient',
      'landing.enter.sub': '醫患同行',
      'landing.enter.main': '開始守護',
      'landing.lab': 'CBL-AICM Lab',
      'landing.themeDark': 'DARK',
      'landing.themeLight': 'LIGHT',

      // auth
      'auth.brand.subtitle': 'MEDICAL PLATFORM',
      'auth.tab.login': '登入',
      'auth.tab.register': '註冊',
      'auth.label.role': '身份',
      'auth.role.patient': '患者',
      'auth.role.doctor': '醫師',
      'auth.label.username': '帳號',
      'auth.label.password': '密碼',
      'auth.label.password2': '確認密碼',
      'auth.label.nickname': '暱稱',
      'auth.label.doctorKey': '醫師通行碼',
      'auth.placeholder.username': '你的帳號',
      'auth.placeholder.password': '輸入密碼',
      'auth.placeholder.regUsername': '3-32 字元，限英數字 _ . -',
      'auth.placeholder.regPassword': '至少 6 個字元',
      'auth.placeholder.regPassword2': '再次輸入密碼',
      'auth.placeholder.nickname': '顯示在介面上的名字',
      'auth.placeholder.doctorKey': '輸入醫師通行碼',
      'auth.submit.login': '登入',
      'auth.submit.register': '建立帳號',
      'auth.switch.toRegister': '還沒有帳號？',
      'auth.switch.toRegisterLink': '立即註冊',
      'auth.switch.toLogin': '已經有帳號？',
      'auth.switch.toLoginLink': '直接登入',
      'auth.avatar.title': '個人頭像',
      'auth.avatar.hint': '沒上傳的話會自動用「小禾」當頭像',
      'auth.avatar.clear': '移除',
      'auth.avatar.upload': '點此上傳',
      'auth.avatar.tooltip': '點擊上傳頭像',

      // sidebar nav
      'nav.symptoms': '症狀紀錄',
      'nav.medications': '藥物紀錄',
      'nav.vitals': '生理紀錄',
      'nav.emotions': '情緒電力',
      'nav.diet': '飲食紀錄',
      'nav.memo': 'Memo',
      'nav.previsit': '診前報告',
      'nav.education': '衛教專欄',
      'nav.story': '每日故事',
      'nav.labs': '報告數值',
      'nav.pieces': '你的碎片',
      'nav.chat': '醫起聊天',
      'nav.settings': '系統設定',
      'nav.account': '帳號設定',

      'mode.toSenior': '切換為年長版',
      'mode.toNormal': '切換為普通版',
      'mode.hint': '年長版：放大字體與按鈕、提高對比',
      'logout.label': '登出',

      // topbar
      'top.back': '返回首頁',
      'top.backTitle': '返回首頁',
      'top.themeTitle': '切換主題',
      'top.settingsTitle': '系統設定',

      // mobile tabs
      'tab.home': '首頁',
      'tab.symptoms': '症狀',
      'tab.medications': '藥物',
      'tab.more': '更多',
      'tab.quickadd': '紀錄',
      'tab.quickaddAria': '快速紀錄',
      'tab.navAria': '主導覽',

      // page titles (senior / verbose form, used by topbar)
      'page.home': '首頁',
      'page.symptoms': '症狀紀錄',
      'page.medications': '藥物紀錄',
      'page.vitals': '生理紀錄',
      'page.emotions': '情緒電力',
      'page.diet': '飲食紀錄',
      'page.memo': 'Memo',
      'page.previsit': '診前報告',
      'page.education': '衛教專欄',
      'page.story': '每日故事',
      'page.labs': '報告數值',
      'page.pieces': '你的碎片',
      'page.chat': '醫起聊天',
      'page.settings': '系統設定',
      'page.account': '帳號設定',
      'page.records': '我的基本資料',
      'page.doctors': '醫師列表',

      // language toggle button
      'lang.toggleTitle': '切換語言',
      'lang.label': '中',
    },

    'en': {
      'landing.prompt': '> INIT MD.PIECE',
      'landing.tagline': 'Piece together everyday fragments<br>and walk out of the treatment fog together',
      'landing.subTagline': 'Piece by Piece, Patient connects Doctor and Patient',
      'landing.enter.sub': 'Doctor-Patient Together',
      'landing.enter.main': 'Begin Care',
      'landing.lab': 'CBL-AICM Lab',
      'landing.themeDark': 'DARK',
      'landing.themeLight': 'LIGHT',

      'auth.brand.subtitle': 'MEDICAL PLATFORM',
      'auth.tab.login': 'Sign In',
      'auth.tab.register': 'Sign Up',
      'auth.label.role': 'Role',
      'auth.role.patient': 'Patient',
      'auth.role.doctor': 'Doctor',
      'auth.label.username': 'Username',
      'auth.label.password': 'Password',
      'auth.label.password2': 'Confirm Password',
      'auth.label.nickname': 'Display Name',
      'auth.label.doctorKey': 'Doctor Passcode',
      'auth.placeholder.username': 'Your username',
      'auth.placeholder.password': 'Enter password',
      'auth.placeholder.regUsername': '3-32 chars: A-Z a-z 0-9 _ . -',
      'auth.placeholder.regPassword': 'At least 6 characters',
      'auth.placeholder.regPassword2': 'Re-enter password',
      'auth.placeholder.nickname': 'Name shown in the UI',
      'auth.placeholder.doctorKey': 'Enter doctor passcode',
      'auth.submit.login': 'Sign In',
      'auth.submit.register': 'Create Account',
      'auth.switch.toRegister': "Don't have an account? ",
      'auth.switch.toRegisterLink': 'Sign up now',
      'auth.switch.toLogin': 'Already have an account? ',
      'auth.switch.toLoginLink': 'Sign in',
      'auth.avatar.title': 'Profile Photo',
      'auth.avatar.hint': 'If left blank, "Xiaohe" will be used as your avatar',
      'auth.avatar.clear': 'Remove',
      'auth.avatar.upload': 'Tap to upload',
      'auth.avatar.tooltip': 'Click to upload avatar',

      'nav.symptoms': 'Symptoms',
      'nav.medications': 'Medications',
      'nav.vitals': 'Vitals',
      'nav.emotions': 'Mood Battery',
      'nav.diet': 'Diet',
      'nav.memo': 'Memo',
      'nav.previsit': 'Pre-visit Report',
      'nav.education': 'Health Education',
      'nav.story': 'Daily Story',
      'nav.labs': 'Lab Values',
      'nav.pieces': 'Your Pieces',
      'nav.chat': 'Med Chat',
      'nav.settings': 'Settings',
      'nav.account': 'Account',

      'mode.toSenior': 'Switch to Senior Mode',
      'mode.toNormal': 'Switch to Standard Mode',
      'mode.hint': 'Senior mode: larger fonts, larger buttons, higher contrast',
      'logout.label': 'Log Out',

      'top.back': 'Home',
      'top.backTitle': 'Back to Home',
      'top.themeTitle': 'Toggle Theme',
      'top.settingsTitle': 'Settings',

      'tab.home': 'Home',
      'tab.symptoms': 'Symptoms',
      'tab.medications': 'Meds',
      'tab.more': 'More',
      'tab.quickadd': 'Log',
      'tab.quickaddAria': 'Quick log',
      'tab.navAria': 'Main navigation',

      'page.home': 'Home',
      'page.symptoms': 'Symptoms',
      'page.medications': 'Medications',
      'page.vitals': 'Vitals',
      'page.emotions': 'Mood Battery',
      'page.diet': 'Diet',
      'page.memo': 'Memo',
      'page.previsit': 'Pre-visit Report',
      'page.education': 'Health Education',
      'page.story': 'Daily Story',
      'page.labs': 'Lab Values',
      'page.pieces': 'Your Pieces',
      'page.chat': 'Med Chat',
      'page.settings': 'Settings',
      'page.account': 'Account',
      'page.records': 'My Profile',
      'page.doctors': 'Doctors',

      'lang.toggleTitle': 'Switch language',
      'lang.label': 'EN',
    },
  };

  const STORAGE_KEY = 'mdpiece_lang';
  const DEFAULT_LANG = 'zh-TW';

  function getLang() {
    try {
      const v = localStorage.getItem(STORAGE_KEY);
      if (v && DICT[v]) return v;
    } catch (e) {}
    return DEFAULT_LANG;
  }

  function setLang(lang) {
    if (!DICT[lang]) lang = DEFAULT_LANG;
    try { localStorage.setItem(STORAGE_KEY, lang); } catch (e) {}
    document.documentElement.setAttribute('lang', lang);
    applyI18n();
    syncTopbarPageTitle();
    window.dispatchEvent(new CustomEvent('mdpiece-lang-change', { detail: lang }));
  }

  function t(key, lang) {
    lang = lang || getLang();
    const table = DICT[lang] || DICT[DEFAULT_LANG];
    if (key in table) return table[key];
    // fallback to default
    return DICT[DEFAULT_LANG][key] != null ? DICT[DEFAULT_LANG][key] : key;
  }

  function applyI18n(root) {
    const lang = getLang();
    const scope = root || document;

    scope.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      const val = t(key, lang);
      // allow simple <br> in tagline
      if (val.indexOf('<br>') >= 0 || val.indexOf('<br/>') >= 0) {
        el.innerHTML = val;
      } else {
        el.textContent = val;
      }
    });

    scope.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      el.setAttribute('placeholder', t(el.getAttribute('data-i18n-placeholder'), lang));
    });

    scope.querySelectorAll('[data-i18n-title]').forEach(el => {
      el.setAttribute('title', t(el.getAttribute('data-i18n-title'), lang));
    });

    scope.querySelectorAll('[data-i18n-aria-label]').forEach(el => {
      el.setAttribute('aria-label', t(el.getAttribute('data-i18n-aria-label'), lang));
    });

    // Mode toggle button text depends on current mode AND language.
    const modeBtn = scope.querySelector('[data-mode-toggle]');
    if (modeBtn) {
      const isSenior = document.documentElement.getAttribute('data-mode') === 'senior';
      modeBtn.textContent = t(isSenior ? 'mode.toNormal' : 'mode.toSenior', lang);
    }

    // Update every language toggle button label (may be multiple instances).
    document.querySelectorAll('.lang-toggle-label').forEach(lbl => {
      lbl.textContent = t('lang.label', lang);
    });
  }

  // Re-syncs the topbar page-title text to current language.
  function syncTopbarPageTitle() {
    const el = document.getElementById('page-title');
    if (!el) return;
    const key = el.getAttribute('data-i18n-page');
    if (!key) return;
    el.textContent = t('page.' + key);
  }

  // Public: navigation code calls setPageTitleI18n('symptoms') to set
  // the topbar title in the active language. Stores key for re-sync on
  // language switch.
  function setPageTitleI18n(pageKey) {
    const el = document.getElementById('page-title');
    if (!el) return;
    el.setAttribute('data-i18n-page', pageKey);
    el.textContent = t('page.' + pageKey);
  }

  function toggleLang() {
    const next = getLang() === 'zh-TW' ? 'en' : 'zh-TW';
    setLang(next);
  }

  // Expose
  window.MDPiece_i18n = {
    t,
    getLang,
    setLang,
    toggleLang,
    applyI18n,
    setPageTitleI18n,
  };
  // Convenience globals (used from inline onclick)
  window.toggleLang = toggleLang;
  window.setPageTitleI18n = setPageTitleI18n;
  window.applyI18n = applyI18n;

  // Init on DOM ready (script is loaded at end of body, so DOM is parsed).
  document.documentElement.setAttribute('lang', getLang());
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', applyI18n);
  } else {
    applyI18n();
  }
})();
