"""
¿Cuánto se degrada un detector de voz sintética cuando el audio pasa por una nota de voz de WhatsApp?

Detector: AASIST y AASIST-L (clovaai/aasist, entrenados en ASVspoof 2019 LA).
Datos: In-the-Wild (mueller91), voces reales y falsas de 58 figuras públicas, en inglés.
Canal: Opus a 16 kbps y 8 kbps, mono 16 kHz, modo voip (parecido a una nota de voz de WhatsApp y a una red mala).

Diseño honesto:
  - Partición por hablante: nadie aparece en entrenamiento y en prueba.
  - Mitigación = reentrenar AASIST-L con aumento de códec. Control = reentrenar igual pero solo con audio limpio,
    para separar el efecto del códec del simple ajuste al dominio de In-the-Wild.
  - Métrica: EER (tasa de error igual), más exactitud con el umbral fijado en audio limpio (lo que pasa en la
    práctica: el umbral se calibra una vez y luego llega audio comprimido).

Uso (en la máquina de investigación):
  python experimento.py --raiz /opt/voz --salida /opt/voz/resultados
"""

import argparse
import csv
import json
import random
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

LARGO = 64600  # ~4 s a 16 kHz, como en AASIST
CONDICIONES = {"limpio": None, "opus_16k": "16k", "opus_8k": "8k"}


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------
def _pcm(cmd, entrada=None):
    r = subprocess.run(cmd, input=entrada, capture_output=True, check=True)
    return r.stdout


