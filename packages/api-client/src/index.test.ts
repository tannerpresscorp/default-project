import assert from 'node:assert/strict';
import { test } from 'node:test';
import { ping } from './index.ts';

test('ping returns pong', () => {
  assert.equal(ping(), 'pong');
});