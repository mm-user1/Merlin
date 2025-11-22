# Migration Prompt 8-2: Dynamic Parameter Forms - Optimizer & Finalization

**Подэтап**: 2 из 2
**Цель**: Расширить динамическую генерацию на Optimizer, удалить хардкод, оптимизировать, финализировать
**Сложность**: Средняя-Высокая
**Время**: 5-7 часов
**Приоритет**: ВЫСОКИЙ

---

## Контекст

### Что уже сделано в Подэтапе 8-1 ✅

- ✅ Создана базовая инфраструктура динамической генерации форм
- ✅ Реализованы функции: `categorizeParameters()`, `createParameterInput()`, `buildParameterForm()`, `collectDynamicParameters()`
- ✅ Backtester панель использует динамические формы
- ✅ S_03 параметры полностью редактируются в Backtester
- ✅ Референсные тесты проходят (S_01: 230.75%, S_03: 83.56%)

### Что нужно сделать в Подэтапе 8-2 🎯

1. **Реализовать генерацию контролов диапазонов для Optimizer**
   - Определение оптимизируемых параметров (int/float)
   - Создание range controls (from/to/step)
   - Enable/disable чекбоксы для каждого параметра

2. **Обновить Optimizer панель**
   - Добавить динамический контейнер для параметров
   - Добавить динамический контейнер для range controls
   - Обновить `onOptimizerStrategyChange()`
   - Обновить `buildOptimizationConfig()`

3. **Удалить весь хардкод**
   - Удалить захардкоженные поля из Optimizer
   - Очистить неиспользуемый код

4. **Обработать особые случаи**
   - MA types collections для S_01 (trend/trailLong/trailShort)

5. **Оптимизация производительности**
   - Debouncing для rebuild форм
   - Кэширование HTML

6. **Документация и финализация**
   - Обновить CLAUDE.md
   - Финальное тестирование
   - Коммит

---

## Шаг 1: Обновить HTML структуру Optimizer

### 1.1 Найти Optimizer панель

Найдите в `index.html` секцию Optimizer (примерно строки 1200-2000).

### 1.2 Добавить динамические контейнеры

Найдите место после strategy selector и **замените** хардкод параметров на:

```html
<!-- Dynamic Parameter Container for Optimizer -->
<div id="optimizerDynamicParams" class="dynamic-params-container">
  <!-- Параметры будут генерироваться здесь динамически -->
  <p style="color: #999; padding: 20px;">Выберите стратегию для отображения параметров.</p>
</div>

<!-- Dynamic Optimizer Range Controls Container -->
<div id="optimizerDynamicRanges" class="dynamic-ranges-container">
  <!-- Контролы диапазонов будут генерироваться здесь динамически -->
  <p style="color: #999; padding: 20px;">Выберите стратегию для отображения параметров оптимизации.</p>
</div>
```

### 1.3 Добавить CSS стили для range controls

В секции `<style>` добавить (если ещё не добавлено):

```css
/* ========================================
   Dynamic Optimizer Ranges
   ======================================== */

.dynamic-ranges-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 0;
  margin-top: 20px;
}

.range-control {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  background: #f9f9f9;
}

.range-checkbox {
  flex: 0 0 auto;
}

.range-label {
  flex: 0 0 140px;
  font-size: 13px;
  color: #2a2a2a;
  font-weight: 500;
}

.range-inputs {
  flex: 1;
  display: flex;
  gap: 8px;
  align-items: center;
}

.range-inputs input {
  width: 80px;
  padding: 5px 8px;
  font-size: 12px;
  border: 1px solid #ccc;
  border-radius: 3px;
}

.range-inputs .separator {
  font-size: 12px;
  color: #666;
}

.range-control.disabled {
  opacity: 0.5;
  pointer-events: none;
}
```

---

## Шаг 2: Реализовать генератор контролов оптимизатора

### 2.1 Функции определения оптимизируемых параметров

Добавить в секцию `<script>`:

