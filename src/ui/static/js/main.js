/**
 * Main entry: binds DOM events and initializes UI state.
 */

document.addEventListener('DOMContentLoaded', async () => {
  await loadStrategiesList();

  document.querySelectorAll('.collapsible').forEach((collapsible) => {
    const header = collapsible.querySelector('.collapsible-header');
    if (!header) return;
    header.addEventListener('click', () => {
      collapsible.classList.toggle('open');
    });
  });

  const linkToScoreConfig = document.getElementById('linkToScoreConfig');
  if (linkToScoreConfig) {
    linkToScoreConfig.addEventListener('click', (event) => {
      event.preventDefault();
      const scoreConfigBtn = document.getElementById('scoreConfigBtn');
      const scoreConfigCollapsible = document.getElementById('scoreConfigCollapsible');
      if (scoreConfigBtn && scoreConfigCollapsible) {
        if (!scoreConfigCollapsible.classList.contains('open')) {
          scoreConfigCollapsible.classList.add('open');
        }
        scoreConfigBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
        scoreConfigCollapsible.style.outline = '3px solid #90caf9';
        window.setTimeout(() => {
          scoreConfigCollapsible.style.outline = '';
        }, 2000);
      }
    });
  }

  const budgetModeRadios = document.querySelectorAll('input[name="budgetMode"]');
  budgetModeRadios.forEach((radio) => {
    radio.addEventListener('change', syncBudgetInputs);
  });
  syncBudgetInputs();
  toggleWFSettings();

  const csvFileInputEl = document.getElementById('csvFile');
  if (csvFileInputEl) {
    csvFileInputEl.addEventListener('change', () => {
      const files = Array.from(csvFileInputEl.files || []);
      if (files.length) {
        const firstFile = files[0];
        const derivedPath = (firstFile && (firstFile.path || firstFile.webkitRelativePath)) || '';
        const fallbackName = firstFile && firstFile.name ? firstFile.name : '';
        window.selectedCsvPath = (derivedPath || fallbackName || '').trim();
      } else {
        window.selectedCsvPath = '';
      }
      renderSelectedFiles(files);
    });
  }

  const presetToggleEl = document.getElementById('presetToggle');
  const presetMenuEl = document.getElementById('presetMenu');
  const presetDropdownEl = document.getElementById('presetDropdown');
  const presetImportInput = document.getElementById('presetImportInput');

  if (presetToggleEl) {
    presetToggleEl.addEventListener('click', (event) => {
      event.stopPropagation();
      togglePresetMenu();
    });
  }

  if (presetMenuEl) {
    presetMenuEl.addEventListener('click', (event) => {
      event.stopPropagation();
      const actionButton = event.target.closest('.preset-action');
      if (!actionButton) return;

      const action = actionButton.dataset.action;
      if (action === 'apply-defaults') {
        handleApplyDefaults();
      } else if (action === 'save-as') {
        handleSaveAsPreset();
      } else if (action === 'save-defaults') {
        handleSaveDefaults();
      } else if (action === 'import') {
        if (presetImportInput) {
          presetImportInput.value = '';
          presetImportInput.click();
        }
      }
    });
  }

  if (presetImportInput) {
    presetImportInput.addEventListener('change', async (event) => {
      const file = event.target.files && event.target.files[0];
      if (!file) {
        presetImportInput.value = '';
        closePresetMenu();
        return;
      }
      try {
        const data = await importPresetFromCsvRequest(file);
        applyPresetValues(data?.values || {}, { clearResults: false });
        const appliedKeys = Array.from(new Set(data?.applied || []));
        const appliedLabels = appliedKeys.map((key) => formatPresetLabel(key));
        const message = appliedLabels.length
          ? `Imported parameters: ${appliedLabels.join(', ')}.`
          : 'CSV import did not change any settings.';
        showResultsMessage(message);
        clearErrorMessage();
      } catch (error) {
        showErrorMessage(error.message || 'Failed to import settings from CSV');
      } finally {
        presetImportInput.value = '';
        closePresetMenu();
      }
    });
  }

  document.addEventListener('click', (event) => {
    if (
      presetDropdownEl &&
      presetDropdownEl.classList.contains('open') &&
      !presetDropdownEl.contains(event.target)
    ) {
      closePresetMenu();
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      closePresetMenu();
    }
  });

  const cancelBtn = document.getElementById('cancelBtn');
  if (cancelBtn) {
    cancelBtn.addEventListener('click', () => {
      const backtestForm = document.getElementById('backtestForm');
      if (backtestForm) backtestForm.reset();
      applyDefaults({ clearResults: true });
    });
  }

  const backtestForm = document.getElementById('backtestForm');
  if (backtestForm) {
    backtestForm.addEventListener('submit', runBacktest);
  }

  const optimizerForm = document.getElementById('optimizerForm');
  if (optimizerForm) {
    optimizerForm.addEventListener('submit', submitOptimization);
  }

  bindOptimizerInputs();
  bindMinProfitFilterControl();
  bindScoreControls();
  bindMASelectors();

  await initializePresets();
});
