# Project Directory Structure (Personal Use)

Проект предназначен для личного использования, без упаковки в pip-пакет, поэтому весь код лежит напрямую в `src/` без дополнительного уровня (`app/` и т.п.).

```text
project-root/
├── README.md
├── requirements.txt                 # зависимости проекта
├── .gitignore
│
├── docs/                            # документация
│   ├── PROJECT_TARGET_ARCHITECTURE.md
│   ├── PROJECT_MIGRATION_PLAN.md
│   └── ...                          # дополнительные заметки/спеки
│
├── data/                            # данные (НЕ код)
│   ├── raw/                         # исходные CSV с котировками
│   ├── processed/                   # подготовленные/агрегированные датасеты (опционально)
│   └── baseline/                    # baseline для регрессии S_01 (метрики/сделки)
│
├── tools/                           # скрипты для разработки и отладки
│   ├── generate_baseline_s01.py     # генерация эталонных результатов
│   └── ...                          # конвертеры, разовые утилиты и т.п.
│
├── tests/                           # автотесты
│   ├── test_regression_s01.py
│   ├── test_backtest_engine.py
│   ├── test_optuna_engine.py
│   ├── test_indicators.py
│   ├── test_metrics.py
│   └── ...
│
├── src/                             # весь исполняемый код проекта
│   ├── core/                        # ядро: движки + общие утилиты
│   │   ├── __init__.py
│   │   ├── backtest_engine.py       # основной бэктест-движок
│   │   ├── optuna_engine.py         # единственный оптимизатор (Optuna-only)
│   │   ├── walkforward_engine.py    # WFA-движок (надстройка над Optuna + backtest)
│   │   ├── metrics.py               # расчёт всех метрик (Basic/Advanced/WFA)
│   │   └── export.py                # экспорт результатов (CSV для Optuna/WFA/сделок)
│   │
│   ├── indicators/                  # библиотека индикаторов
│   │   ├── __init__.py
│   │   ├── ma.py                    # скользящие средние (SMA, EMA, и т.п.)
│   │   ├── volatility.py            # ATR, NATR и другие волатильностные индикаторы
│   │   ├── oscillators.py           # RSI, Stoch, CCI и т.п.
│   │   ├── volume.py                # OBV и прочие volume-based индикаторы
│   │   ├── trend.py                 # ADX и трендовые индикаторы
│   │   └── misc.py                  # всё остальное
│   │
│   ├── strategies/                  # стратегии и их параметры
│   │   ├── __init__.py
│   │   ├── base.py                  # BaseStrategy + fallback для индикаторов
│   │   ├── simple_ma/
│   │   │   ├── __init__.py
│   │   │   ├── strategy.py          # простая стратегия для обкатки архитектуры
│   │   │   └── config.json          # описание параметров/диапазонов
│   │   └── s01_trailing_ma/
│   │       ├── __init__.py
│   │       ├── strategy.py          # реализация S01TrailingMAv2
│   │       └── config.json          # описание параметров/диапазонов
│   │   # здесь же будут другие стратегии, по тому же шаблону
│   │
│   ├── ui/                          # сервер и фронт
│   │   ├── __init__.py
│   │   ├── server.py                # Flask/FastAPI, HTTP API
│   │   ├── templates/
│   │   │   └── index.html           # основная HTML-страница
│   │   └── static/
│   │       ├── js/
│   │       │   └── main.js          # логика фронтенда
│   │       └── css/
│   │           └── style.css        # стили
│   │
│   └── cli/                         # опционально: CLI-инструменты
│       ├── __init__.py
│       └── run_backtest.py          # запуск бэктеста из командной строки (включая флаг логирования)
│
└── ...
```

### Краткие комментарии

- **`src/core/`** — три главных движка (`backtest_engine.py`, `optuna_engine.py`, `walkforward_engine.py`) и общие модули `metrics.py` и `export.py`.
- **`src/indicators/`** — общие индикаторы для всех стратегий.
- **`src/strategies/`**:
  - `base.py` задаёт интерфейс и общий функционал,
  - `simple_ma/` — тренировочная стратегия для обкатки архитектуры,
  - `s01_trailing_ma/` — S_01_v2 на новой архитектуре.
- **`src/ui/`** — отдельный “остров” для веб-интерфейса:
  - `server.py` общается с ядром,
  - `templates/` + `static/` — фронтенд.
- **`src/cli/`** — не обязателен, но удобно иметь лёгкий CLI для локальных прогонов без UI (с опциональным логированием).
- **`data/`, `tools/`, `tests/`, `docs/`** — чётко отделены от кода, чтобы не мешаться при работе с логикой проекта.
