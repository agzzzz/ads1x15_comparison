# Comparativo ADS1015 vs ADS1115

Analise comparativa de sinais adquiridos pelos ADCs ADS1015 (12 bits, 3300 SPS) e ADS1115 (16 bits, 860 SPS), ambos configurados com PGA = +-4.096V em modo single-ended.

## Estrutura

- `logs/` — arquivos de aquisicao (CSV: sample, timestamp_us, raw, voltage_V)
- `signal_utils.py` — funcoes auxiliares (parse, RMS, pico, Vpp, conversao TC)
- `plot_comparison.py` — gera grafico HTML interativo comparando os dois ADCs com referencia ideal
- `generate_all.py` — gera HTMLs para todos os sinais em `logs/`

## Uso

```bash
pip install -r requirements.txt

# Gerar grafico para um sinal
python3 plot_comparison.py sine_60hz_33.85mVrms --i_primary 100

# Gerar todos os graficos
python3 generate_all.py --i_primary 100
```

Os HTMLs sao salvos em `output/`.
