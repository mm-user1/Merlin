# Migration Prompt 8-1: Dynamic Parameter Forms - Backtester Foundation

**Подэтап**: 1 из 2
**Цель**: Создать базовую инфраструктуру динамической генерации форм и реализовать для Backtester
**Сложность**: Средняя
**Время**: 4-6 часов
**Приоритет**: ВЫСОКИЙ

---

## Контекст

### Проблема ❌

**Phase 7 Implementation**:
- UI формы захардкожены для параметров S_01
- S_03 не имеет полей ввода для своих специфичных параметров:
  - `maFastType`, `maFastLength` (Fast MA)
  - `maSlowType`, `maSlowLength` (Slow MA)
  - `maTrendType`, `maTrendLength` (Trend MA)
  - `equityPct` (размер позиции)
- Backend заполняет параметры S_03 значениями по умолчанию (server.py:1034)
- **Результат**: Пользователи НЕ МОГУТ настраивать S_03 через UI

**Влияние**:
- ❌ Невозможно оптимизировать типы/длины MA для S_03
- ❌ Невозможно экспериментировать с настройками S_03
- ❌ Добавление новых стратегий требует изменения HTML
- ❌ Не масштабируется для 10+ стратегий

### Решение Подэтапа 8-1 ✅

**Создать динамическую генерацию форм для Backtester**:
1. Читать `strategy.parameters` из кэша метаданных стратегий
2. Генерировать поля форм автоматически на основе типов параметров
3. Поддержка всех типов: `int`, `float`, `bool`, `str`, `categorical`
4. Группировка параметров по логическим категориям
5. Сохранение значений при переключении стратегий
6. Базовая инфраструктура для последующего расширения на Optimizer

---

## Что НЕ входит в Подэтап 8-1

Следующие компоненты будут реализованы в Подэтапе 8-2:
- ❌ Генерация контролов диапазонов для оптимизатора
- ❌ Динамические формы для Optimizer панели
- ❌ Удаление хардкода из Optimizer
- ❌ Обработка особых случаев MA types для S_01
- ❌ Оптимизация производительности
- ❌ Полная документация

**Фокус 8-1**: ТОЛЬКО Backtester + базовые функции генерации форм.

---

## Архитектура

### Поток данных

```
Пользователь выбирает стратегию в Backtester
    ↓
Frontend берет strategy.parameters из strategyMetadataCache
    ↓
buildParameterForm('backtesterDynamicParams', strategy) генерирует HTML
    ↓
Поля формы создаются на основе типов параметров
    ↓
Пользователь редактирует значения
    ↓
collectBacktesterParameters() читает из динамической формы
    ↓
Параметры отправляются в backend через /api/backtest
```

### Структура компонентов

```
┌─────────────────────────────────────┐
│ Strategy Selector Dropdown          │
│ (#backtesterStrategy)               │
└─────────────────────────────────────┘
          ↓
┌─────────────────────────────────────┐
│ Strategy Info Panel                 │
│ - Name, Type, Description           │
│ (#backtesterStrategyInfo)           │
└─────────────────────────────────────┘
          ↓
┌─────────────────────────────────────┐
│ ⭐ NEW: Dynamic Parameter Container │
│ (#backtesterDynamicParams)          │
│                                     │
│  [Основные настройки Section]       │
│  [Скользящие средние Section]       │
│  [Условия входа Section]            │
│  [Условия выхода Section]           │
│  [Управление рисками Section]       │
└─────────────────────────────────────┘
```

---

## Шаг 1: Обновить HTML структуру

### 1.1 Найти существующую форму Backtester

Найдите в `index.html` секцию Backtester (примерно строки 800-1200).

Определите блок с существующими полями параметров:
- MA Length
- Close Count Long/Short
- Stop/Trail настройки
- Risk настройки

### 1.2 Заменить хардкод на динамический контейнер

**Заменить все** существующие `<div class="form-group">` блоки параметров на:

```html
<!-- Dynamic Parameter Container for Backtester -->
<div id="backtesterDynamicParams" class="dynamic-params-container">
  <!-- Параметры будут генерироваться здесь динамически -->
  <p style="color: #999; padding: 20px;">Выберите стратегию для отображения параметров.</p>
</div>
```

