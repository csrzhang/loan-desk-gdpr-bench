import assert from 'node:assert/strict';
import test from 'node:test';
import {readFileSync} from 'node:fs';
import {evaluateVerdicts, inlineText, articleLinks, gdprIndex} from './dist/presentation.mjs';

test('score binary violation flags and exact four-state verdicts separately', () => {
  const checks = [
    ['CONTRADICTED','CONTRADICTED'], ['CONTRADICTED','SUPPORTED'],
    ['INSUFFICIENT','CONTRADICTED'], ['NOT_APPLICABLE','SUPPORTED'],
    ['SUPPORTED','SUPPORTED']
  ].map(([verdict,reference])=>({verdict,reference}));
  assert.deepEqual(evaluateVerdicts(checks), {tp:1,fp:1,fn:1,tn:2,matches:2,unresolved:2,count:5,
    precision:0.5,recall:0.5,f1:0.5});
});

test('distinguish undefined, measured zero and missing predictions', () => {
  for(const cases of [[],[{verdict:'SUPPORTED',reference:'SUPPORTED'}]]) {
    const metrics=evaluateVerdicts(cases);
    for(const k of ['precision','recall','f1']) assert.equal(metrics[k],null);
  }
  const missed=evaluateVerdicts([{verdict:'SUPPORTED',reference:'CONTRADICTED'}]);
  assert.equal(missed.precision,null);assert.equal(missed.recall,0);assert.equal(missed.f1,0);
  const falseAlarm=evaluateVerdicts([{verdict:'CONTRADICTED',reference:'SUPPORTED'}]);
  assert.equal(falseAlarm.precision,0);assert.equal(falseAlarm.recall,null);assert.equal(falseAlarm.f1,0);
});

test('format code spans and plain-text citations while escaping HTML', () => {
  assert.equal(inlineText('Read `stage` in store.py:19.'),'Read <code>stage</code> in <code>store.py:19</code>.');
  assert.equal(inlineText('``a`b``'),' <code>a`b</code>'.trim());
  assert.equal(inlineText('<img> `<tag>`'),'&lt;img&gt; <code>&lt;tag&gt;</code>');
  assert.equal(inlineText('unmatched `'),'unmatched `');
});

test('every Loan Desk citation preserves the paragraph label and links to its GDPR.eu article', () => {
  assert.equal(gdprIndex, 'https://gdpr.eu/tag/gdpr/');
  const {obligations} = JSON.parse(readFileSync(new URL('../scope.json', import.meta.url), 'utf8'));
  const distinct = new Set();
  for (const rule of obligations) {
    const labels = rule.article.split(/,\s*/);
    const anchors = [...articleLinks(rule.article).matchAll(/href="([^"]+)"[^>]*>Art\. ([^<]+)<\/a>/g)];
    assert.deepEqual(anchors.map(match => match[2]), labels);
    for (const [,href,label] of anchors) {
      const number = /^\d+/.exec(label)[0];
      const url = new URL(href);
      assert.equal(url.origin, 'https://gdpr.eu');
      assert.ok(url.pathname.startsWith('/article-' + number + '-'));
      distinct.add(href);
    }
  }
  assert.equal(distinct.size, 15);
  assert.ok(articleLinks('7(3)').includes('https://gdpr.eu/article-7-how-to-get-consent-to-collect-personal-data/'));
});
