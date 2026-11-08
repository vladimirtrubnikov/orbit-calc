"""core/latex_formulas.py — LaTeX-формулы для --latex."""

LATEX = {
    "1": [
        r"r_p = a\,(1 - e)", r"r_a = a\,(1 + e)",
        r"p = a\,(1 - e^2)", r"h = \sqrt{\mu\,p}",
        r"\varepsilon = -\dfrac{\mu}{2a}", r"T = 2\pi\sqrt{\dfrac{a^3}{\mu}}",
    ],
    "2": [
        r"a = \dfrac{r_p + r_a}{2}", r"e = \dfrac{r_a - r_p}{r_a + r_p}",
    ],
    "3": [
        r"a = \dfrac{r_p}{1 - e}", r"r_a = a\,(1 + e)",
    ],
    "4": [
        r"\varepsilon = \dfrac{v^2}{2} - \dfrac{\mu}{r}",
        r"h = r\,v\cos\gamma",
        r"a = -\dfrac{\mu}{2\varepsilon}",
        r"e = \sqrt{1 - \dfrac{p}{a}}",
    ],
    "5": [
        r"a = -\dfrac{\mu}{2\varepsilon}", r"p = \dfrac{h^2}{\mu}",
        r"e = \sqrt{1 - \dfrac{p}{a}}",
    ],
    "6": [
        r"\varepsilon = \dfrac{v_p^2}{2} - \dfrac{\mu}{r_p}",
        r"a = -\dfrac{\mu}{2\varepsilon}",
        r"e = \sqrt{1 - \dfrac{p}{a}}",
    ],
    "11": [
        r"e = \dfrac{v_p - v_a}{v_p + v_a}",
        r"a = \dfrac{\mu}{v_p\,v_a}",
    ],
    "25": [
        r"\Delta v_1' = \sqrt{v_{1c}^2 + v_{1t}^2 - 2\,v_{1c}\,v_{1t}\cos\Delta i}",
        r"\Delta v_2' = \sqrt{v_{2t}^2 + v_{2c}^2 - 2\,v_{2t}\,v_{2c}\cos\Delta i}",
    ],
    "27": [
        r"\sqrt{\mu}\,\Delta t = \dfrac{y(z)}{C(z)}^{3/2}\,S(z) + A\,\sqrt{y(z)}",
        r"A = \sin\Delta\nu\sqrt{\dfrac{r_1 r_2}{1 - \cos\Delta\nu}}",
    ],
    "34": [
        r"a_t = \dfrac{r_1 + r_2}{2}",
        r"\Delta v_1 = \sqrt{\mu\left(\dfrac{2}{r_1} - \dfrac{1}{a_t}\right)} - \sqrt{\dfrac{\mu}{r_1}}",
        r"\Delta v_2 = \sqrt{\dfrac{\mu}{r_2}} - \sqrt{\mu\left(\dfrac{2}{r_2} - \dfrac{1}{a_t}\right)}",
        r"t = \pi\sqrt{\dfrac{a_t^3}{\mu}}",
    ],
    "36": [
        r"m_1 = m_0\,e^{-\Delta v/v_e}",
        r"m_{\text{fuel}} = m_0 - m_1",
        r"v_e = I_{sp}\,g_0",
    ],
    "46": [
        r"\vec{h} = \vec{r} \times \vec{v}",
        r"\vec{e} = \dfrac{\vec{v}\times\vec{h}}{\mu} - \dfrac{\vec{r}}{|\vec{r}|}",
        r"i = \arccos\dfrac{h_z}{|\vec{h}|}",
        r"\Omega = \operatorname{atan2}(n_y, n_x)",
    ],
    "47": [
        r"\dfrac{d\Omega}{dt} = -\dfrac{3}{2}\,J_2\,n\left(\dfrac{R_\oplus}{p}\right)^2\cos i",
        r"\dfrac{d\omega}{dt} = \dfrac{3}{4}\,J_2\,n\left(\dfrac{R_\oplus}{p}\right)^2(5\cos^2 i - 1)",
        r"\dfrac{dM_0}{dt} = \dfrac{3}{4}\,J_2\,n\left(\dfrac{R_\oplus}{p}\right)^2\sqrt{1-e^2}\,(3\cos^2 i - 1)",
    ],
    "49": [
        r"\Delta v_{\text{circ}} = \sqrt{\dfrac{\mu}{R_\oplus + H}} - v_{\text{rot}}(\varphi)",
        r"v_{\text{rot}}(\varphi) = 465.1\,\cos\varphi \;\text{м/с}",
        r"\Delta v_{\text{total}} = \Delta v_{\text{circ}} + \Delta v_{\text{grav}} + \Delta v_{\text{drag}}",
    ],
    "50": [
        r"m_{\text{payload}} = m_0 - m_{\text{fuel}} - m_{\text{dry}}",
        r"m_{\text{fuel}} = m_0\left(1 - e^{-\Delta v/v_e}\right)",
    ],
    "51": [
        r"\dfrac{m_{\text{pl}}}{m_0} = \left[e^{-\Delta v_i/(I_{sp}\,g_0)} - \varepsilon\right]^{N}",
        r"\Delta v_i = \dfrac{\Delta v_{\text{total}}}{N}",
    ],
    "52": [
        r"x - \dfrac{(1-\mu)(x+\mu)}{r_1^3} - \dfrac{\mu(x-1+\mu)}{r_2^3} = 0",
        r"x_{k+1} = x_k - \dfrac{f(x_k)}{f'(x_k)}",
    ],
    "53": [
        r"i_{\text{crit}} = \arccos\left(\dfrac{1}{\sqrt{5}}\right) \approx 63.4349^\circ",
        r"\left.\dfrac{d\omega}{dt}\right|_{i = i_{\text{crit}}} = 0",
    ],
}


def get_formulas(solver_id: str) -> list[str]:
    """LaTeX-строки для случая; пустой список если нет."""
    return LATEX.get(str(solver_id), [])