**ВАЖНО**: Сохранить следующие элементы (НЕ удалять):
- ✅ Date Filter чекбокс и поля дат
- ✅ CSV file upload
- ✅ Кнопка "Run Backtest"

### 1.3 Добавить CSS стили

В секции `<style>` (перед `</style>`) добавить:

```css
/* ========================================
   Dynamic Parameter Forms
   ======================================== */

.dynamic-params-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 12px 0;
}

.param-section {
  border: 1px solid #ddd;
  border-radius: 4px;
  padding: 16px;
  background: #fafafa;
}

.param-section-title {
  font-size: 15px;
  font-weight: 600;
  color: #333;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 2px solid #4a90e2;
}

.param-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.param-row:last-child {
  margin-bottom: 0;
}

.param-label {
  flex: 0 0 180px;
  font-size: 13px;
  color: #2a2a2a;
  font-weight: 500;
}

.param-input {
  flex: 1;
  min-width: 0;
}

.param-input input[type="number"],
.param-input input[type="text"],
.param-input select {
  width: 100%;
  padding: 6px 10px;
  font-size: 13px;
  border: 1px solid #ccc;
  border-radius: 3px;
  background: white;
  color: #2a2a2a;
}

.param-input input[type="number"]:focus,
.param-input input[type="text"]:focus,
.param-input select:focus {
  outline: none;
  border-color: #4a90e2;
  box-shadow: 0 0 0 2px rgba(74, 144, 226, 0.2);
}

.param-input input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
}

.param-description {
  font-size: 11px;
  color: #666;
  font-style: italic;
  margin-top: 4px;
}

/* Parameter Grouping Colors */
.param-group-common {
  background: #f0f7ff;
}

.param-group-ma {
  background: #fff8f0;
}

.param-group-entry {
  background: #f0fff4;
}

.param-group-exit {
  background: #fff0f6;
}

.param-group-risk {
  background: #f5f0ff;
}
```

---

## Шаг 2: Реализовать генератор форм параметров

### 2.1 Функция категоризации параметров

Добавить в секцию `<script>` перед существующими функциями:

```javascript
// ========================================
// Dynamic Parameter Form Generation
// ========================================

/**
 * Categorize parameters into logical groups for better UI organization
 * @param {Object} parameters - Strategy parameter definitions
 * @returns {Object} Grouped parameters
 */
function categorizeParameters(parameters) {
  const groups = {
    common: {
      title: 'Основные настройки',
      cssClass: 'param-group-common',
      params: []
    },
    ma: {
      title: 'Скользящие средние',
      cssClass: 'param-group-ma',
      params: []
    },
    entry: {
      title: 'Условия входа',
      cssClass: 'param-group-entry',
      params: []
    },
    exit: {
      title: 'Условия выхода',
      cssClass: 'param-group-exit',
      params: []
    },
    risk: {
      title: 'Управление рисками',
      cssClass: 'param-group-risk',
      params: []
    }
  };

  // Categorization rules - определяем какие параметры в какую группу
  const categoryRules = {
    common: ['dateFilter', 'useBacktester', 'startDate', 'endDate', 'contractSize', 'commissionRate'],
    ma: [
      'maType', 'maLength', 'maFastType', 'maFastLength', 'maSlowType', 'maSlowLength',
      'maTrendType', 'maTrendLength', 'trailMaLongType', 'trailMaLongLength',
      'trailMaLongOffset', 'trailMaShortType', 'trailMaShortLength', 'trailMaShortOffset'
    ],
    entry: [
      'closeCountLong', 'closeCountShort', 'breakoutMode', 'useClosePrice'
    ],
    exit: [
      'stopLongAtr', 'stopLongRr', 'stopLongLp', 'stopLongMaxPct', 'stopLongMaxDays',
      'stopShortAtr', 'stopShortRr', 'stopShortLp', 'stopShortMaxPct', 'stopShortMaxDays',
      'trailRrLong', 'trailRrShort'
    ],
    risk: [
      'riskPerTradePct', 'equityPct', 'atrPeriod'
    ]
  };

  // Распределяем параметры по группам
  Object.entries(parameters).forEach(([paramId, paramDef]) => {
    let assigned = false;

    // Проверяем каждую категорию
    for (const [category, keywords] of Object.entries(categoryRules)) {
      if (keywords.includes(paramId)) {
        groups[category].params.push({ id: paramId, ...paramDef });
        assigned = true;
        break;
      }
    }

    // По умолчанию в 'common' если нет совпадения
    if (!assigned) {
      groups.common.params.push({ id: paramId, ...paramDef });
    }
  });

  // Удаляем пустые группы
  return Object.entries(groups)
    .filter(([key, group]) => group.params.length > 0)
    .reduce((acc, [key, group]) => {
      acc[key] = group;
      return acc;
    }, {});
}
```