```javascript
// ========================================
// Optimizer Range Controls Generation
// ========================================

/**
 * Check if parameter is optimizable (numeric type)
 * @param {Object} paramDef - Parameter definition
 * @returns {boolean}
 */
function isOptimizable(paramDef) {
  return paramDef.type === 'int' || paramDef.type === 'float';
}

/**
 * Filter optimizable parameters from strategy
 * @param {Object} strategy - Strategy object
 * @returns {Object} Optimizable parameters
 */
function getOptimizableParameters(strategy) {
  if (!strategy || !strategy.parameters) return {};

  const optimizable = {};
  Object.entries(strategy.parameters).forEach(([paramId, paramDef]) => {
    if (isOptimizable(paramDef)) {
      optimizable[paramId] = paramDef;
    }
  });

  return optimizable;
}
```

### 2.2 Функция создания range control

```javascript
/**
 * Create optimizer range control for a parameter
 * @param {string} paramId - Parameter identifier
 * @param {Object} paramDef - Parameter definition
 * @returns {HTMLElement} Range control element
 */
function createRangeControl(paramId, paramDef) {
  const control = document.createElement('div');
  control.className = 'range-control';
  control.setAttribute('data-param-id', paramId);

  // Checkbox to enable/disable optimization for this parameter
  const checkbox = document.createElement('input');
  checkbox.type = 'checkbox';
  checkbox.id = `opt-${paramId}`;
  checkbox.className = 'range-checkbox';
  checkbox.checked = false; // Default unchecked

  const checkboxWrapper = document.createElement('div');
  checkboxWrapper.appendChild(checkbox);

  // Label
  const label = document.createElement('label');
  label.className = 'range-label';
  label.setAttribute('for', `opt-${paramId}`);
  label.textContent = paramDef.description || paramId;

  // Range inputs (from, to, step)
  const rangeInputs = document.createElement('div');
  rangeInputs.className = 'range-inputs';

  const fromInput = document.createElement('input');
  fromInput.type = 'number';
  fromInput.id = `opt-${paramId}-from`;
  fromInput.name = `opt-${paramId}-from`;
  fromInput.placeholder = 'От';
  fromInput.value = paramDef.min !== undefined ? paramDef.min : paramDef.default;
  if (paramDef.min !== undefined) fromInput.min = paramDef.min;
  if (paramDef.max !== undefined) fromInput.max = paramDef.max;
  fromInput.step = paramDef.step || (paramDef.type === 'float' ? 0.01 : 1);

  const separator1 = document.createElement('span');
  separator1.className = 'separator';
  separator1.textContent = '—';

  const toInput = document.createElement('input');
  toInput.type = 'number';
  toInput.id = `opt-${paramId}-to`;
  toInput.name = `opt-${paramId}-to`;
  toInput.placeholder = 'До';
  toInput.value = paramDef.max !== undefined ? paramDef.max : paramDef.default;
  if (paramDef.min !== undefined) toInput.min = paramDef.min;
  if (paramDef.max !== undefined) toInput.max = paramDef.max;
  toInput.step = paramDef.step || (paramDef.type === 'float' ? 0.01 : 1);

  const separator2 = document.createElement('span');
  separator2.className = 'separator';
  separator2.textContent = 'шаг';

  const stepInput = document.createElement('input');
  stepInput.type = 'number';
  stepInput.id = `opt-${paramId}-step`;
  stepInput.name = `opt-${paramId}-step`;
  stepInput.placeholder = 'Шаг';
  stepInput.value = paramDef.step || (paramDef.type === 'float' ? 0.1 : 1);
  stepInput.min = paramDef.type === 'float' ? 0.001 : 1;
  stepInput.step = paramDef.type === 'float' ? 0.001 : 1;

  rangeInputs.appendChild(fromInput);
  rangeInputs.appendChild(separator1);
  rangeInputs.appendChild(toInput);
  rangeInputs.appendChild(separator2);
  rangeInputs.appendChild(stepInput);

  // Enable/disable range inputs based on checkbox
  const updateState = () => {
    if (checkbox.checked) {
      control.classList.remove('disabled');
      fromInput.disabled = false;
      toInput.disabled = false;
      stepInput.disabled = false;
    } else {
      control.classList.add('disabled');
      fromInput.disabled = true;
      toInput.disabled = true;
      stepInput.disabled = true;
    }
  };

  checkbox.addEventListener('change', updateState);
  updateState(); // Initial state

  control.appendChild(checkboxWrapper);
  control.appendChild(label);
  control.appendChild(rangeInputs);

  return control;
}
```

