(() => {
  'use strict';
  const results = document.querySelector('[data-document-results][data-updates-url]');
  if (!results) return;
  const get = (name) => results.querySelector(`[data-document-${name}]`);
  const announcement = document.querySelector('[data-document-announcement]');
  const seen = new Set(Array.from(results.querySelectorAll('[data-document-reference]'),
    (element) => element.dataset.documentReference));
  const fileTypes = new Set(['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
    'odt', 'ods', 'odp', 'rtf', 'txt', 'csv', 'html', 'unknown']);
  const states = new Set(['queued', 'running', 'done', 'error']);
  let failures = 0;
  let inFlight = false;
  let stopped = false;

  function safeUrl(value) {
    if (!text(value, 2048) || !value
        || /[\u0000-\u0020\u007f\\]/.test(value)) return false;
    try {
      const url = new URL(value);
      return ['http:', 'https:'].includes(url.protocol) && Boolean(url.hostname)
        && !url.username && !url.password;
    } catch {
      return false;
    }
  }

  function text(value, limit) {
    // Match Python's Unicode code-point bounds, including supplementary characters.
    return typeof value === 'string' && Array.from(value).length <= limit;
  }

  function validSnapshot(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data)
        || data.mode !== 'name' || !states.has(data.state)
        || !(data.file_type === 'any' || fileTypes.has(data.file_type)
          && !['html', 'unknown'].includes(data.file_type))
        || !Number.isSafeInteger(data.checked) || data.checked < 0 || data.checked > 1
        || data.total !== 1 || !Number.isSafeInteger(data.elapsed) || data.elapsed < 0
        || !text(data.error, 2048)
        || !Array.isArray(data.references) || data.references.length > 10) return false;
    if (data.queue_position !== undefined && data.queue_position !== null
        && (!Number.isSafeInteger(data.queue_position) || data.queue_position < 0)) return false;
    if (data.query !== undefined && !text(data.query, 300)) return false;
    if (data.google_url !== undefined && !safeUrl(data.google_url)) return false;
    const urls = new Set(seen);
    for (const reference of data.references) {
      if (!reference || typeof reference !== 'object' || Array.isArray(reference)
          || !safeUrl(reference.url) || reference.id !== reference.url
          || !text(reference.title, 300) || !text(reference.snippet, 1600)
          || !text(reference.source, 253) || !fileTypes.has(reference.file_type)) return false;
      urls.add(reference.url);
    }
    return urls.size <= 10;
  }

  function appendText(parent, tag, className, value) {
    const element = document.createElement(tag);
    element.className = className;
    element.textContent = value;
    parent.append(element);
    return element;
  }

  function referenceCard(reference) {
    const article = document.createElement('article');
    article.className = 'profile document-reference';
    article.dataset.documentReference = reference.url;
    const heading = document.createElement('h3');
    const anchor = document.createElement('a');
    anchor.href = reference.url;
    anchor.target = '_blank';
    anchor.rel = 'noopener noreferrer';
    anchor.textContent = reference.title;
    heading.append(anchor);
    article.append(heading);
    appendText(article, 'p', 'document-meta', `${reference.source} · ${reference.file_type.toUpperCase()} · tipo inferido pela URL, não verificado`);
    appendText(article, 'p', 'document-snippet', reference.snippet);
    appendText(article, 'p', 'profile-url', reference.url);
    return article;
  }

  function show(data) {
    // Validate the entire bounded snapshot before changing any visible content.
    if (!validSnapshot(data)) throw new Error('Invalid snapshot');
    for (const reference of data.references) {
      if (seen.has(reference.url)) continue;
      get('list').append(referenceCard(reference));
      seen.add(reference.url);
    }
    const active = data.state === 'queued' || data.state === 'running';
    const queue = data.state === 'queued' ? data.queue_position : null;
    const stateText = {queued: 'Aguardando para buscar', running: 'Buscando referências',
      done: 'Busca concluída', error: 'Busca não concluída'}[data.state];
    get('state').textContent = stateText;
    get('progress-label').textContent = `${data.checked} de 1 solicitação ao provedor · ${data.elapsed}s`;
    get('queue').hidden = !queue;
    get('queue').textContent = queue ? `Posição na fila: ${queue}.` : '';
    get('progress').value = data.checked;
    get('progress').hidden = !active;
    get('scanner').hidden = !active;
    get('heading').hidden = !seen.size && data.state !== 'done';
    get('count').textContent = String(seen.size);
    get('count-label').textContent = seen.size === 1 ? 'referência encontrada' : 'referências encontradas';
    get('empty').hidden = data.state !== 'done' || seen.size > 0;
    get('error').textContent = data.error;
    get('error').hidden = data.state !== 'error';
    get('update-error').hidden = true;
    get('retry').hidden = true;
    const refresh = get('refresh');
    if (refresh) refresh.hidden = !active;
    results.setAttribute('aria-busy', String(active));
    announcement.textContent = queue ? `Sua busca está na posição ${queue} da fila.`
      : data.state === 'queued' ? 'Sua busca está aguardando para começar.'
      : `${stateText}: ${data.checked} de 1 solicitação ao provedor; ${seen.size} referências.`;
    stopped = !active;
  }

  function unavailable(expired) {
    const message = expired ? 'Esta busca expirou ou não está disponível nesta sessão. Envie uma nova busca.'
      : 'Não foi possível atualizar os resultados. Tente atualizar novamente ou use o link Atualizar.';
    get('update-error').textContent = message;
    get('update-error').hidden = false;
    get('retry').hidden = expired;
    get('scanner').hidden = true;
    get('progress').hidden = true;
    get('queue').hidden = true;
    results.setAttribute('aria-busy', 'false');
    announcement.textContent = message;
    stopped = true;
  }

  async function poll() {
    if (inFlight || stopped) return;
    inFlight = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    try {
      const endpoint = new URL(results.dataset.updatesUrl, location.origin);
      if (endpoint.origin !== location.origin) throw new Error('Invalid endpoint');
      const response = await fetch(endpoint, {credentials: 'same-origin', cache: 'no-store',
        headers: {Accept: 'application/json'}, signal: controller.signal, redirect: 'error'});
      if (response.status === 404) {
        unavailable(true);
        return;
      }
      if (!response.ok) throw new Error('Update unavailable');
      show(await response.json());
      failures = 0;
    } catch {
      failures += 1;
      if (failures >= 3) unavailable(false);
    } finally {
      clearTimeout(timeout);
      inFlight = false;
      if (!stopped) setTimeout(poll, failures ? 400 * failures : 800);
    }
  }

  get('retry').addEventListener('click', () => {
    stopped = false;
    failures = 0;
    get('retry').hidden = true;
    get('update-error').hidden = true;
    announcement.textContent = 'Atualizando os resultados novamente.';
    poll();
  });
  poll();
})();
