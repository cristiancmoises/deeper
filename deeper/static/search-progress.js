(() => {
  'use strict';

  const results = document.querySelector('.results[data-updates-url]');
  if (!results) return;

  const progress = results.querySelector('[data-search-progress]');
  const progressLabel = results.querySelector('[data-progress-label]');
  const liveStatus = results.querySelector('[data-update-status]');
  const updateError = results.querySelector('[data-update-error]');
  const resultHeading = results.querySelector('[data-results-heading]');
  const resultCount = results.querySelector('[data-result-count]');
  const resultLabel = results.querySelector('[data-result-label]');
  const resultSummary = results.querySelector('[data-results-summary]');
  const profileGrid = results.querySelector('[data-profile-grid]');
  const profileNote = results.querySelector('[data-profile-note]');
  const emptyState = results.querySelector('[data-empty-state]');
  const terminalMessage = results.querySelector('[data-terminal-message]');
  const scanner = results.querySelector('.scanner');
  const terminalStates = new Set(['done', 'partial', 'error']);
  const validStates = new Set(['queued', 'running', ...terminalStates]);
  const seenProfiles = new Set(Array.from(
    results.querySelectorAll('.profile[data-profile-name]'),
    (card) => card.dataset.profileName,
  ));

  let cursor = parseCursor(results.dataset.cursor);
  let failures = 0;
  let inFlight = false;
  let stopped = false;
  let lastAnnouncedCheck = -1;

  function parseCursor(value) {
    if (typeof value !== 'string' || !/^[0-9]{1,10}$/.test(value)) return null;
    const parsed = Number(value);
    return Number.isSafeInteger(parsed) ? parsed : null;
  }

  function safeHttpUrl(value) {
    if (typeof value !== 'string' || value.length > 4096
        || /[\u0000-\u0020\u007f\\]/.test(value)) return null;
    try {
      const url = new URL(value);
      if (!['http:', 'https:'].includes(url.protocol) || !url.hostname
          || url.username || url.password) return null;
      return url.href;
    } catch {
      return null;
    }
  }

  function isTextList(value, limit) {
    return Array.isArray(value) && value.length <= limit
      && value.every((item) => typeof item === 'string');
  }

  function validProfile(profile) {
    return profile !== null && typeof profile === 'object' && !Array.isArray(profile)
      && typeof profile.name === 'string' && profile.name.length <= 2048
      && typeof profile.url === 'string'
      && isTextList(profile.tags, 8)
      && Array.isArray(profile.details) && profile.details.length <= 32
      && profile.details.every((item) => item !== null && typeof item === 'object'
        && typeof item.label === 'string' && typeof item.value === 'string')
      && isTextList(profile.links, 16)
      && typeof profile.similar === 'boolean';
  }

  function appendText(parent, tagName, className, value) {
    const element = document.createElement(tagName);
    if (className) element.className = className;
    element.textContent = value;
    parent.append(element);
    return element;
  }

  function appendLink(parent, value, label, className) {
    const href = safeHttpUrl(value);
    if (!href) return false;
    const anchor = document.createElement('a');
    if (className) anchor.className = className;
    anchor.href = href;
    anchor.target = '_blank';
    anchor.rel = 'noopener noreferrer';
    anchor.textContent = label;
    parent.append(anchor);
    return true;
  }

  function createProfile(profile) {
    const article = document.createElement('article');
    article.className = 'profile';
    article.dataset.profileName = profile.name;

    const top = document.createElement('div');
    top.className = 'profile-top';
    const heading = document.createElement('h3');
    if (!appendLink(heading, profile.url, profile.name, 'profile-link')) {
      heading.textContent = profile.name;
    }
    top.append(heading);
    if (profile.similar) appendText(top, 'span', 'tag', 'Aproximado');
    article.append(top);

    if (safeHttpUrl(profile.url)) appendText(article, 'p', 'profile-url', safeHttpUrl(profile.url));
    if (profile.tags.length) {
      const tags = document.createElement('ul');
      tags.className = 'tags';
      tags.setAttribute('aria-label', 'Categorias');
      for (const tag of profile.tags) appendText(tags, 'li', '', tag);
      article.append(tags);
    }
    if (profile.details.length) {
      const details = document.createElement('dl');
      details.className = 'profile-details';
      for (const item of profile.details) {
        const pair = document.createElement('div');
        appendText(pair, 'dt', '', item.label);
        appendText(pair, 'dd', '', item.value);
        details.append(pair);
      }
      article.append(details);
    }
    const links = profile.links.filter((link) => safeHttpUrl(link));
    if (links.length) {
      const list = document.createElement('ul');
      list.className = 'profile-links';
      list.setAttribute('aria-label', 'Links do perfil');
      for (const link of links) {
        const item = document.createElement('li');
        appendLink(item, link, link, '');
        list.append(item);
      }
      article.append(list);
    }
    return article;
  }

  function appendProfile(profile) {
    if (!validProfile(profile)) throw new Error('Formato de perfil inválido');
    if (seenProfiles.has(profile.name)) return false;
    profileGrid.append(createProfile(profile));
    seenProfiles.add(profile.name);
    resultHeading.hidden = false;
    profileNote.hidden = false;
    emptyState.hidden = true;
    resultCount.textContent = String(seenProfiles.size);
    resultLabel.textContent = seenProfiles.size === 1 ? 'perfil encontrado' : 'perfis encontrados';
    return true;
  }

  function validateUpdate(update) {
    if (update === null || typeof update !== 'object' || Array.isArray(update)
        || !validStates.has(update.state)
        || !Number.isSafeInteger(update.checked) || update.checked < 0
        || !Number.isSafeInteger(update.total) || update.total < 0
        || !Number.isSafeInteger(update.unknown) || update.unknown < 0
        || !Number.isSafeInteger(update.elapsed) || update.elapsed < 0
        || !Number.isSafeInteger(update.cursor) || update.cursor < cursor
        || !Array.isArray(update.profiles)
        || update.cursor !== cursor + update.profiles.length
        || typeof update.error !== 'string'
        || !update.profiles.every(validProfile)) {
      throw new Error('Resposta de progresso inválida');
    }
    return update;
  }

  function updateCounters(update, addedProfiles) {
    if (progress) {
      progress.max = Math.max(1, update.total);
      progress.value = Math.min(update.checked, progress.max);
    }
    if (progressLabel) {
      progressLabel.textContent = update.total
        ? `${update.checked} de ${update.total} sites verificados · ${update.elapsed}s`
        : `Preparando os sites · ${update.elapsed}s`;
    }
    if (resultSummary) {
      resultSummary.textContent = `${update.checked}${update.total ? `/${update.total}` : ''} sites · ${update.elapsed}s`;
    }
    const unknownNote = results.querySelector('[data-unknown-note]');
    if (unknownNote) {
      unknownNote.hidden = update.unknown === 0;
      unknownNote.textContent = `${update.unknown} ${update.unknown === 1
        ? 'verificação inconclusiva' : 'verificações inconclusivas'}. Sites indisponíveis ou bloqueados não confirmam a ausência de um perfil.`;
    }
    if (liveStatus && (addedProfiles || update.checked !== lastAnnouncedCheck)) {
      const newProfiles = addedProfiles
        ? ` ${addedProfiles} novo${addedProfiles === 1 ? '' : 's'} perfil${addedProfiles === 1 ? '' : 'is'} encontrado${addedProfiles === 1 ? '' : 's'}.`
        : '';
      liveStatus.textContent = `${update.checked} de ${update.total} sites verificados.${newProfiles}`;
      lastAnnouncedCheck = update.checked;
    }
  }

  function stopUnavailable() {
    stopped = true;
    results.setAttribute('aria-busy', 'false');
    if (scanner) scanner.hidden = true;
    if (liveStatus) liveStatus.textContent = 'Esta busca não está mais disponível. Atualize a página para conferir os resultados.';
  }

  function stopAfterFailures() {
    stopped = true;
    updateError.hidden = false;
    updateError.textContent = 'Não foi possível atualizar os resultados agora. A busca pode continuar em segundo plano; atualize a página para conferir o que já foi encontrado.';
    if (liveStatus) liveStatus.textContent = updateError.textContent;
  }

  function finish(update) {
    stopped = true;
    results.setAttribute('aria-busy', 'false');
    if (scanner) scanner.hidden = true;
    if (update.state === 'partial') {
      terminalMessage.hidden = false;
      terminalMessage.textContent = 'O tempo da busca terminou. Os resultados obtidos até agora estão abaixo.';
      if (update.total > update.checked) {
        appendText(results, 'p', 'result-note', `${update.total - update.checked} sites não concluíram a verificação dentro do prazo.`);
      }
    } else if (update.state === 'error') {
      terminalMessage.hidden = false;
      terminalMessage.setAttribute('role', 'alert');
      terminalMessage.classList.add('error');
      terminalMessage.textContent = update.error || 'Não foi possível concluir a busca. Tente novamente.';
    } else if (seenProfiles.size === 0) {
      emptyState.hidden = false;
    }
    if (liveStatus) {
      liveStatus.textContent = update.state === 'done'
        ? `Busca concluída. ${seenProfiles.size} ${seenProfiles.size === 1 ? 'perfil encontrado' : 'perfis encontrados'}.`
        : update.state === 'partial'
          ? 'Busca parcial concluída. Os resultados disponíveis estão abaixo.'
          : update.error || 'A busca terminou com erro.';
    }
  }

  function showUnavailableError() {
    stopped = true;
    updateError.hidden = false;
    updateError.textContent = 'Não foi possível validar esta busca. Atualize a página para conferir os resultados.';
    if (liveStatus) liveStatus.textContent = updateError.textContent;
  }

  async function poll() {
    if (stopped || inFlight) return;
    inFlight = true;
    try {
      const requestUrl = new URL(endpoint.href);
      requestUrl.searchParams.set('after', String(cursor));
      const response = await fetch(requestUrl.href, {
        method: 'GET',
        headers: { Accept: 'application/json' },
        cache: 'no-store',
        credentials: 'same-origin',
        mode: 'same-origin',
      });
      if (!response.ok) {
        if (response.status >= 500 || response.status === 429) throw new Error('Servidor indisponível');
        stopUnavailable();
        return;
      }
      const update = validateUpdate(await response.json());
      let addedProfiles = 0;
      for (const profile of update.profiles) {
        if (appendProfile(profile)) addedProfiles += 1;
      }
      cursor = update.cursor;
      failures = 0;
      updateCounters(update, addedProfiles);
      if (terminalStates.has(update.state)) finish(update);
    } catch {
      failures += 1;
      if (failures >= 3) stopAfterFailures();
    } finally {
      inFlight = false;
      if (!stopped) window.setTimeout(poll, 1000);
    }
  }

  let endpoint;
  try {
    endpoint = new URL(results.dataset.updatesUrl, window.location.href);
    if (endpoint.origin !== window.location.origin || endpoint.username || endpoint.password) {
      showUnavailableError();
      return;
    }
  } catch {
    showUnavailableError();
    return;
  }
  if (cursor === null || !profileGrid || !resultHeading || !resultCount || !resultLabel
      || !profileNote || !emptyState || !updateError || !terminalMessage) {
    showUnavailableError();
    return;
  }
  window.setTimeout(poll, 0);
})();
