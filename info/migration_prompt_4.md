# Migration Prompt 4: Dynamic UI Forms

## Objective

Update the web UI to dynamically load and display strategy-specific forms based on config.json, and add a warmup bars input field.

## Prerequisites

Complete **migration_prompt_3.md** before starting this stage.

## Context

The current index.html has hardcoded forms for S01 strategy parameters. We need to:
1. Add a strategy selector dropdown
2. Generate forms dynamically from strategy config.json
3. Add a warmup bars input field
4. Keep existing forms hidden as fallback

## Tasks

### Task 4.1: Add Strategy Selector

Open `src/index.html` and add the strategy selector section at the top of the main form (after the `<h1>` title):

```html
<!-- ============================================ -->
<!-- STRATEGY SELECTOR -->
<!-- ============================================ -->
<div class="strategy-selector-section" style="margin-bottom: 30px; padding: 20px; background-color: #f0f8ff; border: 2px solid #4a90e2; border-radius: 8px;">
  <h2 style="margin-top: 0; color: #4a90e2;">📊 Select Strategy</h2>

  <div class="form-group">
    <label style="font-weight: bold;">Strategy:</label>
    <select id="strategySelect" onchange="handleStrategyChange()" style="padding: 8px; font-size: 14px; min-width: 300px;">
      <option value="">Loading strategies...</option>
    </select>
  </div>

  <div id="strategyInfo" style="margin-top: 15px; padding: 15px; background-color: white; border-radius: 5px; display: none;">
    <div style="display: grid; grid-template-columns: auto 1fr; gap: 10px; font-size: 14px;">
      <strong>Name:</strong> <span id="strategyName"></span>
      <strong>Version:</strong> <span id="strategyVersion"></span>
      <strong>Description:</strong> <span id="strategyDescription"></span>
      <strong>Parameters:</strong> <span id="strategyParamCount"></span>
    </div>
  </div>
</div>
```

### Task 4.2: Add Warmup Bars Field

Add the warmup bars input field in the Date Range section (find the existing date inputs and add this after the End Date/Time fields):

```html
<!-- Add after End Time input -->
<div class="form-group">
  <label>Warmup Bars:</label>
  <input type="number" id="warmupBars" name="warmupBars" value="1000" min="100" max="5000" step="100" style="width: 120px;">
  <span style="margin-left: 10px; font-size: 12px; color: #666;">
    (Bars before Start Date for indicator calculation. Recommended: 1000-2000)
  </span>
</div>
```

### Task 4.3: Create Dynamic Forms Container

Add a new container for dynamically generated forms (add this after the Date Range section, BEFORE the existing parameter forms):

```html
<!-- ============================================ -->
<!-- DYNAMIC STRATEGY PARAMETERS -->
<!-- ============================================ -->
<div id="dynamicParameterForms" style="margin-top: 30px;">
  <h2>Strategy Parameters</h2>

  <!-- Backtest Parameters Container -->
  <div id="backtestParamsContainer" class="params-section">
    <h3>Backtest Parameters</h3>
    <div id="backtestParamsContent">
      <!-- Generated forms will appear here -->
    </div>
  </div>

  <!-- Optimization Parameters Container -->
  <div id="optimizerParamsContainer" class="params-section" style="margin-top: 30px;">
    <h3>Optimization Parameters</h3>
    <div id="optimizerParamsContent">
      <!-- Generated forms will appear here -->
    </div>
  </div>
</div>

<!-- Hide old hardcoded forms (keep for fallback) -->
<div id="legacyForms" style="display: none;">
  <!-- Existing hardcoded forms moved here -->
</div>
```

### Task 4.4: Understanding Current UI Structure

**IMPORTANT:** Generated forms must match the existing UI appearance exactly. The current UI uses specific CSS classes and HTML patterns:

**CSS Classes:**
- `.form-group` - Standard form field wrapper
- `.param-group` - Multiple inline parameters (used for grouped inputs like "Label: Input Label: Input")
- `.checkbox-group` - Checkbox with label
- `.opt-section` - Optimizer parameter section (gray background)
- `.opt-section-title` - Section title in optimizer (uppercase, small font)
- `.opt-row` - Single optimizer parameter row
- `.opt-label` - Optimizer parameter label
- `.opt-controls` - Container for From/To/Step inputs
- `.tiny-input` - Small input field (60px width)
- `.collapsible` - Collapsible section
- `.collapsible-header`, `.collapsible-content` - For collapsible sections

