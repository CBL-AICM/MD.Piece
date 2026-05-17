// Browser-side ONNX inference for the Layer-3 model.
//
// Loads pwa/model/model.onnx via onnxruntime-web and exposes
// MDP_Inference.runWindow(features) and MDP_Inference.runPatient(patient, dayEnd).

window.MDP_Inference = (function () {
  let session = null;
  let scaler = null;
  let loading = null;

  async function ensureLoaded() {
    if (session) return;
    if (loading) return loading;
    loading = (async () => {
      // onnxruntime-web WASM files live alongside the umd bundle on the CDN
      ort.env.wasm.wasmPaths =
        'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.18.0/dist/';
      const [s, sc] = await Promise.all([
        ort.InferenceSession.create('model/model.onnx',
                                    { executionProviders: ['wasm'] }),
        fetch('model/scaler.json').then(r => r.json()),
      ]);
      session = s;
      scaler = sc;
    })();
    return loading;
  }

  function sigmoid(x) { return 1 / (1 + Math.exp(-x)); }

  /** Standardise + run inference on one (window_size, n_features) array. */
  async function runWindow(windowMatrix) {
    await ensureLoaded();
    const T = scaler.window_size;
    const F = scaler.feature_names.length;
    if (windowMatrix.length !== T || windowMatrix[0].length !== F) {
      throw new Error(`expected ${T}x${F} matrix, got ${windowMatrix.length}x${windowMatrix[0].length}`);
    }
    const flat = new Float32Array(T * F);
    for (let t = 0; t < T; t++) {
      for (let f = 0; f < F; f++) {
        flat[t * F + f] = (windowMatrix[t][f] - scaler.mean[f]) / scaler.std[f];
      }
    }
    const tensor = new ort.Tensor('float32', flat, [1, T, F]);
    const out = await session.run({ input: tensor });
    return {
      activity_pred: out.reg.data[0],
      flare_prob: sigmoid(out.cls_logit.data[0]),
    };
  }

  /** Convenience: build the last-T-day window for a patient timeseries and run. */
  async function runPatient(patient, dayEnd, overrides = {}) {
    await ensureLoaded();
    const T = scaler.window_size;
    const feats = scaler.feature_names;
    const ts = patient.timeseries;
    // find indices [dayEnd-T .. dayEnd-1]
    const rows = [];
    for (let d = dayEnd - T; d < dayEnd; d++) {
      const r = ts.find(x => x.day === d);
      if (!r) throw new Error(`missing day ${d}`);
      rows.push(r);
    }
    const matrix = rows.map(r => feats.map(f => _featureValue(r, patient, f, overrides)));
    return runWindow(matrix);
  }

  /** Map a feature-name to its numeric value, applying optional override knobs. */
  function _featureValue(row, patient, fname, overrides) {
    // core dynamic columns
    if (fname === 'activity') return row.activity;
    if (fname === 'irreversible_burden') return row.irreversible_burden;
    if (fname === 'n_active_triggers') return row.n_active_triggers;
    if (fname === 'life_event_active') {
      if (overrides.no_life_events) return 0;
      return row.life_event_active;
    }
    if (fname === 'long_tail_active') return row.long_tail_active;
    if (fname === 'dose_any_skipped') {
      if (overrides.perfect_adherence) return 0;
      return row.dose_any_skipped;
    }
    // demographics
    if (fname === 'age') return patient.age;
    if (fname === 'sex_F') return patient.sex === 'F' ? 1 : 0;
    // disease one-hot
    if (fname.startsWith('is_')) {
      return patient.disease_id === fname.slice(3) ? 1 : 0;
    }
    // treatment one-hot on_<tx_id>
    if (fname.startsWith('on_')) {
      const txId = fname.slice(3);
      return patient.treatments.some(t => t.id === txId) ? 1 : 0;
    }
    // biomarkers prefixed bm_
    if (fname.startsWith('bm_')) {
      const col = fname.slice(3);
      return row[col] !== undefined ? row[col] : 0;
    }
    return 0;
  }

  return { ensureLoaded, runWindow, runPatient, get featureNames() {
    return scaler ? scaler.feature_names.slice() : [];
  } };
})();