### 2.2 Функция создания поля ввода

```javascript
/**
 * Create input element for a parameter based on its type
 * @param {string} paramId - Parameter identifier
 * @param {Object} paramDef - Parameter definition
 * @param {*} currentValue - Current value (null to use default)
 * @returns {HTMLElement} Parameter row element
 */
function createParameterInput(paramId, paramDef, currentValue = null) {
  const wrapper = document.createElement('div');
  wrapper.className = 'param-row';
  wrapper.setAttribute('data-param-id', paramId);

  const label = document.createElement('label');
  label.className = 'param-label';
  label.setAttribute('for', `param-${paramId}`);
  label.textContent = paramDef.description || paramId;

  const inputContainer = document.createElement('div');
  inputContainer.className = 'param-input';

  let input;

  switch (paramDef.type) {
    case 'int':
    case 'float':
      input = document.createElement('input');
      input.type = 'number';
      input.id = `param-${paramId}`;
      input.name = paramId;
      input.value = currentValue !== null ? currentValue : paramDef.default;

      if (paramDef.min !== undefined) input.min = paramDef.min;
      if (paramDef.max !== undefined) input.max = paramDef.max;
      if (paramDef.step !== undefined) input.step = paramDef.step;

      if (paramDef.type === 'float') {
        input.step = input.step || 0.01;
      } else {
        input.step = input.step || 1;
      }
      break;

    case 'bool':
      input = document.createElement('input');
      input.type = 'checkbox';
      input.id = `param-${paramId}`;
      input.name = paramId;
      input.checked = currentValue !== null ? currentValue : paramDef.default;
      break;

    case 'str':
      input = document.createElement('input');
      input.type = 'text';
      input.id = `param-${paramId}`;
      input.name = paramId;
      input.value = currentValue !== null ? currentValue : (paramDef.default || '');
      break;

    case 'categorical':
      input = document.createElement('select');
      input.id = `param-${paramId}`;
      input.name = paramId;

      if (paramDef.choices && Array.isArray(paramDef.choices)) {
        paramDef.choices.forEach((choice) => {
          const option = document.createElement('option');
          option.value = choice;
          option.textContent = choice;
          input.appendChild(option);
        });

        input.value = currentValue !== null ? currentValue : paramDef.default;
      }
      break;

    default:
      console.warn(`Unknown parameter type: ${paramDef.type} for ${paramId}`);
      input = document.createElement('input');
      input.type = 'text';
      input.id = `param-${paramId}`;
      input.name = paramId;
      input.value = currentValue !== null ? currentValue : (paramDef.default || '');
  }

  inputContainer.appendChild(input);

  // Добавляем описание если доступно
  if (paramDef.description) {
    const description = document.createElement('div');
    description.className = 'param-description';
    description.textContent = paramDef.description;
    inputContainer.appendChild(description);
  }

  wrapper.appendChild(label);
  wrapper.appendChild(inputContainer);

  return wrapper;
}
```

### 2.3 Функция построения формы

