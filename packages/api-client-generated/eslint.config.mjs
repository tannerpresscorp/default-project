import js from '@eslint/js';
import tseslint from 'typescript-eslint';

// Generated files (`*.gen.ts`) come from openapi-ts — don't lint them.
export default tseslint.config(
  { ignores: ['node_modules/**', 'dist/**', 'src/**/*.gen.ts'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['**/*.ts'],
    languageOptions: { sourceType: 'module' },
  },
);