### 2.3 Функция построения всех range controls

```javascript
/**
 * Build optimizer range controls for all optimizable parameters
 * @param {string} containerId - ID контейнера для вставки
 * @param {Object} strategy - Strategy object
 */
function buildOptimizerRanges(containerId, strategy) {
  const container = document.getElementById(containerId);
  if (!container) {
    console.error(`Container ${containerId} not found`);
    return;
  }

  container.innerHTML = '';

  if (!strategy || !strategy.parameters) {
    container.innerHTML = '<p style="color: #999; padding: 20px;">Выберите стратегию для отображения параметров оптимизации.</p>';
    return;
  }

  const optimizableParams = getOptimizableParameters(strategy);

  if (Object.keys(optimizableParams).length === 0) {
    container.innerHTML = '<p style="color: #999; padding: 20px;">Нет оптимизируемых параметров для этой стратегии.</p>';
    return;
  }

  const title = document.createElement('h3');
  title.textContent = 'Диапазоны для оптимизации';
  title.style.marginBottom = '12px';
  title.style.fontSize = '15px';
  title.style.fontWeight = '600';
  container.appendChild(title);

  Object.entries(optimizableParams).forEach(([paramId, paramDef]) => {
    const control = createRangeControl(paramId, paramDef);
    container.appendChild(control);
  });

  console.log(`Built optimizer ranges for ${Object.keys(optimizableParams).length} parameters`);
}
```

---

## Шаг 3: Обновить обработчик смены стратегии Optimizer

### 3.1 Найти функцию onOptimizerStrategyChange

### 3.2 Обновить вызовы

```javascript
/**
 * Handle optimizer strategy change
 */
function onOptimizerStrategyChange() {
  const strategyId = document.getElementById('optimizerStrategy').value;
  if (!strategyId) return;

  currentOptimizerStrategy = strategyMetadataCache[strategyId];
  if (!currentOptimizerStrategy) {
    console.error('Strategy not found:', strategyId);
    return;
  }

  // Update info panel
  document.getElementById('optimizerStrategyName').textContent = currentOptimizerStrategy.name;
  document.getElementById('optimizerStrategyType').textContent =
    currentOptimizerStrategy.type === 'trend' ? 'Трендовая' : 'Реверсивная';
  document.getElementById('optimizerStrategyDesc').textContent = currentOptimizerStrategy.description;
  document.getElementById('optimizerStrategyInfo').style.display = 'block';

  // ⭐ NEW: Build dynamic parameter form
  buildParameterForm('optimizerDynamicParams', currentOptimizerStrategy, true);

  // ⭐ NEW: Build optimizer range controls
  buildOptimizerRanges('optimizerDynamicRanges', currentOptimizerStrategy);

  console.log('Optimizer strategy changed to:', strategyId);
}
```

---

## Шаг 4: Обновить сбор параметров Optimizer

### 4.1 Функция сбора параметров оптимизатора

```javascript
/**
 * Collect optimizer parameters (new dynamic version)
 */
function collectOptimizerParameters() {
  return collectDynamicParameters('optimizerDynamicParams');
}
```

### 4.2 Обновить buildOptimizationConfig

Найдите существующую функцию `buildOptimizationConfig()` и **обновите** логику сбора параметров:

