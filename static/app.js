async function loadSignalsChart(){
  const el = document.getElementById("signalsChart");
  if(!el) return;

  const res = await fetch("/api/signals?limit=80");
  const data = await res.json();

  let buy = 0, sell = 0;
  for (const s of data){
    if(!s.is_active) continue;
    if(s.side === "BUY") buy++;
    if(s.side === "SELL") sell++;
  }

  const ctx = el.getContext("2d");
  new Chart(ctx, {
    type: "bar",
    data: {
      labels: ["BUY", "SELL"],
      datasets: [{
        label: "Signals attivi (ultimi 80)",
        data: [buy, sell],
      }]
    },
    options: {
      plugins: { legend: { display: true } },
      responsive: true,
      scales: {
        y: { beginAtZero: true }
      }
    }
  });
}

document.addEventListener("DOMContentLoaded", loadSignalsChart);
