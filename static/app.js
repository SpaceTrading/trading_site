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

// =========================
// MONTE CARLO BACKGROUND (HOME ONLY)
// =========================

function initMonteCarloBackground() {

  const canvas = document.getElementById("mc-lines");
  if (!canvas) return; // importantissimo: solo home

  const ctx = canvas.getContext("2d");

  let width, height;

  function resize() {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  }

  resize();
  window.addEventListener("resize", resize);

  // crea linee
  const lines = [];

  for (let i = 0; i < 30; i++) {
    lines.push({
      points: Array.from({ length: 80 }, (_, i) => ({
        x: (i / 80) * width,   // copre tutta la larghezza
        y: height * (0.3 + Math.random() * 0.4),
        vy: 0
      })),
      volatility: 0.5 + Math.random() * 1.5,
      drift: (Math.random() - 0.5) * 0.2  
    });
  }

  function draw() {
    ctx.clearRect(0, 0, width, height);

    lines.forEach(line => {

      ctx.beginPath();

      line.points.forEach((p, i) => {

        // movimento random tipo equity
        // aggiornamento velocità (inerzia)
        p.vy += (Math.random() - 0.5) * line.volatility;
        
        // damping (effetto morbido)
        p.vy *= 0.9;
        
        // applica velocità + trend
        p.y += p.vy + line.drift;
        
        // movimento orizzontale lento
        p.x += 0.3;

        if (i === 0) {
          ctx.moveTo(p.x, p.y);
        } else {
          ctx.lineTo(p.x, p.y);
        }
      });

      // shift
      if (line.points[line.points.length - 1].x > width + 20) {
        line.points.pop();
      
        line.points.unshift({
          x: -20,
          y: line.points[0].y,
          vy: 0
        });
      }

      ctx.strokeStyle = "rgba(120,180,255,0.4)";
      ctx.lineWidth = 1.5;
      ctx.lineWidth = 1;
      ctx.stroke();
    });

    requestAnimationFrame(draw);
  }

  draw();
}

// inizializzazione
window.addEventListener("load", initMonteCarloBackground);

// =========================
// LOGIN MODAL
// =========================

window.openLogin = function() {
  const modal = document.getElementById("loginModal");
  if (modal) modal.style.display = "flex";
}

window.closeLogin = function() {
  const modal = document.getElementById("loginModal");
  if (modal) modal.style.display = "none";
}

// =========================
// REGISTER MODAL
// =========================

window.openRegister = function() {
  const modal = document.getElementById("registerModal");
  if (modal) modal.style.display = "flex";
}

window.closeRegister = function() {
  const modal = document.getElementById("registerModal");
  if (modal) modal.style.display = "none";
}

// =========================
// CLICK OUTSIDE (chiusura)
// =========================

window.addEventListener("click", function(e) {
  const loginModal = document.getElementById("loginModal");
  const registerModal = document.getElementById("registerModal");

  if (e.target === loginModal) loginModal.style.display = "none";
  if (e.target === registerModal) registerModal.style.display = "none";
  const forgotModal = document.getElementById("forgotModal");
  if (e.target === forgotModal) forgotModal.style.display = "none";
});

// =========================
// ESC KEY
// =========================

window.addEventListener("keydown", function(e) {
  if (e.key === "Escape") {
    closeLogin();
    closeRegister();
    closeForgot();
  }
});

// =========================
// FORGOT PASSWORD MODAL
// =========================

window.openForgot = function() {
  const modal = document.getElementById("forgotModal");
  modal.style.display = "flex";
}

window.closeForgot = function() {
  const modal = document.getElementById("forgotModal");
  modal.style.display = "none";
}

// =========================
// MOBILE MENU TOGGLE
// =========================

function toggleMenu() {
  const menu = document.getElementById("navMenu");
  menu.classList.toggle("active");
}

window.addEventListener("click", function(e) {
  const menu = document.getElementById("navMenu");
  const button = document.querySelector(".menu-toggle");

  if (!menu.contains(e.target) && !button.contains(e.target)) {
    menu.classList.remove("active");
  }
});