```javascript
function buildOptimizationConfig(state) {
  const strategyId = state.strategyId || currentOptimizerStrategy?.strategy_id || 's01_trailing_ma';
  const strategy = currentOptimizerStrategy || strategyMetadataCache[strategyId];

  const enabledParams = {};
  const paramRanges = {};
  const fixedParams = {
    dateFilter: state.payload.dateFilter,
    useBacktester: state.payload.useBacktester || state.payload.backtester
  };

  // Собираем общие параметры (date range)
  const startDateEl = document.getElementById('startDate');
  const endDateEl = document.getElementById('endDate');
  if (startDateEl) fixedParams.startDate = startDateEl.value;
  if (endDateEl) fixedParams.endDate = endDateEl.value;

  // ⭐ NEW: Collect enabled parameters and ranges from dynamic range controls
  const rangeContainer = document.getElementById('optimizerDynamicRanges');
  if (rangeContainer) {
    rangeContainer.querySelectorAll('.range-control').forEach((control) => {
      const paramId = control.getAttribute('data-param-id');
      const checkbox = control.querySelector(`#opt-${paramId}`);

      if (checkbox && checkbox.checked) {
        // This parameter is enabled for optimization
        enabledParams[paramId] = true;

        const fromInput = control.querySelector(`#opt-${paramId}-from`);
        const toInput = control.querySelector(`#opt-${paramId}-to`);
        const stepInput = control.querySelector(`#opt-${paramId}-step`);

        paramRanges[paramId] = [
          parseFloat(fromInput.value) || 0,
          parseFloat(toInput.value) || 0,
          parseFloat(stepInput.value) || 1
        ];
      } else {
        // This parameter is fixed (not optimized)
        enabledParams[paramId] = false;
        const paramInput = document.getElementById(`param-${paramId}`);
        if (paramInput) {
          if (paramInput.type === 'checkbox') {
            fixedParams[paramId] = paramInput.checked;
          } else if (paramInput.type === 'number') {
            fixedParams[paramId] = parseFloat(paramInput.value);
          } else {
            fixedParams[paramId] = paramInput.value;
          }
        }
      }
    });
  }

  // ⭐ NEW: Collect all other non-numeric parameters as fixed
  const allParams = collectOptimizerParameters();
  Object.entries(allParams).forEach(([key, value]) => {
    if (!(key in enabledParams)) {
      fixedParams[key] = value;
    }
  });

  // Build config object
  const config = {
    strategy_id: strategyId,
    enabled_params: enabledParams,
    param_ranges: paramRanges,
    fixed_params: fixedParams,
    worker_processes: getWorkerProcessesValue(),
    filter_min_profit: state.payload.filterMinProfit,
    min_profit_threshold: state.payload.minProfitThreshold,
    optimization_mode: state.payload.optimizationMode || 'grid',
    // ... rest of existing config (optuna settings, walk-forward, etc.)
  };

  // Preserve other config fields if they exist
  if (state.payload.optunaTarget) config.optuna_target = state.payload.optunaTarget;
  if (state.payload.optunaBudgetMode) config.optuna_budget_mode = state.payload.optunaBudgetMode;
  if (state.payload.optunaNTrials) config.optuna_n_trials = state.payload.optunaNTrials;
  if (state.payload.optunaTimeLimit) config.optuna_time_limit = state.payload.optunaTimeLimit;
  if (state.payload.optunaConvergence) config.optuna_convergence = state.payload.optunaConvergence;

  return config;
}
```

---

## Шаг 5: Обработать особый случай - MA Types для S_01

### 5.1 Проблема

S_01 имеет специальную логику для выбора **множественных** MA типов (trend/trailLong/trailShort).

Текущий UI использует `collectSelectedTypes()` для сбора выбранных MA типов.

### 5.2 Решение: Сохранить существующую логику MA types

**Для Подэтапа 8-2** - сохраним текущую логику MA type collections как есть.

**Найдите** существующие элементы:
- Trend MA Types (checkboxes SMA, EMA, HMA, etc.)
- Trail Long Types
- Trail Short Types
- Lock Trail Types checkbox

**НЕ УДАЛЯЙТЕ** эти элементы. Они останутся для S_01.

**Обновите** `buildOptimizationConfig()` чтобы добавить MA types:

```javascript
// В конце buildOptimizationConfig(), после создания config:

