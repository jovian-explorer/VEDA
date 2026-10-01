# Third-Party Software Licenses and Attributions

VEDA (Visualization, Exploration, and Data Analysis) bundles or depends on the third-party open-source projects below. This document gives their copyright notices and license terms. The standalone app bundles all of them; a pip install fetches the Python packages from PyPI. Data from the space agency archives are not software and are covered by [DATA_POLICY.md](DATA_POLICY.md).

---

## Table of Third-Party Dependencies

| Component | Ecosystem | License | Primary Purpose in VEDA |
| :--- | :--- | :--- | :--- |
| **KaTeX** | Frontend (JavaScript/CSS) | MIT License | Offline mathematical typesetting of LaTeX equations in UI drawers |
| **Plotly.js** | Frontend (JavaScript) | MIT License | Interactive profile, comparison, map, globe and 3D orbit plots |
| **Natural Earth coastlines** | Frontend (data) | Public domain | Plotly geographic outlines, bundled for offline use (`vendor/topojson`) |
| **FastAPI** | Backend (Python) | MIT License | High-performance asynchronous REST API backend |
| **Pydantic** | Backend (Python) | MIT License | Data validation and scientific schema definitions |
| **Uvicorn** | Backend (Python) | BSD 3-Clause | Asynchronous ASGI web server |
| **NumPy** | Backend (Python) | BSD 3-Clause | Vectorized multi-dimensional array mathematics and gridding |
| **SciPy** | Backend (Python) | BSD 3-Clause | Scientific interpolation, filtering, numerical derivatives, and integration |
| **Astropy** | Backend (Python) | BSD 3-Clause | Astronomical coordinate transformations, FITS file I/O, and header parsing |
| **Matplotlib** | Backend (Python) | PSF / BSD Compatible | Server-side generation of 300-DPI publication figures |
| **PyWebView** | Backend (Python) | BSD 3-Clause | Native desktop window binding with Edge WebView2 runtime |
| **Requests** | Backend (Python) | Apache 2.0 | HTTP client for archive indexes, product and kernel downloads |
| **Pillow** | Backend (Python) | MIT-CMU (HPND) | Image rendering and PNG thumbnails |
| **SpiceyPy** | Backend (Python) | MIT License | Python interface to the NAIF CSPICE toolkit |
| **NAIF CSPICE** | Backend (C library, via SpiceyPy) | NAIF rules (free to use) | Ephemerides, frames, light time and illumination angles for observation geometry |

---

## 1. KaTeX

* **License**: MIT License
* **Copyright**: Copyright (c) 2013-2023 Khan Academy and other contributors
* **Repository**: https://github.com/KaTeX/KaTeX

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

## 2. Plotly.js

* **License**: MIT License
* **Copyright**: Copyright (c) 2026 Plotly, Inc.
* **Repository**: https://github.com/plotly/plotly.js

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

---

## 3. SpiceyPy and NAIF CSPICE

* **SpiceyPy license**: MIT License
* **SpiceyPy copyright**: Copyright (c) 2014-2026 Andrew Annex and contributors
* **Repository**: https://github.com/AndrewAnnex/SpiceyPy
* **CSPICE**: the SPICE toolkit is produced by the Navigation and Ancillary Information Facility (NAIF), Jet Propulsion Laboratory, California Institute of Technology, for NASA. It is free to use and redistribute under the NAIF rules at https://naif.jpl.nasa.gov/naif/rules.html, which ask users to acknowledge NAIF. The toolkit is provided without warranty.
* **Reference**: Acton, C. H. (1996). Ancillary data services of NASA's Navigation and Ancillary Information Facility. *Planetary and Space Science*, 44(1), 65-70. Annex, A. M., et al. (2020). SpiceyPy: a Pythonic wrapper for the SPICE toolkit. *Journal of Open Source Software*, 5(46), 2050.

The SpiceyPy license is the MIT License; its text is identical to the one reproduced in section 1, with the copyright line above.

---

## 4. FastAPI and Pydantic

* **License**: MIT License
* **FastAPI Copyright**: Copyright (c) 2018-2026 Sebastián Ramírez
* **Pydantic Copyright**: Copyright (c) 2017-2026 Samuel Colvin

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

## 5. NumPy, SciPy, Astropy, Uvicorn, and PyWebView

* **License**: BSD 3-Clause License
* **NumPy Copyright**: Copyright (c) 2005-2026, NumPy Developers
* **SciPy Copyright**: Copyright (c) 2001-2026, SciPy Developers
* **Astropy Copyright**: Copyright (c) 2011-2026, Astropy Developers
* **Uvicorn Copyright**: Copyright (c) 2017-present, Encode OSS Ltd.
* **PyWebView Copyright**: Copyright (c) 2014-2026, Roman Sirokov

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.
3. Neither the name of the copyright holder nor the names of its contributors
   may be used to endorse or promote products derived from this software
   without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

---

## 6. Requests

* **License**: Apache License, Version 2.0
* **Copyright**: Copyright 2019 Kenneth Reitz
* **Licensed under the Apache License, Version 2.0** (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at: http://www.apache.org/licenses/LICENSE-2.0

---

## 7. Matplotlib

* **License**: Matplotlib License (PSF Compatible)
* **Copyright**: Copyright (c) 2002-2026 Matplotlib Development Team
* **Terms**: Redistribution and use in source and binary forms, with or without modification, are permitted under the terms of the Matplotlib License agreement.

---

## 8. Pillow (PIL Fork)

* **License**: HPND License (Historical Permission Notice and Disclaimer)
* **Copyright**:
  * Copyright (c) 2010-2026 by Jeffrey A. Clark and contributors
  * Copyright (c) 1997-2011 by Secret Labs AB
  * Copyright (c) 1995-2011 by Fredrik Lundh
* **Terms**: Permission to use, copy, modify, and distribute this software and its documentation for any purpose and without fee is hereby granted, provided that the above copyright notice appear in all copies and that both that copyright notice and this permission notice appear in supporting documentation.

---

## 9. Natural Earth

* **License**: Public domain
* **Source**: https://www.naturalearthdata.com/
* **Use**: the Plotly map outline files in `src/veda/frontend/vendor/topojson` are derived from Natural Earth 1:110m and 1:50m data. Natural Earth asks for, but does not require, the credit "Made with Natural Earth".