```javascript
/**
 * Build complete parameter form for a strategy
 * @param {string} containerId - ID контейнера для вставки формы
 * @param {Object} strategy - Объект стратегии с parameters
 * @param {boolean} preserveValues - Сохранять ли текущие значения
 */
function buildParameterForm(containerId, strategy, preserveValues = true) {
  const container = document.getElementById(containerId);
  if (!container) {
    console.error(`Container ${containerId} not found`);
    return;
  }

  // Сохраняем текущие значения перед очисткой
  const currentValues = {};
  if (preserveValues) {
    container.querySelectorAll('input, select').forEach((input) => {
      const paramId = input.name;
      if (!paramId) return;

      if (input.type === 'checkbox') {
        currentValues[paramId] = input.checked;
      } else if (input.type === 'number') {
        currentValues[paramId] = parseFloat(input.value);
      } else {
        currentValues[paramId] = input.value;
      }
    });
  }

  // Очищаем существующую форму
  container.innerHTML = '';

  if (!strategy || !strategy.parameters) {
    container.innerHTML = '<p style="color: #999; padding: 20px;">Параметры для этой стратегии недоступны.</p>';
    return;
  }

  // Категоризируем параметры
  const groups = categorizeParameters(strategy.parameters);

  // Строим каждую секцию
  Object.entries(groups).forEach(([groupKey, group]) => {
    const section = document.createElement('div');
    section.className = `param-section ${group.cssClass}`;

    const title = document.createElement('div');
    title.className = 'param-section-title';
    title.textContent = group.title;
    section.appendChild(title);

    // Добавляем параметры в секцию
    group.params.forEach((param) => {
      const currentValue = currentValues[param.id] !== undefined ? currentValues[param.id] : null;
      const inputElement = createParameterInput(param.id, param, currentValue);
      section.appendChild(inputElement);
    });

    container.appendChild(section);
  });

  console.log(`Built parameter form for ${strategy.strategy_id} with ${Object.keys(strategy.parameters).length} parameters`);
}
```

---

## Шаг 3: Обновить обработчик смены стратегии Backtester

### 3.1 Найти функцию onBacktesterStrategyChange

Найдите существующую функцию `onBacktesterStrategyChange()` в index.html.

### 3.2 Добавить вызов генерации формы

Обновите функцию:

```javascript
/**
 * Handle backtester strategy change
 */
function onBacktesterStrategyChange() {
  const strategyId = document.getElementById('backtesterStrategy').value;
  if (!strategyId) return;

  currentBacktesterStrategy = strategyMetadataCache[strategyId];
  if (!currentBacktesterStrategy) {
    console.error('Strategy not found:', strategyId);
    return;
  }

  // Update info panel
  document.getElementById('backtesterStrategyName').textContent = currentBacktesterStrategy.name;
  document.getElementById('backtesterStrategyType').textContent =
    currentBacktesterStrategy.type === 'trend' ? 'Трендовая' : 'Реверсивная';
  document.getElementById('backtesterStrategyDesc').textContent = currentBacktesterStrategy.description;
  document.getElementById('backtesterStrategyInfo').style.display = 'block';

  // ⭐ NEW: Build dynamic parameter form
  buildParameterForm('backtesterDynamicParams', currentBacktesterStrategy, true);

  console.log('Backtester strategy changed to:', strategyId);
}
```

---

## Шаг 4: Обновить сбор параметров Backtester

### 4.1 Реализовать универсальный сборщик параметров

Добавьте новую функцию:

```javascript
/**
 * Collect parameters from dynamic form
 * @param {string} containerId - ID контейнера с динамической формой
 * @returns {Object} Параметры
 */
function collectDynamicParameters(containerId) {
  const container = document.getElementById(containerId);
  if (!container) {
    console.error(`Container ${containerId} not found`);
    return {};
  }

  const params = {};

  container.querySelectorAll('input, select').forEach((input) => {
    const paramId = input.name;
    if (!paramId) return;

    if (input.type === 'checkbox') {
      params[paramId] = input.checked;
    } else if (input.type === 'number') {
      const value = parseFloat(input.value);
      params[paramId] = isNaN(value) ? 0 : value;
    } else {
      params[paramId] = input.value;
    }
  });

  return params;
}
```

### 4.2 Заменить collectBacktesterParameters