// Специальная обработка MA types для S_01
if (strategyId === 's01_trailing_ma') {
  // Проверяем наличие функции collectSelectedTypes
  if (typeof collectSelectedTypes === 'function') {
    const trendTypes = collectSelectedTypes('trend');
    const trailLongTypes = collectSelectedTypes('trailLong');
    const trailShortTypes = collectSelectedTypes('trailShort');
    const lockTrailTypes = document.getElementById('lockTrailTypes')?.checked || false;

    if (trendTypes.length > 0 || trailLongTypes.length > 0 || trailShortTypes.length > 0) {
      config.ma_type_combinations = {
        trend: trendTypes,
        trailLong: trailLongTypes,
        trailShort: trailShortTypes,
        locked: lockTrailTypes
      };
    }
  }
}

return config;
```

**Примечание**: Это промежуточное решение. В будущем MA types можно сделать полностью динамическими через multi-select.

---

## Шаг 6: Удалить хардкод из Optimizer

### 6.1 Что удалить

**Удалить** все захардкоженные поля параметров в Optimizer:
- ❌ MA Length range controls
- ❌ Close Count range controls
- ❌ Stop ATR/RR/LP range controls
- ❌ Trail MA range controls
- ❌ Risk Per Trade range controls

**НЕ УДАЛЯТЬ**:
- ✅ Date Filter controls
- ✅ CSV file upload
- ✅ Worker processes
- ✅ Optimization mode (Grid/Optuna)
- ✅ Optuna settings panel
- ✅ Walk-Forward settings panel
- ✅ Score weights panel
- ✅ **MA Types checkboxes** (trend/trailLong/trailShort) - оставляем для S_01

### 6.2 Очистить неиспользуемый код

Проверьте и удалите (если больше не используются):
- Функции создания hardcoded range controls
- Старые ID элементов которые больше не существуют

---

## Шаг 7: Оптимизация производительности

### 7.1 Debouncing для rebuild форм

Добавьте debouncing чтобы избежать лишних rerenders:

```javascript
// Global debounce timer
let formRebuildTimeout = null;

/**
 * Debounced version of onOptimizerStrategyChange
 */
function onOptimizerStrategyChange() {
  // Clear pending rebuild
  if (formRebuildTimeout) {
    clearTimeout(formRebuildTimeout);
  }

  // Debounce form rebuild (100ms delay)
  formRebuildTimeout = setTimeout(() => {
    const strategyId = document.getElementById('optimizerStrategy').value;
    if (!strategyId) return;

    currentOptimizerStrategy = strategyMetadataCache[strategyId];
    if (!currentOptimizerStrategy) {
      console.error('Strategy not found:', strategyId);
      return;
    }

    // Update info panel
    document.getElementById('optimizerStrategyName').textContent = currentOptimizerStrategy.name;
    document.getElementById('optimizerStrategyType').textContent =
      currentOptimizerStrategy.type === 'trend' ? 'Трендовая' : 'Реверсивная';
    document.getElementById('optimizerStrategyDesc').textContent = currentOptimizerStrategy.description;
    document.getElementById('optimizerStrategyInfo').style.display = 'block';

    // Build forms
    buildParameterForm('optimizerDynamicParams', currentOptimizerStrategy, true);
    buildOptimizerRanges('optimizerDynamicRanges', currentOptimizerStrategy);

    console.log('Optimizer strategy changed to:', strategyId);
  }, 100);
}
```

---

## Шаг 8: Полное тестирование

### 8.1 Создать тестовую функцию

```javascript
/**
 * Test complete dynamic form system (console test)
 */
