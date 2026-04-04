'use strict';

const $ = id => document.getElementById(id);
let aChart=null, dChart=null, cmpChart=null, corrChart=null;

const POLL_CFG = {
  aqi:  {lbl:'AQI',    color:'#4ba9ff'},
  pm25: {lbl:'PM₂.₅',  color:'#e74c3c'},
  pm10: {lbl:'PM₁₀',   color:'#e67e00'},
  no2:  {lbl:'NO₂',    color:'#8e44ad'},
  so2:  {lbl:'SO₂',    color:'#2980b9'},
  o3:   {lbl:'O₃',     color:'#16a085'},
  co:   {lbl:'CO',     color:'#7f8c8d'},
};

async function loadAnalytics() {
  const city = $('analyticsCitySelect')?.value || '';
  const poll = $('analyticsPollSelect')?.value || 'aqi';

  try {
    const url = city ? `/api/historical?city=${encodeURIComponent(city)}&hours=48&fresh=1` : '/api/historical?hours=48&fresh=1';
    const r = await fetch(url);
    const d = await r.json();
    if (d.error) return;

    const cfg = POLL_CFG[poll] || POLL_CFG.aqi;
    const vals = d[poll] || d.aqi;

    // Trend chart
    if (aChart) { aChart.destroy(); aChart=null; }
    aChart = new Chart($('analyticsChart'), {
      type:'line',
      data:{
        labels: d.timestamps,
        datasets:[{
          label: cfg.lbl, data: vals,
          borderColor: cfg.color, backgroundColor: cfg.color+'15',
          fill:true, tension:.4, pointRadius:2, borderWidth:2,
        }]
      },
      options:{
        responsive:true, maintainAspectRatio:false,
        plugins:{ legend:{display:false}, tooltip:{mode:'index',intersect:false, backgroundColor:'rgba(255,255,255,.96)', titleColor:'#1a1d2e', bodyColor:'#4a5568', borderColor:'#e8eaed', borderWidth:1} },
        scales:{
          x:{ ticks:{color:'#9ca3af', font:{size:10}, maxTicksLimit:12}, grid:{color:'rgba(0,0,0,.04)'} },
          y:{ ticks:{color:'#9ca3af', font:{size:10}}, grid:{color:'rgba(0,0,0,.04)'} }
        }
      }
    });

    // Distribution
    if (dChart) { dChart.destroy(); dChart=null; }
    const bins = Array(10).fill(0);
    const numericVals = (vals || []).map(v => Number(v)).filter(v => Number.isFinite(v));
    const max = numericVals.length ? Math.max(...numericVals) : 0;
    const min = numericVals.length ? Math.min(...numericVals) : 0;
    const span = Math.max(max - min, 1);
    const step = span / 10;
    numericVals.forEach(v => {
      const idx = Math.max(0, Math.min(Math.floor((v - min) / step), 9));
      bins[idx] += 1;
    });
    const binLabels = bins.map((_,i)=>(min+i*step).toFixed(0));

    dChart = new Chart($('distChart'), {
      type:'bar',
      data:{
        labels: binLabels,
        datasets:[{ label:'Frequency', data:bins, backgroundColor: cfg.color+'aa', borderRadius:6, borderWidth:0 }]
      },
      options:{
        responsive:true, maintainAspectRatio:false,
        plugins:{ legend:{display:false} },
        scales:{
          x:{ ticks:{color:'#9ca3af', font:{size:10}}, grid:{display:false} },
          y:{ ticks:{color:'#9ca3af', font:{size:10}}, grid:{color:'rgba(0,0,0,.04)'} }
        }
      }
    });
  } catch {}

  // Comparison chart (all cities avg AQI)
  try {
    const r = await fetch('/api/city-ranking?fresh=1');
    const d = await r.json();
    if (!d.cities) return;

    const CATS_COLORS = {Good:'#009966', Moderate:'#c9a000', Poor:'#e67e00', Unhealthy:'#cc0033', Severe:'#660099', Hazardous:'#7e0023'};
    if (cmpChart) { cmpChart.destroy(); cmpChart=null; }
    cmpChart = new Chart($('comparisonChart'), {
      type:'bar',
      data:{
        labels: d.cities.map(c=>c.city),
        datasets:[{
          label:'AQI',
          data: d.cities.map(c=>c.aqi),
          backgroundColor: d.cities.map(c=>CATS_COLORS[c.level]||'#9ca3af'),
          borderRadius:8, borderWidth:0,
        }]
      },
      options:{
        responsive:true, maintainAspectRatio:false,
        plugins:{ legend:{display:false}, tooltip:{ backgroundColor:'rgba(255,255,255,.96)', titleColor:'#1a1d2e', bodyColor:'#4a5568', borderColor:'#e8eaed', borderWidth:1 } },
        scales:{
          x:{ ticks:{color:'#9ca3af', font:{size:10}}, grid:{display:false} },
          y:{ ticks:{color:'#9ca3af', font:{size:10}}, grid:{color:'rgba(0,0,0,.04)'} }
        }
      }
    });
  } catch {}

  // Correlation chart (temp vs AQI scatter)
  try {
    const corrUrl = city ? `/api/historical?city=${encodeURIComponent(city)}&hours=100&fresh=1` : '/api/historical?hours=100&fresh=1';
    const r = await fetch(corrUrl);
    const d = await r.json();
    if (d.error) return;
    // Use PM2.5 vs AQI as proxy for correlation
    if (corrChart) { corrChart.destroy(); corrChart=null; }
    const pts = d.pm25.map((v,i)=>({x:v, y:d.aqi[i]})).filter(p=>p.x&&p.y);
    corrChart = new Chart($('correlationChart'), {
      type:'scatter',
      data:{
        datasets:[{ label:'PM2.5 vs AQI', data:pts, backgroundColor:'rgba(75,169,255,.5)', pointRadius:3 }]
      },
      options:{
        responsive:true, maintainAspectRatio:false,
        plugins:{ legend:{display:false}, tooltip:{ backgroundColor:'rgba(255,255,255,.96)', bodyColor:'#4a5568', borderColor:'#e8eaed', borderWidth:1 } },
        scales:{
          x:{ title:{display:true, text:'PM₂.₅', color:'#9ca3af', font:{size:11}}, ticks:{color:'#9ca3af', font:{size:10}}, grid:{color:'rgba(0,0,0,.04)'} },
          y:{ title:{display:true, text:'AQI',   color:'#9ca3af', font:{size:11}}, ticks:{color:'#9ca3af', font:{size:10}}, grid:{color:'rgba(0,0,0,.04)'} },
        }
      }
    });
  } catch {}

  // Heatmap
  loadHeatmap(city);
}

