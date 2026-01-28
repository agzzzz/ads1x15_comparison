import numpy as np

# Constantes do ADC — saída bipolar (complemento de 2), PGA = ±4.096V
# Registro de 16 bits com sinal: -32768 a +32767
# Em modo single-ended, apenas códigos positivos são utilizados (0 a 32767)
ADC_VREF = 4.096          # Tensão de referência / fundo de escala positivo (V)
ADC_MAX_CODE = 32768      # 2^15 (metade da faixa do registrador de 16 bits)
ADS1015_LSB = 2.0e-3      # Resolução do ADS1015: 12 bits, LSB = 4.096/2048 = 2 mV
ADS1115_LSB = 0.125e-3    # Resolução do ADS1115: 16 bits, LSB = 4.096/32768 = 0.125 mV

# Constante do TC
CT_FS_VOLTAGE = 0.333  # Tensão de fundo de escala do TC (V)


def parse_log(filepath):
    """Lê um arquivo de log CSV e retorna os dados como arrays numpy.

    Colunas esperadas: sample, timestamp_us, raw, voltage_V

    Retorna dict com:
        timestamps_us: array de timestamps (µs)
        raw: array de valores raw (int)
        voltage: array de tensão calculada a partir do raw (V)
    """
    skip = 0
    with open(filepath) as f:
        for line in f:
            if line.startswith("#") or line.startswith("sample"):
                skip += 1
            else:
                break
    data = np.loadtxt(filepath, delimiter=",", skiprows=skip)
    raw = data[:, 2].astype(int)
    return {
        "timestamps_us": data[:, 1],
        "raw": raw,
        "voltage": raw * ADC_VREF / ADC_MAX_CODE,
    }


def remove_dc_bias(signal):
    """Remove o componente DC (média) de um sinal."""
    return signal - np.mean(signal)


def calc_rms(signal):
    """Calcula o valor RMS de um sinal, removendo o bias DC."""
    ac = remove_dc_bias(signal)
    return float(np.sqrt(np.mean(ac ** 2)))


def calc_peak(signal, percentile=99.5):
    """Calcula o valor de pico após remoção do bias DC.

    Usa percentil sobre |sinal| para descartar picos espúrios.
    """
    ac = remove_dc_bias(signal)
    return float(np.percentile(np.abs(ac), percentile))


def calc_peak_to_peak(signal, percentile=99.5):
    """Calcula o valor pico a pico após remoção do bias DC.

    Usa percentis simétricos (percentile e 100-percentile) para descartar
    picos espúrios em ambos os extremos.
    """
    ac = remove_dc_bias(signal)
    high = np.percentile(ac, percentile)
    low = np.percentile(ac, 100 - percentile)
    return float(high - low)


def vrms_to_current(vrms, i_primary):
    """Converte tensão RMS do secundário do TC para corrente primária.

    Args:
        vrms: tensão RMS medida no secundário (V)
        i_primary: corrente nominal primária do TC (A) — fundo de escala

    Returns:
        Corrente medida em Ampères.
    """
    return vrms * i_primary / CT_FS_VOLTAGE
