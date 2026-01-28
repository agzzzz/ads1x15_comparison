import argparse
import os
import re

import numpy as np
import plotly.graph_objects as go

from signal_utils import (
    parse_log,
    remove_dc_bias,
    calc_rms,
    calc_peak,
    calc_peak_to_peak,
    vrms_to_current,
)

LOGS_DIR = "logs"
OUTPUT_DIR = "output"


def parse_signal_name(name):
    """Extrai tipo de onda, frequência, Vrms nominal e parâmetros extras do nome do sinal.

    Retorna dict com chaves: type, freq_hz, vrms_v, e opcionais: duty_pct, mod_freq_hz.
    """
    # Dimmer: dimmer_50pct_60hz_118mVrms
    m = re.match(
        r"dimmer_(\d+)pct_(\d+)hz_([\d.]+)mVrms", name, re.IGNORECASE
    )
    if m:
        return {
            "type": "dimmer",
            "duty_pct": int(m.group(1)),
            "freq_hz": int(m.group(2)),
            "vrms_v": float(m.group(3)) * 1e-3,
        }

    # AM: sine_60hz_mod_400hz_10.18mVrms
    m = re.match(
        r"sine_(\d+)hz_mod_(\d+)hz_([\d.]+)mVrms", name, re.IGNORECASE
    )
    if m:
        return {
            "type": "sine_mod",
            "freq_hz": int(m.group(1)),
            "mod_freq_hz": int(m.group(2)),
            "vrms_v": float(m.group(3)) * 1e-3,
        }

    # Sine, square, triangle: tipo_60hz_X.XXmVrms
    m = re.match(
        r"(sine|square|triangle)_(\d+)hz_([\d.]+)mVrms", name, re.IGNORECASE
    )
    if m:
        return {
            "type": m.group(1).lower(),
            "freq_hz": int(m.group(2)),
            "vrms_v": float(m.group(3)) * 1e-3,
        }

    raise ValueError(f"Nome de sinal não reconhecido: {name}")


def generate_reference(params, duration=1.0, n_points=10000):
    """Gera onda de referência ideal com RMS igual ao Vrms nominal.

    Retorna (t_s, waveform_v): arrays numpy com tempo em segundos e tensão em Volts.
    """
    t = np.linspace(0, duration, n_points, endpoint=False)
    f = params["freq_hz"]
    vrms = params["vrms_v"]
    wtype = params["type"]

    if wtype == "sine":
        wave = np.sin(2 * np.pi * f * t)

    elif wtype == "square":
        wave = np.sign(np.sin(2 * np.pi * f * t))

    elif wtype == "triangle":
        # Onda triangular via sawtooth: 2*|2*(ft - floor(ft + 0.5))| - 1 ... simpler:
        phase = (f * t) % 1.0
        wave = 4 * np.abs(phase - 0.5) - 1

    elif wtype == "dimmer":
        # Leading-edge TRIAC: corte no início de cada semi-ciclo
        duty_pct = params["duty_pct"]
        firing_angle = np.pi * (1 - duty_pct / 100.0)  # 50% → π/2
        full_sine = np.sin(2 * np.pi * f * t)
        phase_in_cycle = (2 * np.pi * f * t) % np.pi
        wave = np.where(phase_in_cycle >= firing_angle, full_sine, 0.0)

    elif wtype == "sine_mod":
        # AM 100% de profundidade: portadora × (1 + cos(2π f_mod t))
        f_mod = params["mod_freq_hz"]
        carrier = np.sin(2 * np.pi * f * t)
        envelope = 1 + np.cos(2 * np.pi * f_mod * t)
        wave = carrier * envelope

    else:
        raise ValueError(f"Tipo de onda desconhecido: {wtype}")

    # Escalar para que o RMS da forma de onda seja igual ao Vrms nominal
    rms_raw = np.sqrt(np.mean(wave ** 2))
    if rms_raw > 0:
        wave = wave * (vrms / rms_raw)

    return t, wave


