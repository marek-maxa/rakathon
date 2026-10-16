const loading = document.querySelector('#loading');
const card = document.querySelector('.form-card');
let submitting = false;

document.addEventListener('submit', (event) => {
  if (submitting) {
    event.preventDefault();
    return;
  }

  const form = event.target;
  const button = event.submitter;
  if (button?.name) {
    const action = document.createElement('input');
    action.type = 'hidden';
    action.name = button.name;
    action.value = button.value;
    action.dataset.submitAction = '';
    form.append(action);
  }

  submitting = true;
  loading.hidden = false;
  card.setAttribute('aria-busy', 'true');
  document.querySelectorAll('button').forEach((button) => {
    button.disabled = true;
  });
});

window.addEventListener('pageshow', () => {
  submitting = false;
  loading.hidden = true;
  card.removeAttribute('aria-busy');
  document.querySelectorAll('[data-submit-action]').forEach((action) => action.remove());
  document.querySelectorAll('button').forEach((button) => {
    button.disabled = false;
  });
});
