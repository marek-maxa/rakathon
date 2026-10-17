document.querySelectorAll('.patient-email').forEach((form) => {
  form.addEventListener('submit', (event) => {
    if (form.getAttribute('aria-busy') === 'true') {
      event.preventDefault();
      return;
    }
    const button = event.submitter;
    const action = document.createElement('input');
    action.type = 'hidden';
    action.name = 'action';
    action.value = button?.value || 'send';
    action.dataset.submissionAction = 'true';
    form.append(action);
    form.querySelectorAll('button').forEach((item) => { item.disabled = true; });
    form.setAttribute('aria-busy', 'true');
    if (button) {
      button.dataset.originalText = button.textContent;
      button.textContent = action.value === 'save_contact' ? 'Ukládání…' : 'Odesílání…';
    }
  });
});

window.addEventListener('pageshow', () => {
  document.querySelectorAll('.patient-email').forEach((form) => {
    form.querySelectorAll('button').forEach((button) => {
      button.disabled = false;
      if (button.dataset.originalText) button.textContent = button.dataset.originalText;
    });
    form.querySelectorAll('[data-submission-action]').forEach((input) => input.remove());
    form.removeAttribute('aria-busy');
  });
});