def cargar(ruta, condicion):
    """Primeros ~4 s, mono 16 kHz, pasando opcionalmente por Opus. Devuelve float32 de LARGO muestras."""
    base = ["ffmpeg", "-v", "error", "-t", "4.2", "-i", str(ruta), "-ac", "1", "-ar", "16000"]
    if CONDICIONES[condicion] is None:
        crudo = _pcm(base + ["-f", "s16le", "-"])
    else:
        ogg = _pcm(base + ["-c:a", "libopus", "-b:a", CONDICIONES[condicion], "-application", "voip", "-f", "ogg", "-"])
        crudo = _pcm(["ffmpeg", "-v", "error", "-i", "-", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], ogg)
    x = np.frombuffer(crudo, dtype=np.int16).astype(np.float32) / 32768.0
    if len(x) == 0:
        x = np.zeros(1, dtype=np.float32)
    if len(x) < LARGO:
        x = np.tile(x, LARGO // len(x) + 1)
    return x[:LARGO]


def preparar(lista, condicion, hilos=16):
    with ThreadPoolExecutor(hilos) as ex:
        return np.stack(list(ex.map(lambda r: cargar(r, condicion), lista)))


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------
def eer(puntajes, etiquetas):
    """EER con bona fide = 1 (puntaje alto = real). Devuelve (eer, umbral)."""
    orden = np.argsort(puntajes)
    p, y = np.asarray(puntajes)[orden], np.asarray(etiquetas)[orden]
    n_real, n_falso = (y == 1).sum(), (y == 0).sum()
    frr = np.cumsum(y == 1) / n_real              # reales por debajo del umbral (rechazados)
    far = 1 - np.cumsum(y == 0) / n_falso         # falsos por encima del umbral (aceptados)
    i = np.argmin(np.abs(frr - far))
    return float((frr[i] + far[i]) / 2), float(p[i])


def exactitud(puntajes, etiquetas, umbral):
    pred = (np.asarray(puntajes) > umbral).astype(int)
    y = np.asarray(etiquetas)
    falsos = y == 0
    return {"exactitud": float((pred == y).mean()),
            "falsos_aceptados_como_reales": float((pred[falsos] == 1).mean())}


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------
def modelo(raiz, nombre):
    sys.path.insert(0, str(raiz / "aasist"))
    from models.AASIST import Model
    conf = json.loads((raiz / "aasist" / "config" / f"{nombre}.conf").read_text())
    m = Model(conf["model_config"])
    m.load_state_dict(torch.load(raiz / "aasist" / "models" / "weights" / f"{nombre}.pth", map_location="cpu", weights_only=True))
    return m, conf["model_config"]


@torch.no_grad()
def puntuar(m, X, lote=64):
    m.eval()
    salida = []
    for i in range(0, len(X), lote):
        _, out = m(torch.from_numpy(X[i:i + lote]))
        salida.append((out[:, 1] - out[:, 0]).numpy())  # margen a favor de "real"
    return np.concatenate(salida)


def reentrenar(m, datos_por_cond, y, condiciones, epocas, semilla, lote_n=16):
    torch.manual_seed(semilla)
    rng = np.random.default_rng(semilla)
    opt = torch.optim.Adam(m.parameters(), lr=1e-4, weight_decay=1e-4)
    perdida = nn.CrossEntropyLoss()
    yt = torch.from_numpy(y).long()
    n = len(y)
    for ep in range(epocas):
        m.train()
        orden = rng.permutation(n)
        total = 0.0
        for i in range(0, n, lote_n):
            idx = orden[i:i + lote_n]
            conds = rng.choice(condiciones, size=len(idx))
            lote = np.stack([datos_por_cond[c][j] for c, j in zip(conds, idx)])
            ganancia = rng.uniform(0.5, 1.0, size=(len(idx), 1)).astype(np.float32)  # volumen variable
            _, out = m(torch.from_numpy(lote * ganancia))
            loss = perdida(out, yt[idx])
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += loss.item() * len(idx)
        print(f"    época {ep + 1}/{epocas}: pérdida {total / n:.4f}", flush=True)
    return m


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz", default="/opt/voz")
    ap.add_argument("--salida", default="/opt/voz/resultados")
    ap.add_argument("--prueba-por-clase", type=int, default=600)
    ap.add_argument("--entreno-por-clase", type=int, default=1000)
    ap.add_argument("--epocas", type=int, default=4)
    ap.add_argument("--semilla", type=int, default=7)
    ap.add_argument("--omitir-preentrenados", action="store_true",
                    help="reutiliza la evaluación de los modelos preentrenados de un resultados.json anterior")
    a = ap.parse_args()
    raiz, salida = Path(a.raiz), Path(a.salida)
    salida.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(max(1, torch.get_num_threads()))
    t0 = time.time()

    meta_ruta = next((raiz / "itw").rglob("meta.csv"))
    carpeta = meta_ruta.parent
    filas = list(csv.DictReader(meta_ruta.open(encoding="utf-8")))
    hablantes = sorted({f["speaker"] for f in filas})
    rng = random.Random(a.semilla)
    rng.shuffle(hablantes)
    corte = int(len(hablantes) * 0.7)
    h_entreno, h_prueba = set(hablantes[:corte]), set(hablantes[corte:])

    def muestra(hs, n):
        reales = [f for f in filas if f["speaker"] in hs and f["label"].strip().lower().startswith("bona")]
        falsos = [f for f in filas if f["speaker"] in hs and not f["label"].strip().lower().startswith("bona")]
        rng.shuffle(reales)
        rng.shuffle(falsos)
        sel = reales[:n] + falsos[:n]
        return [carpeta / f["file"] for f in sel], np.array([1] * len(reales[:n]) + [0] * len(falsos[:n]))

    rutas_p, y_p = muestra(h_prueba, a.prueba_por_clase)
    rutas_e, y_e = muestra(h_entreno, a.entreno_por_clase)
    info = {"hablantes_total": len(hablantes), "hablantes_entreno": len(h_entreno), "hablantes_prueba": len(h_prueba),
            "prueba": {"reales": int(y_p.sum()), "falsos": int((y_p == 0).sum())},
            "entreno": {"reales": int(y_e.sum()), "falsos": int((y_e == 0).sum())},
            "clips_totales_dataset": len(filas)}
    print("Datos:", json.dumps(info), flush=True)

    print("Preparando audio (limpio, Opus 16k, Opus 8k)…", flush=True)
    Xp = {c: preparar(rutas_p, c) for c in CONDICIONES}
    print(f"  prueba lista ({time.time() - t0:.0f} s)", flush=True)
    Xe = {c: preparar(rutas_e, c) for c in CONDICIONES}
    print(f"  entreno listo ({time.time() - t0:.0f} s)", flush=True)

    resultados = {"datos": info, "condiciones": {"opus_16k": "Opus 16 kbps mono 16 kHz voip (nota de voz)",
                                                 "opus_8k": "Opus 8 kbps (red mala)"}, "modelos": {}}

    def evaluar(nombre, m):
        r = {}
        punt = {c: puntuar(m, Xp[c]) for c in CONDICIONES}
        e_limpio, umbral = eer(punt["limpio"], y_p)
        for c in CONDICIONES:
            e, _ = eer(punt[c], y_p)
            r[c] = {"eer": e, **exactitud(punt[c], y_p, umbral),
                    "percentiles_reales": np.percentile(punt[c][y_p == 1], [10, 25, 50, 75, 90]).round(3).tolist(),
                    "percentiles_falsos": np.percentile(punt[c][y_p == 0], [10, 25, 50, 75, 90]).round(3).tolist()}
        r["umbral_calibrado_en_limpio"] = umbral
        resultados["modelos"][nombre] = r
        print(f"  {nombre:<34} " + " · ".join(f"{c}: EER {r[c]['eer']:.1%}" for c in CONDICIONES), flush=True)
        (salida / "resultados.json").write_text(json.dumps(resultados, indent=2, ensure_ascii=False))

    previo = salida / "resultados.json"
    if a.omitir_preentrenados and previo.exists():
        anteriores = json.loads(previo.read_text()).get("modelos", {})
        resultados["modelos"].update({k: v for k, v in anteriores.items() if "preentrenado" in k})
        print("Preentrenados: se reutiliza la evaluación anterior.", flush=True)
    else:
        print("Evaluando modelos preentrenados (ASVspoof 2019)…", flush=True)
        for nombre in ("AASIST-L", "AASIST"):
            m, _ = modelo(raiz, nombre)
            evaluar(f"{nombre} preentrenado", m)


    print("Control: reentrenar AASIST-L solo con audio limpio…", flush=True)
    m, _ = modelo(raiz, "AASIST-L")
    m = reentrenar(m, Xe, y_e, ["limpio"], a.epocas, a.semilla)
    evaluar("AASIST-L reentrenado (solo limpio)", m)

    print("Mitigación: reentrenar AASIST-L con aumento de códec…", flush=True)
    m, _ = modelo(raiz, "AASIST-L")
    m = reentrenar(m, Xe, y_e, list(CONDICIONES), a.epocas, a.semilla)
    evaluar("AASIST-L reentrenado (con códec)", m)
    torch.save(m.state_dict(), salida / "AASIST-L_eco_codec.pth")
    resultados["umbral_mitigado"] = resultados["modelos"]["AASIST-L reentrenado (con códec)"]["umbral_calibrado_en_limpio"]
    resultados["segundos"] = round(time.time() - t0)
    (salida / "resultados.json").write_text(json.dumps(resultados, indent=2, ensure_ascii=False))
    print(f"Listo en {resultados['segundos']} s", flush=True)


if __name__ == "__main__":
    main()
