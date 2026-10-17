/* Dashboard logic: polls /api/status, renders SVG schematic, section cards,
   Chart.js trends and the fault/event tables. */

const API = "";
const COLORS = { HEALTHY: "#2ea043", FAULTY: "#f85149", ISOLATED: "#8b949e",
                 RESTORING: "#d29922", RESTORED: "#58a6ff" };

let currentStatus = null;
let currentCharts = null, voltageChart = null;

async function api(path, opts) {
  const r = await fetch(API + path, opts);
  if (!r.ok) throw new Error(path + " -> " + r.status);
  return r.json();
}

async function post(path, body) {
  return api(path, { method: "POST",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

/* ---------------- schematic ---------------- */
function renderSchematic(s) {
  const secs = s.sections;
  const w = 960, boxH = 70, gap = 250, x0 = 70, y = 70;
  let svg = `<svg width="${w}" height="220" viewBox="0 0 ${w} 220">`;

  // main source
  svg += `<circle cx="40" cy="${y}" r="22" fill="#12361f" stroke="#2ea043" stroke-width="2"/>
          <text x="40" y="${y - 30}" text-anchor="middle">${s.source.id} (11 kV)</text>`;
  // main breaker CB0
  svg += `<rect x="80" y="${y - 10}" width="24" height="20" fill="${s.main_breaker.status === "CLOSED" ? "#2ea043" : "#f85149"}"/>
          <text x="92" y="${y - 18}" text-anchor="middle">${s.main_breaker.id}</text>`;

  // sections along the main feeder
  let prevX = 104;
  secs.forEach((sec, i) => {
    const x = x0 + i * gap;
    svg += `<line x1="${prevX}" y1="${y}" x2="${x}" stroke="#8b949e" stroke-width="2" ${sec.state === "ISOLATED" ? 'stroke-dasharray="5,4"' : ""}/>`;
    // switch
    const swColor = sec.switch_status === "CLOSED" ? "#2ea043" : "#f85149";
    svg += `<rect x="${x}" y="${y - 10}" width="24" height="20" fill="${swColor}"/>
            <text x="${x + 12}" y="${y - 18}" text-anchor="middle">${sec.switch_id}</text>`;
    // section box
    const bx = x + 36;
    svg += `<rect x="${bx}" y="${y - boxH / 2}" width="160" height="${boxH}" rx="8"
              fill="#0d1117" stroke="${COLORS[sec.state]}" stroke-width="3"/>
            <text x="${bx + 80}" y="${y - 12}" text-anchor="middle" font-weight="bold">${sec.id}</text>
            <text x="${bx + 80}" y="${y + 4}" text-anchor="middle">${sec.load_kw} kW load</text>
            <text x="${bx + 80}" y="${y + 20}" text-anchor="middle" fill="${COLORS[sec.state]}">${sec.state}</text>`;
    if (!sec.sensor_online)
      svg += `<text x="${bx + 80}" y="${y + 34}" text-anchor="middle" fill="#f85149">SENSOR OFFLINE</text>`;
    prevX = bx + 160;
  });

  // alternate feeder + tie breaker
  const tieX = x0 + (secs.length - 1) * gap + 48;
  const altY = 180;
  svg += `<line x1="${tieX}" y1="${y + 35}" x2="${tieX}" y2="${altY}" stroke="#58a6ff" stroke-width="2" stroke-dasharray="6,4"/>
          <rect x="${tieX - 12}" y="${altY}" width="24" height="20" fill="${s.tie_breaker.status === "CLOSED" ? "#58a6ff" : "#30363d"}"/>
          <text x="${tieX}" y="${altY + 36}" text-anchor="middle">${s.tie_breaker.id} (${s.tie_breaker.status})</text>
          <circle cx="${tieX + 70}" cy="${altY + 10}" r="20" fill="#0d2a4a" stroke="#58a6ff" stroke-width="2"/>
          <text x="${tieX + 70}" y="${altY + 40}" text-anchor="middle">${s.alternate_source.id}</text>`;
  svg += "</svg>";
  document.getElementById("schematic").innerHTML = svg;
}

/* ---------------- section cards ---------------- */
function renderCards(s) {
  const el = document.getElementById("sectionCards");
  el.innerHTML = s.sections.map(sec => `
    <div class="card ${sec.state}">
      <h3>${sec.name} <small>(${sec.id})</small></h3>
      <div class="state" style="color:${COLORS[sec.state]}">${sec.state}</div>
      <p>Switch ${sec.switch_id}: <b>${sec.switch_status}</b><br>
         Voltage: <b>${sec.voltage_kv} kV</b><br>
         Current: <b>${sec.current_a} A</b> (In = ${sec.rated_current_a} A)<br>
         Supply: <b>${sec.supply_source || "NONE"}</b>
         ${sec.sensor_online ? "" : '<br><span class="sensor-off">SENSOR OFFLINE</span>'}</p>
    </div>`).join("");
  const sel = document.getElementById("ctrlSection");
  if (!sel.options.length)
    s.sections.forEach(sec => sel.add(new Option(sec.id, sec.id)));
}

/* ---------------- charts ---------------- */
async function renderCharts() {
  const data = (await api("/api/telemetry?limit=120")).telemetry;
  const labels = [...new Set(data.map(d => d.tick))];
  const bySec = id => labels.map(t => {
    const rec = data.find(d => d.tick === t && d.section_id === id);
    return rec ? rec.current_a : null;
  });
  const bySecV = id => labels.map(t => {
    const rec = data.find(d => d.tick === t && d.section_id === id);
    return rec ? rec.voltage_kv : null;
  });
  const secIds = ["SEC1", "SEC2", "SEC3"];
  const mk = (id, ds) => {
    const ctx = document.getElementById(id).getContext("2d");
    return new Chart(ctx, { type: "line",
      data: { labels, datasets: ds },
      options: { animation: false, responsive: true,
        scales: { x: { ticks: { color: "#8b949e" } },
                  y: { ticks: { color: "#8b949e" } } },
        plugins: { legend: { labels: { color: "#e6edf3" } } } } });
  };
  const colors = ["#2ea043", "#d29922", "#58a6ff"];
  if (currentCharts) currentCharts.destroy();
  if (voltageChart) voltageChart.destroy();
  currentCharts = mk("currentChart", secIds.map((id, i) => ({
    label: id, data: bySec(id), borderColor: colors[i],
    spanGaps: true, pointRadius: 0, borderWidth: 2 })));
  voltageChart = mk("voltageChart", secIds.map((id, i) => ({
    label: id, data: bySecV(id), borderColor: colors[i],
    spanGaps: true, pointRadius: 0, borderWidth: 2 })));
}

/* ---------------- tables ---------------- */
async function renderTables() {
  const faults = (await api("/api/faults")).faults;
  document.querySelector("#faultTable tbody").innerHTML = faults.map(f => `
    <tr><td>${f.timestamp}</td><td>${f.section_id}</td><td>${f.fault_type}</td>
        <td>${f.voltage_kv}</td><td>${f.current_a}</td><td>${f.response}</td></tr>`).join("");
  const events = (await api("/api/events?limit=40")).events;
  document.querySelector("#eventTable tbody").innerHTML = events.map(e => `
    <tr><td>${e.timestamp}</td><td>${e.type}</td><td>${e.message}</td></tr>`).join("");
}

/* ---------------- polling ---------------- */
async function refresh() {
  try {
    currentStatus = await api("/api/status");
    renderSchematic(currentStatus);
    renderCards(currentStatus);
    const conn = document.getElementById("connStatus");
    conn.textContent = "LIVE — tick " + currentStatus.tick;
    conn.className = "conn ok";
  } catch (e) {
    const conn = document.getElementById("connStatus");
    conn.textContent = "BACKEND OFFLINE";
    conn.className = "conn bad";
  }
}

document.getElementById("btnInject").onclick = async () => {
  const section_id = document.getElementById("ctrlSection").value;
  const fault_type = document.getElementById("ctrlFault").value;
  await post("/api/simulate/fault", { section_id, fault_type });
};
document.getElementById("btnClear").onclick = async () => {
  const section_id = document.getElementById("ctrlSection").value;
  await post("/api/simulate/clear", { section_id });
};
let sensorOff = false;
document.getElementById("btnSensor").onclick = async () => {
  const section_id = document.getElementById("ctrlSection").value;
  sensorOff = !sensorOff;
  await post("/api/simulate/sensor-failure", { section_id, online: !sensorOff });
};

refresh(); renderTables(); renderCharts();
setInterval(refresh, 1500);
setInterval(renderTables, 4000);
setInterval(renderCharts, 6000);