window.testCompleteDynamicForms = function() {
  console.log('=== Testing Complete Dynamic Form System ===');

  // Test 1: Backtester S_01
  console.log('Test 1: Backtester S_01 form');
  const s01 = strategyMetadataCache['s01_trailing_ma'];
  buildParameterForm('backtesterDynamicParams', s01, false);
  const s01BtParams = document.querySelectorAll('#backtesterDynamicParams .param-row').length;
  console.log(`✅ S_01 Backtester: ${s01BtParams} параметров`);

  // Test 2: Backtester S_03
  console.log('Test 2: Backtester S_03 form');
  const s03 = strategyMetadataCache['s03_reversal'];
  buildParameterForm('backtesterDynamicParams', s03, false);
  const s03BtParams = document.querySelectorAll('#backtesterDynamicParams .param-row').length;
  console.log(`✅ S_03 Backtester: ${s03BtParams} параметров`);

  // Test 3: Optimizer S_01
  console.log('Test 3: Optimizer S_01 forms');
  buildParameterForm('optimizerDynamicParams', s01, false);
  buildOptimizerRanges('optimizerDynamicRanges', s01);
  const s01OptParams = document.querySelectorAll('#optimizerDynamicParams .param-row').length;
  const s01Ranges = document.querySelectorAll('#optimizerDynamicRanges .range-control').length;
  console.log(`✅ S_01 Optimizer: ${s01OptParams} параметров, ${s01Ranges} range controls`);

  // Test 4: Optimizer S_03
  console.log('Test 4: Optimizer S_03 forms');
  buildParameterForm('optimizerDynamicParams', s03, false);
  buildOptimizerRanges('optimizerDynamicRanges', s03);
  const s03OptParams = document.querySelectorAll('#optimizerDynamicParams .param-row').length;
  const s03Ranges = document.querySelectorAll('#optimizerDynamicRanges .range-control').length;
  console.log(`✅ S_03 Optimizer: ${s03OptParams} параметров, ${s03Ranges} range controls`);

  // Test 5: Parameter collection
  console.log('Test 5: Parameter collection');
  const btParams = collectBacktesterParameters();
  const optParams = collectOptimizerParameters();
  console.log(`✅ Backtester collected: ${Object.keys(btParams).length} параметров`);
  console.log(`✅ Optimizer collected: ${Object.keys(optParams).length} параметров`);

  console.log('=== All Tests Completed ===');
};
```

### 8.2 Ручное UI тестирование

**Optimizer панель**:
- [ ] Выбрать S_01 → показывает ~30 параметров + ~20 range controls
- [ ] Выбрать S_03 → показывает ~15 параметров + ~10 range controls
- [ ] Enable `maFastLength` range → inputs становятся активными
- [ ] Set range: 50-150, step 25 → должно дать 5 комбинаций
- [ ] Disable range → inputs становятся disabled
- [ ] Переключить S_01 → S_03 → S_01 → значения сохраняются
- [ ] Нет ошибок JavaScript в консоли

**Интеграционное тестирование**:

**Тест 1: S_03 Grid Optimization**

1. Выбрать S_03 в Optimizer
2. Enable `maFastLength` range: 50-150, step 50 (3 значения)
3. Оставить все остальные параметры fixed
4. Загрузить CSV
5. Optimization mode = Grid
6. Нажать "Optimize"
7. **Ожидается**:
   - CSV с 3 строками
   - maFastLength values: 50, 100, 150
   - Результаты отличаются для каждого значения

**Тест 2: S_01 Multi-Parameter Optimization**

1. Выбрать S_01
2. Enable `maLength`: 100-200, step 50 (3 значения)
3. Enable `closeCountLong`: 3-5, step 1 (3 значения)
4. Total combinations: 3 × 3 = 9
5. Нажать "Optimize"
6. **Ожидается**:
   - CSV с 9 строками
   - Все комбинации присутствуют

**Тест 3: Optuna Optimization**

1. Выбрать S_03
2. Enable `maFastLength`: 20-200
3. Enable `maTrendLength`: 50-300
4. Optimization mode = Optuna
5. n_trials = 20
6. Нажать "Optimize"
7. **Ожидается**:
   - CSV с 20 строками
   - Различные значения maFastLength и maTrendLength
   - Optuna прогресс в консоли

### 8.3 Референсные тесты

После завершения всех изменений:

```bash
cd src
python run_backtest.py --csv "../data/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv" --strategy s01_trailing_ma
# Expected: 230.75% / 20.03% / 93 trades ✅

python run_backtest.py --csv "../data/OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv" --strategy s03_reversal
# Expected: 83.56% / 35.34% / 224 trades ✅
```

---

## Шаг 9: Обновить документацию

### 9.1 Обновить CLAUDE.md

Добавить в конец файла `CLAUDE.md`:

```markdown
## Dynamic Parameter Forms (Phase 8)

Starting from Phase 8, the UI automatically generates parameter forms from strategy metadata, eliminating the need for hardcoded HTML.