**HTML Structure Examples:**

Basic form field:
```html
<div class="form-group">
  <label for="paramName">Parameter Label</label>
  <input type="number" id="paramName" min="0" />
</div>
```

Grouped parameters (multiple on one line):
```html
<div class="param-group">
  <label for="param1">Param 1</label>
  <input type="number" id="param1" min="0" />
  <label for="param2">Param 2</label>
  <input type="number" id="param2" min="0" />
</div>
```

Optimizer parameter:
```html
<div class="opt-section">
  <div class="opt-section-title">SECTION NAME</div>
  <div class="opt-row">
    <input id="opt-paramName" type="checkbox" />
    <label class="opt-label" for="opt-paramName">Parameter Label</label>
    <div class="opt-controls">
      <label>From:</label>
      <input class="tiny-input" id="paramName-from" type="number" value="10" />
      <label>To:</label>
      <input class="tiny-input" id="paramName-to" type="number" value="100" />
      <label>Step:</label>
      <input class="tiny-input" id="paramName-step" type="number" value="10" />
    </div>
  </div>
</div>
```

### Task 4.5: Add JavaScript Form Generation

Add the following JavaScript code to `index.html` (place it in the `<script>` section, or create a new one at the end of `<body>`).

**NOTE:** The code below uses the existing CSS classes to ensure forms match current appearance:

```javascript
// ============================================
// STRATEGY MANAGEMENT
// ============================================

let currentStrategyId = null;
let currentStrategyConfig = null;

/**
 * Load list of available strategies on page load
 */
async function loadStrategiesList() {
    try {
        const response = await fetch('/api/strategies');
        const data = await response.json();

        const select = document.getElementById('strategySelect');
        select.innerHTML = '';

        if (!data.strategies || data.strategies.length === 0) {
            select.innerHTML = '<option value="">No strategies found</option>';
            console.error('No strategies discovered');
            return;
        }

        // Populate dropdown
        data.strategies.forEach(strategy => {
            const option = document.createElement('option');
            option.value = strategy.id;
            option.textContent = `${strategy.name} ${strategy.version}`;
            select.appendChild(option);
        });

        // Auto-select first strategy
        if (data.strategies.length > 0) {
            currentStrategyId = data.strategies[0].id;
            select.value = currentStrategyId;
            await loadStrategyConfig(currentStrategyId);
        }

    } catch (error) {
        console.error('Failed to load strategies:', error);
        alert('Error loading strategies. Check console for details.');
    }
}

/**
 * Handle strategy selection change
 */
async function handleStrategyChange() {
    const select = document.getElementById('strategySelect');
    currentStrategyId = select.value;

    if (!currentStrategyId) {
        return;
    }

    await loadStrategyConfig(currentStrategyId);
}

/**
 * Load strategy configuration and generate forms
 */
async function loadStrategyConfig(strategyId) {
    try {
        // Fetch full config
        const response = await fetch(`/api/strategies/${strategyId}/config`);
        currentStrategyConfig = await response.json();

        // Update strategy info display
        updateStrategyInfo(currentStrategyConfig);

        // Generate forms
        generateBacktestForm(currentStrategyConfig);
        generateOptimizerForm(currentStrategyConfig);

        console.log(`Loaded strategy: ${currentStrategyConfig.name}`);

    } catch (error) {
        console.error('Failed to load strategy config:', error);
        alert('Error loading strategy configuration');
    }
}

/**
 * Update strategy info panel
 */
function updateStrategyInfo(config) {
    document.getElementById('strategyName').textContent = config.name;
    document.getElementById('strategyVersion').textContent = config.version;
    document.getElementById('strategyDescription').textContent = config.description || 'N/A';
    document.getElementById('strategyParamCount').textContent = Object.keys(config.parameters || {}).length;
    document.getElementById('strategyInfo').style.display = 'block';
}

/**
 * Generate backtest parameters form from config
 */
function generateBacktestForm(config) {
    const container = document.getElementById('backtestParamsContent');
    container.innerHTML = '';

    const params = config.parameters || {};
    const groups = {};

    // Group parameters by category
    for (const [paramName, paramDef] of Object.entries(params)) {
        const group = paramDef.group || 'Other';
        if (!groups[group]) {
            groups[group] = [];
        }
        groups[group].push({ name: paramName, def: paramDef });
    }

    // Generate HTML for each group
    for (const [groupName, groupParams] of Object.entries(groups)) {
        const groupDiv = document.createElement('div');
        groupDiv.className = 'param-group';
        groupDiv.style.marginBottom = '25px';

        const groupTitle = document.createElement('h4');
        groupTitle.textContent = groupName;
        groupTitle.style.color = '#4a90e2';
        groupTitle.style.marginBottom = '15px';
        groupDiv.appendChild(groupTitle);

        // Generate form fields for each parameter
        groupParams.forEach(({ name, def }) => {
            const formGroup = createFormField(name, def, 'backtest');
            groupDiv.appendChild(formGroup);
        });

        container.appendChild(groupDiv);
    }
}

/**
 * Generate optimizer parameters form from config
 * Uses existing UI classes: .opt-section, .opt-row, .opt-label, .opt-controls
 *
 * IMPORTANT: Only shows parameters where optimize.enabled !== false
 * This allows platform settings (commission_rate, contract_size, etc.) to be in
 * Backtester forms but not in Optimizer forms.
 */
function generateOptimizerForm(config) {
    const container = document.getElementById('optimizerParamsContent');
    container.innerHTML = '';

    const params = config.parameters || {};
    const groups = {};

    // Group parameters by category
    // IMPORTANT: Only include parameters where optimize.enabled !== false
    for (const [paramName, paramDef] of Object.entries(params)) {
        // Skip parameters that are not optimizable
        const optimizeEnabled = paramDef.optimize?.enabled;
        if (optimizeEnabled === false) {
            continue; // Don't show in optimizer (e.g., commission_rate, contract_size)
        }

        const group = paramDef.group || 'Other';
        if (!groups[group]) {
            groups[group] = [];
        }
        groups[group].push({ name: paramName, def: paramDef });
    }

    // Generate sections for each group
    for (const [groupName, groupParams] of Object.entries(groups)) {
        const section = document.createElement('div');
        section.className = 'opt-section';

        const sectionTitle = document.createElement('div');
        sectionTitle.className = 'opt-section-title';
        sectionTitle.textContent = groupName.toUpperCase();
        section.appendChild(sectionTitle);

        // Generate parameter rows
        groupParams.forEach(({ name, def }) => {
            const optimizeEnabled = def.optimize?.enabled || false;

            const row = document.createElement('div');
            row.className = 'opt-row';

            // Checkbox
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.id = `opt-${name}`;
            checkbox.checked = optimizeEnabled;

            // Label
            const label = document.createElement('label');
            label.className = 'opt-label';
            label.htmlFor = `opt-${name}`;
            label.textContent = def.label || name;

            row.appendChild(checkbox);
            row.appendChild(label);

            // Controls (From/To/Step)
            if (def.type === 'int' || def.type === 'float') {
                const controls = document.createElement('div');
                controls.className = 'opt-controls';
                controls.id = `opt-${name}-controls`;
                controls.style.display = optimizeEnabled ? 'flex' : 'none';

                const step = def.optimize?.step || def.step || (def.type === 'int' ? 1 : 0.1);

                controls.innerHTML = `
                    <label>From:</label>
                    <input class="tiny-input" id="${name}-from" type="number"
                           value="${def.optimize?.min || def.min || def.default}" step="${step}" />
                    <label>To:</label>
                    <input class="tiny-input" id="${name}-to" type="number"
                           value="${def.optimize?.max || def.max || def.default}" step="${step}" />
                    <label>Step:</label>
                    <input class="tiny-input" id="${name}-step" type="number"
                           value="${step}" step="${def.type === 'int' ? 1 : 0.1}" />
                `;

                row.appendChild(controls);

                // Toggle visibility
                checkbox.addEventListener('change', function() {
                    controls.style.display = this.checked ? 'flex' : 'none';
                });
            }

            section.appendChild(row);
        });

        container.appendChild(section);
    }
}

/**
 * Create a form field based on parameter definition
 */
function createFormField(paramName, paramDef, prefix) {
    const formGroup = document.createElement('div');
    formGroup.className = 'form-group';
    formGroup.style.marginBottom = '15px';

    const label = document.createElement('label');
    label.textContent = paramDef.label || paramName;
    label.style.display = 'inline-block';
    label.style.width = '200px';
    formGroup.appendChild(label);

    let input;

    if (paramDef.type === 'select') {
        input = document.createElement('select');
        input.id = `${prefix}_${paramName}`;
        input.name = paramName;
        input.style.padding = '5px';
        input.style.minWidth = '150px';

        (paramDef.options || []).forEach(option => {
            const opt = document.createElement('option');
            opt.value = option;
            opt.textContent = option;
            if (option === paramDef.default) {
                opt.selected = true;
            }
            input.appendChild(opt);
        });

    } else if (paramDef.type === 'int' || paramDef.type === 'float') {
        input = document.createElement('input');
        input.type = 'number';
        input.id = `${prefix}_${paramName}`;
        input.name = paramName;
        input.value = paramDef.default || 0;
        input.min = paramDef.min !== undefined ? paramDef.min : '';
        input.max = paramDef.max !== undefined ? paramDef.max : '';
        input.step = paramDef.step || (paramDef.type === 'int' ? 1 : 0.1);
        input.style.padding = '5px';
        input.style.width = '120px';

    } else if (paramDef.type === 'bool') {
        input = document.createElement('input');
        input.type = 'checkbox';
        input.id = `${prefix}_${paramName}`;
        input.name = paramName;
        input.checked = paramDef.default || false;
    }

    formGroup.appendChild(input);
    return formGroup;
}

// ============================================
// INITIALIZE ON PAGE LOAD
// ============================================

window.addEventListener('DOMContentLoaded', () => {
    loadStrategiesList();
});
```

