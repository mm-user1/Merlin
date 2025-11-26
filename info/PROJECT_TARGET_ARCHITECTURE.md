
# Target Architecture Overview
# Unified Core + Strategies + Optimization

**Version:** 1.3  
**Scope:** Финальное целевое состояние проекта после миграции с legacy-архитектуры на новую.

---

## 1. High-Level Structure

Проект делится на несколько логических слоёв:

- **Core Engines (3 основных движка)**
  - `backtest_engine.py`
  - `optuna_engine.py`
  - `walkforward_engine.py`

- **Core Utilities**
  - `metrics.py` — единый слой расчёта метрик
  - `export.py` — единый слой экспорта результатов

- **Domain Layers**
  - `indicators/` — библиотека индикаторов
  - `strategies/` — стратегии и их конфигурации

- **Interface Layer**
  - `server.py` — HTTP API (Flask)
  - `index.html` + `main.js` + `style.css` — фронтенд
  - `run_backtest.py` — CLI-обёртка для локальных запусков (опционально, dev-утилита)

Цель: вся основная бизнес-логика сосредоточена в трёх движках и нескольких чётких вспомогательных модулях. Стратегии и индикаторы изолированы, UI и обвязка не зависят от внутренних деталей ядра.

---

## 2. Core Engines

### 2.1. `backtest_engine.py` — Движок бэктеста

**Назначение:**  
Единый модуль для прогона одной стратегии на заданных данных.

**Основные задачи:**

1. **Подготовка данных**
   - Приём входного DataFrame (или уже загруженных данных).
   - Применение:
     - фильтра по `date_range`,
     - прогрева (`warmup_bars`),
     - нормализации индекса и колонок (OHLCV).
   - Возврат подготовленного датасета для симуляции.

2. **Симуляция сделок (баровый цикл)**

- Обход баров:
  - вызов логики стратегии (через основной контракт стратегии, см. ниже),
  - постановка ордеров стратегией через свой API,
  - исполнение ордеров ядром с учётом:
    - типа объёма (фиксированный `qty` или процент от equity),
    - комиссии,
    - размера контракта,
    - возможного slippage (если будет добавлен).
- Поддержка:
  - входа/выхода в позицию,
  - смены направления (по необходимости),
  - простого pyramiding (если будет использоваться).

3. **Результаты и структуры данных**

`backtest_engine.py` определяет и использует базовые структуры данных:

- `TradeRecord` — запись одной сделки:
  - время входа/выхода,
  - цена входа/выхода,
  - объём,
  - комиссия,
  - PnL и вспомогательные поля.

- `StrategyResult` — результат прогона стратегии:
  - список `TradeRecord`,
  - equity-curve / balance-curve,
  - базовые агрегаты (по желанию),
  - служебная информация (например, параметры запуска).

Обе структуры объявлены **внутри** `backtest_engine.py` (как `dataclass` или TypedDict) и импортируются из него другими модулями (`metrics.py`, `optuna_engine.py`, `walkforward_engine.py`, тестами). Отдельный `types.py` не используется.

> На текущем коде часть метрик уже считается внутри `backtest_engine.py`. Целевое состояние — расчёт метрик в `metrics.py`, при этом `StrategyResult` остаётся общим контейнером для результатов и метрик.

4. **Контракт**

- Вход:
  - класс стратегии / идентификатор стратегии,
  - параметры стратегии (`StrategyParams`),
  - торговые настройки (комиссия, тип объёма и т.д.),
  - подготовленные данные.
- Выход:
  - `StrategyResult` — единый формат результата, который потом потребляется `metrics.py`, `optuna_engine.py`, `walkforward_engine.py` и UI.

---

### 2.2. `optuna_engine.py` — Движок оптимизации

**Назначение:**  
Единственный оптимизатор в проекте, использующий Optuna.

**Основные задачи:**

1. **Конфигурация оптимизации**

- `OptunaConfig` / `OptimizationConfig`:
  - стратегия (id / класс),
  - описание пространства поиска (диапазоны параметров, типы),
  - параметры Optuna (число трейлов, sampler, pruner),
  - конфигурация целевой функции (какие метрики используются в score).
- `OptimizationResult`:
  - параметры,
  - метрики,
  - итоговый score.

Структуры конфигурации/результатов могут быть оформлены как dataclass’ы в самом `optuna_engine.py` или рядом с ним.

2. **Интеграция с `backtest_engine` и `metrics`**