Найдите существующую функцию `collectBacktesterParameters()` и **замените** её на:

```javascript
/**
 * Collect backtester parameters (new dynamic version)
 */
function collectBacktesterParameters() {
  const params = collectDynamicParameters('backtesterDynamicParams');

  // Добавляем общие параметры (date filter, CSV)
  params.dateFilter = document.getElementById('dateFilter').checked;
  params.startDate = document.getElementById('startDate').value;
  params.endDate = document.getElementById('endDate').value;

  // Добавляем csvPath если есть
  const csvPathElement = document.getElementById('csvPath');
  if (csvPathElement) {
    params.csvPath = csvPathElement.value;
  }

  return params;
}
```

---

## Шаг 5: Тестирование

### 5.1 Создать тестовую функцию

Добавить в конец секции `<script>`:

```javascript
/**
 * Test parameter form generation (console test)
 */
window.testBacktesterFormGeneration = function() {
  console.log('=== Testing Backtester Parameter Form Generation ===');

  // Test S_01
  console.log('Test 1: S_01 form generation');
  const s01 = strategyMetadataCache['s01_trailing_ma'];
  if (s01) {
    buildParameterForm('backtesterDynamicParams', s01, false);
    const s01ParamCount = document.querySelectorAll('#backtesterDynamicParams .param-row').length;
    console.log(`✅ S_01: ${s01ParamCount} параметров отрендерено`);
  } else {
    console.error('❌ S_01 strategy not found in cache');
  }

  // Test S_03
  console.log('Test 2: S_03 form generation');
  const s03 = strategyMetadataCache['s03_reversal'];
  if (s03) {
    buildParameterForm('backtesterDynamicParams', s03, false);
    const s03ParamCount = document.querySelectorAll('#backtesterDynamicParams .param-row').length;
    console.log(`✅ S_03: ${s03ParamCount} параметров отрендерено`);
  } else {
    console.error('❌ S_03 strategy not found in cache');
  }

  // Test parameter collection
  console.log('Test 3: Parameter collection');
  const params = collectBacktesterParameters();
  console.log(`✅ Собрано ${Object.keys(params).length} параметров:`, params);

  console.log('=== Backtester Tests Completed ===');
};
```

### 5.2 Ручное тестирование

После реализации:

1. **Запустить сервер**:
   ```bash
   cd src
   python server.py
   ```

2. **Открыть браузер**: http://localhost:8000

3. **Открыть DevTools Console**

4. **Запустить тест**:
   ```javascript
   testBacktesterFormGeneration()
   ```

5. **Проверить консоль**:
   - ✅ Нет ошибок JavaScript
   - ✅ S_01 показывает N параметров
   - ✅ S_03 показывает N параметров
   - ✅ collectBacktesterParameters() возвращает объект с параметрами

### 5.3 UI тестирование

**Backtester панель**:
- [ ] Выбрать S_01 → форма показывает ~30 параметров
- [ ] Выбрать S_03 → форма показывает ~15 параметров
- [ ] Редактировать S_03 `maFastType` → меняется с SMA на EMA
- [ ] Редактировать S_03 `maFastLength` → меняется с 100 на 50
- [ ] Переключить S_01 → S_03 → S_01 → значения сохраняются
- [ ] Нет ошибок JavaScript в консоли
- [ ] Форма рендерится быстро (< 200ms)

### 5.4 Интеграционное тестирование с backend

**Тест 1: S_03 бэктест с кастомными параметрами**

1. Выбрать S_03 в Backtester
2. Изменить `maFastType` на "EMA"
3. Изменить `maFastLength` на 50
4. Изменить `maTrendLength` на 200
5. Загрузить CSV: `OKX_LINKUSDT.P, 15 2025.05.01-2025.11.20.csv`
6. Нажать "Run Backtest"
7. **Ожидается**: Результаты отличаются от дефолтных (не 83.56%)

**Тест 2: Референсный тест S_03 (дефолтные параметры)**

1. Выбрать S_03
2. Не менять параметры (оставить дефолтные)
3. Загрузить CSV
4. Нажать "Run Backtest"
5. **Ожидается**:
   - Net Profit: 83.56%
   - Max Drawdown: 35.34%
   - Trades: 224

