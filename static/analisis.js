/* Análisis de las reclamaciones en el navegador.
 *
 * Ejecuta las 3 tecnologías sobre las reclamaciones (por la ruta de revisión de la app) y las compara con la referencia
 * (el revisor por reglas). Todo vive en la memoria de esta página: no se guarda en archivo, base de datos ni
 * localStorage/sessionStorage, y desaparece al refrescar.
 */
(function () {
  const A = window.Agente, esc = A.esc, num = A.num;
  const T = ['pydantic_ai', 'claude_sdk', 'langgraph'];
  const NOM = A.NOMBRES;
  const V = ['Aprobado', 'Validar', 'Rechazado'];
  const $ = id => document.getElementById(id);
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const valida = r => !!r && !r.error && !(r.stats && r.stats.fallback);

  let ref = [], res = {}, corriendo = false, parar = false, pendiente = null;

  /* ---------------------------------------------------------------- ejecución por fases */
  async function correr(id, arq) {
    for (let intento = 0; intento < 40 && !parar; intento++) {
      try {
        res[id][arq] = await A.ejecutar(id, arq, $('ana-modelo') ? $('ana-modelo').value : null, null);
        break;
      } catch (e) {
        if (/demasiadas revisiones/i.test(e.message)) { await sleep(4000); continue; }  // cupo de la app lleno: esperar
        res[id][arq] = {error: e.message};
        break;
      }
    }
    pintarPronto();
  }

  async function fase(nombre, techs, workers) {
    const cola = ref.flatMap(c => techs.filter(t => !valida(res[c.id][t])).map(t => [c.id, t]));
    $('ana-fase').hidden = false;
    $('ana-fase').textContent = 'Fase ' + nombre + ': ' + cola.length + ' corrida' + (cola.length === 1 ? '' : 's') + ' (' + workers + ' a la vez)';
    let i = 0;
    await Promise.all(Array.from({length: workers}, async () => {
      while (!parar && i < cola.length) { const [id, t] = cola[i++]; await correr(id, t); }
    }));
  }

  async function iniciar() {
    // El campo limita cuántas reclamaciones se ejecutan: entero entre 1 y el máximo del campo (por defecto, el valor inicial).
    const campo = $('ana-n'), tope = +campo.max || 1;
    let n = parseInt(campo.value, 10);
    if (!Number.isFinite(n)) n = +campo.defaultValue || 1;
    n = Math.max(1, Math.min(n, tope));
    campo.value = n;  // se muestra el valor realmente aplicado
    corriendo = true; parar = false;
    $('ana-iniciar').disabled = true; $('ana-parar').hidden = false;
    $('ana-fase').hidden = false; $('ana-fase').textContent = 'Calculando la referencia…';
    ref = (await (await fetch('/api/referencia')).json()).slice(0, n);
    res = {}; ref.forEach(c => { res[c.id] = {}; });
    $('ana-resultados').hidden = false;
    pintar();
    // Ejecución SECUENCIAL: una sola corrida cada vez, reclamación a reclamación (Pydantic AI → Claude Agent SDK → LangGraph).
    await fase('1 (secuencial: Pydantic AI → Claude Agent SDK → LangGraph)', T, 1);
    if (!parar) await fase('2 (repetir lo que falló, de una en una)', T, 1);
    corriendo = false;
    $('ana-iniciar').disabled = false; $('ana-parar').hidden = true;
    $('ana-fase').textContent = parar ? 'Detenido.' : 'Terminado.';
    pintar();
  }

  /* ---------------------------------------------------------------- cálculos */
  const mediana = a => { const s = [...a].sort((x, y) => x - y); return s.length ? s[Math.floor(s.length / 2)] : 0; };
  const p95 = a => { const s = [...a].sort((x, y) => x - y); return s.length ? s[Math.min(s.length - 1, Math.floor(s.length * 0.95))] : 0; };
  const media = a => a.length ? a.reduce((x, y) => x + y, 0) / a.length : 0;
  const pct = (a, b) => b ? Math.round(100 * a / b) + ' %' : '—';

  function calcular() {
    const filas = ref.map(c => ({c, a: res[c.id] || {}}));
    const porTec = {};
    T.forEach(t => {
      const runs = filas.filter(f => f.a[t]);
      const buenas = runs.filter(f => valida(f.a[t]));
      const o = {hechas: runs.length, buenas: buenas.length, fallos: runs.length - buenas.length, ok: 0, aprobIndebida: 0, rechazoIndebido: 0,
                 validarDeMas: 0, validarDeMenos: 0, impOk: 0, impN: 0, seg: [], llam: [], tin: [], tout: [], conf: {}, lineas: {}, errores: []};
      V.forEach(r => V.forEach(p => { o.conf[r + '|' + p] = 0; }));
      buenas.forEach(f => {
        const a = f.a[t], r = f.c.veredicto, p = a.veredicto;
        o.ok += p === r; o.conf[r + '|' + p]++;
        o.aprobIndebida += (p === 'Aprobado' && r !== 'Aprobado'); o.rechazoIndebido += (p === 'Rechazado' && r !== 'Rechazado');
        o.validarDeMas += (p === 'Validar' && r !== 'Validar'); o.validarDeMenos += (r === 'Validar' && p !== 'Validar');
        if (p === 'Aprobado' && r === 'Aprobado') { o.impN++; o.impOk += a.importeAPagar === f.c.importe; }
        o.seg.push(a.stats.duracionSeg); o.llam.push(a.stats.llamadas); o.tin.push(a.stats.tokensEntrada); o.tout.push(a.stats.tokensSalida);
        (a.lineas || []).forEach(l => {
          if (!(l.id in f.c.lineas)) return;
          const x = o.lineas[l.id] || (o.lineas[l.id] = {ok: 0, n: 0}); x.n++; x.ok += l.estado === f.c.lineas[l.id];
        });
        if (p !== r) {
          const mal = (a.lineas || []).filter(l => l.id in f.c.lineas && l.estado !== f.c.lineas[l.id]).map(l => l.id);
          const ex = (a.lineas || []).find(l => l.id === 'exclusiones');
          o.errores.push({id: f.c.id, ref: r, ag: p, motivo: a.motivo || '',
                          causa: mal.length ? 'línea mal leída: ' + mal.join(', ') : (ex && ex.estado !== 'cumple' ? 'exclusiones: ' + ex.estado : 'veredicto ajustado')});
        }
      });
      porTec[t] = o;
    });
    const completas = filas.filter(f => T.every(t => valida(f.a[t])));
    const v = (f, t) => f.a[t].veredicto;
    const unanimes = completas.filter(f => new Set(T.map(t => v(f, t))).size === 1);
    const pares = [[0, 1], [0, 2], [1, 2]].map(([i, j]) => ({a: T[i], b: T[j], ig: completas.filter(f => v(f, T[i]) === v(f, T[j])).length}));
    const mayoria = completas.filter(f => {
      const c = {}; T.forEach(t => { c[v(f, t)] = (c[v(f, t)] || 0) + 1; });
      return Object.entries(c).sort((x, y) => y[1] - x[1])[0][0] === f.c.veredicto;
    }).length;
    return {filas, porTec, completas, unanimes, unanimesOk: unanimes.filter(f => v(f, T[0]) === f.c.veredicto).length, pares, mayoria};
  }

  /* ---------------------------------------------------------------- pintado */
  function pintarPronto() { if (!pendiente) pendiente = setTimeout(() => { pendiente = null; pintar(); }, 400); }

  const badge = (x) => x ? '<span class="badge v-' + esc(x) + '">' + esc(x) + '</span>' : '<span class="muted">…</span>';

  function pintar() {
    if (!ref.length) return;
    const R = calcular();
    // progreso
    $('ana-prog').innerHTML = T.map(t => {
      const o = R.porTec[t], total = ref.length;
      return '<div><b>' + esc(NOM[t]) + '</b><div class="barra"><i style="width:' + Math.round(100 * o.hechas / total) + '%"></i></div>'
        + '<small>' + o.hechas + ' / ' + total + ' corridas · ' + o.fallos + ' fallo' + (o.fallos === 1 ? '' : 's') + '</small></div>';
    }).join('');
    // resumen
    let h = '<div class="scroll"><table class="simple"><thead><tr><th>Tecnología</th><th>Corridas válidas</th><th>Veredicto correcto</th><th>Aprobaciones indebidas</th>'
      + '<th>Rechazos indebidos</th><th>Validar de más</th><th>Validar de menos</th><th>Importe exacto</th><th>Mediana · p95</th><th>Llamadas</th><th>Tokens ent.</th></tr></thead><tbody>';
    T.forEach(t => {
      const o = R.porTec[t];
      h += '<tr><td><b>' + esc(NOM[t]) + '</b></td><td>' + o.buenas + '/' + o.hechas + '</td><td><b>' + o.ok + '/' + o.buenas + ' (' + pct(o.ok, o.buenas) + ')</b></td>'
        + '<td>' + o.aprobIndebida + '</td><td>' + o.rechazoIndebido + '</td><td>' + o.validarDeMas + '</td><td>' + o.validarDeMenos + '</td>'
        + '<td>' + o.impOk + '/' + o.impN + '</td><td>' + num(mediana(o.seg)) + ' · ' + num(p95(o.seg)) + ' s</td><td>' + num(media(o.llam)) + '</td><td>' + num(media(o.tin), 0) + '</td></tr>';
    });
    $('ana-resumen').innerHTML = h + '</tbody></table></div><p class="muted small">Aprobación indebida = el agente aprueba y la referencia no (pagar lo que no toca): es el error más grave. '
      + 'Las corridas que cayeron a reglas o fallaron no cuentan como decisión del agente.</p>';
    // coinciden las 3
    const n = R.completas.length;
    $('ana-igual').innerHTML = n ? '<p><b>Los 3 decidieron IGUAL en ' + R.unanimes.length + ' de ' + n + ' reclamaciones (' + pct(R.unanimes.length, n) + ').</b> De esas, '
      + R.unanimesOk + ' coinciden con la referencia.</p><ul class="plain">' + R.pares.map(p => '<li>' + esc(NOM[p.a]) + ' y ' + esc(NOM[p.b]) + ': ' + p.ig + '/' + n + ' (' + pct(p.ig, n) + ')</li>').join('')
      + '</ul><p>El voto de la mayoría (2 de 3) coincide con la referencia en ' + R.mayoria + '/' + n + ' (' + pct(R.mayoria, n) + ').</p>'
      : '<p class="muted">Aún no hay reclamaciones con las 3 corridas válidas.</p>';
    // matrices de confusión
    $('ana-conf').innerHTML = T.map(t => {
      const o = R.porTec[t];
      return '<div><b>' + esc(NOM[t]) + '</b><table class="simple"><thead><tr><th>ref \\ agente</th>' + V.map(x => '<th>' + x + '</th>').join('') + '</tr></thead><tbody>'
        + V.map(r => '<tr><th>' + r + '</th>' + V.map(p => '<td class="' + (r === p ? 'diag' : 'fuera') + (o.conf[r + '|' + p] ? '' : ' cero') + '">' + o.conf[r + '|' + p] + '</td>').join('') + '</tr>').join('')
        + '</tbody></table></div>';
    }).join('');
    // por línea
    const ids = [...new Set(R.filas.flatMap(f => Object.keys(f.c.lineas)))].sort();
    $('ana-lineas').innerHTML = '<div class="scroll"><table class="simple"><thead><tr><th>Comprobación</th>' + T.map(t => '<th>' + esc(NOM[t]) + '</th>').join('') + '</tr></thead><tbody>'
      + ids.map(id => '<tr><td class="mono">' + esc(id) + '</td>' + T.map(t => { const x = R.porTec[t].lineas[id]; return '<td>' + (x ? x.ok + '/' + x.n + ' (' + pct(x.ok, x.n) + ')' : '—') + '</td>'; }).join('') + '</tr>').join('')
      + '</tbody></table></div><p class="muted small">La comprobación «exclusiones» no tiene referencia (solo la juzga el LLM) y no aparece aquí.</p>';
    // tabla de reclamaciones
    const solo = $('ana-solo-dif').checked;
    let rows = '<thead><tr><th>ID</th><th>Tipo de reclamación</th><th>Referencia</th>' + T.map(t => '<th>' + esc(NOM[t]) + '</th>').join('') + '<th>¿Los 3 igual?</th></tr></thead><tbody>';
    let mostradas = 0;
    R.filas.forEach(f => {
      const todas = T.every(t => valida(f.a[t])), vs = T.map(t => valida(f.a[t]) ? f.a[t].veredicto : null);
      const igual = todas && new Set(vs).size === 1, distintoRef = vs.some(x => x && x !== f.c.veredicto);
      const dif = (todas && !igual) || distintoRef;
      if (solo && !dif) return;
      mostradas++;
      rows += '<tr class="' + (dif ? 'dif' : '') + '"><td class="mono"><a href="/reclamaciones/' + encodeURIComponent(f.c.id) + '" target="_blank" rel="noopener">' + esc(f.c.id) + '</a></td><td>' + esc(f.c.tipo) + '</td><td>' + badge(f.c.veredicto) + '</td>'
        + T.map((t, i) => { const a = f.a[t]; return '<td class="' + (vs[i] && vs[i] !== f.c.veredicto ? 'mal' : '') + '">' + (a ? (valida(a) ? badge(a.veredicto) : '<span class="muted" title="' + esc(a.error || a.nota || '') + '">sin LLM / error</span>') : '<span class="muted">…</span>') + '</td>'; }).join('')
        + '<td>' + (todas ? (igual ? 'SÍ' : 'NO ◄') : '—') + '</td></tr>';
    });
    $('ana-tabla').innerHTML = rows + (mostradas ? '' : '<tr><td colspan="7" class="ana-tabla-vacia muted">Ninguna reclamación cumple el filtro.</td></tr>') + '</tbody>';
    // errores
    const errs = T.flatMap(t => R.porTec[t].errores.map(e => ({t, ...e}))).sort((a, b) => a.id.localeCompare(b.id));
    $('ana-errores').innerHTML = errs.length ? '<div class="scroll"><table class="simple"><thead><tr><th>ID</th><th>Tecnología</th><th>Referencia</th><th>Agente</th><th>Causa</th><th>Motivo del agente</th></tr></thead><tbody>'
      + errs.map(e => '<tr><td class="mono">' + esc(e.id) + '</td><td>' + esc(NOM[e.t]) + '</td><td>' + badge(e.ref) + '</td><td>' + badge(e.ag) + '</td><td>' + esc(e.causa) + '</td><td class="muted">' + esc(e.motivo.slice(0, 160)) + '</td></tr>').join('')
      + '</tbody></table></div>' : '<p class="muted">Sin errores de veredicto en las corridas válidas.</p>';
  }

  // Estimación en vivo de lo que supone el máximo elegido (3 tecnologías por reclamación, ~1 min por reclamación en secuencia).
  function estimacion() {
    const campo = $('ana-n'), tope = +campo.max || 1;
    let n = parseInt(campo.value, 10);
    const fuera = !Number.isFinite(n) || n < 1 || n > tope;
    if (!Number.isFinite(n)) n = +campo.defaultValue || 1;
    n = Math.max(1, Math.min(n, tope));
    $('ana-estimacion').innerHTML = (fuera ? '⚠ Valor fuera de rango: se usará <b>' + n + '</b>. ' : '')
      + 'Se ejecutarán <b>' + n + ' ' + (n === 1 ? 'reclamación' : 'reclamaciones') + '</b> × 3 tecnologías = <b>' + (3 * n) + ' corridas</b>, una cada vez (unos ' + n + ' min).';
  }
  $('ana-n').addEventListener('input', estimacion);
  estimacion();

  $('ana-iniciar').addEventListener('click', iniciar);
  $('ana-parar').addEventListener('click', () => { parar = true; $('ana-fase').textContent = 'Deteniendo… (terminan las corridas en curso)'; });
  $('ana-solo-dif').addEventListener('change', pintar);
})();
