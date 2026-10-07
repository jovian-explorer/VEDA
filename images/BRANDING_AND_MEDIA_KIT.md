# VEDA: Branding and Media Kit

This directory contains master high-resolution graphical assets for VEDA (Visualization, Exploration, and Data Analysis), intended for scientific posters, conference slide decks, journal publications, and planetary exploration reports.

---

## 1. Asset Overview

| Filename | Resolution | Format | Recommended Usage |
|---|---|---|---|
| `veda_logo_full.png` | 1024 x 1024 | PNG (RGBA) | Master orbiter emblem with full platform typography |
| `veda_promotional_logo.png` | 1024 x 1024 | PNG (RGBA) | High-contrast promotional emblem for slide decks and posters |
| `veda_iconic_orbiter_symbol.png`| 1024 x 1024 | PNG (RGBA) | Clean geometric spacecraft orbiter symbol |
| `veda_minimal_scientific_logo.png`| 1024 x 1024 | PNG (RGBA) | Minimalist monochrome logo for publications |
| `veda_emblem_circle.png` | 1024 x 1024 | PNG (Alpha Mask) | Circular cutout for conference badges and stamps |
| `veda_emblem_square.png` | 1024 x 1024 | PNG (Alpha Mask) | Rounded square app icon badge |
| `veda_orbiter_emblem.png` | 1024 x 1024 | PNG (RGBA) | Circular planetary limb occultation emblem |
| `veda_orbiter_icon.png` | 1024 x 1024 | PNG (RGBA) | High-resolution orbiter mark |
| `veda.ico` | 16 to 256 px | Windows ICO | Multi-resolution desktop executable and window icon |

---

## 2. Official Color Palette

* **Cosmic Void Black**: `#050814` / `rgb(5, 8, 20)`
* **Orbital Cyan / Plasma Blue**: `#00D2FF` / `rgb(0, 210, 255)`
* **Venusian Gold / Solar Flare**: `#FFAA00` / `rgb(255, 170, 0)`
* **Martian Rust / Atmospheric Red**: `#FF4B4B` / `rgb(255, 75, 75)`
* **Deep Space Slate**: `#0F172A` / `rgb(15, 23, 42)`
* **Pure Starlight White**: `#FFFFFF` / `rgb(255, 255, 255)`

---

## 3. LaTeX Usage for Academic Papers and Posters

### Including in Beamer Slide Decks
```latex
\begin{figure}[t]
  \centering
  \includegraphics[width=0.28\textwidth]{images/veda_logo_full.png}
  \caption{VEDA Multi-Mission Planetary Exploration Platform}
\end{figure}
```

### Conference Poster Header (e.g. DPS, LPSC, EPSC, COSPAR)
```latex
% In your poster preamble:
\usepackage{graphicx}

% In the title banner / header:
\begin{minipage}{0.12\textwidth}
  \includegraphics[width=\linewidth]{images/veda_emblem_circle.png}
\end{minipage}
\hfill
\begin{minipage}{0.85\textwidth}
  \textbf{\LARGE VEDA: Multi-Mission Planetary Science and Radio Occultation Analysis}\\
  \large Keshav Aggarwal\\
  \small Student visitor, Space Physics Laboratory (SPL), Vikram Sarabhai Space Centre (VSSC), ISRO, Thiruvananthapuram, India
\end{minipage}
```

---

## 4. Academic Attribution and Citation

When utilizing these logos or scientific software outputs in publications or posters, please credit:

* **Lead Researcher and Author**: Keshav Aggarwal
* **Affiliation**: Student visitor, Space Physics Laboratory (SPL), Vikram Sarabhai Space Centre (VSSC), Indian Space Research Organisation (ISRO), Thiruvananthapuram, Kerala, India (Former PMRF Scholar at DAASE, IIT Indore).

```bibtex
@software{Aggarwal_VEDA_2026,
  author = {Aggarwal, Keshav},
  title = {{VEDA: Visualization, Exploration, and Data Analysis for Planetary Science and Comparative Atmospheric Profiling}},
  year = {2026},
  address = {Thiruvananthapuram, Kerala, India},
  doi = {10.5281/zenodo.23215291},
  url = {https://github.com/jovian-explorer/VEDA}
}
```