**Тест 3: Референсный тест S_01**

1. Выбрать S_01
2. Не менять параметры
3. Загрузить CSV
4. Нажать "Run Backtest"
5. **Ожидается**:
   - Net Profit: 230.75%
   - Max Drawdown: 20.03%
   - Trades: 93

---

## Критерии приемки Подэтапа 8-1

Подэтап 8-1 считается завершенным когда:

1. ✅ HTML обновлен - добавлен контейнер `#backtesterDynamicParams`
2. ✅ CSS стили добавлены
3. ✅ Функция `categorizeParameters()` реализована
4. ✅ Функция `createParameterInput()` реализована
5. ✅ Функция `buildParameterForm()` реализована
6. ✅ Функция `collectDynamicParameters()` реализована
7. ✅ Функция `collectBacktesterParameters()` обновлена
8. ✅ Функция `onBacktesterStrategyChange()` вызывает `buildParameterForm()`
9. ✅ S_03 параметры полностью редактируются в Backtester UI
10. ✅ S_01 бэктест возвращает 230.75% / 20.03% / 93 (референс не сломан)
11. ✅ S_03 бэктест возвращает 83.56% / 35.34% / 224 (референс не сломан)
12. ✅ S_03 бэктест с кастомными параметрами возвращает ДРУГИЕ результаты
13. ✅ Переключение стратегий сохраняет значения параметров
14. ✅ Нет ошибок JavaScript в консоли
15. ✅ Форма генерируется быстро (< 200ms)
16. ✅ Тест `testBacktesterFormGeneration()` проходит успешно

---

## Важные замечания

### Что СОХРАНИТЬ из старого кода

**НЕ удалять** следующие элементы из HTML:
- ✅ Date Filter чекбокс (`#dateFilter`)
- ✅ Start Date / End Date (`#startDate`, `#endDate`)
- ✅ CSV upload (`#csvPath` или аналог)
- ✅ Worker processes selector
- ✅ Run Backtest button
- ✅ Strategy selector dropdown (`#backtesterStrategy`)
- ✅ Strategy info panel (`#backtesterStrategyInfo`)

### Что УДАЛИТЬ

**Удалить** все захардкоженные поля параметров:
- ❌ MA Length inputs
- ❌ Close Count Long/Short inputs
- ❌ Stop ATR/RR/LP inputs
- ❌ Trail MA inputs
- ❌ Risk Per Trade inputs

**Заменить** их на `#backtesterDynamicParams` контейнер.

### Совместимость с Подэтапом 8-2

Убедитесь что следующие функции доступны глобально (для использования в 8-2):
- `categorizeParameters(parameters)`
- `createParameterInput(paramId, paramDef, currentValue)`
- `buildParameterForm(containerId, strategy, preserveValues)`
- `collectDynamicParameters(containerId)`

Эти функции будут переиспользованы в 8-2 для Optimizer панели.

---

## Следующий шаг

После успешного завершения Подэтапа 8-1:
1. Закоммитить изменения
2. Запустить референсные тесты
3. Убедиться что всё работает корректно
4. Перейти к **migration_prompt_8-2.md**

---

## Структура коммита

```bash
git add src/index.html
git commit -m "Phase 8-1: Dynamic parameter forms for Backtester

- Add dynamic parameter container for backtester
- Implement categorizeParameters() for grouping
- Implement createParameterInput() for all types (int, float, bool, str, categorical)
- Implement buildParameterForm() with value preservation
- Update onBacktesterStrategyChange() to rebuild form
- Update collectBacktesterParameters() to use dynamic form
- Add CSS styles for param sections and inputs
- Remove hardcoded S_01 parameter fields from backtester
- S_03 parameters now fully editable in UI

Reference tests:
- S_01: 230.75% / 20.03% / 93 trades ✅
- S_03: 83.56% / 35.34% / 224 trades ✅
- S_03 with custom params: different results ✅

Next: Phase 8-2 (Optimizer + finalization)"
```

---

**Конец migration_prompt_8-1.md**