### How It Works

1. **Backend defines parameters** in `strategy.get_param_definitions()`
2. **Frontend fetches** strategy list from `/api/strategies` on page load
3. **JavaScript builds forms** dynamically based on parameter types
4. **No HTML changes** needed when adding new strategies

### Supported Parameter Types

- `int`: Number input with min/max/step validation
- `float`: Decimal number input with precision control
- `bool`: Checkbox
- `str`: Text input
- `categorical`: Dropdown select with predefined choices

### Adding New Strategies

To add a new strategy with full UI support:

1. Create strategy class inheriting from `BaseStrategy`
2. Implement `get_param_definitions()` class method
3. Register in `StrategyRegistry.register_strategy()`
4. **UI updates automatically** - no frontend changes needed

Example parameter definition:
```python
@classmethod
def get_param_definitions(cls) -> Dict[str, Dict[str, Any]]:
    return {
        "maLength": {
            "type": "int",
            "default": 100,
            "min": 1,
            "max": 500,
            "step": 1,
            "description": "MA Period"
        },
        "maType": {
            "type": "categorical",
            "choices": ["SMA", "EMA", "HMA"],
            "default": "SMA",
            "description": "MA Type"
        }
    }
```

### Parameter Grouping

Parameters are automatically grouped into logical sections:
- **Основные настройки** (Common) - dateFilter, startDate, etc.
- **Скользящие средние** (Moving Averages) - maType, maLength, etc.
- **Условия входа** (Entry Rules) - closeCountLong, breakoutMode, etc.
- **Условия выхода** (Exit Rules) - stopLongAtr, trailRrLong, etc.
- **Управление рисками** (Risk Management) - riskPerTradePct, equityPct, etc.

Grouping is based on parameter ID patterns in `categorizeParameters()` function.

### Optimizer Range Controls

For numeric parameters (`int`, `float`), the optimizer automatically generates:
- Enable/disable checkbox
- From/To range inputs
- Step input
- Min/max validation from parameter definition

Users can enable any subset of parameters for optimization without code changes.

### Benefits

- ✅ Scalable: Adding 10 new strategies requires ZERO HTML changes
- ✅ Maintainable: Single source of truth in `get_param_definitions()`
- ✅ Consistent: All strategies have uniform UI
- ✅ Validated: Min/max/step enforced automatically
- ✅ Fast: Form generation < 200ms
```

---

## Шаг 10: Финальный коммит

### 10.1 Проверить всё перед коммитом

Checklist:
- [ ] Все функции реализованы
- [ ] HTML очищен от хардкода
- [ ] CSS стили добавлены
- [ ] Optimizer работает для S_01 и S_03
- [ ] Референсные тесты проходят
- [ ] Нет ошибок в консоли
- [ ] CLAUDE.md обновлен
- [ ] Тесты пройдены

### 10.2 Структура коммита

```bash
git add src/index.html CLAUDE.md
git commit -m "Phase 8-2: Complete dynamic parameter forms - Optimizer & finalization

- Add dynamic parameter container for optimizer
- Add dynamic range controls container for optimizer
- Implement isOptimizable(), getOptimizableParameters()
- Implement createRangeControl(), buildOptimizerRanges()
- Update onOptimizerStrategyChange() to rebuild forms
- Update buildOptimizationConfig() to collect from dynamic ranges
- Add debouncing for form rebuilds (100ms)
- Remove all hardcoded parameter fields from optimizer
- Keep MA types checkboxes for S_01 (special case)
- Update CLAUDE.md with dynamic forms documentation
- Add testCompleteDynamicForms() for validation

Phase 8 Complete:
- Dynamic forms for both Backtester and Optimizer ✅
- S_01 and S_03 fully supported ✅
- ~3000 lines of hardcoded HTML removed ✅
- Adding new strategies requires ZERO HTML changes ✅

Reference tests:
- S_01: 230.75% / 20.03% / 93 trades ✅
- S_03: 83.56% / 35.34% / 224 trades ✅
- S_03 optimization with varied params ✅

