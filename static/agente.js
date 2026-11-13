/* Agente de revisión en el navegador.
 *
 * Los resultados son SOLO VIRTUALES: llegan en directo desde el servidor mientras se calculan y viven únicamente
 * en la memoria de esta página. No se guardan en archivo, base de datos, localStorage ni sessionStorage;
 * al refrescar la página todo vuelve al estado inicial.
 */
window.Agente = (function () {
  const NOMBRES = {langgraph: 'LangGraph', pydantic_ai: 'Pydantic AI', claude_sdk: 'Claude Agent SDK',
                   lineas: 'Línea por línea', una_llamada: 'Una sola llamada', reglas: 'Reglas'};
  const TECNOLOGIAS = ['langgraph', 'pydantic_ai', 'claude_sdk'];
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  const num = (n, d = 1) => Number(n).toLocaleString('es-ES', {maximumFractionDigits: d});
  const eur = n => Number(n).toLocaleString('es-ES', {maximumFractionDigits: 0}) + ' €';
  const nombre = a => NOMBRES[a] || a;
  const tecnologiaDe = r => (r.stats.fallback && r.stats.intento) ? r.stats.intento.arquitectura : r.stats.arquitectura;

  /** Ejecuta una revisión y llama a onProgreso({lineas, fase}) mientras avanza. Devuelve el resultado. */
  async function ejecutar(id, arq, modelo, onProgreso) {
    const resp = await fetch('/reclamaciones/' + encodeURIComponent(id) + '/revision', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({arquitectura: arq, modelo: modelo || null})});
    if (!resp.ok) {
      let msg = 'error ' + resp.status;
      try { msg = (await resp.json()).error || msg; } catch (e) { /* sin cuerpo JSON */ }
      throw new Error(msg);
    }
    const lector = resp.body.getReader(), dec = new TextDecoder();
    let buf = '';
    for (;;) {
      const {done, value} = await lector.read();
      if (done) break;
      buf += dec.decode(value, {stream: true});
      let i;
      while ((i = buf.indexOf('\n')) >= 0) {
        const linea = buf.slice(0, i).trim();
        buf = buf.slice(i + 1);
        if (!linea) continue;
        const ev = JSON.parse(linea);
        if (ev.tipo === 'progreso') { if (onProgreso) onProgreso(ev); }
        else if (ev.tipo === 'fin') return ev.resultado;
        else if (ev.tipo === 'error') throw new Error(ev.error);
      }
    }
    throw new Error('La revisión terminó sin resultado');
  }

  function lineasHtml(lineas) {
    return (lineas || []).map(k => `<li class="ln ln-${esc(k.estado)}"><span class="ico"></span><span class="txt">${esc(k.requisito)}<small class="d">${esc(k.detalle)}</small></span><span class="grp">${esc(k.grupo)}</span></li>`).join('');
  }

  function estadisticasLinea(r) {
    const s = r.stats;
    return `⏱ Procesado en <b>${num(s.duracionSeg)} s</b> con <b>${esc(nombre(s.arquitectura))}</b>${s.modelo ? ' (' + esc(s.modelo) + ')' : ''} · ${s.llamadas} llamada${s.llamadas === 1 ? '' : 's'} · ${num(s.tokensEntrada + s.tokensSalida, 0)} tokens${s.fallback ? ' · <span class="tag no">sin LLM: cayó a reglas</span>' : ''}`;
  }

  /** Veredicto, estadísticas y detalle de UNA corrida. */
  function resultadoHtml(r) {
    const s = r.stats;
    let h = `<div class="verdict v-${esc(r.veredicto)}"><span class="vlabel">Veredicto</span><b>${esc(r.veredicto)}</b>`;
    if (r.veredicto === 'Aprobado' && r.importeAPagar != null) h += `<span class="vamount">Importe a pagar: ${eur(r.importeAPagar)}</span>`;
    h += `</div><p class="vstats">${estadisticasLinea(r)} <a href="#estadisticas-corrida">ver detalle</a></p>`;
    h += `<p class="vmotivo">${esc(r.motivo)}</p>`;
    if (r.veredicto === 'Validar') h += `<label class="vcomment"><span>Comentario del agente</span><textarea readonly rows="4">${esc(r.comentario)}</textarea></label>`;
    if (r.nota) h += `<p class="reject-box">${esc(r.nota)}</p>`;
    h += `<h3 id="estadisticas-corrida">Estadísticas de la corrida</h3><div class="statgrid">`
      + `<div><span>Duración</span><b>${num(s.duracionSeg)} s</b></div>`
      + `<div><span>Arquitectura</span><b>${esc(nombre(s.arquitectura))}</b></div>`
      + `<div><span>Modelo</span><b>${esc(s.modelo || 'sin LLM')}</b></div>`
      + `<div><span>Llamadas al LLM</span><b>${s.llamadas}</b></div>`
      + `<div><span>Tokens (entrada / salida)</span><b>${num(s.tokensEntrada, 0)} / ${num(s.tokensSalida, 0)}</b></div>`
      + `<div><span>Acuerdo con las reglas</span><b>${s.acuerdoVeredicto == null ? '—' : (s.acuerdoVeredicto ? 'Sí' : 'No (reglas: ' + esc(s.veredictoReglas) + ')')}${s.lineasComparables ? ' · líneas ' + s.lineasAcuerdo + '/' + s.lineasComparables : ''}</b></div></div>`;
    if (s.tiempos && s.tiempos.length > 1) {
      const mx = Math.max(...s.tiempos.map(t => t.seg)) || 1;
      h += `<details class="clause-box"><summary><b>Tiempo por línea</b><span class="muted">veredicto: ${num(s.veredictoSeg)} s</span></summary><table class="mini bars"><tbody>`
        + s.tiempos.map(t => `<tr><td class="mono">${esc(t.id)}</td><td><span class="bar" style="width:${Math.round(100 * t.seg / mx)}%"></span></td><td class="num mono">${num(t.seg, 2)} s</td></tr>`).join('')
        + `</tbody></table></details>`;
    }
    return h;
  }

  /** Compara la última corrida de cada tecnología (las 3) sobre una misma reclamación. */
  function comparativa(corridas) {
    const ultima = {};
    corridas.forEach(c => { const t = tecnologiaDe(c); if (TECNOLOGIAS.includes(t)) ultima[t] = c; });
    const cols = TECNOLOGIAS.map(t => { const c = ultima[t]; return {arq: t, corrida: c, disponible: !!(c && !c.stats.fallback), nota: (c && c.stats.fallback) ? c.nota : null}; });
    const ok = cols.filter(k => k.disponible);
    const lineas = [], vistas = {};
    ok.forEach(k => (k.corrida.lineas || []).forEach(l => {
      if (!vistas[l.id]) { vistas[l.id] = {id: l.id, requisito: l.requisito, estados: {}}; lineas.push(vistas[l.id]); }
      vistas[l.id].estados[k.arq] = l.estado;
    }));
    lineas.forEach(l => { l.difiere = new Set(Object.values(l.estados)).size > 1; });
    const dur = {};
    ok.forEach(k => { dur[k.arq] = k.corrida.stats.duracionSeg; });
    return {cols, lineas, n: ok.length, difLineas: lineas.filter(l => l.difiere).length,
            coinciden: ok.length > 1 ? new Set(ok.map(k => k.corrida.veredicto)).size === 1 : null,
            masRapida: ok.length > 1 ? Object.keys(dur).reduce((a, b) => dur[a] <= dur[b] ? a : b) : null};
  }

  function comparacionHtml(corridas) {
    const c = comparativa(corridas);
    let h = '<h2>Comparación de las 3 tecnologías</h2>';
    if (!c.n && !c.cols.some(k => k.corrida)) return h + '<p class="muted">Aún no hay corridas de LangGraph, Pydantic AI ni Claude Agent SDK en esta página. Pulsa «Ejecutar las 3 y comparar».</p>';
    if (c.coinciden !== null) h += `<p class="agree ${c.coinciden ? 'ok' : 'diff'}">${c.coinciden ? '✓ Las ' + c.n + ' tecnologías coinciden en el veredicto' : '⚠ Las tecnologías <b>no coinciden</b> en el veredicto'}${c.difLineas ? ' · ' + c.difLineas + ' línea' + (c.difLineas > 1 ? 's' : '') + ' con resultados distintos' : ''}.</p>`;
    const celdas = f => c.cols.map(k => `<td${f.cls ? ' class="' + f.cls(k) + '"' : ''}>${f.v(k)}</td>`).join('');
    const sdisp = (k, fn) => k.disponible ? fn(k.corrida) : '—';
    h += `<div class="scroll"><table class="cmp3"><thead><tr><th></th>${c.cols.map(k => `<th>${esc(nombre(k.arq))}${k.disponible ? '<small>' + esc(k.corrida.stats.modelo || '') + '</small>' : ''}</th>`).join('')}</tr></thead><tbody>`;
    const fila = (t, f) => `<tr><th>${t}</th>${celdas(f)}</tr>`;
    h += fila('Veredicto', {v: k => k.disponible ? `<span class="badge v-${esc(k.corrida.veredicto)}">${esc(k.corrida.veredicto)}</span>` : (k.corrida ? `<span class="muted">No disponible</span><small class="d">${esc(k.nota)}</small>` : '<span class="muted">Sin ejecutar</span>')});
    h += fila('Importe a pagar', {cls: () => 'mono', v: k => sdisp(k, r => r.veredicto === 'Aprobado' && r.importeAPagar != null ? eur(r.importeAPagar) : '—')});
    h += fila('Duración', {cls: k => 'mono' + (k.arq === c.masRapida ? ' best' : ''), v: k => sdisp(k, r => num(r.stats.duracionSeg) + ' s') + (k.arq === c.masRapida ? ' ⚡' : '')});
    h += fila('Llamadas al modelo', {v: k => sdisp(k, r => r.stats.llamadas)});
    h += fila('Tokens (entrada / salida)', {cls: () => 'mono', v: k => sdisp(k, r => num(r.stats.tokensEntrada, 0) + ' / ' + num(r.stats.tokensSalida, 0))});
    h += fila('Acuerdo con las reglas', {v: k => sdisp(k, r => r.stats.acuerdoVeredicto == null ? '—' : (r.stats.acuerdoVeredicto ? 'Sí' : 'No (reglas: ' + esc(r.stats.veredictoReglas) + ')') + (r.stats.lineasComparables ? ' · ' + r.stats.lineasAcuerdo + '/' + r.stats.lineasComparables + ' líneas' : ''))});
    h += fila('Motivo', {cls: () => 'motivo', v: k => sdisp(k, r => esc(r.motivo))});
    if (c.lineas.length) {
      h += `<tr class="sep"><th colspan="4">Resultado por línea</th></tr>`;
      h += c.lineas.map(l => `<tr class="${l.difiere ? 'dif' : ''}"><th>${esc(l.requisito)}</th>${c.cols.map(k => { const e = l.estados[k.arq]; return `<td>${e ? `<span class="eico e-${esc(e)}" title="${esc(e.replace('_', ' '))}"></span>` : '—'}</td>`; }).join('')}</tr>`).join('');
    }
    return h + '</tbody></table></div>';
  }

  /** Tabla con todas las corridas hechas en esta página (la más reciente primero). */
  function corridasHtml(corridas) {
    return '<h2>Corridas de esta reclamación <span class="muted">· solo en esta página</span></h2><table class="mini cmp"><thead><tr><th>Hora</th><th>Arquitectura</th><th>Modelo</th><th>Veredicto</th><th class="num">Duración</th><th class="num">Llamadas</th><th class="num">Tokens</th></tr></thead><tbody>'
      + corridas.slice().reverse().map(r => `<tr><td class="mono">${esc(r._hora.toLocaleTimeString('es-ES'))}</td><td>${esc(nombre(r.stats.arquitectura))}</td><td>${esc(r.stats.modelo || '—')}${r.stats.fallback ? ' <span class="tag no">fallback</span>' : ''}</td><td><span class="badge v-${esc(r.veredicto)}">${esc(r.veredicto)}</span></td><td class="num mono">${num(r.stats.duracionSeg)} s</td><td class="num">${r.stats.llamadas}</td><td class="num mono">${num(r.stats.tokensEntrada + r.stats.tokensSalida, 0)}</td></tr>`).join('')
      + '</tbody></table>';
  }

  /** Resumen de varias corridas (una por reclamación) para el listado. Devuelve [[título, valor], ...]. */
  function resumen(resultados) {
    const todas = resultados.filter(r => r && r.stats);
    if (!todas.length) return [];
    const dur = todas.map(r => r.stats.duracionSeg).sort((a, b) => a - b);
    const suma = f => todas.reduce((t, r) => t + (f(r) || 0), 0);
    const v = k => todas.filter(r => r.veredicto === k).length;
    const comp = todas.filter(r => r.stats.acuerdoVeredicto != null);
    return [
      ['Reclamaciones procesadas', todas.length],
      ['Veredictos (A / R / V)', v('Aprobado') + ' / ' + v('Rechazado') + ' / ' + v('Validar')],
      ['Duración total', num(suma(r => r.stats.duracionSeg)) + ' s'],
      ['Duración media · mediana · máx.', num(suma(r => r.stats.duracionSeg) / todas.length) + ' · ' + num(dur[Math.floor(dur.length / 2)]) + ' · ' + num(dur[dur.length - 1]) + ' s'],
      ['Llamadas al modelo', num(suma(r => r.stats.llamadas), 0)],
      ['Tokens (entrada / salida)', num(suma(r => r.stats.tokensEntrada), 0) + ' / ' + num(suma(r => r.stats.tokensSalida), 0)],
      ['Acuerdo con las reglas', comp.length ? Math.round(100 * comp.filter(r => r.stats.acuerdoVeredicto).length / comp.length) + ' % (' + comp.length + ')' : '—'],
      ['Sin LLM (cayeron a reglas)', todas.filter(r => r.stats.fallback).length],
    ];
  }

  return {NOMBRES, TECNOLOGIAS, esc, num, nombre, ejecutar, lineasHtml, resultadoHtml, comparacionHtml, corridasHtml, resumen};
})();
