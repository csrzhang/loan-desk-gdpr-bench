export function escapeText(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);
}

// Raw HTML is always text. Only backtick spans and recognizable source citations get code styling.
export function inlineText(value) {
  const parts = String(value ?? '').split(/(`+)/g);
  const plain = text => text.split(/(\b[\w-]+\.(?:py|css|js|json)(?:(?::|\s+)\d+(?:[-–]\d+)?)?|\b[a-z]\w*\.[a-z_]\w*(?=\())/g)
    .map((token, i) => i % 2 ? '<code>' + escapeText(token) + '</code>' : escapeText(token)).join('');
  const html = [];
  for (let i = 0; i < parts.length; i++) {
    if (i % 2 === 0) { html.push(plain(parts[i])); continue; }
    const end = parts.indexOf(parts[i], i + 1);
    if (end === -1) { html.push(parts[i]); continue; }
    let code = parts.slice(i + 1, end).join('').replace(/\r?\n/g, ' ');
    if (/^ [\s\S]* $/.test(code) && code.trim()) code = code.slice(1,-1);
    html.push('<code>' + escapeText(code) + '</code>');
    i = end;
  }
  return html.join('');
}

// Article pages are addressed by editorial slugs in the GDPR.eu table of contents.
export const gdprIndex = 'https://gdpr.eu/tag/gdpr/';
const articlePages = {
  5: 'article-5-how-to-process-personal-data',
  6: 'article-6-how-to-process-personal-data-legally',
  7: 'article-7-how-to-get-consent-to-collect-personal-data',
  12: 'article-12-how-controllers-should-provide-personal-data-to-the-subject',
  13: 'article-13-personal-data-collected',
  14: 'article-14-personal-data-not-obtained-from-data-subject',
  15: 'article-15-right-of-access',
  16: 'article-16-right-to-rectification',
  17: 'article-17-right-to-be-forgotten',
  18: 'article-18-right-to-restriction-of-processing',
  20: 'article-20-right-to-data-portability',
  21: 'article-21-right-to-object',
  22: 'article-22-automated-individual-decision-making',
  25: 'article-25-data-protection-by-design',
  32: 'article-32-security-of-processing'
};

export function articleLinks(article) {
  return article.split(/,\s*/).map(citation => {
    const number = /^\d+/.exec(citation)?.[0];
    const page = articlePages[number];
    const href = page ? new URL('/' + page + '/', gdprIndex).href : gdprIndex;
    return '<a href="' + href + '" target="_blank" rel="noopener noreferrer" title="' +
      (page ? 'Read Article ' + number + ' on GDPR.eu' : 'Browse the GDPR.eu table of contents') + '">Art. ' +
      escapeText(citation) + '</a>';
  }).join('<span class="sep"> · </span>');
}

export function evaluateVerdicts(findings) {
  let tp = 0, fp = 0, fn = 0, tn = 0, matches = 0, unresolved = 0;
  for (const { verdict, reference } of findings) {
    if (verdict === reference) matches++;
    if (verdict !== 'SUPPORTED' && verdict !== 'CONTRADICTED') unresolved++;
    if (reference === 'CONTRADICTED') {
      if (verdict === 'CONTRADICTED') tp++; else fn++;
    } else if (reference === 'SUPPORTED') {
      if (verdict === 'CONTRADICTED') fp++; else tn++;
    }
  }
  const ratio = (numerator, denominator) => denominator ? numerator / denominator : null;
  return {tp, fp, fn, tn, matches, unresolved, count: findings.length,
    precision: ratio(tp, tp + fp), recall: ratio(tp, tp + fn), f1: ratio(2 * tp, 2 * tp + fp + fn)};
}