Phase 8-1: Dynamic backtester forms (completed)
Phase 8-2: Dynamic optimizer forms (completed)
Multi-strategy migration: COMPLETE"

git push -u origin claude/mg-stage-1-check-0159d5ZWE51FdnYTT8qhmQkz
```

---

## Критерии приемки Подэтапа 8-2

Подэтап 8-2 считается завершенным когда:

1. ✅ HTML обновлен - добавлены контейнеры `#optimizerDynamicParams` и `#optimizerDynamicRanges`
2. ✅ CSS стили для range controls добавлены
3. ✅ Функция `isOptimizable()` реализована
4. ✅ Функция `getOptimizableParameters()` реализована
5. ✅ Функция `createRangeControl()` реализована
6. ✅ Функция `buildOptimizerRanges()` реализована
7. ✅ Функция `onOptimizerStrategyChange()` обновлена
8. ✅ Функция `collectOptimizerParameters()` реализована
9. ✅ Функция `buildOptimizationConfig()` обновлена для динамических ranges
10. ✅ MA types обработка для S_01 сохранена
11. ✅ Весь хардкод удален (кроме MA types)
12. ✅ Debouncing добавлен
13. ✅ S_03 параметры оптимизируются через UI
14. ✅ S_01 оптимизация работает (Grid и Optuna)
15. ✅ S_03 оптимизация работает (Grid и Optuna)
16. ✅ Референсные тесты проходят
17. ✅ CLAUDE.md обновлен
18. ✅ Тест `testCompleteDynamicForms()` проходит
19. ✅ Нет ошибок JavaScript
20. ✅ Изменения закоммичены и запушены

---

## Критерии приемки всего Phase 8 (8-1 + 8-2)

Phase 8 полностью завершен когда:

1. ✅ Все hardcoded формы параметров удалены из HTML
2. ✅ Формы генерируются динамически из `strategy.parameters`
3. ✅ Все 5 типов параметров поддерживаются (int, float, bool, str, categorical)
4. ✅ Optimizer range controls генерируются динамически
5. ✅ S_03 параметры полностью редактируются в UI
6. ✅ S_01 backtest возвращает 230.75% / 20.03% / 93
7. ✅ S_03 backtest возвращает 83.56% / 35.34% / 224
8. ✅ S_03 backtest с кастомными параметрами возвращает ДРУГИЕ результаты
9. ✅ S_03 optimization может варьировать MA параметры
10. ✅ Переключение стратегий сохраняет значения параметров
11. ✅ Нет ошибок JavaScript в консоли
12. ✅ Генерация форм < 200ms
13. ✅ Документация обновлена
14. ✅ Код закоммичен и запушен

---

## Troubleshooting

### Проблема: Range controls не отключаются

**Решение**: Проверьте что `updateState()` вызывается после добавления event listener:
```javascript
checkbox.addEventListener('change', updateState);
updateState(); // ← Важно!
```

### Проблема: buildOptimizationConfig не находит range inputs

**Решение**: Убедитесь что используете правильные ID:
- Checkbox: `opt-${paramId}`
- From: `opt-${paramId}-from`
- To: `opt-${paramId}-to`
- Step: `opt-${paramId}-step`

### Проблема: Параметры не собираются

**Решение**: Проверьте что `input.name` установлен правильно в `createParameterInput()`:
```javascript
input.name = paramId; // ← Обязательно!
```

### Проблема: S_01 MA types не работают

**Решение**: Убедитесь что НЕ удалили MA types checkboxes и функцию `collectSelectedTypes()`.

---

## Следующие шаги (после Phase 8)

Phase 8 завершает базовую multi-strategy миграцию. Возможные улучшения:

1. **Advanced parameter types**:
   - Range sliders для numeric параметров
   - Color pickers
   - Multi-select для categorical

2. **Parameter presets per strategy**:
   - Сохранение/загрузка комбинаций параметров
   - Import/export JSON

3. **Conditional parameters**:
   - Show/hide на основе других значений
   - Cross-parameter validation

4. **Performance**:
   - HTML caching для больших форм
   - Virtual scrolling для 100+ параметров

---

**Конец migration_prompt_8-2.md**