- Для каждого trial:
  - формирует `StrategyParams` (набор параметров стратегии) из `Trial`,
  - запускает `backtest_engine.run_backtest(...)`,
  - передаёт результат в `metrics.calculate_basic/advanced`,
  - агрегирует метрики и вычисляет score.

3. **Управление процессом Optuna**

- Создание и настройка Optuna study.
- Логика:
  - early stopping (через pruners),
  - при необходимости — сериализация/восстановление.
- В будущем: возможность добавить seed для воспроизводимости (сейчас — не обязательно).

4. **Интеграция с экспортом**

- Для сохранения результатов оптимизации вызывает функции из `export.py`, например:
  - `export_optuna_results(results, path)`.

---

### 2.3. `walkforward_engine.py` — Движок Walk-Forward

**Назначение:**  
Оркестратор WFA, стоящий над `optuna_engine` и `backtest_engine`.

**Основные задачи:**

1. **Разбиение на окна**

- Деление общего датасета на последовательность in-sample / out-of-sample окон:
  - фиксированные окна,
  - sliding/rolling окна (по необходимости).
- Конфигурация:
  - длина in-sample,
  - длина OOS,
  - шаг сдвига.

2. **Оптимизация на in-sample**

- На каждом окне:
  - формирует `OptimizationConfig`,
  - вызывает `optuna_engine` для поиска лучших параметров,
  - выбирает лучший trial по score.

3. **Тестирование на OOS**

- Для каждой пары in-sample / OOS:
  - запускает `backtest_engine` с лучшими параметрами на OOS-участке,
  - получает `StrategyResult` для OOS.

4. **Агрегирование WFA**

- Сохраняет:
  - метрики по каждому окну (in-sample, OOS),
  - общие итоговые метрики по всей WFA.
- Для расчёта использует `metrics.calculate_basic/advanced` и при необходимости `metrics.calculate_for_wfa(...)`.

5. **Экспорт**

- Вызывает `export.export_wfa_summary(wfa_results, path)` или другие функции `export.py` для сохранения результатов.

---

## 3. Core Utilities

### 3.1. `metrics.py`

**Назначение:**  
Единое место для расчёта всех метрик.

**Структуры данных:**

- `BasicMetrics`:
  - Net Profit / Net Profit %,
  - Gross Profit / Gross Loss,
  - Max Drawdown / Max DD %,
  - Total Trades,
  - Win Rate и т.п.

- `AdvancedMetrics`:
  - Sharpe,
  - Sortino,
  - Ulcer Index,
  - Profit Factor,
  - Consistency,
  - ROMAD и т.п.

- `WFAMetrics` (опционально):
  - агрегированные метрики по всем окнам WFA (например, средний Net Profit, средний MaxDD, процент успешных окон и т.п.).

Эти структуры объявляются **внутри** `metrics.py` и импортируются другими модулями (`optuna_engine.py`, `walkforward_engine.py`, UI, тестами).

**Функции/зоны ответственности:**

- `calculate_basic(result: StrategyResult) -> BasicMetrics`
- `calculate_advanced(result: StrategyResult) -> AdvancedMetrics`
- `calculate_for_wfa(wfa_results) -> WFAMetrics` (если будет нужен отдельный формат для WFA)

---

### 3.2. `export.py`

**Назначение:**  
Все операции экспорта данных наружу.

**Примеры функций:**

- `export_trades_tv(trades, path: str) -> None`  
  Экспорт списка сделок в CSV-формат, который понимает TradingView Trading Report Generator.

- `export_optuna_results(results, path: str) -> None`  
  Сохранение результатов Optuna-оптимизации (лучшие параметры, метрики и score) в CSV.

- `export_wfa_summary(wfa_results, path: str) -> None`  
  Экспорт сводки Walk-Forward по окнам и итоговых метрик.

При необходимости сюда же можно добавить:

- экспорт в JSON,
- экспорт для Excel,
- генерацию агрегированных отчётов.

---

## 4. Indicators Layer (`indicators/`)

**Структура:**

```text
src/indicators/
  __init__.py
  ma.py           # SMA, EMA, WMA, KAMA, T3, HMA и т.п.
  volatility.py   # ATR, NATR и другие волатильностные индикаторы
  oscillators.py  # RSI, Stoch, CCI и т.д.
  volume.py       # OBV и другие volume-based индикаторы
  trend.py        # ADX и трендовые индикаторы
  misc.py         # прочие индикаторы и хелперы
```

**Правила использования:**

