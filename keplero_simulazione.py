"""
Simulazione della Terza Legge di Keplero  (T² ∝ a³)
====================================================

Derivazione teorica
-------------------
Partiamo da due sole leggi di Newton (Principia, 1687):

    (1)  F = m · a              seconda legge della dinamica
    (2)  F = G · M · m / r²     legge di gravitazione universale

Uguagliando F nelle due equazioni si ricava l'accelerazione che il Sole
(massa M) imprime al pianeta (massa m):

    a(r) = - G·M / r²  ·  r̂

Questa è una equazione differenziale vettoriale del secondo ordine.
La sua soluzione analitica (Newton, conica → ellisse) porta alla
formula chiusa della terza legge di Keplero:

    T² = (4π² / G·M) · a³        →     T² / a³ = costante

In questa simulazione *non* imponiamo mai questa relazione: ci limitiamo a
integrare numericamente a(r) con il metodo di Velocity Verlet partendo
dal perielio, misuriamo il periodo T per orbite con semiassi a diversi e
verifichiamo che il fit log–log di T vs a abbia pendenza ≈ 1.5
(ovvero T ∝ a^(3/2) ⇒ T² ∝ a³).

La terza legge di Keplero (1619) emerge così come *conseguenza* della
gravitazione universale, non come postulato indipendente.

Unità di misura
---------------
    distanze :  UA  (unità astronomica)
    tempo    :  anni
    massa    :  masse solari

Applicando T² = 4π²/GM · a³ alla Terra (a = 1 UA, T = 1 anno, M = 1 M☉):

        GM_sole = 4 π²   [UA³ / anno²]

"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation


# Costante gravitazionale × massa del Sole nelle nostre unità.
# Deriva da T² = 4π²/GM · a³ applicata alla Terra (a=1, T=1).
GM = 4.0 * np.pi**2


# ---------------------------------------------------------------------------
#  Classe Orbita
# ---------------------------------------------------------------------------

class Orbita:
    """Orbita kepleriana piana attorno al Sole.

    L'orbita è definita da:
        a : semiasse maggiore        [UA]
        e : eccentricità             [adimensionale, 0 ≤ e < 1]

    Le condizioni iniziali sono prese al perielio (punto più vicino al
    Sole), dove la velocità è perpendicolare al raggio vettore.
    """

    def __init__(self, a, e, nome=""):
        self.a = a
        self.e = e
        self.nome = nome or f"a={a} UA"

        # --- condizioni iniziali al perielio ---
        # Distanza al perielio:       r_p = a (1 - e)
        # Velocità al perielio (vis-viva):
        #     v_p = sqrt( GM/a · (1+e)/(1-e) )
        r_peri = a * (1.0 - e)
        v_peri = np.sqrt(GM / a * (1.0 + e) / (1.0 - e))

        self.r0 = np.array([r_peri, 0.0])
        self.v0 = np.array([0.0,     v_peri])

        # risultati popolati da integra()
        self.t      = None
        self.pos    = None
        self.vel    = None
        self.E      = None
        self.T_sim  = None

    # -----------------------------------------------------------------
    # Forza e energia: contengono *tutta* la fisica della simulazione
    # -----------------------------------------------------------------

    @staticmethod
    def accelerazione(r):
        """Accelerazione gravitazionale newtoniana.

        Dalle (1) e (2):  a = F/m = -GM/r² · r̂
        (segno meno = sempre attrattiva verso il Sole, posto in origine).
        """
        d = np.linalg.norm(r)
        return -GM * r / d**3

    @staticmethod
    def energia(r, v):
        """Energia meccanica specifica (per unità di massa).

            E/m = ½ v² - GM/r

        Per un'orbita chiusa kepleriana deve restare costante: la sua
        variazione è il nostro indicatore di affidabilità numerica.
        """
        return 0.5 * np.dot(v, v) - GM / np.linalg.norm(r)

    # -----------------------------------------------------------------
    # Integratore: Velocity Verlet (simplettico)
    # -----------------------------------------------------------------

    def integra(self, dt, t_max):
        """Integra il moto con il metodo di Velocity Verlet.

        Schema (un passo da t a t+dt):
            r(t+dt) = r(t) + v(t)·dt + ½ a(t) dt²
            a(t+dt) = -GM · r(t+dt)/|r(t+dt)|³
            v(t+dt) = v(t) + ½ [a(t) + a(t+dt)] · dt

        È un integratore *simplettico*: conserva ottimamente l'energia
        su tempi lunghi, requisito essenziale per orbite chiuse.
        L'integrazione si interrompe automaticamente quando il pianeta
        torna al perielio (rilevamento del periodo).
        """
        n_max = int(t_max / dt) + 2
        pos = np.zeros((n_max, 2))
        vel = np.zeros((n_max, 2))
        E   = np.zeros(n_max)
        t   = np.arange(n_max) * dt

        pos[0] = self.r0
        vel[0] = self.v0
        E[0]   = self.energia(pos[0], vel[0])
        a_curr = self.accelerazione(pos[0])

        T_sim = None
        v_r_prev = 0.0          # al perielio iniziale dr/dt = 0
        i_end = n_max - 1

        for i in range(1, n_max):
            # --- passo di Verlet ---
            pos[i] = pos[i-1] + vel[i-1] * dt + 0.5 * a_curr * dt**2
            a_new  = self.accelerazione(pos[i])
            vel[i] = vel[i-1] + 0.5 * (a_curr + a_new) * dt
            a_curr = a_new
            E[i]   = self.energia(pos[i], vel[i])

            # --- rilevamento ritorno al perielio ---
            # v_r = (r · v) / |r|  è la velocità radiale.
            # Al perielio r è minimo ⇒ v_r = 0; subito dopo v_r > 0
            # (il pianeta si allontana), all'afelio v_r di nuovo = 0,
            # poi v_r < 0 fino al perielio successivo (cambio di segno).
            r_mag = np.linalg.norm(pos[i])
            v_r   = np.dot(pos[i], vel[i]) / r_mag
            if T_sim is None and i > 20:
                if v_r_prev < 0.0 and v_r >= 0.0:
                    # interpolazione lineare per stimare meglio l'istante
                    frac = -v_r_prev / (v_r - v_r_prev)
                    T_sim = t[i-1] + frac * dt
                    i_end = i
                    break
            v_r_prev = v_r

        # tronchiamo gli array al primo periodo completo
        self.pos   = pos[:i_end+1]
        self.vel   = vel[:i_end+1]
        self.E     = E[:i_end+1]
        self.t     = t[:i_end+1]
        self.T_sim = T_sim
        return self.t, self.pos


# ---------------------------------------------------------------------------
#  Simulazione di più orbite
# ---------------------------------------------------------------------------

def simula_orbite(parametri, passi_per_orbita=10000):
    """Crea e integra una lista di orbite.

    parametri : lista di (a, e, nome)
    passi_per_orbita : risoluzione temporale (dt ≈ T/passi_per_orbita)
    """
    orbite = []
    for a, e, nome in parametri:
        orb = Orbita(a, e, nome)
        # T atteso da Keplero per scegliere dt (lo usiamo SOLO per
        # dimensionare il passo: il valore vero di T lo misureremo).
        T_atteso = a ** 1.5
        dt = T_atteso / passi_per_orbita
        orb.integra(dt=dt, t_max=2.0 * T_atteso)
        orbite.append(orb)
        print(f"  • {nome:<10s}  a={a:5.2f} UA  e={e:4.2f}  "
              f"T_sim={orb.T_sim:7.4f} anni  "
              f"ΔE/|E|={(orb.E.max()-orb.E.min())/abs(orb.E[0]):.2e}")
    return orbite


# ---------------------------------------------------------------------------
#  Grafico log–log
# ---------------------------------------------------------------------------

def grafico_log_log(orbite, salva="keplero_loglog.png"):
    """Grafico log T vs log a con fit lineare.

    Se T = k · a^m  ⇒  log T = m · log a + log k.
    La terza legge di Keplero predice m = 1.5 (cioè T² ∝ a³).
    """
    a_vals = np.array([o.a     for o in orbite])
    T_vals = np.array([o.T_sim for o in orbite])

    log_a = np.log10(a_vals)
    log_T = np.log10(T_vals)
    m, q = np.polyfit(log_a, log_T, 1)

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.loglog(a_vals, T_vals, 'o', color='#d62728',
              markersize=10, label='Dati simulati')
    a_fit = np.logspace(np.log10(a_vals.min()) - 0.1,
                        np.log10(a_vals.max()) + 0.1, 100)
    T_fit = 10**q * a_fit**m
    ax.loglog(a_fit, T_fit, '-', color='#1f77b4',
              label=f'Fit:  T = {10**q:.3f} · a^{m:.4f}')

    # linea teorica T = a^1.5 per confronto
    ax.loglog(a_fit, a_fit**1.5, '--', color='gray', alpha=0.7,
              label='Teoria: T = a^1.5')

    for o in orbite:
        ax.annotate(o.nome, (o.a, o.T_sim),
                    xytext=(6, 4), textcoords='offset points', fontsize=8)

    ax.set_xlabel("semiasse maggiore  a  [UA]")
    ax.set_ylabel("periodo  T  [anni]")
    ax.set_title("Terza legge di Keplero  (pendenza attesa = 1.5)")
    ax.grid(True, which='both', alpha=0.3)
    ax.legend(loc='upper left')
    fig.tight_layout()
    if salva:
        fig.savefig(salva, dpi=130)
    return fig, m, q


# ---------------------------------------------------------------------------
#  Animazione
# ---------------------------------------------------------------------------

def animazione(orbite, n_frames=300, salva_png="keplero_orbite.png",
               salva_anim=None):
    """Animazione delle orbite attorno al Sole.

    Ogni pianeta avanza nel suo tempo proprio: in un dato intervallo
    di animazione, i pianeti veloci (a piccolo) completano più giri di
    quelli lenti (a grande), rendendo *visivamente* la terza legge.
    """
    fig, ax = plt.subplots(figsize=(9, 9))
    r_max = max(o.a * (1.0 + o.e) for o in orbite) * 1.15
    ax.set_xlim(-r_max, r_max)
    ax.set_ylim(-r_max, r_max)
    ax.set_aspect('equal')
    ax.set_facecolor('#05050f')
    ax.set_title("Orbite integrate da  F = G·M·m / r²")
    ax.set_xlabel("x [UA]"); ax.set_ylabel("y [UA]")
    ax.grid(True, color='white', alpha=0.08)

    # Sole
    ax.plot(0, 0, marker='o', color='gold', markersize=22,
            markeredgecolor='orange', zorder=5)

    colori   = plt.cm.plasma(np.linspace(0.15, 0.9, len(orbite)))
    scie     = []
    pianeti  = []
    etichette = []
    for o, c in zip(orbite, colori):
        linea, = ax.plot([], [], '-', color=c, linewidth=1.3, alpha=0.7)
        punto, = ax.plot([], [], 'o', color=c, markersize=8,
                          markeredgecolor='white', markeredgewidth=0.5)
        scie.append(linea)
        pianeti.append(punto)
        etichette.append(f"{o.nome}  (a={o.a} UA, T={o.T_sim:.2f} a)")
    ax.legend(pianeti, etichette, loc='upper right', fontsize=8,
              facecolor='#101025', labelcolor='white', framealpha=0.8)

    # tempo totale dell'animazione: 1.2 periodi del pianeta più lento
    T_max   = max(o.T_sim for o in orbite)
    t_total = 1.2 * T_max
    dt_anim = t_total / n_frames

    def update(frame):
        t_curr = frame * dt_anim
        for o, linea, punto in zip(orbite, scie, pianeti):
            n = len(o.pos)
            if t_curr < o.T_sim:
                # prima orbita in corso: la scia cresce
                idx = int((t_curr / o.T_sim) * (n - 1))
                linea.set_data(o.pos[:idx+1, 0], o.pos[:idx+1, 1])
            else:
                # ellisse già completata: scia = orbita intera
                linea.set_data(o.pos[:, 0], o.pos[:, 1])
                t_in_orb = t_curr % o.T_sim
                idx = int((t_in_orb / o.T_sim) * (n - 1))
            punto.set_data([o.pos[idx, 0]], [o.pos[idx, 1]])
        return scie + pianeti

    anim = FuncAnimation(fig, update, frames=n_frames,
                         interval=40, blit=True)

    # frame statico per la relazione (tutte le orbite complete)
    for o, linea, punto in zip(orbite, scie, pianeti):
        linea.set_data(o.pos[:, 0], o.pos[:, 1])
        punto.set_data([o.pos[0, 0]], [o.pos[0, 1]])
    if salva_png:
        fig.savefig(salva_png, dpi=130, facecolor=fig.get_facecolor())

    if salva_anim:
        try:
            anim.save(salva_anim, fps=25, dpi=100)
            print(f"  Animazione salvata in {salva_anim}")
        except Exception as exc:
            print(f"  (animazione non salvata: {exc})")

    return fig, anim


# ---------------------------------------------------------------------------
#  Tabella e riassunto
# ---------------------------------------------------------------------------

def stampa_tabella(orbite):
    """Tabella numerica dei risultati."""
    print("\n" + "=" * 78)
    print(f"{'pianeta':<10s} {'a [UA]':>8s} {'e':>6s}"
          f" {'T_sim [a]':>11s} {'T_teor [a]':>11s}"
          f" {'T²/a³':>10s} {'ΔE/|E| [%]':>12s}")
    print("-" * 78)
    risultati = []
    for o in orbite:
        T = o.T_sim
        T_teor   = o.a ** 1.5
        rapporto = T**2 / o.a**3
        dE_perc  = (o.E.max() - o.E.min()) / abs(o.E[0]) * 100
        print(f"{o.nome:<10s} {o.a:8.3f} {o.e:6.2f}"
              f" {T:11.5f} {T_teor:11.5f}"
              f" {rapporto:10.5f} {dE_perc:12.2e}")
        risultati.append((o.nome, o.a, o.e, T, rapporto, dE_perc))
    print("=" * 78)
    print("Nelle nostre unità (UA, anni, M☉) la terza legge prevede T²/a³ = 1.")
    print("ΔE/|E| piccolo conferma la stabilità del Velocity Verlet.")
    return risultati


def riassunto_relazione(orbite, pendenza, intercetta):
    """Riassunto finale formattato per essere incollato nella relazione."""
    a_vals = np.array([o.a     for o in orbite])
    T_vals = np.array([o.T_sim for o in orbite])
    rapporti = T_vals**2 / a_vals**3
    dE_max = max((o.E.max() - o.E.min()) / abs(o.E[0]) for o in orbite) * 100

    print("\n" + "*" * 78)
    print(" RIASSUNTO PER LA RELAZIONE ".center(78, "*"))
    print("*" * 78)
    print(f"""
