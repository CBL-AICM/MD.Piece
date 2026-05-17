// Cohort data layer — fetches cohort.json once, caches in IndexedDB.

const DB_NAME = 'mdpiece';
const STORE = 'cohort';
const KEY = 'latest';

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = e => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE);
    };
    req.onsuccess = e => resolve(e.target.result);
    req.onerror = () => reject(req.error);
  });
}

async function idbGet() {
  try {
    const db = await openDB();
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readonly');
      const r = tx.objectStore(STORE).get(KEY);
      r.onsuccess = () => resolve(r.result);
      r.onerror = () => reject(r.error);
    });
  } catch (e) { return null; }
}

async function idbSet(value) {
  try {
    const db = await openDB();
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite');
      tx.objectStore(STORE).put(value, KEY);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } catch (e) { /* ignore */ }
}

window.MDP = {
  cohort: null,
  flatPatients: [],
  async load() {
    const res = await fetch('data/cohort.json');
    if (!res.ok) throw new Error(`fetch failed ${res.status}`);
    const data = await res.json();
    this.cohort = data;
    this.flatPatients = [];
    for (const did of Object.keys(data.diseases)) {
      for (const p of data.diseases[did].patients) {
        this.flatPatients.push(p);
      }
    }
    await idbSet(data);
    return data;
  },
  async loadCached() {
    const cached = await idbGet();
    if (cached) {
      this.cohort = cached;
      this.flatPatients = [];
      for (const did of Object.keys(cached.diseases)) {
        for (const p of cached.diseases[did].patients) this.flatPatients.push(p);
      }
      return cached;
    }
    return null;
  },
  filter({ disease, ageBin, sex, responder }) {
    return this.flatPatients.filter(p =>
      (!disease || p.disease_id === disease) &&
      (!ageBin || p.age_bin === ageBin) &&
      (!sex || p.sex === sex) &&
      (!responder || p.responder_class === responder)
    );
  },
};