def build_metrics_table(params, ref_wave, voltage_1015, voltage_1115, i_primary):
    """Constrói HTML da tabela de métricas comparativas."""
    vrms_nom = params["vrms_v"]

    # Referência (onda gerada já sem DC)
    ref_rms = calc_rms(ref_wave)
    ref_peak = calc_peak(ref_wave)
    ref_pp = calc_peak_to_peak(ref_wave)
    ref_i = vrms_to_current(ref_rms, i_primary)

    # ADS1015
    rms_1015 = calc_rms(voltage_1015)
    peak_1015 = calc_peak(voltage_1015)
    pp_1015 = calc_peak_to_peak(voltage_1015)
    i_1015 = vrms_to_current(rms_1015, i_primary)

    # ADS1115
    rms_1115 = calc_rms(voltage_1115)
    peak_1115 = calc_peak(voltage_1115)
    pp_1115 = calc_peak_to_peak(voltage_1115)
    i_1115 = vrms_to_current(rms_1115, i_primary)

    rows = [
        (
            "Vrms (mV)",
            f"{vrms_nom * 1000:.3f}",
            f"{rms_1015 * 1000:.3f}",
            f"{rms_1115 * 1000:.3f}",
        ),
        (
            "Vpico (mV)",
            f"{ref_peak * 1000:.3f}",
            f"{peak_1015 * 1000:.3f}",
            f"{peak_1115 * 1000:.3f}",
        ),
        (
            "Vpp (mV)",
            f"{ref_pp * 1000:.3f}",
            f"{pp_1015 * 1000:.3f}",
            f"{pp_1115 * 1000:.3f}",
        ),
        (
            "Corrente (A)",
            f"{ref_i:.4f}",
            f"{i_1015:.4f}",
            f"{i_1115:.4f}",
        ),
    ]

    html = """
<div style="max-width:700px; margin:20px auto; font-family:sans-serif;">
  <h3 style="text-align:center;">Métricas comparativas (TC primário: {i_p:.0f} A)</h3>
  <table style="width:100%; border-collapse:collapse; text-align:center;">
    <thead>
      <tr style="background:#f0f0f0;">
        <th style="padding:8px; border:1px solid #ccc;">Métrica</th>
        <th style="padding:8px; border:1px solid #ccc;">Referência</th>
        <th style="padding:8px; border:1px solid #ccc;">ADS1015</th>
        <th style="padding:8px; border:1px solid #ccc;">ADS1115</th>
      </tr>
    </thead>
    <tbody>
""".format(i_p=i_primary)

    for label, ref_val, v1015, v1115 in rows:
        html += f"""      <tr>
        <td style="padding:8px; border:1px solid #ccc; font-weight:bold;">{label}</td>
        <td style="padding:8px; border:1px solid #ccc;">{ref_val}</td>
        <td style="padding:8px; border:1px solid #ccc;">{v1015}</td>
        <td style="padding:8px; border:1px solid #ccc;">{v1115}</td>
      </tr>
"""

    html += """    </tbody>
  </table>
</div>
"""
    return html


def main():
    parser = argparse.ArgumentParser(
        description="Gráfico comparativo ADS1015 vs ADS1115 com referência ideal"
    )
    parser.add_argument(
        "signal_name",
        help="Nome base do sinal (ex: sine_60hz_33.85mVrms)",
    )
    parser.add_argument(
        "--i_primary",
        type=float,
        required=True,
        help="Corrente nominal primária do TC em Ampères",
    )
    args = parser.parse_args()

    params = parse_signal_name(args.signal_name)

    # Carregar dados dos ADCs
    path_1015 = os.path.join(LOGS_DIR, f"{args.signal_name}_ads1015.log")
    path_1115 = os.path.join(LOGS_DIR, f"{args.signal_name}_ads1115.log")
    data_1015 = parse_log(path_1015)
    data_1115 = parse_log(path_1115)

    # Componente AC dos sinais adquiridos
    ac_1015 = remove_dc_bias(data_1015["voltage"])
    ac_1115 = remove_dc_bias(data_1115["voltage"])

    # Timestamps em ms
    t_1015_ms = data_1015["timestamps_us"] / 1000.0
    t_1115_ms = data_1115["timestamps_us"] / 1000.0

    # Referência ideal
    t_ref, ref_wave = generate_reference(params)
    t_ref_ms = t_ref * 1000.0

    # Gráfico Plotly
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=t_ref_ms, y=ref_wave * 1000,
        mode="lines",
        name="Referência",
        line=dict(color="gray", width=1.5, dash="dash"),
    ))

    fig.add_trace(go.Scatter(
        x=t_1015_ms, y=ac_1015 * 1000,
        mode="lines+markers",
        name="ADS1015",
        marker=dict(size=2),
        line=dict(color="#1f77b4", width=1),
    ))

    fig.add_trace(go.Scatter(
        x=t_1115_ms, y=ac_1115 * 1000,
        mode="lines+markers",
        name="ADS1115",
        marker=dict(size=2),
        line=dict(color="#ff7f0e", width=1),
    ))

    fig.update_layout(
        title=f"Comparação ADC — {args.signal_name}",
        xaxis_title="Tempo (ms)",
        yaxis_title="Tensão (mV)",
        template="plotly_white",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
        ),
        hovermode="x unified",
    )

    # Tabela de métricas
    table_html = build_metrics_table(
        params, ref_wave, data_1015["voltage"], data_1115["voltage"],
        args.i_primary,
    )

    # Gerar HTML combinado
    chart_html = fig.to_html(full_html=False, include_plotlyjs="cdn")
    full_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Comparação ADC — {args.signal_name}</title>
</head>
<body>
{chart_html}
{table_html}
</body>
</html>
"""

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"{args.signal_name}.html")
    with open(out_path, "w") as f:
        f.write(full_html)

    print(f"HTML salvo em: {out_path}")


if __name__ == "__main__":
    main()