Numero di orbite simulate:   {len(orbite)}
Semiassi (UA):               {', '.join(f'{a:.2f}' for a in a_vals)}
Integratore:                 Velocity Verlet (simplettico)
Unità:                       UA, anni, masse solari   →   GM_sole = 4π²

Risultato del fit log-log di T vs a :
    log T = m · log a + q
    pendenza  m = {pendenza:.5f}        (teoria: 1.5)
    intercetta q = {intercetta:.5f}      (teoria: 0)
    discrepanza relativa su m:  {abs(pendenza - 1.5)/1.5 * 100:.4f} %

Rapporto T²/a³ medio:  {rapporti.mean():.5f}  ±  {rapporti.std():.5f}
(valore teorico = 1.00000  →  la costante di Keplero)

Conservazione dell'energia:
    massima variazione relativa ΔE/|E| sul singolo periodo: {dE_max:.2e} %
    → la simulazione è numericamente affidabile.

Conclusione fisica:
    Partendo unicamente dalle due leggi di Newton
        F = m·a      (dinamica)
        F = G·M·m/r² (gravitazione universale, 1687)
    e integrando numericamente con Velocity Verlet, abbiamo OSSERVATO
    emergere la relazione  T² ∝ a³  (Keplero, 1619) per orbite di
    diversi semiassi ed eccentricità.

    La terza legge di Keplero NON è quindi un postulato indipendente,
    ma una conseguenza diretta della legge di gravitazione universale.
