'use strict';

const CATS = [
  {max:50,  level:'Good',       color:'#009966',bg:'#e8f8f2'},
  {max:100, level:'Moderate',   color:'#c9a000',bg:'#fffde8'},
  {max:150, level:'Poor',       color:'#e67e00',bg:'#fff3e0'},
  {max:200, level:'Unhealthy',  color:'#cc0033',bg:'#fde8ed'},
  {max:300, level:'Severe',     color:'#660099',bg:'#f3e8ff'},
  {max:999, level:'Hazardous',  color:'#7e0023',bg:'#fde8e8'},
];
const getCat = aqi => CATS.find(c => aqi <= c.max) || CATS[CATS.length-1];
const $ = id => document.getElementById(id);
const css = (k,v) => document.documentElement.style.setProperty(k,v);

let contribChart = null;

// ── Sync sliders ─────────────────────────────────────────
['pm25','pm10','no2','so2','o3','co','temperature','humidity','wind_speed'].forEach(id => {
  const inp = $(id), rng = $(id+'Range');
  if (!inp || !rng) return;
  inp.addEventListener('input', () => { rng.value = inp.value; });
  rng.addEventListener('input', () => { inp.value = rng.value; });
});

// ── Presets ──────────────────────────────────────────────
const PRESETS = {
  good:      {pm25:8, pm10:18, no2:12, so2:3, o3:30, co:0.4, temperature:22, humidity:50, wind_speed:8},
  moderate:  {pm25:28, pm10:58, no2:35, so2:10, o3:55, co:1.0, temperature:28, humidity:60, wind_speed:5},
  unhealthy: {pm25:90, pm10:160, no2:70, so2:20, o3:90, co:2.5, temperature:32, humidity:70, wind_speed:2},
  hazardous: {pm25:280, pm10:400, no2:180, so2:80, o3:180, co:8, temperature:38, humidity:80, wind_speed:1},
};

document.querySelectorAll('.preset-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const p = PRESETS[btn.dataset.preset];
    if (!p) return;
    Object.entries(p).forEach(([k,v]) => {
      const inp = $(k), rng = $(k+'Range');
      if (inp) inp.value = v;
      if (rng) rng.value = v;
    });
    document.querySelectorAll('.preset-btn').forEach(b=>b.style.borderColor='');
    btn.style.borderColor = '#4ba9ff';
  });
});

// ── Predict ──────────────────────────────────────────────
$('btnPredict')?.addEventListener('click', async () => {
  const body = {
    pm25:        parseFloat($('pm25')?.value)||0,
    pm10:        parseFloat($('pm10')?.value)||0,
    no2:         parseFloat($('no2')?.value)||0,
    so2:         parseFloat($('so2')?.value)||0,
    o3:          parseFloat($('o3')?.value)||0,
    co:          parseFloat($('co')?.value)||0,
    temperature: parseFloat($('temperature')?.value)||25,
    humidity:    parseFloat($('humidity')?.value)||50,
    wind_speed:  parseFloat($('wind_speed')?.value)||5,
  };

  const btn = $('btnPredict');
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Predicting…';
  btn.disabled = true;

  try {
    const r = await fetch('/api/predict', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(body),
    });
    const d = await r.json();
    if (!d.success) throw new Error(d.error);
    renderResult(d);
  } catch(e) {
    toast('Prediction failed: '+e.message, 'error');
  } finally {
    btn.innerHTML = '<i class="fa-solid fa-bolt"></i> Predict AQI';
    btn.disabled = false;
  }
});

function renderResult(d) {
  const cat = getCat(d.predicted_aqi);
  css('--aqi-color', cat.color);
  css('--aqi-bg', cat.bg);

  $('resultPlaceholder').classList.add('hidden');
  $('resultContent').classList.remove('hidden');
  $('resultCard').style.borderTopColor = cat.color;

  // Gauge
  const circ = 408;
  const pct = Math.min(d.predicted_aqi / 500, 1);
  const arc = $('resultGaugeArc');
  arc.style.strokeDashoffset = circ - circ * pct;
  arc.setAttribute('stroke', cat.color);

  $('resultAqiNum').textContent = Math.round(d.predicted_aqi);
  $('resultAqiNum').style.color = cat.color;
  $('resultLevel').textContent = d.category;
  $('resultLevel').style.color = cat.color;
  $('resultDesc').textContent = d.description;
  $('resultMethod').textContent = d.method || 'EPA Formula';

  // Contributions
  if (contribChart) { contribChart.destroy(); contribChart=null; }
  const keys = Object.keys(d.contributions);
  const colors = ['#e74c3c','#e67e00','#8e44ad','#2980b9','#16a085','#7f8c8d'];
  const LABELS = {pm25:'PM₂.₅',pm10:'PM₁₀',no2:'NO₂',so2:'SO₂',o3:'O₃',co:'CO'};

  contribChart = new Chart($('contribChart'), {
    type:'bar',
    data:{
      labels: keys.map(k=>LABELS[k]||k),
      datasets:[{
        data: keys.map(k => d.contributions[k]),
        backgroundColor: colors,
        borderRadius:6, borderWidth:0,
      }]
    },
    options:{
      responsive:true, maintainAspectRatio:false, indexAxis:'y',
      plugins:{ legend:{display:false}, tooltip:{
        backgroundColor:'rgba(255,255,255,.96)', titleColor:'#1a1d2e', bodyColor:'#4a5568',
        borderColor:'#e8eaed', borderWidth:1,
        callbacks:{ label: ctx => ` ${ctx.parsed.x.toFixed(1)}%` }
      }},
      scales:{
        x:{ ticks:{callback:v=>v+'%', color:'#9ca3af', font:{size:10}}, grid:{color:'rgba(0,0,0,.04)'}, max:100 },
        y:{ ticks:{color:'#4a5568', font:{size:11, weight:'600'}}, grid:{display:false} }
      }
    }
  });

  // Health tips
  const icons = ['fa-lungs','fa-person-walking','fa-mask-face','fa-house','fa-triangle-exclamation'];
  $('healthTips').innerHTML = d.health_tips.map((tip,i) =>
    `<div class="health-tip" style="background:${cat.bg}">
      <i class="fa-solid ${icons[i]||'fa-circle-info'}" style="color:${cat.color}"></i>
      <span>${tip}</span>
    </div>`
  ).join('');
}

function toast(msg, type='info') {
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.innerHTML = `<i class="fa-solid fa-circle-xmark"></i> ${msg}`;
  document.getElementById('toastContainer')?.appendChild(t);
  setTimeout(()=>t.remove(), 3500);
}
