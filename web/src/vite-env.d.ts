/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_OPERATOR_SECRET: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
