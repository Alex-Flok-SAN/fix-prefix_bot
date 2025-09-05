# Binance M1 Exporter (отдельно от бота)

Утилита для выгрузки минутных свечей (1m) с Binance (Spot/USDT-M Futures) в **Parquet по месяцам**.

## Установка
```bash
python -m pip install -r requirements.txt
```

## Запуск
```bash
python binance_m1_export.py \
  --symbol BTCUSDT \
  --market spot \
  --start 2024-01-01 \
  --end 2024-03-31 \
  --out-dir ./data/binance_spot/BTCUSDT
```

## Выходные файлы
- `BTCUSDT_M1_YYYY-MM.parquet` — минутки за месяц.
- `BTCUSDT_M1_YYYY-MM.manifest.json` — контрольный файл (строки, диапазон ts, sha256).

## Гарантии качества
- Таймстемпы в **миллисекундах** (UTC).
- Дедуп по `ts_open_ms`, сортировка, базовая проверка инвариантов OHLC.
- Проверка непрерывности (шаг 60_000 мс), попытка дозагрузить «дыры».
- Названия файлов **чистые**, без постфиксов.

## Подсказки
- Для Futures используйте `--market futures`.
- При 429/5xx утилита сама подождёт и повторит попытку.
- Можно уменьшить нагрузку на API: `--sleep-ms 250`.
