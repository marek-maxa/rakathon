// Keep graph layout and source navigation usable inside native disclosures.
function revealSource() {
  if (!location.hash) return;
  let element = document.getElementById(decodeURIComponent(location.hash.slice(1)));
  while (element) {
    if (element.tagName === "DETAILS") element.open = true;
    element = element.parentElement;
  }
}
let chartLoading;
async function loadCharts() {
  if (!window.meddiCharts?.length) return;
  if (!chartLoading) {
    chartLoading = new Promise((resolve, reject) => {
      if (window.Plotly) return resolve();
      const source = document.getElementById("plotly-source");
      if (!source) return resolve();
      const script = document.createElement("script");
      script.src = JSON.parse(source.textContent);
      script.onload = resolve;
      script.onerror = reject;
      document.head.append(script);
    });
  }
  try {
    await chartLoading;
    await Promise.all(window.meddiCharts.splice(0).map(render => render()));
    window.dispatchEvent(new Event("resize"));
  } catch {
    document.querySelectorAll(".chart").forEach(chart => {
      if (!chart.querySelector(".plot-container")) chart.textContent = "Graf se nepodařilo načíst. Hodnoty jsou dostupné v historii měření.";
    });
  }
}
revealSource();
window.addEventListener("hashchange", revealSource);
document.addEventListener("toggle", (event) => {
  if (event.target.tagName === "DETAILS" && event.target.open) {
    if (event.target.classList.contains("doctor-full-report")) loadCharts();
    window.dispatchEvent(new Event("resize"));
  }
}, true);
if (document.querySelector(".doctor-full-report[open]")) loadCharts();
