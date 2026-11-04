import {defineConfig} from 'vite';
import {previewBrowserCache} from '../../packages/web-ui/preview-cache.mjs';

export default defineConfig({plugins: [previewBrowserCache()]});
