import { defineConfig } from '@hey-api/openapi-ts';

// Generates a typed fetch client from the committed OpenAPI schema at the
// repo root. Refresh the schema first:
//   .venv\Scripts\python.exe manage.py spectacular --file openapi.json --format openapi-json
export default defineConfig({
  input: '../../openapi.json',
  output: {
    path: 'src',
  },
  plugins: ['@hey-api/typescript', '@hey-api/sdk', '@hey-api/client-fetch'],
});