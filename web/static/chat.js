const form = document.querySelector('.chat-form');
const input = document.querySelector('#message');
const messages = document.querySelector('.messages');

form.addEventListener('submit', (event) => {
  event.preventDefault();
  const text = input.value.trim();
  if (!text) return;

  const message = document.createElement('p');
  message.className = 'message message-user';
  message.textContent = text;
  messages.append(message);
  messages.scrollTop = messages.scrollHeight;
  form.reset();
  input.focus();
});