""")
    print("*" * 78)


# ---------------------------------------------------------------------------
#  Main
# ---------------------------------------------------------------------------

def main():
    # Sei orbite con semiassi che coprono ~ un fattore 12.
    # Eccentricità varie per mostrare che la legge vale anche per orbite
    # marcatamente ellittiche.
    parametri = [
        (0.39, 0.21, "Mercurio"),
        (0.72, 0.01, "Venere"),
        (1.00, 0.02, "Terra"),
        (1.52, 0.09, "Marte"),
        (2.77, 0.25, "Cerere*"),   # asteroide (eccentricità maggiorata)
        (5.20, 0.05, "Giove"),
    ]

    print("Integrazione delle orbite (Velocity Verlet)…\n")
    orbite = simula_orbite(parametri, passi_per_orbita=10000)

    # 1) tabella numerica
    stampa_tabella(orbite)

    # 2) grafico log–log con fit
    print("\nGenerazione grafico log–log…")
    _, pendenza, intercetta = grafico_log_log(orbite,
                                              salva="keplero_loglog.png")
    print("  salvato:  keplero_loglog.png")

    # 3) animazione + figura statica
    print("Generazione animazione…")
    animazione(orbite, n_frames=300,
               salva_png="keplero_orbite.png",
               salva_anim=None)   # impostare "keplero_orbite.gif" per salvare
    print("  salvato:  keplero_orbite.png")

    # 4) riassunto per la relazione
    riassunto_relazione(orbite, pendenza, intercetta)

    # Mostra le finestre (no-op in ambienti senza display)
    try:
        plt.show()
    except Exception:
        pass


if __name__ == "__main__":
    main()
