"use strict";
const slides = [...document.querySelectorAll(".slide")];
let current = 0;
const progress = document.querySelector(".deck-progress");
slides.forEach((slide, i) => {
  const button = document.createElement("button");
  button.type = "button";
  button.setAttribute("aria-label", "Слайд " + (i + 1) + ": " + slide.getAttribute("aria-label").replace(/^\d+\.\s*/, ""));
  button.onclick = () => show(i);
  progress.appendChild(button);
});
function show(index) {
  current = Math.max(0, Math.min(slides.length - 1, index));
  slides.forEach((slide, i) => {
    slide.classList.toggle("active", i === current);
    slide.hidden = i !== current;
    slide.setAttribute("aria-hidden", String(i !== current));
  });
  progress.querySelectorAll("button").forEach((button, i) => {
    button.classList.toggle("active", i === current);
    if (i === current) button.setAttribute("aria-current", "step");
    else button.removeAttribute("aria-current");
  });
  document.getElementById("count").textContent = String(current + 1).padStart(2, "0") + " / 07";
  document.getElementById("prev").disabled = current === 0;
  document.getElementById("next").disabled = current === slides.length - 1;
  history.replaceState(null, "", "#" + (current + 1));
}
document.getElementById("prev").onclick = () => show(current - 1);
document.getElementById("next").onclick = () => show(current + 1);
document.getElementById("print").onclick = () => window.print();
document.addEventListener("keydown", (event) => {
  if (event.ctrlKey || event.altKey || event.metaKey || /INPUT|TEXTAREA|SELECT/.test(event.target.tagName)) return;
  if (event.key === " " && /SUMMARY|BUTTON|A/.test(event.target.tagName)) return;
  if (["ArrowRight", "PageDown", " "].includes(event.key)) { event.preventDefault(); show(current + 1); }
  if (["ArrowLeft", "PageUp"].includes(event.key)) { event.preventDefault(); show(current - 1); }
  if (event.key === "Home") { event.preventDefault(); show(0); }
  if (event.key === "End") { event.preventDefault(); show(slides.length - 1); }
});
const printState = [];
window.addEventListener("beforeprint", () => {
  slides.forEach((slide, i) => {
    printState[i] = slide.hidden;
    slide.hidden = false;
    slide.setAttribute("aria-hidden", "false");
  });
});
window.addEventListener("afterprint", () => show(current));
show((Number(location.hash.slice(1)) || 1) - 1);