function heatColor(v) {
  if (!v) return '#f0f0f0';
  if (v<=50)  return '#009966';
  if (v<=100) return '#ffde33';
  if (v<=150) return '#ff9933';
  if (v<=200) return '#cc0033';
  if (v<=300) return '#660099';
  return '#7e0023';
}

async function loadHeatmap(city = '') {
  try {
    const url = city ? `/api/heatmap?city=${encodeURIComponent(city)}&hours=48&fresh=1` : '/api/heatmap?hours=48&fresh=1';
    const r = await fetch(url);
    const d = await r.json();
    if (!d.data) return;
    const cont = $('analyticsHeatmap');
    if (!cont) return;

    let html = `<table class="heatmap-table"><thead><tr><th></th>`;
    d.hours.forEach(h => html += `<th>${h%3===0?h+'h':''}</th>`);
    html += '</tr></thead><tbody>';
    d.days.forEach((day,di) => {
      html += `<tr><th style="text-align:right;padding-right:8px;font-size:.6rem;color:#9ca3af;white-space:nowrap">${day.slice(0,3)}</th>`;
      d.hours.forEach((_,hi) => {
        const v = d.data[di][hi];
        html += `<td style="background:${heatColor(v)}" title="${day} ${hi}:00 — AQI:${v}">${v>0?Math.round(v):''}</td>`;
      });
      html += '</tr>';
    });
    html += '</tbody></table>';
    cont.innerHTML = html;
  } catch {}
}

// Populate city dropdown
async function populateCities() {
  try {
    const r = await fetch('/api/city-ranking?fresh=1');
    const d = await r.json();
    const sel = $('analyticsCitySelect');
    if (!sel||!d.cities) return;
    sel.innerHTML = '<option value="">All Cities</option>' + d.cities.map(c=>`<option value="${c.city}">${String(c.city || '').replace(/\b\w/g, ch => ch.toUpperCase())}</option>`).join('');
  } catch {}
}

$('btnAnalyticsLoad')?.addEventListener('click', loadAnalytics);

(async()=>{
  await populateCities();
  loadAnalytics();
})();
