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

      // home page
      'home.greet.morning': '早安',
      'home.greet.afternoon': '午安',
      'home.greet.evening': '晚安',
      'home.greet.fallbackName': '你',
      'home.calm.0': '每一小步，都是照顧自己的開始',
      'home.calm.1': '健康是一塊一塊拼起來的拼圖',
      'home.calm.2': '慢慢來，我們陪你一起',
      'home.calm.3': '今天也要好好照顧自己喔',
      'home.calm.4': '記錄每個碎片，拼出完整的你',
      'home.calm.5': '你不是一個人，我們一直都在',
      'home.tip.0': '深呼吸三次，讓肩膀放鬆下來，你做得很好。',
      'home.tip.1': '喝一杯溫水，給身體最簡單的關愛。',
      'home.tip.2': '今天有按時吃藥嗎？每一次準時都是對自己的守護。',
      'home.tip.3': '散步十分鐘，陽光是最好的維他命。',
      'home.tip.4': '寫下今天的感受，情緒也是健康的一塊拼圖。',
      'home.tip.5': '睡前放下手機，讓大腦也好好休息。',
      'home.tip.6': '跟身邊的人說說話，連結也是一種療癒。',
      'home.tip.7': '不用完美，只要每天進步一點點就好。',
      'home.weekday.prefix': '星期',
      'home.weekday.0': '日',
      'home.weekday.1': '一',
      'home.weekday.2': '二',
      'home.weekday.3': '三',
      'home.weekday.4': '四',
      'home.weekday.5': '五',
      'home.weekday.6': '六',
      'home.visit.set': '設定下次回診',
      'home.visit.label': '下次回診',
      'home.visit.editTitle': '點此修改',
      'home.visit.clearTitle': '清除',
      'home.visit.daysLeft': '剩 {n} 天',
      'home.visit.today': '就是今天！',
      'home.visit.daysAgo': '{n} 天前已回診',
      'home.quick.symptoms': '記錄症狀',
      'home.quick.meds': '服藥打卡',
      'home.quick.records': '基本資料',
      'home.quick.education': '衛教知識',
      'home.ov.meds': '今日服藥',
      'home.ov.mood': '今日心情',
      'home.ov.tip': '健康小語',
      'home.ov.loading': '載入中...',
      'home.med.empty': '尚無藥物紀錄，從藥物管理開始記錄吧',
      'home.med.error': '開始記錄你的第一顆藥物吧',
      'home.med.tracking': '種藥物追蹤中',
      'home.med.go': '前往服藥 →',
      'home.mood.empty': '尚未記錄心情，按下方按鈕分享今天的感覺',
      'home.mood.error': '分享你今天的感受吧',
      'home.mood.go': '記錄心情 →',
      'home.mood.update': '更新電量 →',
      'home.mood.latestAvg': '最新電量 · 7 天平均 {avg}',
      'home.section.label': '功能拼圖',
      'home.card.symptoms.title': '症狀分析',
      'home.card.symptoms.desc': 'AI 助你釐清身體訊號',
      'home.card.records.title': '我的基本資料',
      'home.card.records.desc': '性別、過敏、慢性病… 看診時帶著走',
      'home.card.doctors.title': '醫師列表',
      'home.card.doctors.desc': '管理你的醫療團隊',
      'home.card.medications.title': '藥物管理',
      'home.card.medications.desc': '拍藥袋、記服藥、追療效',
      'home.card.education.title': '衛教專欄',
      'home.card.education.desc': '溫暖易懂的健康知識',
      'home.card.chat.title': '醫起聊天',
      'home.card.chat.desc': '和小禾聊聊，幫你把感受寫成文章',
      'home.card.settings.title': '系統設定',
      'home.card.settings.desc': '字體、主題、年長版等偏好',
      'home.footer.tagline': '將日常碎片拼起，醫起走出治療的迷霧',
      'home.footer.credit': 'CBL-AICM Lab · Piece by Piece',
      'home.avatarAlt': '{name} 頭像',

      // doctors page
      'doctors.add.title': '新增醫師',
      'doctors.placeholder.name': '醫師姓名',
      'doctors.placeholder.specialty': '專科（例如：內科、外科）',
      'doctors.placeholder.phone': '電話（選填）',
      'doctors.add.submit': '新增',
      'doctors.list.title': '醫師列表',
      'doctors.list.loading': '載入中...',
      'doctors.list.empty': '尚無醫師資料',
      'doctors.delete': '刪除',
      'doctors.delete.confirm': '確定刪除此醫師？',

      // medications page
      'meds.title': '藥物管理',
      'meds.intro.prefix': '拍攝',
      'meds.intro.bold': '藥袋或藥單',
      'meds.intro.suffix': '即可自動辨識藥物，記錄服藥、追蹤療效。',
      'meds.recognize.title': '藥袋／藥單辨識',
      'meds.recognize.desc.prefix': '拍攝或上傳',
      'meds.recognize.desc.bold': '藥袋、藥單、處方箋',
      'meds.recognize.desc.suffix': '照片，AI 自動辨識藥物資訊',
      'meds.tips.title': '拍攝小提示',
      'meds.tips.1.prefix': '把藥單／藥袋',
      'meds.tips.1.bold': '放滿整個畫面',
      'meds.tips.1.suffix': '，不要從遠處拍（小字會糊掉）',
      'meds.tips.2': '平放在桌面，避免皺摺、傾斜、反光',
      'meds.tips.3.prefix': '在光線充足處拍攝，盡量讓',
      'meds.tips.3.bold': '藥名、劑量、用法',
      'meds.tips.3.suffix': '清楚可讀',
      'meds.tips.4': '多包藥袋請一次拍一包；長條藥單可一次完整入鏡',
      'meds.btn.capture': '拍攝藥袋／藥單',
      'meds.btn.upload': '上傳照片',
      'meds.btn.manual': '手動輸入',
      'meds.manual.hint': '直接填寫藥物資訊，按「加入我的藥物」即可寫入。',
      'meds.list.title': '我的藥物',
      'meds.list.refresh': '重新整理',
      'meds.list.loading': '載入中...',
      'meds.list.empty': '尚無藥物紀錄，拍攝藥袋開始記錄吧！',
      'meds.checkin.title': '服藥追蹤提醒',
      'meds.improvement.title': '每日改善',
      'meds.improvement.desc': '服藥率 + 療效 合成的每日改善分數',
      'meds.stats.title': '服藥統計',
      'meds.report.title': '回診報告',
      'meds.report.desc': '產出藥物管理報告供下次回診使用',
      'meds.report.days7': '最近 7 天',
      'meds.report.days14': '最近 14 天',
      'meds.report.days30': '最近 30 天',
      'meds.report.days90': '最近 90 天',
      'meds.report.generate': '產出報告',
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

      // home page
      'home.greet.morning': 'Good morning',
      'home.greet.afternoon': 'Good afternoon',
      'home.greet.evening': 'Good evening',
      'home.greet.fallbackName': 'friend',
      'home.calm.0': 'Every small step is the start of caring for yourself',
      'home.calm.1': 'Health is a puzzle pieced together one bit at a time',
      'home.calm.2': "Take it slow — we're walking this with you",
      'home.calm.3': 'Take good care of yourself today too',
      'home.calm.4': 'Log each piece, and you become whole',
      'home.calm.5': "You're not alone — we're always here",
      'home.tip.0': "Take three deep breaths and let your shoulders relax. You're doing great.",
      'home.tip.1': 'Sip a glass of warm water — the simplest kindness for your body.',
      'home.tip.2': 'Did you take your meds on time today? Every on-time dose is self-care.',
      'home.tip.3': 'A 10-minute walk in the sun is the best vitamin.',
      'home.tip.4': 'Write down how you feel — emotions are part of the health puzzle too.',
      'home.tip.5': 'Put the phone down before bed and let your brain rest.',
      'home.tip.6': 'Talk to someone close to you — connection heals.',
      'home.tip.7': 'You don\'t need to be perfect, just a little better each day.',
      'home.weekday.prefix': '',
      'home.weekday.0': 'Sunday',
      'home.weekday.1': 'Monday',
      'home.weekday.2': 'Tuesday',
      'home.weekday.3': 'Wednesday',
      'home.weekday.4': 'Thursday',
      'home.weekday.5': 'Friday',
      'home.weekday.6': 'Saturday',
      'home.visit.set': 'Set next visit',
      'home.visit.label': 'Next visit',
      'home.visit.editTitle': 'Click to edit',
      'home.visit.clearTitle': 'Clear',
      'home.visit.daysLeft': '{n} days left',
      'home.visit.today': "It's today!",
      'home.visit.daysAgo': '{n} days ago',
      'home.quick.symptoms': 'Log Symptoms',
      'home.quick.meds': 'Med Check-in',
      'home.quick.records': 'Profile',
      'home.quick.education': 'Health Edu',
      'home.ov.meds': "Today's Meds",
      'home.ov.mood': "Today's Mood",
      'home.ov.tip': 'Wellness Tip',
      'home.ov.loading': 'Loading...',
      'home.med.empty': 'No medications yet — start logging from Medications',
      'home.med.error': 'Start tracking your first medication',
      'home.med.tracking': 'medications tracked',
      'home.med.go': 'Go to Meds →',
      'home.mood.empty': 'No mood logged yet — tap below to share how you feel',
      'home.mood.error': 'Share how you feel today',
      'home.mood.go': 'Log mood →',
      'home.mood.update': 'Update battery →',
      'home.mood.latestAvg': 'Latest · 7-day avg {avg}',
      'home.section.label': 'Feature Pieces',
      'home.card.symptoms.title': 'Symptom Analysis',
      'home.card.symptoms.desc': 'AI helps you read your body signals',
      'home.card.records.title': 'My Profile',
      'home.card.records.desc': 'Gender, allergies, chronic conditions — bring them to your visit',
      'home.card.doctors.title': 'Doctor List',
      'home.card.doctors.desc': 'Manage your care team',
      'home.card.medications.title': 'Medication Manager',
      'home.card.medications.desc': 'Snap your pill bag, log doses, track effect',
      'home.card.education.title': 'Health Education',
      'home.card.education.desc': 'Warm, easy-to-understand health knowledge',
      'home.card.chat.title': 'Med Chat',
      'home.card.chat.desc': 'Chat with Xiaohe — turn feelings into a story',
      'home.card.settings.title': 'Settings',
      'home.card.settings.desc': 'Fonts, theme, senior mode and more',
      'home.footer.tagline': "Piece together everyday fragments, walk out of the treatment fog together",
      'home.footer.credit': 'CBL-AICM Lab · Piece by Piece',
      'home.avatarAlt': "{name}'s avatar",

      // doctors page
      'doctors.add.title': 'Add Doctor',
      'doctors.placeholder.name': 'Doctor name',
      'doctors.placeholder.specialty': 'Specialty (e.g. Internal Medicine, Surgery)',
      'doctors.placeholder.phone': 'Phone (optional)',
      'doctors.add.submit': 'Add',
      'doctors.list.title': 'Doctor List',
      'doctors.list.loading': 'Loading...',
      'doctors.list.empty': 'No doctors yet',
      'doctors.delete': 'Delete',
      'doctors.delete.confirm': 'Delete this doctor?',

      // medications page
      'meds.title': 'Medication Manager',
      'meds.intro.prefix': 'Snap a photo of your ',
      'meds.intro.bold': 'pill bag or prescription',
      'meds.intro.suffix': ' to auto-recognize meds, log doses, and track efficacy.',
      'meds.recognize.title': 'Pill Bag / Prescription Scan',
      'meds.recognize.desc.prefix': 'Take or upload a photo of your ',
      'meds.recognize.desc.bold': 'pill bag, prescription, or Rx slip',
      'meds.recognize.desc.suffix': ' — AI extracts the medication info.',
      'meds.tips.title': 'Photo tips',
      'meds.tips.1.prefix': 'Have the bag / slip ',
      'meds.tips.1.bold': 'fill the frame',
      'meds.tips.1.suffix': ' — don\'t shoot from far (small text gets blurry).',
      'meds.tips.2': 'Lay flat on a table — avoid creases, tilt, and glare.',
      'meds.tips.3.prefix': 'Shoot in bright light so the ',
      'meds.tips.3.bold': 'name, dose, and directions',
      'meds.tips.3.suffix': ' are clearly readable.',
      'meds.tips.4': 'Multiple pill bags: photograph one at a time. A long prescription can fit in a single frame.',
      'meds.btn.capture': 'Take Photo',
      'meds.btn.upload': 'Upload Photo',
      'meds.btn.manual': 'Manual Entry',
      'meds.manual.hint': 'Enter medication info directly, then tap "Add to My Medications" to save.',
      'meds.list.title': 'My Medications',
      'meds.list.refresh': 'Refresh',
      'meds.list.loading': 'Loading...',
      'meds.list.empty': 'No medications yet — snap a pill bag to get started!',
      'meds.checkin.title': 'Medication Reminders',
      'meds.improvement.title': 'Daily Improvement',
      'meds.improvement.desc': 'Daily score combining adherence and efficacy.',
      'meds.stats.title': 'Adherence Stats',
      'meds.report.title': 'Visit Report',
      'meds.report.desc': 'Generate a medication report for your next visit.',
      'meds.report.days7': 'Last 7 days',
      'meds.report.days14': 'Last 14 days',
      'meds.report.days30': 'Last 30 days',
      'meds.report.days90': 'Last 90 days',
      'meds.report.generate': 'Generate Report',
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

  // t with {placeholder} substitution. Example:
  //   tf('home.visit.daysLeft', { n: 8 })  →  '8 days left'
  function tf(key, vars, lang) {
    let s = t(key, lang);
    if (vars) {
      for (const k in vars) {
        s = s.split('{' + k + '}').join(String(vars[k]));
      }
    }
    return s;
  }

  function applyI18n(root) {
    const lang = getLang();
    const scope = root || document;

    scope.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      const val = t(key, lang);
      // 支援字典裡用 <br> / <br/> 換行；不走 innerHTML（避免 XSS sink），
      // 拆字串後用 text node + <br> element 組回去。
      if (val.indexOf('<br>') >= 0 || val.indexOf('<br/>') >= 0) {
        el.textContent = '';
        const parts = val.split(/<br\s*\/?>/i);
        parts.forEach((part, idx) => {
          if (idx > 0) el.appendChild(document.createElement('br'));
          if (part) el.appendChild(document.createTextNode(part));
        });
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
    tf,
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