- Все **общие** индикаторы размещаются здесь.
- Если индикатор нужен только одной стратегии:
  - его можно реализовать в самой стратегии как `indicator_<name>` или через `custom_indicators`.

`BaseStrategy` реализует fallback:

1. Если в классе стратегии есть метод `indicator_<name>` — использовать его.
2. Если индикатор указан в `custom_indicators` — использовать его.
3. Иначе искать функцию `name` в модулях `indicators.*`.

---

## 5. Strategies Layer (`strategies/`)

### 5.1. `strategies/base.py`

**Назначение:**  
Базовый класс для всех стратегий.

**Основные элементы:**

- Основной контракт на первом этапе:
  - статический метод вида `run(df, params, trade_start_idx=0) -> StrategyResult`,
  - который вызывает индикаторы и реализует торговую логику в терминах входных данных и параметров.
- В будущем (опционально) может быть добавлен bar-ориентированный API `on_bar(ctx)`, если это упростит перенос PineScript-логики.
- Доступ к индикаторам через fallback-механизм.
- Доступ к параметрам стратегии (`StrategyParams`).
- Хранение внутреннего состояния между барами (если нужно).

### 5.2. Конкретные стратегии

**Структура:**

```text
src/strategies/
  base.py
  s01_trailing_ma/
    config.json
    strategy.py
  simple_ma/
    config.json
    strategy.py
  s01_trailing_ma_migrated/   # на период миграции
    config.json
    strategy.py
  ...
```

Каждая стратегия:

- описывает свои параметры в `config.json` по единому формату:
  - блок `parameters` с описанием:
    - `type` (int/float/select и т.д.),
    - `default`, `min`, `max`, `step`,
    - флаг/объект `optimize` для Optuna (диапазоны, включён/выключен),
    - при необходимости — `label`, `group` и т.п. для UI;
- реализует торговую логику в `strategy.py` (через основной контракт `run(...)`);
- использует индикаторы из `indicators/` и/или свои локальные.

Движки (`backtest_engine`, `optuna_engine`, `walkforward_engine`) работают только с контрактом стратегии (класс + параметры + `config.json`), не зная внутренней реализации.

---

## 6. Interface Layer

### 6.1. `server.py` — API

**Роль:**

- Принимать запросы от UI/скриптов.
- Преобразовывать входные данные в:
  - параметры стратегии (`StrategyParams`),
  - конфиг бэктеста,
  - конфиг оптимизации / WFA.
- Вызывать:
  - `backtest_engine.run_backtest(...)`,
  - `optuna_engine.run_optimization(...)`,
  - `walkforward_engine.run_walkforward(...)`,
  - функции `export.py` при запросах на экспорт.
- Формировать JSON-ответы для фронтенда.

### 6.2. Фронтенд: `index.html`, `main.js`, `style.css`

- `index.html`:
  - разметка форм (стратегия, параметры, режимы),
  - контейнеры для таблиц/графиков.
- `style.css`:
  - оформление интерфейса.
- `main.js`:
  - сбор параметров,
  - AJAX-запросы к `server.py`,
  - обработка ответов,
  - обновление DOM, отрисовка таблиц и результатов.

### 6.3. `run_backtest.py` (опционально)

- CLI-интерфейс для локального запуска:
  - принимает через аргументы: стратегию, параметры, путь к данным, опциональный флаг логирования (`--debug` / `--log-level`),
  - вызывает `backtest_engine.run_backtest(...)`,
  - печатает метрики или вызывает `export.py` для сохранения результатов.

---

## 7. Summary

Целевая архитектура проекта:

- **3 главных движка**:
  - `backtest_engine.py` — симуляция сделок,
  - `optuna_engine.py` — Optuna-оптимизация,
  - `walkforward_engine.py` — WFA.

- **2 универсальных модуля**:
  - `metrics.py` — расчёт метрик (с `BasicMetrics`, `AdvancedMetrics`, `WFAMetrics`),
  - `export.py` — экспорт.

- **2 доменных слоя**:
  - `indicators/` — индикаторы,
  - `strategies/` — стратегии.

- **Interface Layer**:
  - `server.py` + фронтенд (HTML/JS/CSS) + опциональный CLI.

Структуры данных (`TradeRecord`, `StrategyResult`, `BasicMetrics` и др.) определяются внутри соответствующих модулей и переиспользуются через импорты, без отдельного `types.py`. Простая тестовая стратегия и S_01_v2 (через временную папку `s01_trailing_ma_migrated`) живут в `strategies/` и используют общую архитектуру.