## Testing

### Test 4.1: Strategy Selector Loads
1. Open browser and navigate to `http://localhost:8000`
2. Verify strategy dropdown is populated
3. Check that "S01 Trailing MA v26" appears
4. Strategy info panel should display metadata

### Test 4.2: Backtest Form Generation
1. Select S01 strategy from dropdown
2. Verify backtest parameters are generated
3. Check that parameters are grouped (Entry, Stops, Trail, Risk)
4. Verify all default values match config.json

### Test 4.3: Optimizer Form Generation
1. Verify optimizer checkboxes are present
2. Check that optimization ranges are hidden by default
3. Click a checkbox - range inputs should appear
4. Verify default ranges match config.json optimize settings
5. **IMPORTANT:** Verify optimizer uses `.opt-section`, `.opt-row`, `.opt-label`, `.opt-controls` classes
6. Check that appearance matches the existing "Optimizer Parameters" window (gray sections, proper spacing)

### Test 4.4: Warmup Bars Field
1. Locate the warmup bars input field
2. Verify default value is 1000
3. Test that values can be changed
4. Verify min/max constraints (100-5000)

### Test 4.5: Browser Console
Open browser console (F12) and check for:
- No JavaScript errors
- Log message: "Loaded strategy: S01 Trailing MA"
- No network errors when fetching `/api/strategies`

## Completion Checklist

- [ ] Strategy selector added and working
- [ ] Warmup bars field added
- [ ] Dynamic forms container created
- [ ] JavaScript form generation implemented using existing CSS classes
- [ ] Backtest forms generated correctly with `.form-group` and `.param-group` classes
- [ ] Optimizer forms generated correctly with `.opt-section`, `.opt-row`, `.opt-label`, `.opt-controls` classes
- [ ] **Generated forms appearance matches existing UI exactly**
- [ ] All UI elements render properly
- [ ] No console errors
- [ ] Git commit: "Migration Stage 4: Add dynamic UI form generation"

## Next Stage

Proceed to **migration_prompt_5.md** for final API integration and testing.
